# RAG Quality Baseline Improvement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve retrieval and generation quality on the fixed 30-case Vietravel evaluation set, measure the take-home metrics, and publish the best complete run as the new report baseline.

**Architecture:** Add intent-aware metadata filtering at the knowledge retriever, remove catalog-only documents from the Ragas retrieval payload, and use bounded structured-output recovery for DeepSeek generation. Aggregate the five Ragas metrics into explicit report fields, then use at most three deterministic provider runs before one final Ragas run writes the canonical artifacts.

**Tech Stack:** Python 3.11+, LangChain/LangGraph, Chroma, DeepSeek OpenAI-compatible chat API, Gemini embeddings, Ragas 0.3.1, Pydantic, pytest, Ruff.

## Global Constraints

- Keep `data/eval/eval_cases.jsonl` fixed at the existing 30 reviewed cases.
- Do not add or expand guardrail-specific tests.
- Do not edit source PDFs, reviewed chunk IDs, or reference answers to raise scores.
- Report Answer Correctness as accuracy.
- Report both `1 - Faithfulness` and the percentage of finite cases with Faithfulness below `1.0` as incorrect/fabricated-answer indicators.
- Report Context Precision, Context Recall, Faithfulness, Answer Relevancy, Answer Correctness, p50/p95 latency, and estimated cost per 1,000 attempted questions.
- Preserve missing Ragas values as missing; never convert them to zero.
- Require 30/30 completed graph cases for the reportable baseline.
- Run at most three full deterministic evaluation rounds and stop after two consecutive rounds improve no retrieval or generation failure by at least one case.
- Investigate before accepting a candidate whose p95 exceeds 18,114 ms, which is 20% above the prior 15,095 ms baseline.
- Run Ragas once for the selected candidate; retry only after an external provider failure such as insufficient balance.
- Present only the selected baseline in `README.md`; do not add a before/after comparison.

---

## File Structure

- Modify `src/vietravel_rag/retrieval/retriever.py`: own the intent-to-section mapping and Chroma knowledge query.
- Modify `src/vietravel_rag/agent/nodes.py`: pass intent into retrieval, keep catalog documents out of evaluated contexts, and invoke bounded structured output.
- Modify `src/vietravel_rag/agent/structured_output.py`: provide the shared two-attempt JSON-mode invocation helper.
- Modify `src/vietravel_rag/agent/prompts.py`: constrain answers to requested facts and concise supported claims.
- Modify `src/vietravel_rag/models.py`: expose generation retry diagnostics in graph state.
- Modify `scripts/evaluate.py`: persist generation diagnostics and aggregate Ragas metrics into report-ready fields.
- Modify `tests/retrieval/test_retriever.py`: verify intent-aware section filters and retrieval limits.
- Modify `tests/agent/test_routing.py`: verify context assembly excludes catalog summaries/full-itinerary aggregates.
- Modify `tests/test_structured_output.py`: verify one retry for parse/validation failure and no retry for provider failure.
- Modify `tests/agent/test_graph.py`: verify recovered generation and terminal structured-output failure behavior.
- Modify `tests/agent/test_prompts.py`: lock the concise, question-focused generation contract.
- Modify `tests/evaluation/test_metrics.py`: verify finite-score aggregation and hallucination-rate calculations.
- Modify `README.md`: replace the evaluation section with the final baseline only.
- Regenerate `results/eval_results.json` and `results/eval_summary.json`: canonical provider-backed baseline artifacts.

---

### Task 1: Add Intent-Aware Knowledge Retrieval

**Files:**
- Modify: `src/vietravel_rag/retrieval/retriever.py:1-18`
- Modify: `src/vietravel_rag/agent/nodes.py:225-240`
- Modify: `scripts/evaluate.py:118-159`
- Test: `tests/retrieval/test_retriever.py`

**Interfaces:**
- Consumes: `QueryAnalysis.intent`, standalone query, resolved tour codes, and a Chroma-compatible store.
- Produces: `sections_for_intent(intent: str) -> tuple[str, ...] | None` and `retrieve_evidence(standalone_query: str, tour_codes: list[str], store, *, intent: str | None = None, comparison: bool = False) -> list`.

