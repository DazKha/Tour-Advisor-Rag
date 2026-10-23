# Vietravel Tour Sales RAG — Design Specification

**Date:** 2026-10-23<br>
**Status:** Approved<br>
**Target:** MVP take-home case study, implementation budget approximately 8 hours

## 1. Problem statement

Build a small, demonstrable RAG assistant that answers questions about the supplied Vietravel tours, including itinerary, price, inclusions, exclusions, baggage, payment, cancellation, visa-related notes, and suitability questions.

The assistant must:

- answer only from the supplied tour data;
- cite the tour, section, and PDF page used;
- support multi-turn follow-up questions;
- distinguish factual evidence from sales communication guidance;
- handle missing, ambiguous, conflicting, time-sensitive, and high-risk information safely;
- provide a minimal Streamlit UI suitable for a live interview demo;
- include an evaluation set and report retrieval, answer quality, safety, latency, and estimated cost.

## 2. Scope

### In scope

- Four supplied tour PDFs.
- One sales-scenario spreadsheet used as communication guidance.
- DeepSeek Flash for query understanding, evidence assessment, and answer generation.
- Google `gemini-embedding-001` for embeddings, using `GEMINI_API_KEY` and 768 output dimensions. Use `RETRIEVAL_DOCUMENT` for stored records and `RETRIEVAL_QUERY` for searches. L2-normalize all output vectors because Gemini Embedding 1 requires manual normalization when dimensions are below 3072.
- LangChain integrations, LangGraph orchestration, and persistent local Chroma.
- Streamlit chat UI with citations and a compact debug view.
- Multi-turn context and follow-up resolution within one Streamlit session.
- Ragas evaluation plus deterministic safety and routing metrics.
- Free application hosting on Streamlit Community Cloud; model API usage is external and may incur cost.

### Out of scope

- Real-time seat availability, booking, cancellation, payment, or CRM operations.
- Collecting passports, phone numbers, payment details, or other sensitive booking data.
- Crawling the Vietravel website or adding facts not present in supplied files.
- A general-purpose document ingestion platform.
- A fully automated fact-extraction or master-data system.
- Production authentication, persistence, monitoring, or horizontal scaling.

## 3. Source authority

Sources have distinct roles and must never be treated as interchangeable.

1. **Tour PDF — authoritative factual evidence**
   - Prices, itinerary, inclusions, exclusions, baggage, payment, cancellation, and tour-specific notes.
   - All factual answers require supporting PDF chunks.

2. **Sales spreadsheet — non-factual communication guidance**
   - Tone, suggested conversational structure, follow-up questions, escalation behavior, and prohibited actions.
   - It must not supply prices, dates, inclusions, policies, availability, or other factual claims.

3. **Assignment document — implementation requirements only**
   - It must not be indexed into the tour knowledge base.

Known source-quality issues must be preserved rather than silently resolved. For example, the Đà Nẵng PDF contains two incompatible baggage allowances, while several statements in the sales spreadsheet conflict with the corresponding PDF.

## 4. Architecture

```text
Offline ingestion
PDFs ──> extraction/cleanup ──> section-aware semantic chunks ──> Chroma
                                  ├── tour_catalog
                                  └── tour_knowledge

XLSX ──> reviewed sales rules ──> sales_guidance.json
Review ─────────────────────────> conflicts.json + chunking_report.json

Online request
User + recent messages
  -> Input Guard
  -> LLM Query Understanding
  -> Tour Resolver
       ├── ambiguous/not found -> Clarification
       ├── off-topic           -> Safe response
       └── resolved
  -> Chroma retrieval + optional full-itinerary direct lookup
  -> Evidence Assessment
       ├── sufficient
       ├── conflict
       ├── insufficient
       ├── realtime_required
       └── high_risk
  -> Response Generation
  -> Deterministic Output Guard
  -> Streamlit answer + citations
```

There is no separate LLM-generated `RetrievalPlan` in the MVP. Query understanding produces only the information needed for routing and follow-ups. Retrieval behavior is small, explicit, and testable.

## 5. Query understanding and conversation state

### Query analysis schema

```python
class QueryAnalysis(BaseModel):
    intent: Literal[
        "price",
        "child_price",
        "compare_tours",
        "recommend_tour",
        "itinerary",
        "included",
        "excluded",
        "baggage",
        "payment",
        "cancellation",
        "visa",
        "health",
        "availability",
        "complaint",
        "general",
        "off_topic",
    ]
    tour_references: list[str]
    standalone_query: str
```

