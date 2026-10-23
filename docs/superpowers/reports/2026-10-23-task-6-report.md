# Task 6 Report: Streamlit Multi-Turn Demo

**Date:** 2026-10-23
**Status:** Implemented and locally verified; provider integration smoke completed with clarification-only scenario outcomes.

## Delivered

- Added a Streamlit chat UI with Vietnamese suggested prompts, status labels, cited source expanders, a safe metadata allowlist, and a visible staff-confirmation note for availability and booking.
- Added `render_citation_label()` for single-page and page-range citations and `build_session_config()` for a stable LangGraph `thread_id`.
- The UI stores the thread ID in session state, uses it for each graph invocation, and rotates it when resetting messages, active tours, and last citations.
- Graph resources are cached. The app builds DeepSeek/Gemini clients from `Settings`, opens the configured persistent Chroma collections, and reports missing configuration or index state without displaying exception details or secret values.
- Added Streamlit theme/server defaults and helper tests.

## TDD and Verification

- RED: `.venv/bin/python -m pytest tests/test_app_helpers.py -v` failed collection because `app.py` and the required helpers did not exist.
- GREEN: the focused helper suite passed — 3 tests.
- Full suite: `.venv/bin/python -m pytest -q` — 140 passed; 7 existing PyMuPDF/SWIG deprecation warnings.
- `.venv/bin/ruff check app.py tests/test_app_helpers.py` — passed.
- `git diff --check` — passed.
- Headless Streamlit started on port 8765; `/_stcore/health` returned `ok`, and `/` returned the Streamlit page.
- During initial UI verification, no provider prompts were sent; the five prompts below were documented for later smoke testing.

## Review Fix Round 1: Multi-Turn History

- RED: a two-turn UI regression using the real LangGraph with a recording fake model showed the second query omitted the first assistant answer from model-visible history.
- Root cause: `_run_turn()` invoked `graph.invoke()` with only the current prompt. The graph checkpoint accumulates user messages, but the response is stored separately; only `invoke_turn()` restores that response as an `AIMessage` before invoking the next turn.
- GREEN: `_run_turn()` now uses `invoke_turn(graph, prompt, session_id)`. A regression verifies that the second model analysis sees the prior assistant answer.
- Added a reset regression: reset clears rendered messages and active tours, generates a new thread identity, and therefore isolates the next graph checkpoint.
- Removed the redundant UI `last_citation_ids` state; citation continuity remains owned by the LangGraph checkpoint.
- Focused helper suite — 5 passed. Full suite — 142 passed, with the same 7 existing PyMuPDF/SWIG deprecation warnings.
- Changed-file Ruff and `git diff --check` passed. Headless Streamlit restarted and `/_stcore/health` returned `ok`.
- At the end of this review round, live provider-backed scenarios remained unrun; the following review round records their eventual sanitized outcomes.

## Review Fix Round 2: DeepSeek JSON Mode

- RED: a production-like fake requiring `method="json_mode"`, the word `json`, and the exact JSON schema in the prompt rejected the graph's default structured-output call before query analysis.
- Root cause evidence supplied by the provider smoke: plain `deepseek-flash` invocation works, while the default `json_schema` format and function-calling mode are rejected by the configured API. JSON mode is supported when the system prompt includes JSON and the exact schema contract.
- GREEN: added one `deepseek_json_output()` adapter used by query analysis, evidence assessment, and answer generation. It selects JSON mode when supported, embeds the compact Pydantic JSON schema (including enum values), and retains legacy injected fakes whose method accepts only `schema`.
- The graph-level regression exercises all three schemas and rejects either missing JSON mode or missing prompt/schema constraints. Existing injected fake graph tests continue to pass.
- Focused provider-adapter/graph tests — 23 passed. Full suite — 143 passed, with 7 existing PyMuPDF/SWIG deprecation warnings.
- Changed-file Ruff and `git diff --check` passed.
- Sanitized real provider smoke: standalone structured query analysis passed with `intent=itinerary`.
- Five graph scenarios completed without provider exceptions, but none reached an answer/citation outcome. Exact sanitized results:
  1. Price: `status=clarification_needed`, `intent=price`, tour codes `thailand-bangkok-pattaya`, `danang-central-5d4n`, no citation IDs.
  2. Child-price follow-up in the same session: `status=clarification_needed`, `intent=child_price`, same tour codes, no citation IDs.
  3. Ambiguous-tour itinerary: `status=clarification_needed`, `intent=itinerary`, tour codes `danang-central-5d4n`, `mekong-my-tho-ben-tre-can-tho`, no citation IDs.
  4. Đà Nẵng baggage: `status=clarification_needed`, `intent=baggage`, tour codes `danang-central-5d4n`, `thailand-bangkok-pattaya`, no citation IDs.
  5. Availability: `status=clarification_needed`, `intent=availability`, tour codes `thailand-bangkok-pattaya`, `mekong-my-tho-ben-tre-can-tho`, no citation IDs.
- The scenario outcomes are not marked successful and no cause is inferred here. No response text, credentials, or raw provider errors were recorded.

## Five-Scenario Demo Prompts

1. Normal factual answer with citations: `Giá tour Bangkok – Pattaya bao nhiêu?`
2. Multi-turn follow-up inheriting the active tour: `Giá trẻ em của tour đó như thế nào?`
3. Ambiguous tour clarification: `Lịch trình tour đó có những điểm nào?`
4. Đà Nẵng baggage conflict: `Hành lý ký gửi của tour Đà Nẵng quy định ra sao?`
5. Real-time availability refusal: `Tour Bangkok – Pattaya hôm nay còn chỗ không?`

## Scope

- No `.env` contents or provider credentials were read or printed.
- No external provider calls were made.
- `raw_data/`, `reference/`, and synchronized project source files were not modified.