- [ ] **Step 1: Write failing tests for section-aware filters**

Add tests that assert the exact Chroma filter and retrieval limit:

```python
def test_child_price_retrieval_filters_to_child_and_price_sections():
    store = RecordingStore()
    retrieve_evidence(
        "Trẻ 8 tuổi tính giá thế nào?",
        ["thailand-bangkok-pattaya"],
        store,
        intent="child_price",
    )
    assert store.search_kwargs == {
        "k": 4,
        "filter": {
            "$and": [
                {"tour_code": "thailand-bangkok-pattaya"},
                {"section_type": {"$in": ["child_price", "price"]}},
            ]
        },
    }


def test_itinerary_retrieval_filters_to_itinerary_sections():
    store = RecordingStore()
    retrieve_evidence(
        "Tour Đà Nẵng 5 ngày đi những đâu?",
        ["danang-central-5d4n"],
        store,
        intent="itinerary",
    )
    assert store.search_kwargs["filter"]["$and"][1] == {
        "section_type": {"$in": ["itinerary", "tour_overview"]}
    }


def test_unknown_intent_keeps_tour_scoping_without_section_filter():
    store = RecordingStore()
    retrieve_evidence("Thông tin tour", ["tour-a"], store, intent="general")
    assert store.search_kwargs == {"k": 6, "filter": {"tour_code": "tour-a"}}
```

Update `RecordingStore.similarity_search()` so it can read `tour_code` from either a simple filter or the first `$and` clause.

- [ ] **Step 2: Run the focused retrieval tests and verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/retrieval/test_retriever.py -v
```

Expected: FAIL because `retrieve_evidence()` does not accept `intent` and always requests six unfiltered chunks.

- [ ] **Step 3: Implement the intent-to-section map and filtered query**

Add this mapping and helper to `retriever.py`:

```python
_INTENT_SECTIONS: dict[str, tuple[str, ...]] = {
    "price": ("price",),
    "child_price": ("child_price", "price"),
    "itinerary": ("itinerary", "tour_overview"),
    "included": ("included",),
    "excluded": ("excluded",),
    "baggage": ("included", "registration_notes"),
    "payment": ("payment", "registration_notes"),
    "cancellation": ("cancellation_standard", "cancellation_holiday"),
    "visa": ("visa", "registration_notes"),
}


def sections_for_intent(intent: str) -> tuple[str, ...] | None:
    return _INTENT_SECTIONS.get(intent)
```

Build the filter as follows:

```python
sections = sections_for_intent(intent or "")
query_filter = {"tour_code": tour_filter}
if sections:
    query_filter = {
        "$and": [
            {"tour_code": tour_filter},
            {"section_type": {"$in": list(sections)}},
        ]
    }