DeepSeek performs this analysis using the current message and recent conversation. It does not select a final tour code, retrieve documents, judge evidence, or write the user-facing answer.

### LangGraph session state

```python
class AgentState(TypedDict):
    messages: list
    query_analysis: dict | None
    active_tour_codes: list[str]
    retrieved_chunks: list[dict]
    evidence_status: str | None
    last_intent: str | None
    last_citation_ids: list[str]
    response: dict | None
```

Keep only the most recent 6–10 messages. Session state may be lost when Streamlit restarts; this is an accepted MVP limitation.

Follow-up behavior:

- “Bé 8 tuổi thì sao?” inherits the active tour and rewrites to a self-contained child-price query.
- “So với miền Tây?” retains the current tour and adds the newly referenced tour.
- “Ngày tiếp theo thì sao?” may use the previous itinerary citation and adjacent `chunk_index`.
- “Tour đó” with more than one plausible active tour triggers clarification.

## 6. Chunking strategy

The selected strategy is **section-aware semantic chunking with aggregate documents**. A section is a hard boundary, but not necessarily one chunk. Chunk boundaries follow domain meaning rather than fixed token counts.

### 6.1 Processing pipeline

```text
Extract each PDF with page provenance
  -> normalize whitespace and bullets
  -> remove confirmed repeating headers/footers and extraction artifacts
  -> detect headings and tables
  -> segment sections into semantic units
  -> create tour summary and full-itinerary aggregates
  -> emit reviewable JSONL
  -> review high-risk chunks and known conflicts
  -> index approved records into Chroma
```

The coding agent must run this pipeline on the four real PDFs, inspect the generated output, and adjust extraction or section handling until the acceptance criteria pass. Delivering only a generic chunking function is insufficient.

### 6.2 Domain rules

| Content | Chunk rule |
|---|---|
| Tour summary | One short aggregate containing identity, duration, route, and other unambiguous headline data |
| Full itinerary | One aggregate assembled deterministically from ordered itinerary chunks; used by direct lookup, not normal similarity search |
| Itinerary | One day per chunk; split an unusually long day only at meaningful morning/afternoon/evening or location boundaries |
| Price table | Keep the complete table, headers, labels, and footnotes in one atomic chunk |
| Flight/departure table | Keep each complete table as one atomic chunk |
| Included / excluded | Separate chunks, never merged |
| Child pricing | Keep all age bands and their shared conditions together |
| Baggage | Preserve every occurrence; do not deduplicate similar claims |
| Payment | Keep deposit, remaining balance, and timing conditions together |
| Cancellation | Split by applicability, such as normal days, holidays, visa-related cases, and no-show; never separate a time condition from its fee |
| Visa | Keep whole when short; otherwise split by applicant/document group |
| Health and special notes | Split only by meaningful audience or condition when necessary |
| Repeated policies | Retain separately for every tour even when text appears identical |

Target size is guidance, not an automatic slicing rule:

- typical narrative chunk: roughly 350–500 tokens;
- review warning above roughly 700 tokens;
- semantic integrity overrides the warning for atomic tables and policies;
- use zero overlap for tables and numeric policies;
- use at most a small overlap for long narrative splits;
- never split solely because a semantic unit crosses a PDF page.

### 6.3 Aggregate documents

Two records support context at different levels:

- `tour_summary`: used for semantic tour resolution and supplied after a tour is resolved.
- `full_itinerary`: concatenated deterministically from itinerary children in `chunk_index` order and fetched directly by `tour_code` when needed.

The full itinerary is added to model context only for itinerary and recommendation requests, or when the user explicitly requests the complete program. Price, baggage, visa, or cancellation questions do not receive the full itinerary.

The full itinerary helps the model understand the program as a whole. Citations still point to the original day chunks rather than the aggregate.

### 6.4 Embedded text versus displayed text

`content` retains clean source text for quoting and display. `embedding_text` adds a contextual prefix so an isolated chunk remains retrievable:

```text
Tour: Bangkok – Pattaya
Tour code: <code>
Section: Lịch trình
Ngày 2: <title>

<clean source content>
```

The prefix is not shown as source content and must not alter the cited wording.

### 6.5 Minimal metadata

