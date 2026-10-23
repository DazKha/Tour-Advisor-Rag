# Professional Consultant Tone Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give generated and deterministic answers a concise, courteous Vietravel consultant voice without adding model calls or exposing raw source chunks.

**Architecture:** The English generation prompt controls normal LLM answers with Vietnamese few-shot outputs. Deterministic paths use matching fixed copy, while known conflicts use a curated factual summary from conflict data rather than interpolating retrieved chunk bodies.

**Tech Stack:** Python 3.12, LangGraph, Pydantic v2, DeepSeek structured output, pytest.

## Global Constraints

- All production code and test implementation must be performed by a GPT Luna agent.
- Follow strict TDD and record RED evidence before production edits.
- Do not add an LLM call or change the two-call ordinary request path.
- All prompt instructions and labels remain English; user-facing examples and answers are Vietnamese.
- Preserve citation allowlisting, deterministic risk routing, and fail-closed behavior.
- Never expose full source chunks, arbitrary metadata, credentials, or `.env` content.
- Keep scope limited to response voice and concise conflict presentation.

---

### Task 1: Add consultant voice and concise deterministic conflict responses

**Files:**
- Modify: `src/vietravel_rag/agent/prompts.py`
- Modify: `src/vietravel_rag/agent/nodes.py`
- Modify: `src/vietravel_rag/guardrails/output_guard.py`
- Modify: `src/vietravel_rag/models.py`
- Modify: `data/processed/conflicts.json`
- Modify: `tests/agent/test_graph.py`
- Modify: `tests/guardrails/test_output_guard.py`
- Modify or create: focused prompt tests
- Modify as needed: conflict validation tests if the curated field is validated

**Interfaces:**
- Consumes: conflict records containing `topic`, official claim chunk IDs, and a non-empty `customer_summary`.
- Produces: `AgentState.conflict_customer_summary: str | None` and a concise cited `TourAnswer` for known conflicts.

- [ ] **Step 1: Write failing tone and conflict tests**

Add tests asserting:

- The answer prompt instructs polite Vietnamese consultant tone, direct answers, relevant summarization, limited honorific use, and contains few-shot examples for factual, itinerary, and conflict answers.
- The Đà Nẵng baggage response starts politely, contains `23kg`, `20kg`, `10kg`, and `7kg`, recommends Vietravel confirmation, retains both official citation IDs, and does not contain unrelated registration text such as `Căn cước công dân` or `Giấy khai sinh`.
- The conflict path still uses only `QueryAnalysis` and no `TourAnswer` model call.
- Fixed responses and output-guard fallbacks are polite and safe.

Run the focused tests and confirm they fail for the expected missing tone/summary behavior.

- [ ] **Step 2: Add the curated conflict summary contract**

Add `customer_summary` to the baggage conflict record with only the two concise source versions. Pass it through conflict state as `conflict_customer_summary`. Do not derive the customer summary by slicing or regexing raw source chunks at runtime. If corpus validation owns conflict-record shape, require a non-empty summary and test the validation failure.

- [ ] **Step 3: Format deterministic conflict output**

Change `output_guard_node` to render the curated summary in this structure:

```text
Dạ, tài liệu tour hiện có hai thông tin chưa thống nhất về hành lý:

<curated concise source versions>

Để tránh ảnh hưởng khi làm thủ tục tại sân bay, anh/chị vui lòng xác nhận lại hạn mức áp dụng với Vietravel trước ngày khởi hành ạ.
```

Keep both official citation IDs and a concise `conflicts` entry. If the curated summary is unexpectedly missing, fail closed with a short polite confirmation request; never fall back to full chunk interpolation.

- [ ] **Step 4: Upgrade the English system prompt with few shots**

Add explicit English voice rules matching the design. Add three compact examples whose labels/instructions are English and whose assistant answer values are Vietnamese. The examples must demonstrate direct factual answering, scannable itinerary bullets, and concise conflict presentation without raw excerpts. Preserve all grounding and safety requirements.

- [ ] **Step 5: Align deterministic copy**

Revise realtime, high-risk, insufficient, clarification, general, off-topic, invalid-output, and output-guard fallback messages to open naturally with “Dạ,” and use “anh/chị” only where appropriate. Keep them concise and preserve their existing statuses and routing behavior.

- [ ] **Step 6: Verify and commit**

Run focused tests, then:

```bash
PYTHONPATH=.:src .venv/bin/pytest -q
.venv/bin/ruff check src tests app.py scripts
git diff --check
```

Expected: all tests and lint pass. Commit with:

```bash
git add src tests data/processed/conflicts.json
git commit -m "feat: refine consultant response tone"
```
