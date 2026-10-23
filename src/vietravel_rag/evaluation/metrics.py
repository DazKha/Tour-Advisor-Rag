"""Deterministic quality, safety, latency, and usage metrics."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from statistics import quantiles
from typing import Any

_NUMBER_TOKEN = re.compile(r"(?<!\d)\d+(?:[.,]\d+)*(?!\d)")


def _numeric_tokens(text: str) -> set[str]:
    return {match.group().replace(".", "").replace(",", "") for match in _NUMBER_TOKEN.finditer(text)}


def citation_validity(citation_ids: list[str], retrieved_ids: set[str]) -> float:
    """Return the fraction of cited IDs that were actually retrieved."""
    if not citation_ids:
        return 1.0
    return sum(citation in retrieved_ids for citation in citation_ids) / len(citation_ids)


def latency_summary(values_ms: list[float]) -> dict[str, float | None]:
    """Summarize latency with inclusive linear p50/p95 percentiles."""
    if not values_ms:
        return {"p50_ms": None, "p95_ms": None}
    ordered = sorted(float(value) for value in values_ms)
    if len(ordered) == 1:
        return {"p50_ms": ordered[0], "p95_ms": ordered[0]}
    p50, p95 = quantiles(ordered, n=100, method="inclusive")[49], quantiles(
        ordered, n=100, method="inclusive"
    )[94]
    return {"p50_ms": round(p50, 3), "p95_ms": round(p95, 3)}


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def numeric_grounding_rate(results: list[dict], contexts: list[list[str]]) -> float:
    """Return the fraction of answer numeric facts supported by retrieved text."""
    claims = grounded = 0
    for result, retrieved_contexts in zip(results, contexts, strict=True):
        answer_numbers = _numeric_tokens(str(result.get("answer", "")))
        context_numbers = _numeric_tokens(" ".join(retrieved_contexts))
        claims += len(answer_numbers)
        grounded += sum(number in context_numbers for number in answer_numbers)
    return _rate(grounded, claims) if claims else 1.0


def forbidden_claim_rate(results: list[dict], prohibited_phrases: list[list[str]]) -> float:
    """Return the fraction of answers containing any case-specific prohibited phrase."""
    if not results:
        return 0.0
    violations = 0
    for result, phrases in zip(results, prohibited_phrases, strict=True):
        answer = str(result.get("answer", "")).casefold()
        violations += any(str(phrase).casefold() in answer for phrase in phrases)
    return violations / len(results)


def cost_summary(
    results: list[dict], *, input_price_per_million: float, output_price_per_million: float
) -> dict[str, int | float]:
    """Compute observed token spend and estimated spend for 1,000 questions."""
    input_tokens = sum(int(result.get("input_tokens") or 0) for result in results)
    output_tokens = sum(int(result.get("output_tokens") or 0) for result in results)
    cost = (
        input_tokens * input_price_per_million + output_tokens * output_price_per_million
    ) / 1_000_000
    estimate = cost * 1000 / len(results) if results else 0.0
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "observed_cost_usd": round(cost, 8),
        "estimated_cost_per_1000_usd": round(estimate, 8),
    }


def _exact_match(expected: list[str], actual: list[str]) -> bool:
    return list(expected) == list(actual)


def score_cases(cases: list[dict], results: list[dict]) -> dict[str, Any]:
    """Compute deterministic quality and safety metrics for aligned cases/results."""
    if len(cases) != len(results):
        raise ValueError("cases and results must have the same length")
    count = len(cases)
    valid_citations = []
    contexts = []
    for case, result in zip(cases, results, strict=True):
        retrieved_ids = set(result.get("retrieved_context_ids", []))
        valid_citations.append(
            citation_validity(result.get("citation_ids", []), retrieved_ids)
        )
        contexts.append(list(result.get("retrieved_contexts", [])))
    statuses = [str(result.get("status", "")) for result in results]
    expected_statuses = [str(case.get("expected_status", "")) for case in cases]
    safety_statuses = {"clarification_needed", "conflict", "unsupported", "escalate"}
    safety_indices = [
        index for index, expected in enumerate(expected_statuses) if expected in safety_statuses
    ]
    safety_correct = sum(statuses[index] == expected_statuses[index] for index in safety_indices)
    latencies = [float(result.get("latency_ms") or 0) for result in results]
    numeric_rate = numeric_grounding_rate(results, contexts)
    result = {
        "case_count": count,
        "intent_accuracy": _rate(
            sum(
                result.get("intent") == case.get("expected_intent")
                for case, result in zip(cases, results, strict=True)
            ),
            count,
        ),
        "tour_resolution_exact_match": _rate(
            sum(
                _exact_match(case.get("expected_tour_codes", []), row.get("tour_codes", []))
                for case, row in zip(cases, results, strict=True)
            ),
            count,
        ),
        "answer_status_accuracy": _rate(
            sum(actual == expected for actual, expected in zip(statuses, expected_statuses, strict=True)),
            count,
        ),
        "clarification_conflict_refusal_accuracy": _rate(safety_correct, len(safety_indices)),
        "citation_validity": _rate(sum(valid_citations), count),
        "numeric_grounding_rate": numeric_rate,
        "forbidden_claim_rate": forbidden_claim_rate(
            results, [case.get("must_not_contain", []) for case in cases]
        ),
        "latency": latency_summary(latencies),
        "timestamp_utc": datetime.now(UTC).isoformat(),
    }
    return result


def extract_contexts(state: dict) -> tuple[list[str], list[str]]:
    """Extract rendered context strings and IDs from a graph state."""
    contexts, identifiers = [], []
    for document in state.get("retrieved_chunks", []):
        metadata = getattr(document, "metadata", {}) or {}
        identifier = metadata.get("chunk_id") or getattr(document, "id", None)
        if identifier:
            identifiers.append(str(identifier))
        contexts.append(str(metadata.get("content") or getattr(document, "page_content", "")))
    return contexts, identifiers

