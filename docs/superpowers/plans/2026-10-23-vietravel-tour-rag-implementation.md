# Vietravel Tour Sales RAG Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and deploy a cited, multi-turn Vietravel tour assistant over four supplied PDFs, with section-aware semantic chunking, DeepSeek generation, Chroma retrieval, guardrails, and Ragas evaluation.

**Architecture:** Offline ingestion produces reviewed JSONL artifacts and two persistent Chroma collections: a catalog for tour resolution/direct full-itinerary lookup and a factual knowledge collection. A LangGraph request flow performs LLM query understanding, tour resolution, scoped retrieval, evidence assessment, guarded generation, and deterministic citation/numeric validation before Streamlit renders the answer.

**Tech Stack:** Python 3.11+, PyMuPDF, openpyxl, Pydantic, LangChain, LangGraph, `langchain-openai`, `langchain-google-genai`, Chroma, Gemini embeddings, DeepSeek OpenAI-compatible chat API, Streamlit, pytest, Ragas.

## Global Constraints

- Implementation budget is approximately 8 hours; complete P0 tasks before optional polish.
- Use `deepseek-flash` through `DEEPSEEK_BASE_URL=https://api.deepseek.com` for chat-model calls.
- Use Google `gemini-embedding-001` with `GEMINI_API_KEY` and 768 output dimensions. Embed corpus records as `RETRIEVAL_DOCUMENT`, queries as `RETRIEVAL_QUERY`, and L2-normalize each 768-value vector before it reaches Chroma.
- Only tour PDFs with `authority="official_tour_pdf"` may ground factual answers.
- The sales XLSX is communication guidance only and must never enter `tour_knowledge`.
- Do not ingest the assignment DOCX into either Chroma collection.
- Do not implement booking, cancellation, payment, availability checking, passport collection, or other external side effects.
- Preserve repeated policies per tour and preserve the known Đà Nẵng baggage contradiction.
- A price table and its footnotes are one atomic chunk; a cancellation condition and its fee must remain together.
- `full_itinerary` is assembled deterministically and fetched by exact metadata, never by normal similarity search.
- Citation IDs must be drawn only from retrieved and approved PDF chunks.
- API secrets must remain in `.env` or Streamlit Secrets and must never be committed.
- Treat `/raw_data` and `/reference` inputs as immutable source material.

---

## File Map

```text
vietravel/
├── app.py                              # Streamlit entry point
├── pyproject.toml                      # Runtime and development dependencies
├── .env.example                       # Secret names without values
├── .gitignore                         # Secrets, caches, local Chroma exclusions
├── README.md                           # Setup, architecture, demo, limitations
├── raw_data/                           # Existing immutable tour PDFs
├── reference/                          # Existing immutable assignment/XLSX files
├── data/
│   ├── processed/                      # Reviewed ingestion artifacts
│   └── eval/eval_cases.jsonl           # At least 30 evaluation cases
├── chroma_db/                          # Persisted local collections; deployment policy in README
├── scripts/
│   ├── ingest.py                       # Build JSONL artifacts and Chroma
│   ├── audit_chunks.py                 # Validate/report chunk invariants
│   └── evaluate.py                     # Run Ragas and deterministic metrics
├── src/vietravel_rag/
│   ├── config.py                       # Environment settings and source paths
│   ├── models.py                       # Shared Pydantic/domain contracts
│   ├── llm.py                          # DeepSeek and Gemini embedding factories
│   ├── ingestion/
│   │   ├── sources.py                  # Four explicit tour manifests and aliases
│   │   ├── pdf_extract.py              # Page-preserving PDF extraction/cleanup
│   │   ├── chunker.py                  # Data-specific semantic segmentation
│   │   ├── aggregates.py               # Tour summary/full-itinerary assembly
│   │   ├── sales_guidance.py           # XLSX-to-reviewed-guidance conversion
│   │   └── validation.py               # Chunk quality checks and reports
│   ├── retrieval/
│   │   ├── index.py                    # Chroma build/load operations
│   │   ├── resolver.py                 # Tour candidate resolution
│   │   └── retriever.py                # Scoped factual retrieval/direct lookup
│   ├── agent/
│   │   ├── prompts.py                  # Query/evidence/answer prompts
│   │   ├── nodes.py                    # LangGraph node implementations
│   │   └── graph.py                    # Graph wiring and session entry point
│   ├── guardrails/
│   │   ├── input_guard.py              # Length, injection, and PII checks
│   │   └── output_guard.py             # Citation, numeric, and prohibited-claim checks
│   └── evaluation/
│       └── metrics.py                  # Deterministic eval metrics and latency/cost summaries
└── tests/
    ├── ingestion/
    ├── retrieval/
    ├── agent/
    ├── guardrails/
    └── evaluation/
```

## Priority and Time Box

| Window | Deliverable | Priority |
|---|---|---|
| 0:00–0:40 | Project scaffold, contracts, configuration | P0 |
| 0:40–2:40 | Real-data extraction, chunking, review artifacts | P0 |
| 2:40–3:30 | Chroma indexing, tour resolver, retrieval | P0 |
| 3:30–5:15 | LangGraph, DeepSeek prompts, guardrails | P0 |
| 5:15–6:00 | Streamlit multi-turn demo | P0 |
| 6:00–7:10 | Evaluation set, Ragas/custom metrics | P0 |
| 7:10–8:00 | Deployment, README, rehearsal, fixes | P0 |

If time slips, keep the five required demo scenarios and deterministic safety metrics; reduce UI polish before reducing chunk review or guardrails.

