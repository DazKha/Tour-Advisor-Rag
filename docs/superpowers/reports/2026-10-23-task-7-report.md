# Task 7 Report: Evaluation Dataset, Ragas, and Safety Metrics

**Date:** 2026-10-23  
**Status:** Implemented and locally verified; live evaluation is partial due to one graph parsing error and exhausted DeepSeek balance during Ragas judging.

## Deliverables

- Added `data/eval/eval_cases.jsonl` with 30 reviewed cases in the required 10 factual, 5 itinerary/recommendation/comparison, 5 multi-turn/ambiguous, 4 insufficient/conflict, 3 realtime/high-risk, and 3 injection/off-topic distribution.
- Validated every `reference_context_id` against the current processed chunk artifact. Dataset validation reports zero errors.
- Added deterministic intent, exact tour resolution, answer status, clarification/conflict/refusal, citation validity, numeric grounding, prohibited-claim, latency percentile, token usage, and cost metrics.
- Added a Ragas 0.3.1 adapter using DeepSeek as judge and Gemini embeddings for Context Precision, Context Recall, Faithfulness, Response Relevancy, and Answer Correctness. Summary records `judge_model_self_evaluation=true`.
- Added `--limit` and `--skip-ragas` for faster deterministic smoke runs. Price-per-million values are required CLI arguments and their source URL and UTC timestamp are saved with the results.
- Constrained `langchain-community<0.4`: Ragas 0.3.1 imports `langchain_community.chat_models.vertexai`, which is absent in community 0.4.2. Aligning the environment to 0.3.31 restored the installed Ragas API.

## Live Run

- Official pricing was checked on 2026-10-23. The [DeepSeek pricing page](https://api-docs.deepseek.com/quick_start/pricing/) lists peak cache-miss input at $0.30 per million tokens and output at $1.20 per million tokens for DeepSeek Flash.
- The one-case deterministic smoke completed successfully: `factual_thai_price` resolved to `thailand-bangkok-pattaya`, status `answered`, with valid citation and numeric grounding.
- The one-case Ragas smoke completed all five metrics with finite scores.
- The full 30-case run completed 29 graph cases. `multiturn_compare_followup` failed with `OutputParserException`.
- Ragas produced 30 metric rows, but insufficient-balance responses from DeepSeek left some metric cells missing. Finite score counts were Context Precision 21/30, Context Recall 22/30, Faithfulness 21/30, Response Relevancy 22/30, and Answer Correctness 17/30. Missing values remain missing.
- Recorded DeepSeek usage across graph and judge calls: 463,546 input tokens and 269,377 output tokens. At the supplied rates the observed cost was $0.4623162; projected cost at this run mix is $15.41054 per 1,000 cases. Gemini embedding charges are not included in this DeepSeek token estimate.

## Deterministic Results

- Intent accuracy: 0.8667
- Tour resolution exact match: 0.9000
- Answer status accuracy: 0.7667
- Clarification/conflict/refusal accuracy: 0.7500
- Citation validity: 1.0000
- Numeric grounding rate: 1.0000
- Forbidden-claim rate: 0.0000
- Latency: p50 7,408.542 ms; p95 15,095.393 ms

The cost and deterministic summary use the 30 attempted cases as the projection denominator; one graph case failed before a normal answer was produced. The cost includes DeepSeek Ragas judge tokens, including the completed portion of judging before balance errors.

## Verification

- RED: metric tests initially failed collection because `vietravel_rag.evaluation` did not exist. Dataset validation tests also failed before `scripts/evaluate.py` existed.
- GREEN: `.venv/bin/python -m pytest tests/evaluation -v` — 8 passed.
- Full suite: `.venv/bin/python -m pytest -q` — 170 passed; 7 existing PyMuPDF/SWIG deprecation warnings.
- `.venv/bin/ruff check src/vietravel_rag/evaluation scripts/evaluate.py tests/evaluation` — passed.
- `git diff --check` — passed.

## Safety and Limits

- No secret values were read, printed, or saved. Provider errors are stored only as error class and case ID; the Ragas library itself emitted transient insufficient-balance diagnostics during its live call.
- No files under `raw_data/` or `reference/` were edited.
- Live acceptance is partial. No retry was made after DeepSeek returned insufficient-balance responses; the graph parser failure also remains unresolved pending separate investigation.