```json
{
  "chunk_id": "danang_itinerary_day_2",
  "tour_code": "danang-central-5d4n",
  "tour_name": "Đà Nẵng – Hội An – Huế",
  "document_type": "knowledge",
  "section_type": "itinerary",
  "section_title": "Ngày 2: Đà Nẵng – Bà Nà – Cầu Vàng",
  "page_start": 2,
  "page_end": 2,
  "parent_section_id": "danang_full_itinerary",
  "chunk_index": 2,
  "source_file": "<pdf filename>",
  "authority": "official_tour_pdf"
}
```

Optional fields such as `departure_date` and `effective_date` are included only when the source states them clearly. Chroma-incompatible compound values must be serialized.

### 6.6 Cleanup and duplication

Remove only confirmed boilerplate and extraction artifacts:

- repeated page headers and footers;
- page numbers and decorative noise;
- duplicated extraction output at the same position;
- irrelevant web-interface labels such as “Xem chương trình tour”.

Do not perform semantic deduplication. It could erase meaningful contradictions such as the two baggage allowances in the Đà Nẵng PDF. Identical policy text is still retained separately for each tour.

### 6.7 Required ingestion artifacts

```text
data/processed/
├── tour_chunks.jsonl
├── tour_catalog.jsonl
├── sales_guidance.json
├── conflicts.json
└── chunking_report.json
```

`conflicts.json` is intentionally simple and curated during chunk review. The MVP does not implement generic structured-fact extraction. Each record identifies a tour, topic, conflicting claims, source chunk IDs, and a `require_human_confirmation` resolution.

`chunking_report.json` contains document/chunk counts, removed boilerplate, exact extraction duplicates, oversized chunks requiring review, unclassified sections, and validation failures.

### 6.8 Chunking acceptance criteria

- No chunk mixes content from different tours.
- No chunk crosses unrelated top-level sections.
- Complete tables, their headers, and footnotes remain together.
- Numeric conditions remain with their qualifiers and applicability.
- Full itineraries reproduce every itinerary child exactly once and in the correct order.
- Every factual chunk has a stable ID, PDF filename, section, and page range.
- Policies remain scoped to their tour.
- The known Đà Nẵng baggage contradiction survives extraction and is recorded in `conflicts.json`.
- Sales spreadsheet content is absent from `tour_knowledge`.
- There are no unexplained unclassified sections before indexing.
- Generated JSONL is inspectable without querying Chroma.

## 7. Storage and retrieval

### `tour_catalog`

Contains `tour_summary` and `full_itinerary` records.

- Tour resolution queries only records with `document_type = "tour_summary"`.
- Full itineraries are fetched with an exact `tour_code` and `document_type = "full_itinerary"` lookup.

### `tour_knowledge`

Contains factual PDF chunks. After resolving a tour, semantic search uses:

- `standalone_query` as the query text;
- an exact filter on one or more resolved `tour_code` values;
- a small default `top_k`, increased for comparisons;
- optional adjacent itinerary expansion for “next/previous day” follow-ups.

The MVP does not hard-filter normal search by `section_type`, because relevant content may appear under an unexpected heading. Section type remains useful for inspection, evaluation, conflict lookup, and targeted itinerary expansion.

## 8. Evidence assessment and conflicts

Evidence assessment receives the standalone question, resolved tours, retrieved PDF chunks, the relevant curated conflict record, and the current date context. It returns one of:

- `sufficient`;
- `conflict`;
- `insufficient`;
- `realtime_required`;
- `high_risk`.

The model must not resolve conflicting source claims by preference. A known conflict produces a response that states both claims with both citations and asks the user to confirm with Vietravel staff.

Questions about current availability, live prices, current promotions, immigration changes, weather, or booking status require confirmation when the supplied documents do not establish the answer.

## 9. Sales guidance

The spreadsheet is converted to reviewed JSON, separated from Chroma factual evidence. It may provide:

- preferred response structure;
- tone and empathy guidance;
- an appropriate follow-up question;
- required escalation or next action;
- prohibited behavior.

Any examples containing prices, dates, discounts, availability, or policies are treated as untrusted examples. Factual claims in a final answer must still be supported by retrieved PDF chunk IDs.

## 10. Guardrails

### Input guard

- Reject empty or excessively long input.
- Detect obvious attempts to override system/source rules.
- Redact sensitive data before application logging.
- Do not solicit passports, bank data, or personal booking information in chat.

### Evidence guard

- Require resolved tour scope for tour-specific claims.
- Only PDF chunks with `authority = "official_tour_pdf"` can ground facts.
- Check curated conflicts before generation.
- Prevent claims of real-time availability or current policy without evidence.
- Route medical, immigration, booking, payment, cancellation execution, and complaint cases to safe guidance or staff confirmation.