---

### Task 1: Project Scaffold, Configuration, and Shared Contracts

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `src/vietravel_rag/__init__.py`
- Create: `src/vietravel_rag/config.py`
- Create: `src/vietravel_rag/models.py`
- Test: `tests/test_config.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Produces: `Settings`, `PageText`, `TourSource`, `ChunkRecord`, `CatalogRecord`, `QueryAnalysis`, `EvidenceAssessment`, `TourAnswer`, and `AgentState`.
- Consumes: no application interfaces; reads environment variables only through `Settings`.

- [ ] **Step 1: Verify the isolated implementation branch**

Run: `git rev-parse --is-inside-work-tree`<br>
Expected: `true`.

Run: `git branch --show-current`<br>
Expected: `codex/vietravel-rag`. Do not add or modify files under `raw_data/` or `reference/`.

- [ ] **Step 2: Create the package definition and secret exclusions**

Use this dependency set in `pyproject.toml`:

```toml
[project]
name = "vietravel-tour-rag"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "chromadb",
  "langchain",
  "langchain-chroma",
  "langchain-openai",
  "langchain-google-genai>=4.0.0",
  "langgraph",
  "openpyxl",
  "pydantic>=2",
  "pydantic-settings",
  "pymupdf",
  "ragas",
  "streamlit",
  "tiktoken",
]