limit = 8 if comparison else (4 if sections else 6)
return store.similarity_search(
    standalone_query,
    k=limit,
    filter=query_filter,
)
```

Pass `analysis.intent` through `_retrieve()` in `nodes.py` and through the `Retriever.retrieve()` adapter in `scripts/evaluate.py`. Preserve compatibility with injected retrievers that do not yet accept `intent` by inspecting the callable signature in the same style already used by `_resolve()`.

- [ ] **Step 4: Run retrieval and routing tests**

Run:

```bash
.venv/bin/python -m pytest tests/retrieval/test_retriever.py tests/agent/test_routing.py -v
```

Expected: PASS. Existing comparison and adjacent-day behavior remains covered.

- [ ] **Step 5: Commit the retrieval filter**

```bash
git add src/vietravel_rag/retrieval/retriever.py src/vietravel_rag/agent/nodes.py scripts/evaluate.py tests/retrieval/test_retriever.py tests/agent/test_routing.py
git commit -m "fix: scope retrieval by question intent"
```

---

### Task 2: Remove Catalog Noise From Evaluated Retrieval Contexts

**Files:**
- Modify: `src/vietravel_rag/agent/nodes.py:254-295`
- Test: `tests/agent/test_routing.py:181-286`

**Interfaces:**
- Consumes: knowledge chunks returned by the retriever and catalog summaries held in `tour_summaries`.
- Produces: `retrieve_node(...)` whose `retrieved_chunks` contains only stable, citable knowledge chunks used by generation and Ragas.

- [ ] **Step 1: Replace the catalog-expansion expectations with failing context-purity tests**

Change the current full-itinerary test to assert that catalog summary and aggregate records remain in state for routing but are absent from `retrieved_chunks`:

```python
def test_retrieval_context_contains_only_citable_knowledge_chunks():
    tour_summary = summary("tour-a", "Tour A")
    knowledge = Document(
        "Ngày 1",
        metadata={
            "chunk_id": "tour-a_itinerary_01",
            "tour_code": "tour-a",
            "document_type": "knowledge",
            "authority": "official_tour_pdf",
            "section_type": "itinerary",
        },
    )

    class Retriever:
        def retrieve(self, query, tour_codes, *, intent=None, comparison=False):
            return [knowledge]

        def get_full_itinerary(self, tour_code):
            raise AssertionError("catalog aggregate must not enter Ragas contexts")

    result = retrieve_node(
        {
            "query_analysis": analysis("itinerary", query="Lịch trình tour A"),
            "active_tour_codes": ["tour-a"],
            "tour_summaries": [tour_summary],
        },
        Retriever(),
    )
    assert result["retrieved_chunks"] == [knowledge]
```

Retain the adjacent-day test because it adds an exact citable knowledge chunk.

- [ ] **Step 2: Run the routing test and verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/agent/test_routing.py -v
```

Expected: FAIL because `retrieve_node()` appends tour summaries and full-itinerary catalog aggregates.

- [ ] **Step 3: Simplify context assembly**

In `retrieve_node()`:

- keep the knowledge chunks from `_retrieve()`;
- remove the loop that appends `tour_summaries`;
- remove automatic `get_full_itinerary()` expansion;
- retain exact adjacent itinerary lookup and deduplication; and
- retain `tour_summaries` and `tour_candidates` elsewhere in graph state for routing and UI use.

Delete `_full_itinerary()` only if no remaining production caller uses it. Keep the catalog API in `resolver.py` because ingestion validation and other consumers may still use it.

- [ ] **Step 4: Run routing, graph, and retrieval tests**

Run:

```bash
.venv/bin/python -m pytest tests/agent/test_routing.py tests/agent/test_graph.py tests/retrieval -v
```

Expected: PASS with no catalog-only document in `retrieved_chunks`.

- [ ] **Step 5: Commit context cleanup**

```bash
git add src/vietravel_rag/agent/nodes.py tests/agent/test_routing.py
git commit -m "fix: keep catalog records out of RAG evidence"
```

---

### Task 3: Add Bounded Structured-Output Recovery

**Files:**
- Modify: `src/vietravel_rag/agent/structured_output.py`
- Modify: `src/vietravel_rag/agent/nodes.py:79-107,426-482`
- Modify: `src/vietravel_rag/models.py:82-106`
- Modify: `scripts/evaluate.py:249-287`
- Test: `tests/test_structured_output.py`
- Test: `tests/agent/test_graph.py:497-509`

**Interfaces:**
- Consumes: a chat model, Pydantic schema, system instructions, and message list.
- Produces: `invoke_deepseek_json(model, schema, instructions, messages, *, max_attempts: int = 2) -> tuple[BaseModel, int]` and graph diagnostics `generation_attempts` plus `generation_error_type`.

- [ ] **Step 1: Write failing retry and provider-failure tests**

Add a model double that raises `OutputParserException` once, then returns a valid `TourAnswer`:

```python
def test_structured_output_retries_one_parser_failure_then_returns_valid_model():
    model = ParserFailureThenSuccessModel()
    answer, attempts = invoke_deepseek_json(
        model,
        TourAnswer,
        ANSWER_GENERATION_SYSTEM_PROMPT,
        [SystemMessage(content="evidence")],
    )
    assert answer.status == "answered"
    assert attempts == 2
    assert model.invoke_count == 2
```

