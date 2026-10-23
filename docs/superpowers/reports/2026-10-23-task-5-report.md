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

## Review Fix Round 2

- RED: reproduced two additional unit-category bypasses: evidence `2 phòng` accepted an answer claiming `2 mét`, and evidence `3 chỗ` accepted `3 phòng`.
- RED: reproduced a range-order bypass: evidence `10-13 ngày` accepted `từ 13 đến 10 ngày` because the earlier implementation compared endpoints independently.
- GREEN: moved every supported spelling and alias into one canonical unit mapping used to generate both unit-capture and range regexes; normalization now reads the same mapping. Range facts retain ordered, normalized endpoints and accept equivalent shared-unit wording.
- Added regressions for the two alias swaps, reversed range rejection, and equivalent range wording acceptance.
- `.venv/bin/pytest -q tests/guardrails/test_output_guard.py` — 24 passed.
- `.venv/bin/pytest -q` — 112 passed; 7 existing PyMuPDF/SWIG deprecation warnings.
- Changed-file Ruff and `git diff --check` — passed.
- No secret values or source-input directories were accessed.

## Review Fix Round 3

- RED: reproduced two qualifier-loss bypasses: `under 12` evidence accepted an unqualified `12`, and a `from 5 to below 12` age range accepted a weakened inclusive upper bound.
- GREEN: numeric facts now carry comparison operators. Scalar and range extraction normalize strict `<`/`>` aliases (`dưới`/`under`/`below`, `trên`/`over`/`above`) and inclusive `>=`/`<=` aliases (`từ`/`from`, `ít nhất`/`at least`, `đến`/`to`, `tối đa`/`at most`, `up to`). Range facts preserve comparator semantics independently for each endpoint.
- Added regressions for strict-bound loss, synonym equivalence, inclusive min/max, strict greater-than, and changing a strict range limit to an inclusive one.
- `.venv/bin/pytest -q tests/guardrails/test_output_guard.py` — 31 passed.
- `.venv/bin/pytest -q` — 119 passed; 7 existing PyMuPDF/SWIG deprecation warnings.
- Changed-file Ruff and `git diff --check` — passed; ordinary date, range, and currency regressions remain green.
- No secret values or source-input directories were accessed.

## Review Fix Round 4

- RED: reproduced both comparator errors: a `from 5` minimum accepted `more than 5`, and `not under 12` was interpreted as strict `under 12`.
- GREEN: comparator aliases now come from one canonical vocabulary sorted longest-first, so negated and multiword phrases take precedence over suffixes. Strict/inclusive English and Vietnamese forms map to `>`, `<`, `>=`, or `<=`; range endpoints use defaults only when no recognized qualifier is present.
- Added matrix regressions for strict, inclusive-minimum, inclusive-maximum, and qualified-range synonyms, plus both reported cases.
- Added prefix currency-code normalization, with `VND 8,990,000` and `USD 100` validated against equivalent suffix/symbol evidence.
- `.venv/bin/pytest -q tests/guardrails/test_output_guard.py` — 41 passed.
- `.venv/bin/pytest -q` — 129 passed; 7 existing PyMuPDF/SWIG deprecation warnings.
- Changed-file Ruff and `git diff --check` — passed; date, range, and currency regressions remain green.
- No secret values or source-input directories were accessed.

## Review Fix Round 5

- RED: reproduced three omitted strict-less aliases (`less than`, `nhỏ hơn`, `ít hơn`) being accepted without their comparator, plus failures to normalize `not/no less/fewer/lower than` and `not/no greater/more/higher than` consistently.
- GREEN: expanded the longest-match canonical vocabulary for all requested English/Vietnamese strict, inclusive, positive, and negated aliases. Added matrix-style scalar and ordered-range endpoint tests across `<`, `<=`, `>`, and `>=`.
- Unknown comparative cues now produce stable `unknown:<phrase>` facts instead of default equality or range bounds. The rule is applied before and after numbers, and comparator lookup is confined to text after the previous numeric token to prevent bounds leaking into later claims.
- Added a regression for the prior-range-to-percentage interaction; the graph child-price follow-up test passes.
- `.venv/bin/pytest -q tests/guardrails/test_output_guard.py` — 49 passed.
- `.venv/bin/pytest -q` — 137 passed; 7 existing PyMuPDF/SWIG deprecation warnings.
- Changed-file Ruff and `git diff --check` — passed; no secrets or source-input directories were accessed.
