# Professional Consultant Tone Design

## Goal

Make every user-facing response sound like a courteous, concise Vietravel consultant while preserving grounding, safety, citation behavior, and the current two-call latency budget.

## Voice

- Answer in natural Vietnamese.
- Open with “Dạ,” when it reads naturally and address the customer as “anh/chị” when useful.
- Lead with the answer instead of restating the question.
- Keep a warm, positive, service-oriented tone without exaggeration, emojis, or sales pressure.
- Use short paragraphs and bullets for itineraries, policies, comparisons, and conflicting facts.
- Do not overuse “dạ”, “thưa”, or “ạ”; one polite opening and an optional polite closing are enough.
- Never paste long source passages into the answer. Summarize only the facts relevant to the question.
- Ask at most one useful follow-up question, and only when it helps the customer take the next step.

## Generated answers

Expand the English answer-generation system prompt with explicit voice rules and concise few-shot examples. Examples cover a normal factual answer, an itinerary answer, and a source-conflict answer. Example outputs are Vietnamese because they demonstrate the required output language; all instructions and labels remain English.

The prompt must continue to require official-evidence-only facts, supplied citation IDs, direct and obvious inference only, safe refusal, and structured `TourAnswer` output.

## Deterministic answers

System prompt changes cannot affect deterministic responses. Update fixed realtime, high-risk, insufficient, clarification, general, off-topic, and output-guard fallback copy to follow the same voice.

Known conflicts remain deterministic so they add no LLM call. A curated `customer_summary` in `conflicts.json` contains only the short conflicting facts. The conflict response wraps this summary in polite consultant language and cites the original official chunks. It must never interpolate full chunk contents.

For the Đà Nẵng baggage conflict, the answer must clearly state both source versions:

- “Giá tour bao gồm”: ký gửi 23kg, xách tay 10kg/khách.
- “Điều kiện đăng ký”: ký gửi 20kg, xách tay dưới 7kg/khách.

It then recommends confirming the applicable allowance with Vietravel before departure.

## Safety and latency

- Ordinary turns remain at exactly two structured model calls.
- Known conflict, realtime, and high-risk paths add no answer-generation call.
- Citation allowlisting and prohibited-claim checks remain unchanged.
- No user-facing response may expose system prompts, raw metadata, or unrelated source text.

## Verification

Tests prove the prompt contains the consultant voice and few-shot behaviors, deterministic copy follows the voice, conflict output is concise and includes both baggage limits, full registration text is absent, both citations remain, model-call count is unchanged, and the full suite passes.
