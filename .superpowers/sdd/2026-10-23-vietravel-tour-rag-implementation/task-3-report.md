# Task 3 Report: Chroma Index and Scoped Retrieval

## Status contract

Implementation and offline verification are complete. The real local index was not built because `OPENAI_API_KEY` is unavailable. No alternate production embedding model was substituted, and no successful index build or live retrieval smoke test is claimed.

## Files

- Added `src/vietravel_rag/llm.py` with injectable DeepSeek chat and OpenAI embedding factories.
- Added `src/vietravel_rag/retrieval/` with the two-collection Chroma builder, tour resolver, exact itinerary lookup, and tour-scoped evidence retrieval.
- Updated `scripts/ingest.py` with `--build-index`, preserving the existing artifact build path.
- Updated `src/vietravel_rag/config.py` to load `.env` by default, with environment variables taking precedence, and added configurable resolution thresholds.
- Added retrieval, model-factory, and isolated dotenv tests.
- No reviewed JSONL artifacts or files under `raw_data/` and `reference/` were modified.

## RED and GREEN evidence

- Config RED: the dotenv regression used a temporary `.env` and initially failed because the Settings model disabled dotenv loading. GREEN: the temporary-file configuration test and the existing defaults test both pass; the defaults test explicitly disables file loading so it never reads the user's real `.env`.
- Retrieval RED: the first run could not collect tests because the local virtual environment lacked LangChain and Chroma dependencies. After installing those declared project dependencies, the first behavioral run exposed three failures in candidate thresholding/clarification and the typed itinerary error assertion. The fixtures and configured cosine relevance thresholds were corrected, and the focused retrieval suite now passes.
- GREEN: `.venv/bin/python -m pytest tests/retrieval -v` — 10 passed.
- GREEN: `.venv/bin/python -m pytest -v` — 49 passed, with 7 existing PyMuPDF/SWIG deprecation warnings.
- GREEN: `ruff check` on all changed Python files — all checks passed. `git diff --check` — clean.
- Fake embeddings are deterministic and local. Tests use temporary Chroma directories and make no paid API or network calls.

## Real index outcome

- Availability check reported `OPENAI_API_KEY` unavailable and `DEEPSEEK_API_KEY` available; only booleans were emitted.
- `.venv/bin/python scripts/ingest.py --build-index` stopped with `OPENAI_API_KEY is required to build the production embedding index` (exit 1).
- No `chroma_db/` directory was created. Collection counts: not built. The real “Tour Bà Nà có gì?” smoke query was not run because there is no production index.

## Commits

- Task 3 code and tests: `aa707316250244a6b5086c0019b039ecb1eedb5c` (`feat: add scoped Chroma retrieval`).
- This report is recorded in a separate documentation commit.

## Concerns

- The production index and live retrieval smoke test remain pending until `OPENAI_API_KEY` is configured. Once available, rerun `python scripts/ingest.py --build-index` and verify counts against the processed JSONL records.