[project.optional-dependencies]
dev = ["pytest", "pytest-cov", "ruff"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
```

`.env.example` must contain names only:

```text
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-flash
GEMINI_API_KEY=
EMBEDDING_MODEL=gemini-embedding-001
EMBEDDING_OUTPUT_DIMENSIONALITY=768
CHROMA_PERSIST_DIR=chroma_db
```

Ignore `.env`, `.streamlit/secrets.toml`, `chroma_db/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, and local evaluation result files.

- [ ] **Step 3: Write failing settings and model tests**

```python
def test_settings_defaults(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-test")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test")
    settings = Settings()
    assert settings.llm_model == "deepseek-flash"
    assert settings.embedding_model == "gemini-embedding-001"
    assert settings.embedding_output_dimensionality == 768

def test_query_analysis_accepts_follow_up_rewrite():
    value = QueryAnalysis(
        intent="child_price",
        tour_references=["Bangkok – Pattaya"],
        standalone_query="Giá trẻ em 8 tuổi của tour Bangkok – Pattaya là bao nhiêu?",
    )
    assert value.intent == "child_price"

def test_tour_answer_rejects_unknown_status():
    with pytest.raises(ValidationError):
        TourAnswer(status="maybe", answer="", citation_ids=[], conflicts=[])
```

- [ ] **Step 4: Run the tests and confirm they fail**

Run: `python -m pytest tests/test_config.py tests/test_models.py -v`<br>
Expected: import errors because the contracts do not exist.

- [ ] **Step 5: Implement settings and contracts**

Use `BaseSettings` with the exact defaults from `.env.example`. Define intents and statuses as `Literal` values from the approved spec. Required record fields:

```python
class PageText(BaseModel):
    page_number: int
    text: str

class TourSource(BaseModel):
    tour_code: str
    tour_name: str
    source_file: str
    aliases: list[str]

class ChunkRecord(BaseModel):
    chunk_id: str
    tour_code: str
    tour_name: str
    document_type: Literal["knowledge"] = "knowledge"
    section_type: str
    section_title: str
    page_start: int
    page_end: int
    parent_section_id: str | None = None
    chunk_index: int = 0
    source_file: str
    authority: Literal["official_tour_pdf"] = "official_tour_pdf"
    content: str
    embedding_text: str

class CatalogRecord(BaseModel):
    record_id: str
    tour_code: str
    tour_name: str
    document_type: Literal["tour_summary", "full_itinerary"]
    content: str
    embedding_text: str
    source_chunk_ids: list[str]

class EvidenceAssessment(BaseModel):
    status: Literal["sufficient", "conflict", "insufficient", "realtime_required", "high_risk"]
    approved_chunk_ids: list[str]
    reason: str
```

Define `TourAnswer.follow_up` as optional with a default of `None`. Define `AgentState` as `TypedDict(total=False)` using the fields in the design spec.

- [ ] **Step 6: Run contract tests and static checks**

Run: `python -m pytest tests/test_config.py tests/test_models.py -v`<br>
Expected: all tests pass.

Run: `ruff check src/vietravel_rag/config.py src/vietravel_rag/models.py tests/test_config.py tests/test_models.py`<br>
Expected: no violations.

- [ ] **Step 7: Commit the scaffold**

```bash
git add pyproject.toml .env.example .gitignore src tests/test_config.py tests/test_models.py
git commit -m "chore: scaffold Vietravel RAG contracts"
```

---

### Task 2: Page-Preserving Extraction and Section-Aware Semantic Chunking

**Files:**
- Create: `src/vietravel_rag/ingestion/__init__.py`
- Create: `src/vietravel_rag/ingestion/sources.py`
- Create: `src/vietravel_rag/ingestion/pdf_extract.py`
- Create: `src/vietravel_rag/ingestion/chunker.py`
- Create: `src/vietravel_rag/ingestion/aggregates.py`
- Create: `src/vietravel_rag/ingestion/sales_guidance.py`
- Create: `src/vietravel_rag/ingestion/validation.py`
- Create: `scripts/ingest.py`
- Create: `scripts/audit_chunks.py`
- Generate: `data/processed/tour_chunks.jsonl`
- Generate: `data/processed/tour_catalog.jsonl`
- Generate: `data/processed/sales_guidance.json`
- Generate: `data/processed/conflicts.json`
- Generate: `data/processed/chunking_report.json`
- Test: `tests/ingestion/test_pdf_extract.py`
- Test: `tests/ingestion/test_chunker.py`
- Test: `tests/ingestion/test_validation.py`

**Interfaces:**
- Consumes: `PageText`, `TourSource`, `ChunkRecord`, and `CatalogRecord` from Task 1.
- Produces: `extract_pdf_pages(path: Path) -> list[PageText]`, `chunk_tour(source: TourSource, pages: list[PageText]) -> list[ChunkRecord]`, `build_catalog(source: TourSource, chunks: list[ChunkRecord]) -> list[CatalogRecord]`, and `validate_corpus(chunks, catalog) -> dict`.

- [ ] **Step 1: Encode the four immutable source manifests**

Create four explicit `TourSource` entries with stable internal codes:

```python
TOUR_SOURCES = (
    TourSource(
        tour_code="danang-central-5d4n",
        tour_name="Đà Nẵng – Hội An – Huế – Phong Nha",
        source_file="Đà Nẵng - Sơn Trà - KDL Bà Nà - Cầu Vàng - Hội An - La Vang - Động Phong Nha & Thiên Đường - Huế (Khách sạn 4_ trọn tour).pdf",
        aliases=["đà nẵng", "hội an", "huế", "bà nà", "phong nha"],
    ),
    TourSource(
        tour_code="mekong-my-tho-ben-tre-can-tho",
        tour_name="Miền Tây – Mỹ Tho – Bến Tre – Cần Thơ",
        source_file="Miền Tây_ Mỹ Tho - Bến Tre - Cần Thơ - Trải Nghiệm Tuyến Cao Tốc Mới Nhất Của Miền Tây.pdf",
        aliases=["miền tây", "mỹ tho", "bến tre", "cần thơ"],
    ),
    TourSource(
        tour_code="thailand-bangkok-pattaya",
        tour_name="Thái Lan – Bangkok – Pattaya",
        source_file="Thái Lan_ Bangkok - Pattaya (Tham quan Hoàng Cung, chùa Phật Ngọc, Vườn lan Nong Nooch, Đảo San Hô, Tặng Buffet Baiyoke Sky + vé xem Show Alcazar).pdf",
        aliases=["thái lan", "bangkok", "pattaya"],
    ),
    TourSource(
        tour_code="china-lijiang-dali-shangrila",
        tour_name="Trung Quốc – Lệ Giang – Đại Lý – Shangrila",
        source_file="Trung Quốc_ Lệ Giang - Đại Lý - Shangrila - Núi tuyết Ngọc Long - Lam Nguyệt Đàm - Hẻm núi Hổ Khiêu Hiệp - Tặng vé cáp treo lớn lên đỉnh Núi tuyết Ngọc Long _ 28 Tết.pdf",
        aliases=["trung quốc", "lệ giang", "đại lý", "shangrila", "núi tuyết ngọc long"],
    ),
)
```

Use the exact existing PDF filenames and keep `raw_data/` read-only. Store aliases in the catalog record, serialized for Chroma metadata when indexing.

- [ ] **Step 2: Write failing extraction and chunk invariant tests**

Tests must assert:

```python
def test_extraction_preserves_page_numbers(danang_pdf):
    pages = extract_pdf_pages(danang_pdf)
    assert pages[0].page_number == 1
    assert "8,990,000" in pages[0].text

def test_price_table_is_atomic(danang_chunks):
    price_chunks = [c for c in danang_chunks if c.section_type == "price"]
    assert len(price_chunks) == 1
    assert "Người lớn" in price_chunks[0].content
    assert "Trẻ em" in price_chunks[0].content

def test_itinerary_is_one_ordered_chunk_per_day(danang_chunks):
    days = [c for c in danang_chunks if c.section_type == "itinerary"]
    assert [c.chunk_index for c in days] == list(range(1, len(days) + 1))

def test_baggage_conflict_survives_chunking(danang_chunks):
    text = "\n".join(c.content for c in danang_chunks)
    assert "23kg" in text and "10kg" in text
    assert "20kg" in text and "7kg" in text

def test_chunk_provenance_matches_its_tour_source(all_chunks, source_by_code):
    assert all(
        c.source_file == source_by_code[c.tour_code].source_file
        and c.tour_name == source_by_code[c.tour_code].tour_name
        for c in all_chunks
    )
```

- [ ] **Step 3: Run ingestion tests and confirm they fail**

Run: `python -m pytest tests/ingestion/test_pdf_extract.py tests/ingestion/test_chunker.py -v`<br>
Expected: import errors or assertion failures before implementation.

- [ ] **Step 4: Implement PDF extraction and conservative cleanup**

Use PyMuPDF page-by-page. Normalize Unicode and whitespace without losing bullet boundaries. Remove only:

- confirmed repeated headers/footers occurring on multiple pages;
- standalone page numbers;
- “Xem chương trình tour” UI text;
- exact duplicated extraction spans.

Do not perform fuzzy or semantic deduplication. Retain original page number on every line/span used to construct a chunk.

- [ ] **Step 5: Implement data-specific section and semantic segmentation**

Recognize these heading families case-insensitively:

```python
SECTION_HEADINGS = {
    "included": ("giá tour bao gồm",),
    "excluded": ("giá tour không bao gồm",),
    "child_price": ("giá vé trẻ em",),
    "payment": ("điều kiện thanh toán",),
    "cancellation_standard": ("các điều kiện hủy tour đối với ngày thường",),
    "cancellation_holiday": ("các điều kiện hủy tour đối với ngày lễ",),
    "force_majeure": ("trường hợp bất khả kháng",),
}
```

Recognize itinerary headings with `^Ngày\s+\d+\s*:`. Keep one day per chunk unless the source itself has clear morning/afternoon/evening subsections and the day triggers the oversized warning. Keep price tables and their immediately following footnotes atomic. Never merge `included` and `excluded`.

Create `embedding_text` from the tour name/code, section title, and clean content. Create stable chunk IDs from `tour_code`, normalized section type, and index; do not hash source text into the public ID.

- [ ] **Step 6: Implement deterministic aggregate creation**

`build_catalog` must create exactly two records per tour:

1. `tour_summary`: route/title, duration when unambiguous, and ordered itinerary day titles.
2. `full_itinerary`: `"\n\n".join(day.content for day in sorted_days)`.

Set `source_chunk_ids` to the exact ordered day chunk IDs for the full itinerary. Assert every itinerary chunk appears exactly once.

- [ ] **Step 7: Convert sales guidance without factual indexing**

Read the XLSX with `openpyxl` and emit JSON objects containing:

```json
{
  "scenario_id": 17,
  "intent": "baggage",
  "response_structure": "Ask which tour; explain baggage depends on the tour document.",
  "required_action": "Ask for the tour of interest.",
  "prohibited_actions": ["Do not state a fixed allowance without tour evidence."]
}
```

Do not copy spreadsheet prices, dates, discounts, availability statements, or policy percentages into the runtime guidance object.

- [ ] **Step 8: Create the minimal curated conflict record**

Write one runtime conflict for the verified Đà Nẵng baggage mismatch, using the actual chunk IDs created by the ingestion run:

```json
{
  "tour_code": "danang-central-5d4n",
  "topic": "baggage",
  "claims": [
    {"text": "23kg ký gửi, 10kg xách tay", "page": 3, "chunk_id": "danang-central-5d4n_included_01"},
    {"text": "20kg ký gửi, dưới 7kg xách tay", "page": 4, "chunk_id": "danang-central-5d4n_registration_notes_01"}
  ],
  "resolution": "require_human_confirmation"
}
```

The ingestion test must assert that these two stable IDs exist before writing the conflict file; if section detection changes an ID, update the record and its test in the same commit.

- [ ] **Step 9: Implement and run corpus validation**

Validation fails with a non-zero exit code when:

- any factual chunk lacks tour, page, section, source, or authority metadata;
- any chunk contains content from two configured tour identities;
- a price table is split across records;
- itinerary indices are missing or duplicated;
- a full itinerary omits or duplicates a day chunk;
- spreadsheet content appears in `tour_chunks.jsonl`;
- an unclassified section remains;
- the two Đà Nẵng baggage claims are missing.

Run: `python scripts/ingest.py --build-artifacts`<br>
Expected: five files created under `data/processed/`.

Run: `python scripts/audit_chunks.py`<br>
Expected: `PASS`, zero unclassified sections, and a reviewed warning list for oversized semantic units.

- [ ] **Step 10: Manually review the generated corpus**

Inspect every chunk with `section_type` in `price`, `child_price`, `baggage`, `payment`, `cancellation_standard`, and `cancellation_holiday`. Confirm page labels against the PDFs. Record counts and removals in `chunking_report.json`; do not “fix” contradictory source facts.

- [ ] **Step 11: Run ingestion tests and commit reviewed artifacts**

Run: `python -m pytest tests/ingestion -v`<br>
Expected: all tests pass.

```bash
git add src/vietravel_rag/ingestion scripts/ingest.py scripts/audit_chunks.py tests/ingestion data/processed
git commit -m "feat: build reviewed semantic tour chunks"
```

---

### Task 3: Chroma Index, Tour Resolution, and Scoped Retrieval

**Files:**
- Create: `src/vietravel_rag/llm.py`
- Create: `src/vietravel_rag/retrieval/__init__.py`
- Create: `src/vietravel_rag/retrieval/index.py`
- Create: `src/vietravel_rag/retrieval/resolver.py`
- Create: `src/vietravel_rag/retrieval/retriever.py`
- Modify: `scripts/ingest.py`
- Test: `tests/retrieval/test_index.py`
- Test: `tests/retrieval/test_resolver.py`
- Test: `tests/retrieval/test_retriever.py`

**Interfaces:**
- Consumes: reviewed JSONL artifacts from Task 2 and `Settings` from Task 1.
- Produces: `get_chat_model()`, `get_embeddings()`, `build_collections()`, `resolve_tours()`, `retrieve_evidence()`, and `get_full_itinerary()`.

- [ ] **Step 1: Write failing retrieval tests with fake embeddings**

Required behaviors:

```python
def test_catalog_search_excludes_full_itinerary(catalog_store):
    matches = resolve_tours("tour Bà Nà", catalog_store, limit=3)
    assert all(m.document_type == "tour_summary" for m in matches)

def test_evidence_is_scoped_to_resolved_tour(knowledge_store):
    docs = retrieve_evidence("hành lý bao nhiêu kg", ["danang-central-5d4n"], knowledge_store)
    assert docs and {d.metadata["tour_code"] for d in docs} == {"danang-central-5d4n"}

def test_full_itinerary_uses_exact_lookup(catalog_store):
    doc = get_full_itinerary("thailand-bangkok-pattaya", catalog_store)
    assert doc.metadata["document_type"] == "full_itinerary"
```

Use a deterministic fake embedding class in tests; unit tests must not call paid APIs.

- [ ] **Step 2: Run retrieval tests and verify failure**

Run: `python -m pytest tests/retrieval -v`<br>
Expected: import errors before implementation.

- [ ] **Step 3: Implement model factories**

Instantiate DeepSeek through `ChatOpenAI(model=settings.llm_model, api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url, temperature=0)`. Instantiate `GoogleGenerativeAIEmbeddings(model=settings.embedding_model, google_api_key=settings.gemini_api_key, output_dimensionality=settings.embedding_output_dimensionality)`. At call time, use `RETRIEVAL_DOCUMENT` for documents and `RETRIEVAL_QUERY` for queries, then L2-normalize all vectors because `gemini-embedding-001` requires manual normalization below 3072 dimensions. Keep factories dependency-injectable so tests can pass fakes.

- [ ] **Step 4: Build the two Chroma collections**

Create:

- `tour_catalog` from `tour_catalog.jsonl`;
- `tour_knowledge` from `tour_chunks.jsonl`.

Store `embedding_text` as the embedded page content while keeping clean `content` and citation fields in metadata. Rebuilding must delete and recreate only these two named collections inside the configured persist directory.

- [ ] **Step 5: Implement tour resolution and ambiguity threshold**

`resolve_tours(query, store, limit=3)` searches only `document_type="tour_summary"`. Return a resolved candidate when the top match is clearly above the configured relevance floor and separated from the second candidate; otherwise return the candidate list for clarification. Exact tour code assignment remains backend-owned rather than LLM-owned.

Include explicit tests for:

- “tour Bà Nà” → Đà Nẵng tour;
- “Bangkok” → Thailand tour;
- “tour miền Trung” → clarification if more than one candidate is plausible;
- an unsupported Japan tour → not found.

- [ ] **Step 6: Implement scoped factual retrieval and aggregate lookup**

`retrieve_evidence` must query by `standalone_query`, filter by resolved `tour_code`, return six chunks by default, and return ten for comparisons. Do not hard-filter by section type. `get_full_itinerary` uses exact metadata lookup and raises a typed error if zero or multiple records are found.

- [ ] **Step 7: Build the real local index and smoke-test it**

Run: `python scripts/ingest.py --build-index`<br>
Expected: both Chroma collections populated with counts matching processed artifacts.

Run a small smoke command that resolves “Tour Bà Nà có gì?” and prints only chunk IDs/titles, not secrets. Expected: the Đà Nẵng tour and itinerary evidence.

- [ ] **Step 8: Run tests and commit**

Run: `python -m pytest tests/retrieval -v`<br>
Expected: all tests pass without network access.

```bash
git add src/vietravel_rag/llm.py src/vietravel_rag/retrieval scripts/ingest.py tests/retrieval
git commit -m "feat: add scoped Chroma retrieval"
```

---

### Task 4: LLM Query Understanding and Multi-Turn Routing

**Files:**
- Create: `src/vietravel_rag/agent/__init__.py`
- Create: `src/vietravel_rag/agent/prompts.py`
- Create: `src/vietravel_rag/agent/nodes.py`
- Test: `tests/agent/test_query_analysis.py`
- Test: `tests/agent/test_routing.py`

**Interfaces:**
- Consumes: `QueryAnalysis`, `AgentState`, `resolve_tours()`, `retrieve_evidence()`, and `get_full_itinerary()`.
- Produces: `analyze_query(state, model)`, `resolve_tour_node(state, resolver)`, and `retrieve_node(state, retriever)`.

- [x] **Step 1: Write failing structured-output tests**

Use a fake structured model and assert:

```python
def test_follow_up_inherits_active_tour():
    state = {
        "messages": [human("Tour Thái Lan giá bao nhiêu?"), ai("Mình sẽ kiểm tra theo tài liệu tour."), human("Bé 8 tuổi thì sao?")],
        "active_tour_codes": ["thailand-bangkok-pattaya"],
    }
    result = analyze_query(state, fake_model)
    assert result["query_analysis"].intent == "child_price"
    assert "Bangkok" in result["query_analysis"].standalone_query

def test_pronoun_with_two_active_tours_requires_clarification():
    state = {"messages": [human("Tour đó bao nhiêu?")], "active_tour_codes": ["a", "b"]}
    result = resolve_tour_node(state, fake_resolver)
    assert result["route"] == "clarification"
```

- [x] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests/agent/test_query_analysis.py tests/agent/test_routing.py -v`<br>
Expected: missing node implementations.

- [x] **Step 3: Implement the query-understanding prompt**

The prompt must:

- use only the current message, recent messages, and active tours;
- choose one approved intent;
- preserve explicitly mentioned tour names/destinations in `tour_references`;
- rewrite follow-ups into a self-contained Vietnamese `standalone_query`;
- return an empty reference list when no tour can be inferred;
- avoid assigning tour codes or answering the question.

Call `model.with_structured_output(QueryAnalysis)` and use temperature zero.

- [x] **Step 4: Implement resolver and retrieval nodes**

Resolver behavior:

- `off_topic` routes to safe response without retrieval;
- no tour needed for a truly general question routes without a forced tour;
- one confident candidate updates `active_tour_codes`;
- multiple candidates or unresolved pronouns route to clarification;
- unsupported tour references route to unsupported response.

Retriever behavior:

- retrieve six factual chunks, ten for comparisons;
- always include the resolved tour summary;
- add exact `full_itinerary` only for `itinerary`, `recommend_tour`, or an explicit complete-program request;
- for “next/previous day”, add the adjacent itinerary chunk using `last_citation_ids` and `chunk_index`.

- [x] **Step 5: Run routing tests and commit**

Run: `python -m pytest tests/agent/test_query_analysis.py tests/agent/test_routing.py -v`<br>
Expected: all tests pass.

```bash
git add src/vietravel_rag/agent tests/agent/test_query_analysis.py tests/agent/test_routing.py
git commit -m "feat: add multi-turn query routing"
```

---

### Task 5: Evidence Assessment, Guardrails, Answer Generation, and LangGraph

**Files:**
- Create: `src/vietravel_rag/guardrails/__init__.py`
- Create: `src/vietravel_rag/guardrails/input_guard.py`
- Create: `src/vietravel_rag/guardrails/output_guard.py`
- Modify: `src/vietravel_rag/agent/prompts.py`
- Modify: `src/vietravel_rag/agent/nodes.py`
- Create: `src/vietravel_rag/agent/graph.py`
- Test: `tests/guardrails/test_input_guard.py`
- Test: `tests/guardrails/test_output_guard.py`
- Test: `tests/agent/test_graph.py`

**Interfaces:**
- Consumes: retrieved chunks, `conflicts.json`, sales guidance, `EvidenceAssessment`, and `TourAnswer`.
- Produces: `build_graph(deps) -> CompiledStateGraph`, `validate_input(text)`, `assess_evidence(state, model)`, `generate_answer(state, model)`, and `validate_answer(answer, approved_chunks)`.

- [ ] **Step 1: Write failing guardrail tests**

Cover these exact outcomes:

```python
def test_unknown_citation_is_rejected():
    answer = TourAnswer(status="answered", answer="Giá tour có trong tài liệu.", citation_ids=["invented"], conflicts=[])
    result = validate_answer(answer, approved_chunks=[chunk("real")])
    assert result.status == "unsupported"

def test_unsupported_number_is_rejected():
    answer = TourAnswer(status="answered", answer="Giá là 7.000.000đ", citation_ids=["price-1"], conflicts=[])
    result = validate_answer(answer, approved_chunks=[chunk("price-1", "Giá 8.990.000đ")])
    assert result.status == "unsupported"

def test_known_baggage_conflict_routes_to_conflict():
    state = danang_baggage_state()
    result = conflict_guard(state, conflicts_fixture)
    assert result["evidence_status"] == "conflict"
```

Also test refusal to expose bank details, guarantee visa approval, claim live availability, give medical advice, or claim a cancellation was executed.

- [ ] **Step 2: Run guardrail tests and verify failure**

Run: `python -m pytest tests/guardrails -v`<br>
Expected: import errors or failed assertions.

- [ ] **Step 3: Implement input and conflict guards**

Input guard rules:

- empty/whitespace → clarification response;
- more than 2,000 characters → ask for a shorter question;
- obvious instructions to ignore sources/system rules → safe refusal;
- redact email addresses, Vietnamese phone numbers, and long digit sequences before logs.

Conflict guard loads `conflicts.json` once and matches exact `tour_code + intent/topic`. The baggage record bypasses free-form evidence selection and forces the two stored claim chunks into approved evidence.

- [ ] **Step 4: Implement evidence-assessment prompt**

Use structured output `EvidenceAssessment`. Require the model to select only chunk IDs supplied in the prompt. Explicitly distinguish:

- `sufficient`: answer fully grounded;
- `conflict`: sources disagree;
- `insufficient`: supplied material cannot answer;
- `realtime_required`: availability, current price/promotion, live weather, or current external rule;
- `high_risk`: medical, immigration, payment, cancellation execution, or complaint requiring staff.

- [ ] **Step 5: Implement answer-generation prompt**

The prompt receives approved chunks, optional tour summary/full itinerary, relevant sales guidance, and evidence status. Require concise Vietnamese, no unsupported facts, one useful follow-up question at most, and structured `TourAnswer` output. Conflict answers must state both source claims and recommend confirming with Vietravel.

- [ ] **Step 6: Implement deterministic output validation**

Validation sequence:

1. Ensure every citation ID is in approved evidence.
2. Extract numbers with units/currency/percent/date patterns from the answer.
3. Normalize separators and confirm each factual number occurs in approved content.
4. Scan prohibited claim patterns for guaranteed visa, confirmed availability, account numbers, guaranteed refund/compensation, medical directives, or completed operations.
5. On failure, return a fixed `unsupported`/`escalate` answer with no invented replacement facts.

Do not make a second generation call after validation failure.

- [ ] **Step 7: Wire the LangGraph**

Create nodes in this order:

```text
START -> input_guard -> query_analysis -> tour_resolver
tour_resolver -> clarification | safe_response | retrieval
retrieval -> conflict_guard -> evidence_assessment
evidence_assessment -> response_generation -> output_guard -> END
```

Use a per-Streamlit-session in-memory checkpointer keyed by session ID. Cap prompt history at the most recent 10 messages.

- [ ] **Step 8: Add end-to-end graph tests**

With fake LLM and fake stores, cover:

- cited price answer;
- child-price follow-up;
- ambiguous “tour đó” clarification;
- Đà Nẵng baggage conflict with two citations;
- live availability request routed to `realtime_required`;
- prompt injection routed to safe refusal.

- [ ] **Step 9: Run tests and commit**

Run: `python -m pytest tests/guardrails tests/agent/test_graph.py -v`<br>
Expected: all tests pass.

```bash
git add src/vietravel_rag/guardrails src/vietravel_rag/agent tests/guardrails tests/agent/test_graph.py
git commit -m "feat: add guarded LangGraph answer flow"
```

---

### Task 6: Streamlit Multi-Turn Demo

**Files:**
- Create: `app.py`
- Create: `.streamlit/config.toml`
- Test: `tests/test_app_helpers.py`

**Interfaces:**
- Consumes: `build_graph()`, `TourAnswer`, and retrieved citation metadata.
- Produces: runnable Streamlit chat application and pure helper functions `render_citation_label(metadata)` and `build_session_config(session_id)`.

- [ ] **Step 1: Write failing UI-helper tests**

```python
def test_citation_label_contains_tour_section_and_page():
    label = render_citation_label({
        "tour_name": "Bangkok – Pattaya",
        "section_title": "Giá trẻ em",
        "page_start": 4,
        "page_end": 4,
    })
    assert label == "Bangkok – Pattaya · Giá trẻ em · Trang 4"
```

Also test a multi-page label such as `Trang 5–6` and stable session-thread configuration.

- [ ] **Step 2: Run helper tests and verify failure**

Run: `python -m pytest tests/test_app_helpers.py -v`<br>
Expected: helpers do not exist.

- [ ] **Step 3: Implement the chat UI**

The page must include:

- title and one-sentence data limitation;
- suggested prompts for itinerary, child price, and baggage;
- `st.chat_message` history;
- answer status, text, rendered citation buttons/labels;
- an expander showing clean source chunk text and similarity/debug metadata;
- a reset button clearing messages, active tours, and last citations;
- a visible note that availability and booking require staff confirmation.

Create graph/resources with `st.cache_resource`. Keep conversation state in `st.session_state` and pass one stable session ID as the LangGraph thread ID.

- [ ] **Step 4: Run UI tests and launch locally**

Run: `python -m pytest tests/test_app_helpers.py -v`<br>
Expected: all tests pass.

Run: `streamlit run app.py`<br>
Manually verify the five demo scenarios from the spec and save the exact prompts in README notes.

- [ ] **Step 5: Commit the UI**

```bash
git add app.py .streamlit/config.toml tests/test_app_helpers.py
git commit -m "feat: add Streamlit multi-turn demo"
```

---

### Task 7: Evaluation Dataset, Ragas, and Safety Metrics

**Files:**
- Create: `data/eval/eval_cases.jsonl`
- Create: `src/vietravel_rag/evaluation/__init__.py`
- Create: `src/vietravel_rag/evaluation/metrics.py`
- Create: `scripts/evaluate.py`
- Test: `tests/evaluation/test_metrics.py`

**Interfaces:**
- Consumes: compiled graph output and reference cases.
- Produces: `results/eval_results.json`, `results/eval_summary.json`, and metric functions for citation validity, route correctness, numeric grounding, safety, latency, and cost.

- [ ] **Step 1: Create at least 30 reviewed eval cases**

Use JSONL records with:

```json
{
  "case_id": "conflict_baggage_danang",
  "turns": ["Tour Đà Nẵng được mang bao nhiêu kg hành lý?"],
  "expected_intent": "baggage",
  "expected_tour_codes": ["danang-central-5d4n"],
  "expected_status": "conflict",
  "reference": "Tài liệu nêu hai tiêu chuẩn hành lý khác nhau và cần Vietravel xác nhận.",
  "reference_context_ids": ["danang-central-5d4n_included_01", "danang-central-5d4n_registration_notes_01"],
  "must_not_contain": ["tôi đã xác nhận", "chắc chắn"]
}
```

Replace the example IDs with real reviewed chunk IDs. Distribution:

- 10 normal factual cases;
- 5 itinerary/recommendation/comparison cases;
- 5 multi-turn or ambiguous-reference cases;
- 4 insufficient/conflicting cases;
- 3 real-time/high-risk cases;
- 3 injection/out-of-scope cases.

- [ ] **Step 2: Write failing deterministic metric tests**

```python
def test_citation_validity():
    assert citation_validity(["a"], retrieved_ids={"a", "b"}) == 1.0
    assert citation_validity(["x"], retrieved_ids={"a", "b"}) == 0.0

def test_percentile_summary():
    summary = latency_summary([100, 200, 300, 400, 500])
    assert summary["p50_ms"] == 300
    assert summary["p95_ms"] >= 400
```

Also test route/status accuracy, forbidden-claim rate, and numeric-grounding rate.

- [ ] **Step 3: Run metric tests and verify failure**

Run: `python -m pytest tests/evaluation -v`<br>
Expected: missing metric implementations.

- [ ] **Step 4: Implement deterministic metrics**

Calculate:

- intent accuracy;
- tour-resolution exact match;
- answer status accuracy;
- citation validity;
- clarification/conflict/safe-refusal accuracy;
- numeric grounding rate;
- forbidden-claim rate;
- latency p50/p95;
- observed token cost and estimated cost per 1,000 questions using configured per-token prices supplied to the evaluation command.

Use conservative peak, cache-miss DeepSeek Flash rates for the initial report: USD 0.30 per million input tokens and USD 1.20 per million output tokens, verified on 2026-10-23 from `https://api-docs.deepseek.com/quick_start/pricing/`. Require CLI arguments `--input-price-per-million` and `--output-price-per-million`, and store the supplied values, source URL, and report timestamp so later runs can update pricing without code changes.

- [ ] **Step 5: Implement the Ragas adapter**

Map each completed case to the current collections-style fields:

- `user_input`;
- `retrieved_contexts`;
- `reference_contexts` when available;
- `retrieved_context_ids`;
- `response`;
- `reference`.

Evaluate Context Precision, Context Recall, Faithfulness, Response Relevancy, and Answer Correctness where references exist. Configure DeepSeek as judge for the deadline and write `judge_model_self_evaluation=true` in the summary limitations.

- [ ] **Step 6: Run unit tests and the evaluation**

Run: `python -m pytest tests/evaluation -v`<br>
Expected: all tests pass.

Run:

```bash
python scripts/evaluate.py \
  --dataset data/eval/eval_cases.jsonl \
  --input-price-per-million 0.30 \
  --output-price-per-million 1.20
```

Before execution, verify the rates on the official pricing page and change the arguments only if the provider has updated them. Expected: both JSON result files, all 30+ cases executed, and failures listed by case ID.

- [ ] **Step 7: Review failures and commit**

Fix only clear ingestion, routing, or prompt defects. Do not tune prompts to copy reference answers. Record remaining errors by category in the README.

```bash
git add data/eval src/vietravel_rag/evaluation scripts/evaluate.py tests/evaluation
git commit -m "test: add RAG and safety evaluation"
```

---

### Task 8: Deployment, Documentation, and Final Verification

**Files:**
- Create: `README.md`
- Create: `.streamlit/secrets.toml.example`
- Modify: `.gitignore`
- Modify: `pyproject.toml` only if the clean deployment install exposes a missing declared dependency

**Interfaces:**
- Consumes: completed application, processed artifacts, test suite, and evaluation summary.
- Produces: reproducible local setup, Streamlit Cloud deployment instructions, demo script, limitations, and verified release candidate.

- [ ] **Step 1: Write README with exact operator flows**

Document:

1. problem and scope;
2. architecture diagram;
3. source-authority rules;
4. chunking strategy and artifact examples;
5. local environment and `pip install -e ".[dev]"`;
6. `python scripts/ingest.py --build-artifacts --build-index`;
7. `streamlit run app.py`;
8. evaluation command and metric definitions;
9. Streamlit Community Cloud secret configuration;
10. limitations: no live availability/actions, session-only memory, curated conflict list, DeepSeek self-judge bias, and API cost despite free hosting;
11. five-prompt interview demo sequence;
12. short error analysis based on actual evaluation output.

- [ ] **Step 2: Define deployment artifact policy**

Measure `chroma_db/`. If it is reasonably small for the repository, commit it and make app startup load-only. Otherwise exclude it and make startup build from committed `data/processed/*.jsonl`, guarded by `st.cache_resource`. Do not run PDF extraction on every app request.

- [ ] **Step 3: Run the complete local verification**

Run:

```bash
ruff check .
python -m pytest -v
python scripts/audit_chunks.py
python scripts/ingest.py --build-index
```

Expected:

- lint succeeds;
- all tests pass;
- chunk audit passes with zero unclassified sections;
- Chroma collection counts match processed artifact counts.

- [ ] **Step 4: Perform five-scenario manual acceptance**

Verify in Streamlit:

1. a factual price or inclusion answer cites the correct PDF page;
2. “Bé 8 tuổi thì sao?” inherits the prior Thailand tour;
3. an ambiguous “tour đó” asks which tour;
4. Đà Nẵng baggage reports both conflicting allowances with both citations;
5. “Tour này còn chỗ không?” states that live availability cannot be confirmed and requests staff confirmation.

Check the debug expander shows only retrieved chunks and contains no secrets.

- [ ] **Step 5: Deploy to Streamlit Community Cloud**

Configure the variables from `.env.example` in Streamlit Secrets, including the two sensitive API keys and the non-sensitive model/base-URL settings. Choose `app.py` as the entry point and deploy. Repeat the five-scenario acceptance test on the deployed URL. Do not paste keys into logs, screenshots, README, or evaluation artifacts.

- [ ] **Step 6: Final repository safety check**

Run:

```bash
git status --short
git diff --check
git grep -nE "(sk-|DEEPSEEK_API_KEY=.+|GEMINI_API_KEY=.+)" -- ':!*.example'
```

Expected: only intentional files are present, no whitespace errors, and no secret matches.

- [ ] **Step 7: Commit the release documentation**

```bash
git add README.md .streamlit/secrets.toml.example .gitignore pyproject.toml
git commit -m "docs: add deployment and demo guide"
```

---

## Final Definition of Done

- [ ] Four tour PDFs produce reviewed semantic chunks with correct page provenance.
- [ ] `tour_catalog` contains one summary and one exact-lookup full itinerary per tour.
- [ ] `tour_knowledge` contains PDF evidence only.
- [ ] Sales guidance cannot supply final factual claims.
- [ ] Multi-turn follow-ups retain the active tour and ambiguous references clarify.
- [ ] The known baggage conflict produces a conflict response rather than a guessed answer.
- [ ] Output validation rejects invented citations and unsupported numbers.
- [ ] Streamlit passes all five demo scenarios locally and after deployment.
- [ ] The 30+ case evaluation reports Ragas, task-specific safety metrics, p50/p95 latency, and estimated cost per 1,000 questions.
- [ ] README records limitations and the DeepSeek self-judge caveat.
- [ ] Full test suite, lint, chunk audit, and secret scan pass.
