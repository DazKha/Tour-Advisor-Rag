"""Deterministic citation, factual-number, and prohibited-claim validation."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from langchain_core.documents import Document

from vietravel_rag.models import TourAnswer

_ISO_DATE = re.compile(r"(?<!\d)(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?!\d)")
_DMY_DATE = re.compile(r"(?<!\d)(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})(?!\d)")
_UNIT_ALIASES: dict[str, tuple[str, Decimal]] = {
    "%": ("percent", Decimal(1)), "phần trăm": ("percent", Decimal(1)),
    "percent": ("percent", Decimal(1)),
    "đ": ("currency_vnd", Decimal(1)), "₫": ("currency_vnd", Decimal(1)),
    "đồng": ("currency_vnd", Decimal(1)),
    "vnd": ("currency_vnd", Decimal(1)), "$": ("currency_usd", Decimal(1)),
    "usd": ("currency_usd", Decimal(1)), "€": ("currency_eur", Decimal(1)),
    "eur": ("currency_eur", Decimal(1)), "£": ("currency_gbp", Decimal(1)),
    "gbp": ("currency_gbp", Decimal(1)), "¥": ("currency_yen", Decimal(1)),
    "jpy": ("currency_yen", Decimal(1)), "cny": ("currency_cny", Decimal(1)),
    "rmb": ("currency_cny", Decimal(1)), "thb": ("currency_thb", Decimal(1)),
    "sgd": ("currency_sgd", Decimal(1)), "krw": ("currency_krw", Decimal(1)),
    "aud": ("currency_aud", Decimal(1)), "cad": ("currency_cad", Decimal(1)),
    "php": ("currency_php", Decimal(1)), "triệu": ("currency_unspecified", Decimal(1_000_000)),
    "tỷ": ("currency_unspecified", Decimal(1_000_000_000)),
    "nghìn": ("currency_unspecified", Decimal(1_000)),
    "ngàn": ("currency_unspecified", Decimal(1_000)),
    "kg": ("mass_gram", Decimal(1_000)), "kilogram": ("mass_gram", Decimal(1_000)),
    "kilograms": ("mass_gram", Decimal(1_000)), "g": ("mass_gram", Decimal(1)),
    "gram": ("mass_gram", Decimal(1)), "grams": ("mass_gram", Decimal(1)),
    "tấn": ("mass_gram", Decimal(1_000_000)), "ton": ("mass_gram", Decimal(1_000_000)),
    "km": ("length_metre", Decimal(1_000)), "kilometer": ("length_metre", Decimal(1_000)),
    "kilometers": ("length_metre", Decimal(1_000)), "kilometre": ("length_metre", Decimal(1_000)),
    "kilometres": ("length_metre", Decimal(1_000)), "mét": ("length_metre", Decimal(1)),
    "m": ("length_metre", Decimal(1)), "meter": ("length_metre", Decimal(1)),
    "meters": ("length_metre", Decimal(1)), "metre": ("length_metre", Decimal(1)),
    "metres": ("length_metre", Decimal(1)), "cm": ("length_metre", Decimal("0.01")),
    "centimeter": ("length_metre", Decimal("0.01")), "centimeters": ("length_metre", Decimal("0.01")),
    "centimetre": ("length_metre", Decimal("0.01")), "centimetres": ("length_metre", Decimal("0.01")),
    "mm": ("length_metre", Decimal("0.001")), "millimeter": ("length_metre", Decimal("0.001")),
    "millimeters": ("length_metre", Decimal("0.001")), "millimetre": ("length_metre", Decimal("0.001")),
    "millimetres": ("length_metre", Decimal("0.001")), "l": ("volume_ml", Decimal(1_000)),
    "lít": ("volume_ml", Decimal(1_000)), "liter": ("volume_ml", Decimal(1_000)),
    "liters": ("volume_ml", Decimal(1_000)), "litre": ("volume_ml", Decimal(1_000)),
    "litres": ("volume_ml", Decimal(1_000)), "ml": ("volume_ml", Decimal(1)),
    "milliliter": ("volume_ml", Decimal(1)), "milliliters": ("volume_ml", Decimal(1)),
    "millilitre": ("volume_ml", Decimal(1)), "millilitres": ("volume_ml", Decimal(1)),
    "ngày": ("duration_day", Decimal(1)), "day": ("duration_day", Decimal(1)),
    "days": ("duration_day", Decimal(1)), "đêm": ("duration_night", Decimal(1)),
    "night": ("duration_night", Decimal(1)), "nights": ("duration_night", Decimal(1)),
    "tuần": ("duration_week", Decimal(1)), "week": ("duration_week", Decimal(1)),
    "weeks": ("duration_week", Decimal(1)), "tháng": ("duration_month", Decimal(1)),
    "month": ("duration_month", Decimal(1)), "months": ("duration_month", Decimal(1)),
    "năm": ("duration_year", Decimal(1)), "year": ("duration_year", Decimal(1)),
    "years": ("duration_year", Decimal(1)), "tuổi": ("age_year", Decimal(1)),
    "years old": ("age_year", Decimal(1)), "giờ": ("duration_hour", Decimal(1)),
    "tiếng": ("duration_hour", Decimal(1)), "hour": ("duration_hour", Decimal(1)),
    "hours": ("duration_hour", Decimal(1)), "phút": ("duration_minute", Decimal(1)),
    "minute": ("duration_minute", Decimal(1)), "minutes": ("duration_minute", Decimal(1)),
    "giây": ("duration_second", Decimal(1)), "second": ("duration_second", Decimal(1)),
    "seconds": ("duration_second", Decimal(1)), "khách": ("people", Decimal(1)),
    "người": ("people", Decimal(1)), "người lớn": ("people", Decimal(1)),
    "pax": ("people", Decimal(1)), "person": ("people", Decimal(1)),
    "persons": ("people", Decimal(1)), "people": ("people", Decimal(1)),
    "passenger": ("people", Decimal(1)), "passengers": ("people", Decimal(1)),
    "phòng": ("rooms", Decimal(1)), "room": ("rooms", Decimal(1)), "rooms": ("rooms", Decimal(1)),
    "vé": ("seats", Decimal(1)), "ticket": ("seats", Decimal(1)), "tickets": ("seats", Decimal(1)),
    "chỗ": ("seats", Decimal(1)), "seat": ("seats", Decimal(1)), "seats": ("seats", Decimal(1)),
    "°c": ("temperature_c", Decimal(1)), "celsius": ("temperature_c", Decimal(1)),
    "°f": ("temperature_f", Decimal(1)), "fahrenheit": ("temperature_f", Decimal(1)),
}
_UNIT_NAMES = tuple(sorted(_UNIT_ALIASES, key=len, reverse=True))
_UNIT_ALTERNATION = "|".join(re.escape(unit) for unit in _UNIT_NAMES)
_UNIT_PATTERN = re.compile(
    r"\s*(?P<unit>" + _UNIT_ALTERNATION + r")(?!\w)",
    re.IGNORECASE,
)
_COMPARATOR_ALIASES = {
    "more than": ">", "greater than": ">", "over": ">", "above": ">", "trên": ">",
    "less than": "<", "fewer than": "<", "lower than": "<", "smaller than": "<",
    "under": "<", "below": "<", "dưới": "<", "nhỏ hơn": "<", "ít hơn": "<", "thấp hơn": "<",
    "at least": ">=", "no less than": ">=", "not less than": ">=", "not under": ">=",
    "no fewer than": ">=", "not fewer than": ">=", "no lower than": ">=", "not lower than": ">=",
    "no smaller than": ">=", "not smaller than": ">=", "tối thiểu": ">=", "ít nhất": ">=",
    "không dưới": ">=", "không nhỏ hơn": ">=", "không ít hơn": ">=", "không thấp hơn": ">=",
    "from": ">=", "từ": ">=",
    "at most": "<=", "no more than": "<=", "not more than": "<=", "not over": "<=",
    "no greater than": "<=", "not greater than": "<=", "no higher than": "<=", "not higher than": "<=",
    "tối đa": "<=", "không quá": "<=", "không lớn hơn": "<=", "không nhiều hơn": "<=",
    "không cao hơn": "<=", "to": "<=", "đến": "<=", "tới": "<=", "up to": "<=",
}
_COMPARATOR_NAMES = tuple(sorted(_COMPARATOR_ALIASES, key=len, reverse=True))
_COMPARATOR_ALTERNATION = "|".join(re.escape(name) for name in _COMPARATOR_NAMES)
_UNKNOWN_CUES = {
    "less", "fewer", "lower", "smaller", "greater", "more", "higher", "larger", "bigger",
    "least", "most", "minimum", "maximum", "under", "over", "above", "below", "not", "no", "than",
    "ít", "hơn", "kém", "tối thiểu", "tối đa",
    "about", "approximately", "roughly", "around", "nearly", "almost", "xấp", "khoảng", "gần",
}
_UNKNOWN_RANGE_QUALIFIER = r"[^\W\d_]+(?:\s+[^\W\d_]+){0,3}"
_CURRENCY_CODES = ("vnd", "usd", "eur", "gbp", "jpy", "cny", "rmb", "thb", "sgd", "krw", "aud", "cad", "php")
_CURRENCY_PREFIX = re.compile(
    r"(?:^|\s)(?P<unit>" + "|".join(sorted(_CURRENCY_CODES, key=len, reverse=True)) + r")\s*$",
    re.IGNORECASE,
)
_RANGE_NUMBER = re.compile(
    r"(?<!\d)(?P<start>\d+(?:[.,]\d+)*)(?P<start_unit>\s*(?:" + _UNIT_ALTERNATION + r")(?!\w))?"
    r"(?P<connector>\s*[-–—]\s*|\s*(?:đến|tới|to)\s*)"
    r"(?P<end_qualifier>(?:" + _COMPARATOR_ALTERNATION + r"|" + _UNKNOWN_RANGE_QUALIFIER + r"))?\s*"
    r"(?P<end>\d+(?:[.,]\d+)*)(?=\s*(?:" + _UNIT_ALTERNATION + r")(?!\w))",
    re.IGNORECASE,
)
_BOUND_PREFIX = re.compile(
    r"(?:^|[\s,;:(])(?P<qualifier>" + _COMPARATOR_ALTERNATION + r")\s*$",
    re.IGNORECASE,
)
_SUFFIX_COMPARATOR_ALIASES = {
    "trở lên": ">=", "or more": ">=", "or older": ">=", "and above": ">=",
    "trở xuống": "<=", "or less": "<=", "or fewer": "<=", "or younger": "<=",
    "and below": "<=",
}
_SUFFIX_COMPARATOR_NAMES = tuple(sorted(_SUFFIX_COMPARATOR_ALIASES, key=len, reverse=True))
_SUFFIX_COMPARATOR_ALTERNATION = "|".join(
    re.escape(name) for name in _SUFFIX_COMPARATOR_NAMES
)
_BOUND_SUFFIX = re.compile(
    r"^\s*(?P<qualifier>" + _SUFFIX_COMPARATOR_ALTERNATION + r")(?!\w)",
    re.IGNORECASE,
)
_NUMBER = re.compile(r"(?<!\d)(?P<number>\d+(?:[.,]\d+)*)(?!\d)")
_PROHIBITED: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("bank_details", re.compile(r"\b(?:stk|số\s+tài\s+khoản|tài\s+khoản\s+(?:ngân\s+hàng|số)|chuyển\s+khoản\s+vào|bank\s+account)\b", re.IGNORECASE)),
    ("visa_guarantee", re.compile(r"\b(?:chắc\s+chắn\s+(?:được\s+cấp|đậu)\s+visa|đảm\s+bảo\s+(?:đậu|được\s+cấp)\s+visa|visa\s+chắc\s+chắn)\b", re.IGNORECASE)),
    ("availability_claim", re.compile(r"\b(?:chắc\s+chắn\s+còn\s+chỗ|còn\s+chỗ\s+(?:hôm\s+nay|ngày\s+này)|đã\s+xác\s+nhận\s+còn\s+chỗ|guaranteed\s+availability)\b", re.IGNORECASE)),
    ("current_price_claim", re.compile(r"\b(?:giá\s+(?:tour\s+)?(?:hiện\s+(?:tại|nay)|hôm\s+nay|mới\s+nhất)|khuyến\s+mãi\s+hiện\s+đang\s+áp\s+dụng)\b", re.IGNORECASE)),
    ("medical_directive", re.compile(r"\b(?:nên\s+(?:ngừng|dừng|bắt\s+đầu|tăng|giảm)\s+(?:uống\s+)?thuốc|hãy\s+(?:ngừng|dừng|uống)\s+thuốc|ngừng\s+uống\s+thuốc)\b", re.IGNORECASE)),
    ("completed_operation", re.compile(r"\b(?:đã\s+(?:hủy|hoàn\s+tất\s+hủy|xử\s+lý\s+yêu\s+cầu)|yêu\s+cầu\s+hủy.{0,40}đã\s+được\s+xử\s+lý|đã\s+hoàn\s+tiền|refund\s+completed)\b", re.IGNORECASE)),
    ("guaranteed_refund", re.compile(r"\b(?:đảm\s+bảo\s+hoàn\s+tiền|chắc\s+chắn\s+được\s+bồi\s+thường|guaranteed\s+compensation)\b", re.IGNORECASE)),
)


def _content(chunk: Document) -> str:
    return str(chunk.metadata.get("content") or chunk.page_content)


@dataclass(frozen=True)
class NumericFact:
    value: str
    unit: str
    comparator: str = "="


def _canonical_date(year: str, month: str, day: str) -> str | None:
    try:
        return date(int(year), int(month), int(day)).isoformat()
    except ValueError:
        return None


def _decimal_value(value: str) -> Decimal | None:
    normalized = value
    if "." in value and "," in value:
        decimal_separator = "." if value.rfind(".") > value.rfind(",") else ","
        grouping_separator = "," if decimal_separator == "." else "."
        normalized = value.replace(grouping_separator, "").replace(decimal_separator, ".")
    elif "." in value or "," in value:
        separator = "." if "." in value else ","
        pieces = value.split(separator)
        if len(pieces) > 1 and all(len(piece) == 3 for piece in pieces[1:]):
            normalized = "".join(pieces)
        elif len(pieces) == 2:
            normalized = ".".join(pieces)
        else:
            normalized = "".join(pieces[:-1]) + "." + pieces[-1]
    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None


def _normalize_unit(unit: str | None, number_start: int, text: str) -> tuple[str, Decimal]:
    normalized = re.sub(r"\s+", " ", (unit or "").strip().casefold())
    if not normalized and number_start > 0 and text[number_start - 1] in "$€£¥":
        normalized = text[number_start - 1]
    if not normalized:
        prefix = text[max(0, number_start - 12) : number_start]
        currency_match = _CURRENCY_PREFIX.search(prefix)
        if currency_match:
            normalized = currency_match.group("unit").casefold()
    if normalized == "năm":
        unit = "age_year" if "tuổi" in text[max(0, number_start - 18) : number_start + 18].casefold() else "duration_year"
        return unit, Decimal(1)
    return _UNIT_ALIASES.get(normalized, ("scalar", Decimal(1)))


def _bound_before(text: str, position: int, default: str = "=") -> str:
    prefix = text[max(0, position - 48) : position]
    prior_numbers = list(re.finditer(r"\d+", prefix))
    if prior_numbers:
        prefix = prefix[prior_numbers[-1].end() :]
    match = _BOUND_PREFIX.search(prefix)
    if match:
        qualifier = re.sub(r"\s+", " ", match.group("qualifier").casefold())
        return _COMPARATOR_ALIASES[qualifier]

    clause = re.split(r"[.!?;,:]", prefix)[-1].casefold()
    words = re.findall(r"[^\W\d_]+", clause)
    for index, word in enumerate(words):
        if word in _UNKNOWN_CUES:
            phrase = " ".join(words[index:])
            return f"unknown:{phrase}"
    return default


def _bound_after(text: str, position: int) -> str | None:
    unit_match = _UNIT_PATTERN.match(text, position)
    tail_start = unit_match.end() if unit_match else position
    tail = re.split(r"[.!?;,:]", text[tail_start : tail_start + 48])[0].casefold()
    suffix_match = _BOUND_SUFFIX.match(tail)
    if suffix_match:
        qualifier = re.sub(r"\s+", " ", suffix_match.group("qualifier"))
        return _SUFFIX_COMPARATOR_ALIASES[qualifier]
    words = re.findall(r"[^\W\d_]+", tail)
    for index, word in enumerate(words):
        if word in _UNKNOWN_CUES:
            return f"unknown:{' '.join(words[index:])}"
    return None


def _combine_bounds(before: str, after: str | None) -> str:
    if after is None:
        return before
    if before == "=":
        return after
    if before == after:
        return before
    return f"unknown:{before}|{after}"


def _range_end_bound(match: re.Match[str], text: str) -> str:
    qualifier = re.sub(r"\s+", " ", (match.group("end_qualifier") or "").casefold())
    if qualifier:
        before = _COMPARATOR_ALIASES.get(qualifier, f"unknown:{qualifier}")
    else:
        before = "<="
    return _combine_bounds(before, _bound_after(text, match.end("end")))


def _number_facts(text: str) -> set[NumericFact]:
    facts: set[NumericFact] = set()
    date_spans: list[tuple[int, int]] = []
    range_spans: list[tuple[int, int]] = []
    for pattern, order in ((_ISO_DATE, (0, 1, 2)), (_DMY_DATE, (2, 1, 0))):
        for match in pattern.finditer(text):
            parts = match.groups()
            normalized = _canonical_date(*(parts[index] for index in order))
            if normalized:
                facts.add(NumericFact(normalized, "date"))
            else:
                facts.add(NumericFact(match.group(), "invalid_date"))
            date_spans.append(match.span())

    for match in _RANGE_NUMBER.finditer(text):
        if any(match.start() < end and match.end() > start for start, end in date_spans):
            continue
        end_unit_match = _UNIT_PATTERN.match(text, match.end("end"))
        end_unit_text = end_unit_match.group("unit") if end_unit_match else None
        start_unit_text = (match.group("start_unit") or "").strip() or None
        shared_unit = end_unit_text or start_unit_text
        start_unit, start_multiplier = _normalize_unit(start_unit_text or shared_unit, match.start(), text)
        end_unit, end_multiplier = _normalize_unit(end_unit_text or shared_unit, match.start(), text)
        unit = start_unit
        if start_unit != end_unit:
            unit = f"incompatible_range:{start_unit}:{end_unit}"
        start = _decimal_value(match.group("start"))
        end = _decimal_value(match.group("end"))
        if start is not None and end is not None:
            start_value = start * start_multiplier
            end_value = end * end_multiplier
            value = f"{format(start_value.normalize(), 'f')}:{format(end_value.normalize(), 'f')}"
            start_bound = _bound_before(text, match.start(), ">=")
            end_bound = _range_end_bound(match, text)
            facts.add(NumericFact(value, f"range:{unit}", f"{start_bound}:{end_bound}"))
        range_spans.append(match.span())

    for match in _NUMBER.finditer(text):
        if any(
            match.start() < end and match.end() > start
            for start, end in [*date_spans, *range_spans]
        ):
            continue
        raw_unit = _UNIT_PATTERN.match(text, match.end())
        unit_text = raw_unit.group("unit") if raw_unit else None
        unit, multiplier = _normalize_unit(unit_text, match.start(), text)
        number = _decimal_value(match.group("number"))
        if number is None:
            continue
        normalized_value = number * multiplier
        comparator = _combine_bounds(
            _bound_before(text, match.start()), _bound_after(text, match.end("number"))
        )
        facts.add(NumericFact(format(normalized_value.normalize(), "f"), unit, comparator))
    return facts


def _fixed(status: str, text: str) -> TourAnswer:
    return TourAnswer(status=status, answer=text, citation_ids=[], conflicts=[])


def validate_answer(answer: TourAnswer, approved_chunks: Iterable[Document]) -> TourAnswer:
    """Reject answers with unapproved citations, unsupported numbers, or unsafe claims."""
    chunks = list(approved_chunks)
    by_id = {
        str(chunk.metadata.get("chunk_id") or chunk.id): chunk
        for chunk in chunks
        if chunk.metadata.get("chunk_id") or chunk.id
    }
    for name, pattern in _PROHIBITED:
        if pattern.search(answer.answer):
            return _fixed(
                "escalate",
                "Mình chưa thể xác nhận hoặc thực hiện yêu cầu này. Vui lòng liên hệ nhân viên Vietravel để được hỗ trợ.",
            )
    if any(citation not in by_id for citation in answer.citation_ids):
        return _fixed("unsupported", "Mình chưa tìm thấy căn cứ phù hợp trong tài liệu tour để trả lời.")
    if answer.status in {"answered", "conflict"} and not answer.citation_ids:
        return _fixed("unsupported", "Mình chưa tìm thấy căn cứ phù hợp trong tài liệu tour để trả lời.")

    evidence = " ".join(_content(by_id[citation]) for citation in answer.citation_ids)
    supported = _number_facts(evidence)
    answer_facts = _number_facts(answer.answer)
    if any(fact.unit == "invalid_date" for fact in answer_facts):
        return _fixed("unsupported", "Mình chưa thể xác nhận con số này từ tài liệu tour.")
    for fact in answer_facts:
        if fact not in supported:
            return _fixed("unsupported", "Mình chưa thể xác nhận con số này từ tài liệu tour.")
    return answer
