# Departure Date Follow-up Fix Design

## Goal

Answer a multi-turn follow-up such as “đi từ ngày mấy đến ngày mấy?” from the selected tour's documented departure and return dates instead of routing it as live availability or leaking stale state from the previous turn.

## Confirmed root causes

The live reproduction selected the correct Bangkok–Pattaya tour and rewrote the follow-up correctly, but classified it as `availability`. The source overview contains the exact dates `26/03/2027` and `30/03/2027`, so the question is a documented schedule question, not a realtime seat-availability request.

The graph also retained `draft_response` from the previous turn. Fixed-response branches returned a new value under `response`, while `output_guard_node` prefers `draft_response`; consequently the old answer was revalidated against the new evidence set and became `unsupported`.

## Query understanding

Keep the existing intent schema. Clarify in the English Query Analyzer prompt:

- `availability` is only for current/live seats, capacity, or bookability.
- Questions about documented departure date, return date, travel period, flight time, or “đi từ ngày nào đến ngày nào” use `itinerary`.
- A multi-turn example must resolve the active tour and rewrite the follow-up as a standalone Vietnamese schedule question.

No rule-based intent override is added.

## Per-turn response contract

`generate_answer` must write every current-turn result to `draft_response`, including realtime, high-risk, insufficient, provider-failure, and normal answer paths. `output_guard_node` then validates that current draft and writes the final `response`. This prevents a prior-turn draft or response from taking precedence.

Do not add model calls or retries. Realtime/high-risk/insufficient paths remain deterministic and skip answer generation calls.

## Expected behavior

After asking for the Bangkok–Pattaya itinerary, the follow-up “đi từ ngày mấy đến ngày mấy?” should produce a concise cited response such as:

> Dạ, tour khởi hành ngày **26/03/2027** và kết thúc ngày **30/03/2027**, tương ứng hành trình 5 ngày ạ.

The answer cites `thailand-bangkok-pattaya_tour_overview_01`.

## Verification

Tests cover the prompt distinction, a two-turn documented-date answer, the stale-draft regression for deterministic realtime/high-risk branches, unchanged model-call counts, citation allowlisting, and the full suite. A live two-turn smoke test must answer with both documented dates.
