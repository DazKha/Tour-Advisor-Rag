# Task 6 Report: Streamlit Multi-Turn Demo

**Date:** 2026-10-23
**Status:** Implemented and locally verified; no external model requests were made.

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
- No provider prompts were sent. The five scenarios below are a demo script only; their live outcomes remain unverified because exercising them would call external model services.

## Five-Scenario Demo Script (Not Executed)

1. Normal factual answer with citations: `Giá tour Bangkok – Pattaya bao nhiêu?`
2. Multi-turn follow-up inheriting the active tour: `Giá trẻ em của tour đó như thế nào?`
3. Ambiguous tour clarification: `Lịch trình tour đó có những điểm nào?`
4. Đà Nẵng baggage conflict: `Hành lý ký gửi của tour Đà Nẵng quy định ra sao?`
5. Real-time availability refusal: `Tour Bangkok – Pattaya hôm nay còn chỗ không?`

## Scope

- No `.env` contents or provider credentials were read or printed.
- No external provider calls were made.
- `raw_data/`, `reference/`, and synchronized project source files were not modified.
