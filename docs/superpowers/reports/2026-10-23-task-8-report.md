# Task 8 Report: Deployment, Documentation, and Final Verification

**Date:** 2026-10-23
**Status:** Local release candidate prepared and verified. Community Cloud publication and fresh live acceptance remain pending.

## Delivered

- Added `README.md` with all 12 required topics: scope, architecture, source authority, semantic chunking, setup, ingestion/indexing, app launch, evaluation, Cloud secrets, limitations, the five-prompt demo, and actual metric/error analysis.
- Added `.streamlit/secrets.toml.example` containing only the two required key names with empty values. `app.py` now reads Community Cloud `st.secrets` and falls back to environment variables and `.env` for local use.
- Kept `chroma_db/` out of Git. It measured 3.7 MB before rebuild and 4.3 MB after rebuilding. `ensure_index_ready()` checks processed JSONL record counts, reuses a matching index, and rebuilds mismatched collections from the JSONL artifacts. The cached resource initializer shares this work across sessions in one Streamlit process; PDF extraction is not part of app startup.
- Added regression tests for Cloud secret loading, index rebuild on count mismatch, and no rebuild for a matching index.
- Fixed all full-repository Ruff findings: sorted imports, removed inactive `noqa` directives, used canonical regex flags, simplified one equivalent conditional, and marked the two shebang scripts executable.
- Added the Task 8 results and remaining external blockers to the plan and SDD progress ledger.
- Committed implementation and lint cleanup separately as `a910d77` (`feat: bootstrap deployment index from reviewed data`).

## Evaluation facts recorded in the README

- 30 requested cases; 29 graph completions. `multiturn_compare_followup` failed with `OutputParserException`.
- Deterministic results: intent 0.867; exact tour resolution 0.900; answer status 0.767; clarification/conflict/refusal 0.750; citation validity 1.000; numeric grounding 1.000; forbidden-claim rate 0.000; latency p50 7.41 seconds and p95 15.10 seconds.
- Ragas finite score means: context precision 0.508 (21/30), context recall 0.727 (22/30), faithfulness 0.726 (21/30), answer relevancy 0.539 (22/30), and answer correctness 0.346 (17/30). Missing values reflect insufficient DeepSeek judge balance. DeepSeek judged answers from the same model family, so self-evaluation bias is disclosed.
- Citation validity is described as checking only emitted IDs against retrieved IDs; it does not establish citation coverage or completeness.
- Recorded DeepSeek-only cost was $0.4623162, projected at $15.41054 per 1,000 attempted cases. Gemini embedding usage is excluded.

## Verification

- `.venv/bin/ruff check .` — passed after cleaning all initial repository findings.
- `.venv/bin/python -m pytest -v` — 174 passed, 7 existing PyMuPDF/SWIG deprecation warnings.
- `.venv/bin/python scripts/audit_chunks.py` — `PASS`; 84 chunks, 8 catalog records, zero unclassified sections, 20 sales guidance scenarios, and one curated conflict.
- `.venv/bin/python scripts/ingest.py --build-index` — `PASS`; `tour_catalog=8`, `tour_knowledge=84` using Gemini embeddings and processed JSONL only.
- Headless Streamlit health endpoint — `ok`; root page — HTTP 200.
- Strict JSON parsing with non-finite constants rejected — passed for both evaluation result files.
- Secret scan using a key-shaped pattern for `sk-` tokens and long values assigned to provider key names — no matches. `.env` and `.streamlit/secrets.toml` remain ignored; no values were read or printed.
- `git diff --check` — passed.
- `raw_data/` and `reference/` were not edited or staged.

## Remaining blockers and limits

- No Git remote is configured and `gh` is not installed. The checkout cannot be published to GitHub or deployed to Streamlit Community Cloud from this environment. No external repository, deployment, or push was attempted.
- The prior Task 7 run recorded insufficient DeepSeek balance during Ragas judging. Task 8 made no live provider prompts; the earlier sanitized five-scenario outcomes remain in the Task 6 report. Do not represent those scenarios as passing acceptance.
- Free Community Cloud hosting does not cover Gemini or DeepSeek API usage. On a restart without persistent local Chroma files, startup re-embeds the processed corpus.
