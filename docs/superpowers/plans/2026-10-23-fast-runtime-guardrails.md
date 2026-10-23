# Fast Runtime Guardrails Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the runtime evidence-assessment LLM call, replace numeric grounding with a thin deterministic output guard, and translate all system prompts to English.

**Architecture:** Retrieved official knowledge chunks flow directly into answer generation after deterministic conflict, realtime, and high-risk checks. The generator owns semantic sufficiency and grounding; the final guard enforces citation membership, citation presence, prohibited-claim safety, and fail-closed structured output.

**Tech Stack:** Python 3.12, LangGraph, LangChain, Pydantic v2, pytest, DeepSeek JSON structured output.

## Global Constraints

- All production code changes and test changes must be implemented by a GPT Luna agent.
- Follow strict TDD: write and run failing tests before changing production code.
- Ordinary factual turns use exactly two structured LLM calls: `QueryAnalysis`, then `TourAnswer`.
- Do not add a runtime LLM grounding verifier.
- User-facing answer text remains Vietnamese; every system prompt constant is English.
- Preserve deterministic conflict, realtime, high-risk, prompt-injection, and citation-integrity behavior.
- Do not retry invalid structured model output.
- Do not expose or modify API keys or `.env` files.

---

### Task 1: Simplify the answer pipeline and runtime guardrails

**Files:**
- Modify: `src/vietravel_rag/agent/graph.py`
- Modify: `src/vietravel_rag/agent/nodes.py`
- Modify: `src/vietravel_rag/agent/prompts.py`
- Modify: `src/vietravel_rag/guardrails/output_guard.py`
- Modify: `src/vietravel_rag/models.py`
- Modify: `tests/agent/test_graph.py`
- Modify: `tests/guardrails/test_output_guard.py`
- Modify as required: other tests that explicitly encode the removed `EvidenceAssessment` call

**Interfaces:**
- Consumes: `AgentState.retrieved_chunks`, deterministic `evidence_status`, and `TourAnswer` structured output.
- Produces: `AgentState.approved_chunks` containing only retrieved documents whose metadata has `authority == "official_tour_pdf"` and `document_type == "knowledge"`; `response` containing a validated `TourAnswer` dictionary.

- [ ] **Step 1: Add failing graph tests for the two-call path**

Update ordinary-answer fakes so their response queue contains only a `QueryAnalysis` and a `TourAnswer`. Assert `model.schemas == [QueryAnalysis, TourAnswer]`, assert the graph has no `evidence_assessment` node, and assert answer generation receives all and only official knowledge chunks retrieved for the active tour. Run:

```bash
pytest tests/agent/test_graph.py -q
```

Expected: FAIL because the graph still invokes `EvidenceAssessment` and still contains that node.

- [ ] **Step 2: Add failing thin-guard tests**

Replace numeric-parser expectations with focused tests proving: an unknown citation is rejected; an answered response without citations is rejected; a known citation passes even when the answer contains a directly inferred or reformatted number; each prohibited claim category escalates; `unsupported` without citations remains valid. Run:

```bash
pytest tests/guardrails/test_output_guard.py -q
```

Expected: at least the numeric test FAILS because the old numeric grounding rejects it.

- [ ] **Step 3: Remove evidence assessment from the runtime graph**

Delete the `evidence_assessment` node and edge from `graph.py`. Replace `assess_evidence` with a deterministic preparation function, or fold the preparation into the existing retrieval/generation boundary, that:

```python
approved = [
    doc for doc in state.get("retrieved_chunks", [])
    if doc.metadata.get("authority") == "official_tour_pdf"
    and doc.metadata.get("document_type") == "knowledge"
]
```

Before generation, preserve existing deterministic routing for conflict, realtime price/availability, health/complaint, visa guarantees, financial actions, and cancellation execution. Ordinary requests pass `approved` directly to `generate_answer`. Remove the unused evidence-assessment prompt and model/state contract where no longer referenced.

- [ ] **Step 4: Replace numeric grounding with the thin output guard**

Reduce `validate_answer(answer, approved_chunks)` to these ordered checks:

1. Escalate if `answer.answer` matches an existing prohibited-claim pattern.
2. Return `unsupported` if any `citation_id` is absent from the approved chunk allowlist.
3. Return `unsupported` if status is `answered` or `conflict` and citations are empty.
4. Otherwise return the original answer unchanged.

Delete numeric/date/unit/range parsing and itinerary-derived fact code. Keep the public function signature stable.

- [ ] **Step 5: Translate system prompts to English**

Write `QUERY_ANALYSIS_SYSTEM_PROMPT` and `ANSWER_GENERATION_SYSTEM_PROMPT` entirely in English. The answer prompt must still require Vietnamese user-facing output, official-evidence-only facts, supplied-ID-only citations, direct/obvious inference only, `unsupported` on insufficient evidence, safe handling of conflicts, and no prohibited operational claims. Remove `EVIDENCE_ASSESSMENT_SYSTEM_PROMPT`.

- [ ] **Step 6: Run focused tests and refactor**

```bash
pytest tests/agent/test_graph.py tests/guardrails/test_output_guard.py tests/test_structured_output.py -q
```

Expected: PASS. Remove stale imports, fixtures, and assertions tied solely to `EvidenceAssessment`.

- [ ] **Step 7: Run the full suite**

```bash
pytest -q
```

Expected: PASS with zero failures.

- [ ] **Step 8: Commit the implementation**

```bash
git add src tests docs/superpowers/specs/2026-10-23-fast-runtime-guardrails-design.md docs/superpowers/plans/2026-10-23-fast-runtime-guardrails.md
git commit -m "refactor: simplify runtime guardrails"
```