### Output guard

- Citation IDs must be a subset of retrieved, approved PDF chunks.
- Numbers in factual claims must appear in approved evidence; otherwise return a safe fallback.
- Prohibit invented availability, guaranteed visa approval, bank-account details, guaranteed refunds/compensation, and medical advice.
- Never claim that an operation such as booking or cancellation was performed.
- A validation failure returns a deterministic fallback rather than making another unconstrained generation call.

## 11. Response contract and citations

```python
class TourAnswer(BaseModel):
    status: Literal[
        "answered",
        "clarification_needed",
        "conflict",
        "unsupported",
        "escalate",
    ]
    answer: str
    citation_ids: list[str]
    conflicts: list[str]
    follow_up: str | None
```

The model emits only stable citation IDs. The backend renders them from trusted metadata:

```text
[Bangkok – Pattaya · Giá trẻ em · Trang 4]
```

The Streamlit debug view may show the exact chunk text, similarity score, and retrieval reason. Normal chat output remains concise.

## 12. UI

The Streamlit MVP includes:

- a chat interface;
- two or three suggested questions;
- answer status and inline citation labels;
- expandable source snippets;
- a “show retrieval details” expander for the interview;
- a “reset conversation” control.

The demo should visibly cover:

1. a normal factual answer with citations;
2. a multi-turn follow-up inheriting the active tour;
3. an ambiguous-tour clarification;
4. the Đà Nẵng baggage conflict;
5. an out-of-scope or real-time availability refusal.

## 13. Evaluation

Create at least 30 reviewed questions across:

- standard factual queries;
- itinerary and comparison queries;
- multi-turn follow-ups;
- ambiguous tour references;
- insufficient information;
- conflicting information;
- real-time requests;
- prompt injection and out-of-scope requests.

Ragas metrics:

- Context Precision;
- Context Recall;
- Faithfulness;
- Response Relevancy;
- Answer Correctness where a reference answer exists.

Deterministic/task-specific metrics:

- intent accuracy;
- tour-resolution accuracy;
- citation validity;
- conflict-detection accuracy;
- clarification accuracy;
- safe-refusal accuracy;
- numeric grounding rate;
- forbidden-fact/hallucination rate;
- latency p50/p95;
- estimated cost per 1,000 questions.

Using DeepSeek as both generator and Ragas judge is acceptable for the deadline but must be reported as a self-evaluation limitation. A small manual review sample should complement automated scores.

## 14. Configuration and deployment

Expected secrets/configuration:

```text
DEEPSEEK_API_KEY
DEEPSEEK_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-flash
GEMINI_API_KEY
EMBEDDING_MODEL=gemini-embedding-001
EMBEDDING_OUTPUT_DIMENSIONALITY=768
CHROMA_PERSIST_DIR=...
```

Deploy the Streamlit application on Streamlit Community Cloud. Commit processed, non-sensitive Chroma data only if repository size permits; otherwise run a deterministic build step during deployment and cache the result. API keys belong only in Streamlit Secrets and `.env` files excluded from Git.

## 15. Testing and completion criteria

Minimum tests:

- section classification and page provenance;
- atomic price-table handling;
- itinerary order and full-itinerary assembly;
- preservation of the known baggage conflict;
- spreadsheet facts excluded from `tour_knowledge`;
- tour resolution and ambiguous resolution;
- multi-turn standalone-query rewriting;
- citation ID validation;
- numeric grounding validation;
- safe responses for availability, payment details, cancellation execution, and prompt injection;
- one end-to-end test per main evidence status.

The MVP is complete when:

- all four PDFs have reviewed chunks indexed in Chroma;
- Streamlit supports the five demo scenarios;
- citations resolve to correct source pages;
- evaluation runs from one command and saves machine-readable results;
- README explains local setup, architecture, limitations, deployment, and demo flow;
- no secrets or personal data are committed.

## 16. Explicit trade-offs

- Data-specific, reviewed ingestion is preferred over a generic chunking framework because there are only four PDFs and the deadline is short.
- Full itinerary is a direct-lookup aggregate, avoiding noisy large-document similarity search.
- Curated conflict records replace a general fact registry in the MVP.
- The assistant does not use a separate LLM retrieval-planning step.
- In-memory conversation state is sufficient for a live demo.
- Source safety and explainability take priority over answering every question.
