# Fast Runtime Guardrails Design

## Goal

Reduce one LLM round trip per answered turn and remove the fragile numeric-regex grounding layer while preserving citation integrity and deterministic safety boundaries.

## Runtime flow

The guarded answer path becomes:

`input guard -> query analysis -> tour resolution -> retrieval -> conflict/risk checks -> answer generation -> thin output guard`

The graph no longer calls an LLM to assess evidence. For an ordinary factual request, every retrieved official knowledge chunk is passed directly to answer generation and is eligible for citation. Answer generation must decide whether the evidence is sufficient and return `unsupported` when it is not.

Existing deterministic pre-generation behavior remains responsible for known document conflicts, realtime requests, and high-risk requests. These paths must not require an answer-generation call when a fixed safe response is available.

## Thin output guard

The output guard retains only inexpensive structural and safety invariants:

- Every citation ID must belong to a retrieved official knowledge chunk supplied to answer generation.
- An `answered` or `conflict` response must contain at least one citation.
- Prohibited operational or guarantee claims remain fail-closed: bank details, visa guarantees, realtime availability/current-price guarantees, medical directives, completed cancellation/refund/payment operations, and guaranteed refunds.
- Invalid structured model output remains a safe `unsupported` response without retrying.

The guard removes numeric parsing, unit normalization, range/comparator parsing, calendar validation, and derived itinerary facts. Semantic grounding is handled by the answer-generation instruction and evaluated offline rather than by a runtime LLM verifier.

## Prompt language

All system prompt constants are written in English. User-facing answers remain Vietnamese. The answer prompt explicitly requires the model to use only supplied official evidence, cite only supplied chunk IDs, perform only direct and obvious inference, and return `unsupported` when evidence is insufficient.

## State cleanup

Remove the runtime `EvidenceAssessment` node, prompt, model, state fields, and direct tests. Keep `evidence_status` and approved chunk fields only where they still express deterministic conflict/risk/realtime state or the set of official retrieved chunks passed to generation. Prefer naming and state construction that make this distinction clear.

## Verification

Tests must prove that an ordinary answer uses exactly two structured model calls (query analysis and answer generation), realtime/high-risk paths avoid answer generation, citation allowlisting remains enforced, factual answers without citations are rejected, prohibited claims escalate, numeric paraphrases are no longer rejected by the output guard, prompts are English, and the complete suite remains green.
