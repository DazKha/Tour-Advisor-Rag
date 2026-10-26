# Chatbot UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing Streamlit chat demo into a polished, responsive tour-consultation interface that makes grounded answers and business limits clear.

**Architecture:** Keep `app.py` as the entry point and leave the RAG graph unchanged. Add focused presentation helpers and a small stylesheet, using existing session state and safe citation data. Render starter and follow-up actions through the same `invoke_turn` path as typed prompts.

**Tech Stack:** Python 3.11+, Streamlit, pytest, Ruff, CSS.

## Global Constraints

- Keep Streamlit deployment and the existing four-tour PDF corpus.
- The four supplied PDFs remain the sole factual authority for tour answers.
- No booking, live inventory, new tour data, website embedding, or RAG prompt/retrieval changes.
- Preserve session continuity, reset behavior, citation allowlist, and sanitized errors.
- Keep the primary experience useful on desktop and narrow mobile screens.
- Do not include unrelated changes already present in the working tree in task commits.

## File map

- `app.py`: existing entry point, session behavior, and UI orchestration; replace only the presentation portion and add deterministic UI helpers.
- `.streamlit/style.css`: new local stylesheet for typography, spacing, color, focus, and responsive layout.
- `tests/test_app_helpers.py`: focused tests for any new pure UI helpers and preserved chat behavior.
- `README.md`: update the app UI description and interview demo instructions; preserve unrelated local edits.

---

### Task 1: Context and suggestion model

**Files:**
- Modify: `app.py`
- Modify: `tests/test_app_helpers.py`

**Interfaces:**
- Produce `active_tour_labels(tour_codes: list[str]) -> list[str]`, mapping only the four reviewed catalog codes to display names; unknown codes yield no label.
- Produce `suggested_questions(tour_codes: list[str], has_messages: bool) -> list[tuple[str, str]]`. Each pair is `(button_label, submitted_question)`; output has at most four items.
- The returned question is passed unchanged to `_run_turn(graph, question)`.

- [ ] **Step 1: Write failing tests**

```python
def test_active_tour_labels_hide_unknown_codes():
    assert app.active_tour_labels(["danang-central-5d4n", "unknown"]) == [
        "Đà Nẵng – Hội An – Huế – Phong Nha"
    ]

def test_suggestions_use_tour_context_without_claiming_facts():
    questions = app.suggested_questions(["danang-central-5d4n"], True)
    assert questions
    assert all("Đà Nẵng" in prompt for _, prompt in questions)
    assert all("còn chỗ" not in label.lower() for label, _ in questions)
```

- [ ] **Step 2: Run `PYTHONPATH=.:src .venv/bin/pytest -q tests/test_app_helpers.py -k 'active_tour_labels or suggestions'` and confirm RED** due to undefined helpers.
- [ ] **Step 3: Implement the four-code display map and deterministic starter/follow-up prompt selection** in `app.py`. Starter intents are itinerary, price and costs, tour comparison, and policies. Use a neutral list when context is empty or ambiguous. Do not read or synthesize answer facts.
- [ ] **Step 4: Run the focused tests and confirm GREEN.**
- [ ] **Step 5: Commit only `app.py` and the focused test file** with `git commit -m "feat: add contextual chatbot suggestions"`.

### Task 2: Chat layout and evidence presentation

**Files:**
- Modify: `app.py`
- Create: `.streamlit/style.css`
- Modify: `tests/test_app_helpers.py`

**Interfaces:**
- Keep `_render_message(message: dict[str, Any]) -> None`, `_run_turn(graph, prompt: str) -> None`, and `reset_conversation(session_state) -> None` callable under their current signatures.
- Add `_render_welcome()`, `_render_context(tour_codes: list[str])`, `_render_suggestions(tour_codes: list[str], has_messages: bool) -> str | None`, and `_render_sources(sources: list[dict[str, Any]]) -> None` as Streamlit-only rendering units.

- [ ] **Step 1: Update focused rendering tests to expect the new hierarchy.** A normal answer has no prominent status caption, while `conflict`, `unsupported`, `clarification_needed`, and `escalate` show their existing Vietnamese labels. A citation disclosure retains tour, section, and page; technical metadata appears only inside a nested “Chi tiết demo” disclosure. Keep assertions that stored messages are unmodified.
- [ ] **Step 2: Run focused rendering tests and confirm RED** against the current always-visible status caption and raw metadata layout.
- [ ] **Step 3: Implement the rendering helpers and CSS.** In `main()`, set a wide page layout, render welcome only for an empty chat, display context labels from `active_tour_codes`, then suggestions and messages. Give the input a concrete Vietnamese placeholder. Keep safe resource and turn-error messages. Use Streamlit controls for interactions; CSS handles appearance and narrow-screen stacking.
- [ ] **Step 4: Run rendering tests and `ruff check app.py tests/test_app_helpers.py`; fix failures.**
- [ ] **Step 5: Commit `app.py`, `.streamlit/style.css`, and focused tests** with `git commit -m "feat: refresh Streamlit chatbot interface"`.

### Task 3: Browser verification and demo guidance

**Files:**
- Modify: `README.md` only if its existing UI and demo instructions need adjustment.

**Interfaces:**
- No new runtime interface. The final app still starts with `streamlit run app.py`.

- [ ] **Step 1: Run `PYTHONPATH=.:src .venv/bin/pytest -q tests/test_app_helpers.py` and `.venv/bin/ruff check app.py tests/test_app_helpers.py`.**
- [ ] **Step 2: Run the full local test suite and `git diff --check`.** Distinguish any failures caused by unrelated local changes.
- [ ] **Step 3: Open the app in a browser at desktop and narrow widths.** Check starter actions, free text, one sourced answer, follow-up context, clarification, conflict, live-availability escalation, source disclosure, demo metadata disclosure, and reset. If provider credentials prevent live turns, report the blocked cases explicitly and verify available static states.
- [ ] **Step 4: Update README's UI/demo wording to match the delivered interface**, preserving unrelated working-tree changes. Commit only the relevant README hunks if safe; otherwise leave the README edit uncommitted and explain why.
- [ ] **Step 5: Report what changed, test evidence, and any unverified interaction.**
