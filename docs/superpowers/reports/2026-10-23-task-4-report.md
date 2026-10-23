# Task 4 Report: Query Understanding and Multi-Turn Routing

**Date:** 2026-10-23  
**Status:** Implemented and integrated with the Task 5 LangGraph state contract.

## Delivered

- Added a Vietnamese structured query-analysis prompt and injectable `analyze_query` node using `model.with_structured_output(QueryAnalysis)`.
- Preserved explicit tour aliases from the current Vietnamese message and supplied recent messages and active tour context to analysis. The analyzer emits no tour codes and does not answer users.
- Added routing for off-topic, general, resolved, ambiguous, unsupported, and unresolved multi-tour pronoun queries. Ordinary multi-candidate requests ask for clarification; comparisons can continue when two named tours resolve.
- Added scoped retrieval orchestration with six chunks by default or ten for comparisons, summary context, exact full-itinerary lookup for itinerary/recommendation/full-program requests, and adjacent-day expansion by cited chunk ID and itinerary index.
- Added offline fake-model and fake-retriever tests. No live model API was called.

## Evidence

- RED: the focused tests initially failed to collect because `vietravel_rag.agent` did not exist.
- GREEN: `.venv/bin/python -m pytest tests/agent/test_query_analysis.py tests/agent/test_routing.py -q` — 12 passed, including the state-channel regression.
- Ruff: `ruff check src tests` — passed.
- Whitespace: `git diff --check` — passed.
- Full suite: `.venv/bin/python -m pytest -q` — 62 passed, with 7 PyMuPDF/SWIG deprecation warnings.
- Environment note: the system Python full-suite attempt could not collect four retrieval/model modules because that interpreter lacks the declared `langchain-google-genai` dependency; the project `.venv` run above is complete.
- No API keys or `.env` values were read.

## State-contract integration fix

The routing node emits `route`, `tour_candidates`, and `tour_summaries`. These are now declared in `AgentState`; the document-bearing fields use `list[Document]`, and `retrieved_chunks` is typed consistently with node output. The regression test confirms every resolver-node output key belongs to the TypedDict state schema. This environment did not have `langgraph` installed, so the regression checks the state annotation contract directly rather than compiling a `StateGraph`.

Fix implementation commit: `3791f5cc6343372f63d4a4dc807d196b63206385`.

## Scope notes

The Task 4 checklist in the implementation plan and the SDD progress ledger were updated. `raw_data/` and `reference/` were left untouched.
