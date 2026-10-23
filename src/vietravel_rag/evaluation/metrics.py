"""Deterministic quality, safety, latency, and usage metrics."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from statistics import quantiles
from typing import Any

_NUMBER_TOKEN = re.compile(r"(?<!\d)\d+(?:[.,]\d+)*(?!\d)")
_ISO_DATE = re.compile(r"(?<!\d)(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?!\d)")
_DMY_DATE = re.compile(r"(?<!\d)(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})(?!\d)")
_UNIT_ALIASES = {
    "million": "scale:million", "millions": "scale:million", "triệu": "scale:million",
    "billion": "scale:billion", "billions": "scale:billion", "tỷ": "scale:billion",
    "thousand": "scale:thousand", "thousands": "scale:thousand", "nghìn": "scale:thousand", "ngàn": "scale:thousand",
    "vnd": "currency:vnd", "đồng": "currency:vnd", "đ": "currency:vnd", "₫": "currency:vnd",
    "usd": "currency:usd", "dollar": "currency:usd", "dollars": "currency:usd", "$": "currency:usd",
    "eur": "currency:eur", "€": "currency:eur", "gbp": "currency:gbp", "£": "currency:gbp",
    "jpy": "currency:jpy", "¥": "currency:jpy", "cny": "currency:cny", "rmb": "currency:cny",
    "thb": "currency:thb", "sgd": "currency:sgd", "krw": "currency:krw",
    "kg": "mass:kg", "kilogram": "mass:kg", "kilograms": "mass:kg",
    "km": "length:km", "kilometer": "length:km", "kilometers": "length:km",
    "%": "percent", "percent": "percent", "phần trăm": "percent",
    "years old": "duration:year", "year": "duration:year", "years": "duration:year", "tuổi": "duration:year",
    "day": "duration:day", "days": "duration:day", "ngày": "duration:day",
    "night": "duration:night", "nights": "duration:night", "đêm": "duration:night",
    "hour": "duration:hour", "hours": "duration:hour", "giờ": "duration:hour", "tiếng": "duration:hour",
    "people": "people", "person": "people", "pax": "people", "người": "people", "khách": "people",
}
_UNIT_TOKEN = re.compile(
    r"(?<!\w)(?:" + "|".join(re.escape(unit) for unit in sorted(_UNIT_ALIASES, key=len, reverse=True)) + r")(?!\w)",
    re.IGNORECASE,
)
_COMPARATORS = {
    "under": "<", "below": "<", "less than": "<", "fewer than": "<", "dưới": "<", "nhỏ hơn": "<",
    "over": ">", "above": ">", "more than": ">", "greater than": ">", "trên": ">", "lớn hơn": ">",
    "at least": ">=", "no less than": ">=", "not less than": ">=", "not under": ">=",
    "no fewer than": ">=", "not fewer than": ">=",
    "at most": "<=", "no more than": "<=", "not more than": "<=", "not over": "<=",
    "no greater than": "<=", "not greater than": "<=",
}
_COMPARATOR_TOKEN = re.compile(
    r"(?<!\w)(?:" + "|".join(re.escape(term) for term in sorted(_COMPARATORS, key=len, reverse=True)) + r")(?!\w)",
    re.IGNORECASE,
)
_UNIT_CONJUNCTION = re.compile(r"\b(?:and|or|then)\b", re.IGNORECASE)
_SUFFIX_COMPARATORS = {
    "or less": "<=", "or fewer": "<=", "or more": ">=", "or older": ">=",
    "trở xuống": "<=", "trở lên": ">=", "and below": "<=", "and above": ">=",
}


def _normalized_date(match: re.Match[str], *, iso: bool) -> str:
    year, month, day = match.groups() if iso else (match.group(3), match.group(2), match.group(1))
    try:
        return date(int(year), int(month), int(day)).isoformat()
    except ValueError:
        return f"invalid:{match.group()}"


def _numeric_facts(text: str) -> set[tuple[str, str, str]]:
    """Extract compact value/unit/comparator facts for offline evaluation only."""
    facts: set[tuple[str, str, str]] = set()
    date_spans: list[tuple[int, int]] = []
    for pattern, is_iso in ((_ISO_DATE, True), (_DMY_DATE, False)):
        for match in pattern.finditer(text):
            facts.add(("date", _normalized_date(match, iso=is_iso), "="))
            date_spans.append(match.span())

    number_matches = list(_NUMBER_TOKEN.finditer(text))
    for index, match in enumerate(number_matches):
        if any(match.start() < end and match.end() > start for start, end in date_spans):
            continue
        prior_boundary = max(text.rfind(mark, 0, match.start()) for mark in ".!?;,:\n")
        prefix = text[max(prior_boundary + 1, match.start() - 48) : match.start()]
        if index and number_matches[index - 1].end() > prior_boundary:
            previous_number = number_matches[index - 1].group()
            prefix = prefix[prefix.rfind(previous_number) + len(previous_number) :]
        next_boundary = min(
            (position for position in (text.find(mark, match.end()) for mark in ".!?;,:\n") if position >= 0),
            default=len(text),
        )
        next_number = number_matches[index + 1].start() if index + 1 < len(number_matches) else len(text)
        suffix_end = min(next_boundary, next_number, match.end() + 48)
        suffix = text[match.end() : suffix_end]
        conjunction = _UNIT_CONJUNCTION.search(suffix)
        suffix_scope = suffix[: conjunction.start()] if conjunction else suffix
        aliases = [token.casefold() for token in _UNIT_TOKEN.findall(suffix_scope)]
        prefix_tokens = list(_UNIT_TOKEN.finditer(prefix))
        if prefix_tokens:
            token = prefix_tokens[-1]
            alias = token.group().casefold()
            if not prefix[token.end() :].strip() and _UNIT_ALIASES[alias].startswith("currency:"):
                aliases.append(alias)
        unit_facts = {_UNIT_ALIASES[token] for token in aliases}
        currencies = sorted(unit.removeprefix("currency:") for unit in unit_facts if unit.startswith("currency:"))
        scales = sorted(unit for unit in unit_facts if unit.startswith("scale:"))
        measures = sorted(unit for unit in unit_facts if not unit.startswith(("currency:", "scale:")))
        unit = "+".join([*currencies, *scales, *measures]) or "scalar"

        comparator = "="
        prefix_cues = list(_COMPARATOR_TOKEN.finditer(prefix))
        if prefix_cues:
            comparator = _COMPARATORS[prefix_cues[-1].group().casefold()]
        else:
            suffix_text = suffix.casefold()
            suffix_matches = [term for term in _SUFFIX_COMPARATORS if term in suffix_text]
            if suffix_matches:
                comparator = _SUFFIX_COMPARATORS[max(suffix_matches, key=len)]
        value = match.group().replace(".", "").replace(",", "")
        facts.add((value, unit, comparator))
    return facts


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
        answer_facts = _numeric_facts(str(result.get("answer", "")))
        context_facts = _numeric_facts(" ".join(retrieved_contexts))
        claims += len(answer_facts)
        grounded += sum(fact in context_facts for fact in answer_facts)
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

