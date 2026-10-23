# Task 3 Report: Chroma Index and Scoped Retrieval

## Status contract

Task 3 is complete, including the Gemini embedding migration, resolver near-tie fix, local index build, and sanitized live retrieval smoke test.

## Files

- Added `src/vietravel_rag/llm.py` with injectable DeepSeek chat and Gemini embedding factories. Gemini corpus and query calls use separate retrieval task types; 768-dimensional output is dimension-checked and L2-normalized.
- Added `src/vietravel_rag/retrieval/` with the two-collection Chroma builder, tour resolver, exact itinerary lookup, and tour-scoped evidence retrieval.
- Updated `scripts/ingest.py` with `--build-index`, preserving the existing artifact build path.
- Updated `src/vietravel_rag/config.py` to load `.env` by default, with environment variables taking precedence, and added Gemini key/model/dimension settings plus configurable resolution thresholds.
- Updated `pyproject.toml`, `.env.example`, the SDD briefs, design spec, and implementation plan to use `langchain-google-genai` and Gemini Embedding 1 while retaining `langchain-openai` for DeepSeek chat.
- Added retrieval, model-factory, and isolated dotenv tests.
- No reviewed JSONL artifacts or files under `raw_data/` and `reference/` were modified.

## RED and GREEN evidence

- Config RED: the dotenv regression used a temporary `.env` and initially failed because the Settings model disabled dotenv loading. GREEN: the temporary-file configuration test and the existing defaults test both pass; the defaults test explicitly disables file loading so it never reads the user's real `.env`.
- Resolver RED: `test_below_floor_runner_up_still_prevents_near_tie_auto_resolution` initially failed with only `tour-a` returned for scores 0.66 and 0.60 against a 0.65 floor and 0.10 separation margin. GREEN: the resolver compares the original top-two scores before returning a single resolved tour; the regression now returns both clarification candidates.
- Gemini RED: updated settings/factory tests initially failed against the OpenAI-only settings and factory. GREEN: settings now require `GEMINI_API_KEY`; the injectable factory configures `gemini-embedding-001` at 768 dimensions, assigns the document/query task types separately, validates vector length, and normalizes each vector.
- Retrieval RED: the first run could not collect tests because the local virtual environment lacked LangChain and Chroma dependencies. After installing those declared project dependencies, the first behavioral run exposed three failures in candidate thresholding/clarification and the typed itinerary error assertion. The fixtures and configured cosine relevance thresholds were corrected, and the focused retrieval suite now passes.
- GREEN: `.venv/bin/python -m pytest tests/retrieval/test_resolver.py -v` — 7 passed; `.venv/bin/python -m pytest tests/retrieval -v` — 11 passed.
- GREEN: `.venv/bin/python -m pytest -v` — 50 passed, with 7 existing PyMuPDF/SWIG deprecation warnings.
- GREEN: `ruff check` on all changed Python files — all checks passed. `git diff --check` — clean.
- Fake embeddings are deterministic and local. Tests use temporary Chroma directories and make no paid API or network calls.

## Real index outcome

- `.venv/bin/python scripts/ingest.py --build-index` — `PASS`; `tour_catalog=8`, `tour_knowledge=84`.
- A sanitized persisted-vector check sampled three vectors from each collection; all sampled vectors had 768 dimensions and unit L2 norm.
- The sanitized “Tour Bà Nà có gì?” smoke query resolved the Đà Nẵng tour and retrieved itinerary evidence, including `danang-central-5d4n_itinerary_02` (“Ngày 2 : Đà Nẵng – KDL Bà Nà – Cầu Vàng”). Exact full-itinerary lookup also returned `danang-central-5d4n_full_itinerary`. Output contained only record IDs and titles.
- Vector behavior follows the [Google Gemini embeddings documentation](https://ai.google.dev/gemini-api/docs/embeddings) and the [LangChain Google GenAI embedding API](https://reference.langchain.com/python/langchain-google-genai/embeddings/GoogleGenerativeAIEmbeddings).

## Commits

- Task 3 code and tests: `aa707316250244a6b5086c0019b039ecb1eedb5c` (`feat: add scoped Chroma retrieval`).
- Task 3 Gemini/resolver fix round: `965b4d5cb3e4f178831353d2972a189e9e144931` (`feat: migrate retrieval embeddings to Gemini`).
- This updated report and SDD ledger entry are recorded in a separate documentation commit.

## Concerns

- The built `chroma_db/` is local and ignored by Git. Rebuild it with `python scripts/ingest.py --build-index` after changing embedding model or dimension; Chroma vectors from different models or dimensions are not interchangeable.
