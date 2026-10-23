# SDD ledger — plan: /Users/minhkha/SidePrj/vietravel/docs/superpowers/plans/2026-10-23-vietravel-tour-rag-implementation.md
Setup: repository initialized on codex/vietravel-rag at d62a369; source files remain untouched.
Task 1: fix round 1/5 (1 addressed, 0 open — supported Python runtime evidence; commits 591f8f8..75ec456)
Task 1: minor (deferred): AgentState uses broad list/dict annotations; final review should triage.
Task 1: minor (deferred): record-model required fields and missing-key behavior lack direct tests; final review should triage.
Task 1: complete (commits d62a369..75ec456, review clean)
Task 2: fix round 1/5 (3 addressed, 1 open — validator exact conflict invariant; commits eb8596b..e438bce)
Task 2: fix round 2/5 (1 addressed, 0 open — exact curated conflict record; commits e438bce..b70f458)
Task 2: fix round 3/5 (2 addressed, 0 open — separate holiday cancellation chunks and whitespace; commits b70f458..0d636b5)
Task 2: minor (deferred): PyMuPDF/SWIG emits seven deprecation warnings under Python 3.13; final review should triage.
Task 2: complete (commits 75ec456..0d636b5, review clean)
Task 3: fix round 1/5 (resolver near-tie separation and Gemini Embedding 1 migration; 2 addressed, 0 open; 768-dimensional normalized vectors; index counts 8/84 and Bà Nà smoke passed; implementation commit 965b4d5)
Task 4: fix round 1/5 (1 addressed, 0 open — declared resolver output state channels for LangGraph; regression confirms node output fields are in AgentState; project .venv full suite 62 passed; implementation commit 3791f5c)
Task 5: complete (guardrails, evidence assessment, answer generation, LangGraph checkpointer and end-to-end tests; full suite 92 passed; changed-file Ruff and diff check passed; full-repository Ruff has 13 findings in untouched prior files; no API keys read; implementation commit recorded separately)
Task 5: fix round 1/5 (6 review findings addressed, 0 open — typed numeric facts prevent unit swaps; valid equivalent dates normalize; general response is intentional; added obvious English ignore-all-rules pattern; 58 focused and 108 full tests passed; changed-file Ruff and diff check passed; no secrets or source inputs accessed)
Task 5: fix round 2/5 (2 review findings addressed, 0 open — extraction and normalization share canonical unit aliases; ordered normalized range facts reject reversed endpoints while accepting equivalent wording; 24 focused and 112 full tests passed; changed-file Ruff and diff check passed; no secrets or source inputs accessed)
Task 5: fix round 3/5 (2 review findings addressed, 0 open — scalar and ordered-range numeric facts preserve strict/inclusive comparator bounds and normalize Vietnamese/English aliases; 31 focused and 119 full tests passed; changed-file Ruff and diff check passed; ordinary date/range/currency regressions green; no secrets or source inputs accessed)
Task 5: fix round 4/5 (3 review findings addressed, 0 open — longest-match canonical comparator vocabulary handles strict/inclusive and negated phrases; range defaults only when unqualified; prefix VND/USD codes normalize to suffix currency facts; 41 focused and 129 full tests passed; changed-file Ruff and diff check passed; no secrets or source inputs accessed)