Add a second test where `invoke()` raises `RuntimeError("provider unavailable")`; assert the error propagates after one call. Update the graph test currently named `test_graph_does_not_retry_when_structured_answer_is_invalid` so the first response is invalid and the second is valid, then assert the recovered answer and two `TourAnswer` attempts.

- [ ] **Step 2: Run structured-output tests and verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_structured_output.py tests/agent/test_graph.py -k "structured or retry" -v
```

Expected: FAIL because no bounded invocation helper exists and generation currently converts every exception directly to `unsupported`.

- [ ] **Step 3: Implement the two-attempt helper**

In `structured_output.py`, catch only output-shape failures:

```python
from langchain_core.exceptions import OutputParserException
from langchain_core.messages import SystemMessage
from pydantic import ValidationError


def invoke_deepseek_json(
    model: Any,
    schema: type,
    instructions: str,
    messages: list,
    *,
    max_attempts: int = 2,
):
    structured, output_prompt = deepseek_json_output(model, schema, instructions)
    invocation_messages = [SystemMessage(content=output_prompt), *messages]
    for attempt in range(1, max_attempts + 1):
        try:
            raw = structured.invoke(invocation_messages)
            parsed = raw if isinstance(raw, schema) else schema.model_validate(raw)
            return parsed, attempt
        except (OutputParserException, ValidationError, json.JSONDecodeError):
            if attempt == max_attempts:
                raise
            invocation_messages = [
                *invocation_messages,
                SystemMessage(
                    content="The previous output was invalid. Return one complete JSON object matching the schema exactly."
                ),
            ]
    raise AssertionError("unreachable")
```

Use the helper in both `analyze_query()` and `generate_answer()`. In generation, preserve the safe unsupported fallback only for exhausted parse/validation failures. Let provider errors propagate to `_run_cases()` as `evaluation_error`.

Add these optional fields to `AgentState`:

```python
generation_attempts: int
generation_error_type: str | None
```

Persist them on each result row in `scripts/evaluate.py` so a report author can distinguish insufficient evidence from parser fallback.

- [ ] **Step 4: Run structured-output and graph tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_structured_output.py tests/agent/test_query_analysis.py tests/agent/test_graph.py -v
```

Expected: PASS. Parse errors receive at most one retry; provider failures are not hidden or retried.

- [ ] **Step 5: Commit bounded recovery**

```bash
git add src/vietravel_rag/agent/structured_output.py src/vietravel_rag/agent/nodes.py src/vietravel_rag/models.py scripts/evaluate.py tests/test_structured_output.py tests/agent/test_graph.py
git commit -m "fix: retry malformed structured model output once"
```

---

### Task 4: Tighten the Generation Contract

**Files:**
- Modify: `src/vietravel_rag/agent/prompts.py:18-36`
- Modify: `src/vietravel_rag/agent/nodes.py:452-475`
- Test: `tests/agent/test_prompts.py`
- Test: `tests/agent/test_graph.py`

**Interfaces:**
- Consumes: standalone question, one intent, and approved official knowledge chunks.
- Produces: concise `TourAnswer` JSON whose factual claims and citations are limited to the requested facts and supplied evidence.

- [ ] **Step 1: Write failing prompt-contract tests**

Add assertions for the new explicit rules:

```python
def test_answer_prompt_requires_question_focused_grounded_output():
    prompt = ANSWER_GENERATION_SYSTEM_PROMPT
    assert "Use only evidence needed to answer the user's exact question" in prompt
    assert "Do not summarize unrelated retrieved chunks" in prompt
    assert "Every factual claim and number must be supported" in prompt
    assert "Prefer one short paragraph" in prompt
    assert "Cite every chunk used for the answer" in prompt
```

Add a graph test whose retriever returns one relevant child-price chunk and one irrelevant cancellation chunk; the fake model response must cite only the child-price chunk, and the output guard must preserve that answer.

