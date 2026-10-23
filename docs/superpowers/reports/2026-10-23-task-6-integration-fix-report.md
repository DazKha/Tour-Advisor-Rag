# Task 6 Report: Live Price Guardrail Integration Fix

**Date:** 2026-10-23
**Status:** Implemented and verified, including one sanitized live price scenario.

## Root Cause and Fix

- Production price age bands use parenthesized prefixes such as `(Dưới 2 tuổi)` and `(Từ 12 tuổi trở lên)`. The comparator-prefix matcher did not accept an opening parenthesis as a valid boundary.
- Comparator aliases were prefix-only, so trailing forms such as `trở lên`, `trở xuống`, `or more`, and `or less` could not normalize.
- The Vietnamese đồng symbol `₫` was absent from the canonical VND unit map and was treated as an unsupported scalar unit.
- Added punctuation-safe prefix bounds, longest-match suffix comparators, and `₫` as a VND alias. Existing comparator mismatch checks continue rejecting dropped or changed bounds and other currency claims.

## Verification

- RED: added regressions for parenthesized/unparenthesized strict age bounds, minimum and maximum suffix synonyms, comparator loss/change, VND symbol normalization, USD rejection, and a representative Thailand price chunk containing adult/child/infant age bands and a `₫` price.
- GREEN: `.venv/bin/pytest -q tests/guardrails/test_output_guard.py` — 57 passed.
- Full suite: `.venv/bin/python -m pytest -q` — 160 passed; 7 existing PyMuPDF/SWIG deprecation warnings.
- Changed-file Ruff and `git diff --check` — passed.
- Live price scenario: status `answered`; citation IDs: `thailand-bangkok-pattaya_price_01`.
- The standalone `pytest` entry point did not include the repository root needed by an existing app-helper test; invoking pytest as a Python module completed the full suite successfully.

## Scope and Safety

- The live response was constrained to status and citation IDs; no answer body, credentials, or source text was emitted.
- Runtime settings were consumed by the application for the live turn; no secret values were printed or logged. No source inputs were edited.

## Suffix-bound correction

- RED: `and above` was treated as strict `>` and `and below` as strict `<`, unlike their intended inclusive equivalents.
- GREEN: both suffixes now normalize to inclusive `>=`/`<=`; regressions verify equivalent `or more`/`or less` phrasing and rejection of strict `over`/`under` claims.
- Latest verification: 59 guardrail tests and 162 full-suite tests passed; changed-file Ruff and diff checks passed. The 7 existing PyMuPDF/SWIG deprecation warnings remain.
