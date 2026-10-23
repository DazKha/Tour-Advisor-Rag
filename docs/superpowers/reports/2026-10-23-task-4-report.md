# Task 4 Report: Query Understanding and Multi-Turn Routing

**Date:** 2026-10-23  
**Status:** Implemented; implementation and report are committed separately.

## Delivered

- Added a Vietnamese structured query-analysis prompt and injectable `analyze_query` node using `model.with_structured_output(QueryAnalysis)`.
- Preserved explicit tour aliases from the current Vietnamese message and supplied recent messages and active tour context to analysis. The analyzer emits no tour codes and does not answer users.
- Added routing for off-topic, general, resolved, ambiguous, unsupported, and unresolved multi-tour pronoun queries. Ordinary multi-candidate requests ask for clarification; comparisons can continue when two named tours resolve.
- Added scoped retrieval orchestration with six chunks by default or ten for comparisons, summary context, exact full-itinerary lookup for itinerary/recommendation/full-program requests, and adjacent-day expansion by cited chunk ID and itinerary index.
- Added offline fake-model and fake-retriever tests. No live model API was called.

## Evidence

- RED: the focused tests initially failed to collect because `vietravel_rag.agent` did not exist.
- GREEN: `python -m pytest tests/agent/test_query_analysis.py tests/agent/test_routing.py -v` — 11 passed.
- Ruff: `ruff check src/vietravel_rag/agent tests/agent` — passed.
- Whitespace: `git diff --check` — passed.
- Full suite attempt: `python -m pytest` could not collect four existing retrieval/model test modules because the environment lacks the declared `langchain-google-genai` dependency. No API keys or `.env` values were read.

## Scope notes

The repository had no separate progress ledger; the Task 4 checklist in the implementation plan was updated. `raw_data/` and `reference/` were left untouched.