- [ ] **Step 2: Run prompt and focused graph tests and verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/agent/test_prompts.py tests/agent/test_graph.py -k "prompt or relevant or child_price" -v
```

Expected: FAIL on the missing explicit prompt contract.

- [ ] **Step 3: Update prompt and generation context ordering**

Add the exact tested rules to `ANSWER_GENERATION_SYSTEM_PROMPT`. In `generate_answer()`, render evidence in retriever rank order and include the question before guidance and evidence:

```python
context = (
    f"Câu hỏi cần trả lời: {analysis.standalone_query}\n"
    f"Intent: {analysis.intent}\n"
    f"Trạng thái bằng chứng: {status}\n"
    f"Bằng chứng theo thứ tự liên quan:\n{evidence}\n"
    f"Hướng dẫn giao tiếp, không phải dữ kiện: {guidance}"
)
```

Do not add new factual few-shot content. Keep existing examples grounded in their paired evidence.

- [ ] **Step 4: Run prompt and graph tests**

Run:

```bash
.venv/bin/python -m pytest tests/agent/test_prompts.py tests/agent/test_graph.py -v
```

Expected: PASS with existing citation validation and answer schemas unchanged.

- [ ] **Step 5: Commit generation constraints**

```bash
git add src/vietravel_rag/agent/prompts.py src/vietravel_rag/agent/nodes.py tests/agent/test_prompts.py tests/agent/test_graph.py
git commit -m "fix: focus generated answers on retrieved evidence"
```

---

### Task 5: Produce Report-Ready Ragas Aggregates

**Files:**
- Modify: `scripts/evaluate.py:163-230,340-394`
- Test: `tests/evaluation/test_metrics.py:155-190`

**Interfaces:**
- Consumes: Ragas `metric_rows` containing nullable metric values.
- Produces: `summarize_ragas_rows(rows: list[dict]) -> dict` with finite counts, means, accuracy, unsupported-claim rate, and case-level hallucination rate.

- [ ] **Step 1: Write failing aggregation tests**

Add this test with one missing value to prove finite-score handling:

```python
def test_ragas_summary_uses_only_finite_scores_and_reports_hallucination_rates():
    rows = [
        {
            "llm_context_precision_with_reference": 0.8,
            "context_recall": 1.0,
            "faithfulness": 1.0,
            "answer_relevancy": 0.7,
            "answer_correctness": 0.9,
        },
        {
            "llm_context_precision_with_reference": 0.6,
            "context_recall": None,
            "faithfulness": 0.5,
            "answer_relevancy": 0.9,
            "answer_correctness": 0.7,
        },
    ]
    summary = summarize_ragas_rows(rows)
    assert summary["metrics"]["context_precision"] == {
        "finite_cases": 2,
        "total_cases": 2,
        "mean": 0.7,
    }
    assert summary["metrics"]["context_recall"]["finite_cases"] == 1
    assert summary["report_metrics"]["accuracy"] == 0.8
    assert summary["report_metrics"]["unsupported_claim_rate"] == 0.25
    assert summary["report_metrics"]["cases_with_unsupported_claim_rate"] == 0.5
```

Also test `math.nan` and infinity are excluded from finite counts.

- [ ] **Step 2: Run the evaluation tests and verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/evaluation/test_metrics.py -v
```

Expected: FAIL because `summarize_ragas_rows()` does not exist.

- [ ] **Step 3: Implement finite-score aggregation**

Define an explicit alias map:

```python
RAGAS_METRICS = {
    "context_precision": "llm_context_precision_with_reference",
    "context_recall": "context_recall",
    "faithfulness": "faithfulness",
    "answer_relevancy": "answer_relevancy",
    "answer_correctness": "answer_correctness",
}
```

For each metric, retain only `int` or `float` values for which `math.isfinite(float(value))` is true. Round means and derived rates to six decimal places. Derive:

