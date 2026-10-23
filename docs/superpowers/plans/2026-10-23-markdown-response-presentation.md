# Markdown Response Presentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce naturally worded, correctly rendered Markdown answers and friendly Streamlit status labels.

**Architecture:** Prompt rules and few shots make CommonMark the primary model output format. A narrowly scoped UI normalizer repairs only line-leading Unicode bullets, while a display-only map translates internal statuses without changing graph semantics.

**Tech Stack:** Python 3.12, Streamlit, DeepSeek structured output, pytest, Ruff.

## Global Constraints

- All production code and tests must be implemented by a GPT Luna agent.
- Follow strict TDD and record RED evidence before production edits.
- Do not add an LLM call or change retrieval, citations, guardrails, or internal status values.
- Keep all system-prompt instructions and labels in English; Vietnamese is used only for user-facing examples.
- Do not touch `.env`, secrets, credentials, or deployment configuration.

---

### Task 1: Improve Markdown formatting, conflict wording, and status presentation

**Files:**
- Modify: `src/vietravel_rag/agent/prompts.py`
- Modify: `app.py`
- Modify: `tests/agent/test_prompts.py`
- Modify: `tests/test_app_helpers.py`
- Modify as needed: other focused presentation tests

**Interfaces:**
- Produce `format_response_markdown(content: str) -> str` as a pure presentation helper.
- Produce `response_status_label(status: str) -> str` as a pure display-only helper.
- Preserve all graph and `TourAnswer.status` interfaces.

- [ ] **Step 1: Write failing prompt-format tests**

Assert that the answer prompt explicitly forbids Unicode `•`, requires CommonMark `- ` items with a blank line before lists, requires one itinerary day per line, avoids default “theo tài liệu” openings, and demonstrates the natural `Điểm anh/chị nên lưu ý` conflict pattern. Verify the few-shot itinerary contains literal newlines and Markdown hyphens.

- [ ] **Step 2: Write failing Streamlit-helper tests**

Add tests for all five status mappings and an unknown-status safe fallback. Test that `format_response_markdown` converts only line-leading Unicode bullets into a Markdown list, inserts a blank line before the first item, preserves already valid Markdown, and leaves `•` embedded in ordinary prose unchanged.

- [ ] **Step 3: Upgrade the answer prompt**

Add concise English formatting and natural-language rules from the design. Rewrite itinerary and conflict few shots using literal CommonMark and a paired illustrative evidence/question/answer context where factual details appear. Preserve grounding, citation, safety, schema, and consultant-tone instructions.

- [ ] **Step 4: Add display-only presentation helpers**

Implement the two pure helpers in `app.py`. Call `response_status_label` when rendering the caption and pass assistant message content through `format_response_markdown` before `st.markdown`. Do not mutate stored chat messages or source content.

- [ ] **Step 5: Verify and commit**

Run focused tests, then:

```bash
PYTHONPATH=.:src .venv/bin/pytest -q
.venv/bin/ruff check src tests app.py scripts
git diff --check
```

Expected: all checks pass. Commit production/test changes with:

```bash
git add app.py src/vietravel_rag/agent/prompts.py tests
git commit -m "feat: improve answer presentation"
```
