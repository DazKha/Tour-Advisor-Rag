# Task 5 Report: Guarded LangGraph Answer Flow

**Date:** 2026-10-23
**Status:** Implemented and verified with local fakes; no paid model API calls.

## Delivered

- Added empty, oversized, and prompt-injection input handling plus a PII redaction utility for email addresses, Vietnamese phone numbers, and long digit sequences.
- Added evidence assessment that accepts only explicitly identified `official_tour_pdf` knowledge chunks. Structured model selections outside the supplied IDs become insufficient evidence.
- Added deterministic current-price, availability, medical, visa-guarantee, payment-detail, cancellation-execution, and complaint escalation routes.
- Added Vietnamese structured answer generation, citation allowlisting, normalized numeric support checks, prohibited-claim checks, and a fixed safe result when generation or validation fails. The graph does not retry generation.
- Numeric checks preserve units and categories across currency, percentage, dates, elapsed time, days versus nights, weight, people, distance, volume, age, room, and seat counts. Equivalent numeric separators, common unit forms, shared range units, and calendar-valid date formats are normalized.
- Added a real LangGraph flow with the specified node sequence, in-memory checkpointing by `thread_id`, follow-up context, and a 10-message cap.
- The Đà Nẵng baggage conflict bypasses model evidence selection and forces both reviewed claims and citations into the final response.
- General questions receive a concise capability response, and obvious English `ignore all rules` injection phrasing is refused by the lexical input guard.
- Added guardrail and graph tests, including price, child-price follow-up, ambiguous pronoun, baggage conflict, live availability, current pricing, risk escalation, input handling, session history, and state isolation.

## TDD Evidence

- RED: the initial focused run failed collection because the guardrail and graph modules did not exist.
- RED: the current-price test showed that a current-price question reached model evidence assessment instead of `realtime_required`.
- RED: a baggage model response citing only the first claim produced only one citation.
- RED: the 10-message test showed 13 messages remained after ordinary list slicing with the LangGraph message reducer.
- RED: a tour-summary test showed catalog summaries could be approved as factual evidence.
- Review-fix RED: tests reproduced three unit-swapping acceptances (`10kg`/`10%`, `75%`/`75 guests`, `10 nights`/`10 days`) and rejection of equivalent date formats. Additional RED checks found missing English `ignore all rules` handling and an unhelpful general response.
- Review-fix GREEN: `.venv/bin/python -m pytest tests/guardrails tests/agent/test_graph.py tests/agent/test_query_analysis.py tests/agent/test_routing.py -q` — 58 passed.
- Full suite: `.venv/bin/python -m pytest -q` — 108 passed; 7 existing PyMuPDF/SWIG deprecation warnings.
- Ruff on changed files — passed.
- Full-repository Ruff reports 13 existing findings in untouched ingestion files and prior test files; no Task 5 files are implicated.
- `git diff --check` — passed.

## Environment and Scope

- Synchronized `.venv` from the declared `pyproject.toml` dependencies, including LangGraph.
- No `.env` values were read or printed. No live APIs were called.
- `raw_data/` and `reference/` remain untouched.
- The PII utility is available for any future log path; this graph currently emits no user-input logs.