```python
report_metrics = {
    "accuracy": answer_correctness_mean,
    "unsupported_claim_rate": 1.0 - faithfulness_mean,
    "cases_with_unsupported_claim_rate": (
        sum(score < 1.0 for score in finite_faithfulness) / len(finite_faithfulness)
    ),
}
```

Return `None` for a derived metric when its source has no finite scores. Attach the summary under `ragas["summary"]` before writing `eval_summary.json`. Add human-readable definitions under top-level `metric_definitions`.

- [ ] **Step 4: Run evaluation tests and strict JSON checks**

Run:

```bash
.venv/bin/python -m pytest tests/evaluation/test_metrics.py -v
.venv/bin/python -c 'import json; json.load(open("results/eval_summary.json"), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))'
```

Expected: tests PASS and the existing committed summary remains strict JSON.

- [ ] **Step 5: Commit report metric aggregation**

```bash
git add scripts/evaluate.py tests/evaluation/test_metrics.py
git commit -m "feat: summarize report-ready RAG metrics"
```

---

### Task 6: Verify the Implementation Offline

**Files:**
- Verify: all files changed in Tasks 1-5

**Interfaces:**
- Consumes: completed retrieval, generation, parser, and metric changes.
- Produces: an offline-verified candidate ready for paid provider runs.

- [ ] **Step 1: Run focused suites**

```bash
.venv/bin/python -m pytest tests/retrieval tests/agent tests/evaluation tests/test_structured_output.py -v
```

Expected: PASS with no guardrail test expansion.

- [ ] **Step 2: Run the full existing suite**

```bash
.venv/bin/python -m pytest -q
```

Expected: PASS. Existing documented PyMuPDF/SWIG deprecation warnings may remain.

- [ ] **Step 3: Run lint and whitespace checks**

```bash
.venv/bin/ruff check src/vietravel_rag/retrieval src/vietravel_rag/agent src/vietravel_rag/evaluation scripts/evaluate.py tests/retrieval tests/agent tests/evaluation tests/test_structured_output.py
git diff --check
```

Expected: both commands exit zero.

- [ ] **Step 4: Commit any verification-only corrections**

If verification required a correction, stage only the affected task files and commit with a message describing that correction. If the working tree is already clean, do not create an empty commit.

---

### Task 7: Run the Bounded Deterministic Evaluation Loop

**Files:**
- Inspect: temporary `eval_results.json` and `eval_summary.json` files outside the repository
- Do not modify: `data/eval/eval_cases.jsonl`

**Interfaces:**
- Consumes: fixed 30-case dataset and current provider configuration.
- Produces: one selected 30/30 candidate or an early-stop decision after at most three rounds.

- [ ] **Step 1: Verify account readiness without issuing evaluation prompts**

Confirm the configured DeepSeek account has enough balance for three deterministic runs plus one Ragas run and that Gemini embeddings are available. Do not print secret values.

- [ ] **Step 2: Run one-case retrieval/generation smoke**

```bash
candidate_dir=$(mktemp -d)
.venv/bin/python scripts/evaluate.py \
  --limit 1 \
  --skip-ragas \
  --results-dir "$candidate_dir" \
  --input-price-per-million 0.3 \
  --output-price-per-million 1.2 \
  --price-source-url https://api-docs.deepseek.com/quick_start/pricing/
```

Expected: `case_count_completed` is 1, no parser failure is recorded, and the answer cites `thailand-bangkok-pattaya_price_01`.

- [ ] **Step 3: Run deterministic round 1 in a fresh temporary directory**

```bash
round_one_dir=$(mktemp -d)
.venv/bin/python scripts/evaluate.py \
  --skip-ragas \
  --results-dir "$round_one_dir" \
  --input-price-per-million 0.3 \
  --output-price-per-million 1.2 \
  --price-source-url https://api-docs.deepseek.com/quick_start/pricing/
```

Expected: 30 requested cases. A reportable candidate requires 30 completed cases.

- [ ] **Step 4: Inspect retrieval/generation failures and latency**

Use `jq` to inspect only report-relevant diagnostics:

