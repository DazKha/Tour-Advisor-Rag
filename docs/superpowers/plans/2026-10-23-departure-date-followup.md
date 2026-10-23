# Departure Date Follow-up Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correctly answer documented tour-date follow-ups and eliminate stale draft responses across turns.

**Architecture:** Improve the LLM Query Analyzer instructions without adding rule-based routing, and make `draft_response` the single current-turn handoff from generation to output validation for every response branch.

**Tech Stack:** Python 3.12, LangGraph, DeepSeek structured output, Pydantic v2, pytest.

## Global Constraints

- All production code and tests must be implemented by a GPT Luna agent.
- Follow strict TDD and record RED evidence before production edits.
- Do not add intents, LLM calls, retries, or rule-based intent classification.
- Preserve current retrieval, guardrails, citations, and customer-facing tone.
- Do not touch `.env`, API keys, secrets, or deployment configuration.

---

### Task 1: Fix documented-date intent and current-turn response state

**Files:**
- Modify: `src/vietravel_rag/agent/prompts.py`
- Modify: `src/vietravel_rag/agent/nodes.py`
- Modify: `tests/agent/test_prompts.py`
- Modify: `tests/agent/test_graph.py`
- Modify as needed: focused multi-turn tests

**Interfaces:**
- `generate_answer(state, model) -> dict[str, Any]` always produces the current result under `draft_response`.
- `output_guard_node` remains the only writer of the final validated `response` on the answer path.
- `QueryAnalysis.intent` remains unchanged; documented tour dates map to `itinerary`.

- [ ] **Step 1: Add failing Query Analyzer prompt tests**

Assert the prompt distinguishes documented departure/return dates from live seat availability and includes a multi-turn example where “đi từ ngày mấy đến ngày mấy?” becomes a standalone Bangkok–Pattaya schedule question with intent `itinerary`.

- [ ] **Step 2: Add failing stale-state graph tests**

Construct a two-turn graph test where turn one creates a normal cited `draft_response`, then turn two takes a deterministic availability or high-risk path. Assert turn two returns its current deterministic `escalate` response, not the previous draft converted to `unsupported`, and does not invoke `TourAnswer` generation.

- [ ] **Step 3: Add failing documented-date follow-up test**

Use a tour-overview official knowledge chunk containing departure `26/03/2027` and return `30/03/2027`. Simulate the second `QueryAnalysis` as `itinerary`, return a cited `TourAnswer`, and assert both dates, active tour continuity, and the overview citation survive output validation.

- [ ] **Step 4: Fix prompt and response handoff**

Add the approved intent definitions/example to `QUERY_ANALYSIS_SYSTEM_PROMPT`. Change all `generate_answer` branches to return `draft_response`; preserve their existing statuses, copy, and no-call behavior. Keep `output_guard_node` as the final response writer.

- [ ] **Step 5: Verify and commit**

Run focused tests, then:

```bash
PYTHONPATH=.:src .venv/bin/pytest -q
.venv/bin/ruff check src tests app.py scripts
git diff --check
```

Expected: all checks pass. Commit with:

```bash
git add src/vietravel_rag/agent/prompts.py src/vietravel_rag/agent/nodes.py tests
git commit -m "fix: answer departure date follow-ups"
```