```bash
jq '{case_count_completed, case_failures, latency: .deterministic_metrics.latency}' "$round_one_dir/eval_summary.json"
jq '[.[] | select(.status == "evaluation_error" or .generation_error_type != null) | {case_id, status, error_type, generation_error_type, generation_attempts}]' "$round_one_dir/eval_results.json"
```

Reject the candidate if it completes fewer than 30 cases. Investigate any p95 above 18,114 ms before another run.

- [ ] **Step 5: Apply at most one evidence-backed correction before the next round**

If a repeated failure has a confirmed retrieval, prompt, or parser cause, add one failing regression test, implement the smallest correction, run its focused suite, and commit it. Do not change the dataset, reference text, or metric formulas.

- [ ] **Step 6: Run rounds 2 and 3 only when the stop rule permits**

Repeat Steps 3-5 with new `mktemp -d` directories. Stop after two consecutive rounds improve no retrieval or generation failure by at least one case. Never exceed three full deterministic rounds.

- [ ] **Step 7: Select the complete candidate**

Select the 30/30 candidate with the strongest retrieval coverage and grounded answers while respecting the latency rule. Because no before/after report is required, do not copy temporary comparison artifacts into the repository.

---

### Task 8: Run Final Ragas Evaluation and Publish the Baseline

**Files:**
- Regenerate: `results/eval_results.json`
- Regenerate: `results/eval_summary.json`
- Modify: `README.md:86-126`

**Interfaces:**
- Consumes: the selected implementation, fixed dataset, verified pricing assumptions, and sufficient provider balance.
- Produces: canonical baseline artifacts and report-ready README metrics.

- [ ] **Step 1: Run the canonical 30-case evaluation with Ragas once**

```bash
.venv/bin/python scripts/evaluate.py \
  --results-dir results \
  --input-price-per-million 0.3 \
  --output-price-per-million 1.2 \
  --price-source-url https://api-docs.deepseek.com/quick_start/pricing/
```

Expected: 30/30 graph cases complete and `ragas_status` is `completed`. A partial judge run may be retried only after resolving an external provider failure.

- [ ] **Step 2: Validate final artifact integrity and required metrics**

```bash
.venv/bin/python -c 'import json; [json.load(open(path), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value))) for path in ("results/eval_results.json", "results/eval_summary.json")]'
jq '{case_count_requested, case_count_completed, case_failures, latency: .deterministic_metrics.latency, cost: {observed_cost_usd: .deterministic_metrics.observed_cost_usd, estimated_cost_per_1000_usd: .deterministic_metrics.estimated_cost_per_1000_usd}, ragas: .ragas.summary}' results/eval_summary.json
```

Expected:

- strict JSON parsing succeeds;
- `case_count_requested` and `case_count_completed` are both 30;
- all five Ragas summaries exist with finite counts;
- report metrics include accuracy, unsupported-claim rate, and case-level unsupported-claim rate;
- latency contains p50 and p95; and
- cost contains observed and per-1,000 values.

- [ ] **Step 3: Replace the README evaluation section with the final baseline**

Report only:

- 30-case dataset and completion count;
- Context Precision, Context Recall, Faithfulness, Answer Relevancy, and Answer Correctness with finite-case counts;
- accuracy as Answer Correctness;
- incorrect/fabricated-answer indicators from Faithfulness;
- p50/p95 latency;
- observed cost and estimated cost per 1,000 questions;
- concise error analysis and remaining limitations; and
- same-family judge bias and excluded Gemini embedding cost when provider usage is unavailable.

Remove the old parser failure and old scores. Do not add a before/after table.

- [ ] **Step 4: Run final verification**

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check src scripts/evaluate.py tests
git diff --check
```

Expected: tests and Ruff pass; `git diff --check` reports no whitespace errors.

- [ ] **Step 5: Commit the report baseline**

```bash
git add results/eval_results.json results/eval_summary.json README.md
git commit -m "docs: publish improved RAG evaluation baseline"
```

The commit must contain the final provider-backed artifacts and README numbers from the same run.
