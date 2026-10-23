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
_UNIT_NAMES = (
    "phần trăm", "years old", "kilometers", "kilometres", "centimeters", "centimetres",
    "millimeters", "millimetres", "milliliters", "millilitres", "passengers", "kilograms",
    "fahrenheit", "celsius", "minutes", "seconds", "months", "nights", "tickets", "people",
    "persons", "meters", "metres", "liters", "litres", "hours", "weeks", "years", "rooms",
    "seats", "người lớn", "nghìn", "ngàn", "ngày", "đêm", "tuần", "tháng", "năm", "tuổi",
    "giờ", "tiếng", "phút", "giây", "khách", "người", "triệu", "tỷ", "đồng", "tấn", "lít", "pax",
    "percent", "kilometer", "kilometre", "centimeter", "centimetre", "millimeter", "millimetre",
    "milliliter", "millilitre", "kilogram", "minute", "second", "month", "night", "ticket",
    "person", "meter", "metre", "liter", "litre", "hour", "week", "year", "room", "seat",
    "fahrenheit", "celsius", "km", "cm", "mm", "ml", "kg", "gram", "grams", "ton", "usd",
    "vnd", "eur", "gbp", "cny", "rmb", "jpy", "thb", "sgd", "krw", "aud", "cad", "php",
    "day", "days", "g", "l", "°c", "°f", "%", "đ", "$", "€", "£", "¥",
)
_UNIT_PATTERN = re.compile(
    r"\s*(?P<unit>" + "|".join(re.escape(unit) for unit in _UNIT_NAMES) + r")(?!\w)",
    re.IGNORECASE,
)
_RANGE_NUMBER = re.compile(
    r"(?<!\d)(?P<start>\d+(?:[.,]\d+)*)(?:\s*[-–—]\s*|\s*(?:đến|tới|to)\s*(?:(?:dưới|trên|under|over|below|above)\s*)?)"
    r"(?P<end>\d+(?:[.,]\d+)*)(?=\s*(?:" + "|".join(re.escape(unit) for unit in _UNIT_NAMES) + r")(?!\w))",
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
    if not normalized and number_start > 0 and text[number_start - 1] in "$€£":
        normalized = text[number_start - 1]
    if normalized in {"%", "phần trăm", "percent"}:
        return "percent", Decimal(1)
    if normalized in {"đ", "đồng", "vnd"}:
        return "currency_vnd", Decimal(1)
    if normalized in {"$", "usd"}:
        return "currency_usd", Decimal(1)
    if normalized in {"€", "eur"}:
        return "currency_eur", Decimal(1)
    if normalized in {"£", "gbp"}:
        return "currency_gbp", Decimal(1)
    if normalized in {"¥", "jpy"}:
        return "currency_yen", Decimal(1)
    if normalized in {"cny", "rmb"}:
        return "currency_cny", Decimal(1)
    if normalized == "thb":
        return "currency_thb", Decimal(1)
    if normalized == "sgd":
        return "currency_sgd", Decimal(1)
    if normalized == "krw":
        return "currency_krw", Decimal(1)
    if normalized == "aud":
        return "currency_aud", Decimal(1)
    if normalized == "cad":
        return "currency_cad", Decimal(1)
    if normalized == "php":
        return "currency_php", Decimal(1)
    if normalized == "triệu":
        return "currency_unspecified", Decimal(1_000_000)
    if normalized in {"tỷ"}:
        return "currency_unspecified", Decimal(1_000_000_000)
    if normalized in {"nghìn", "ngàn"}:
        return "currency_unspecified", Decimal(1_000)
    if normalized in {"kg", "kilogram", "kilograms"}:
        return "mass_gram", Decimal(1_000)
    if normalized in {"g", "gram", "grams"}:
        return "mass_gram", Decimal(1)
    if normalized in {"tấn", "ton"}:
        return "mass_gram", Decimal(1_000_000)
    if normalized in {"km", "kilometer", "kilometers", "kilometre", "kilometres"}:
        return "length_metre", Decimal(1_000)
    if normalized in {"mét", "meter", "meters", "metre", "metres"}:
        return "length_metre", Decimal(1)
    if normalized in {"cm", "centimeter", "centimeters", "centimetre", "centimetres"}:
        return "length_metre", Decimal("0.01")
    if normalized in {"mm", "millimeter", "millimeters", "millimetre", "millimetres"}:
        return "length_metre", Decimal("0.001")
    if normalized in {"l", "lít", "liter", "liters", "litre", "litres"}:
        return "volume_ml", Decimal(1_000)
    if normalized in {"ml", "milliliter", "milliliters", "millilitre", "millilitres"}:
        return "volume_ml", Decimal(1)
    if normalized in {"ngày", "day", "days"}:
        return "duration_day", Decimal(1)
    if normalized in {"đêm", "night", "nights"}:
        return "duration_night", Decimal(1)
    if normalized in {"tuần", "week", "weeks"}:
        return "duration_week", Decimal(1)
    if normalized in {"tháng", "month", "months"}:
        return "duration_month", Decimal(1)
    if normalized in {"năm", "year", "years"}:
        return "age_year" if "tuổi" in text[max(0, number_start - 18) : number_start + 18].casefold() else "duration_year", Decimal(1)
    if normalized in {"tuổi", "years old"}:
        return "age_year", Decimal(1)
    if normalized in {"giờ", "tiếng", "hour", "hours"}:
        return "duration_hour", Decimal(1)
    if normalized in {"phút", "minute", "minutes"}:
        return "duration_minute", Decimal(1)
    if normalized in {"giây", "second", "seconds"}:
        return "duration_second", Decimal(1)
    if normalized in {"khách", "người", "người lớn", "pax", "person", "persons", "people", "passenger", "passengers"}:
        return "people", Decimal(1)
    if normalized in {"phòng", "room", "rooms"}:
        return "rooms", Decimal(1)
    if normalized in {"vé", "ticket", "tickets", "chỗ", "seat", "seats"}:
        return "seats", Decimal(1)
    if normalized in {"°c", "celsius"}:
        return "temperature_c", Decimal(1)
    if normalized in {"°f", "fahrenheit"}:
        return "temperature_f", Decimal(1)
    return "scalar", Decimal(1)


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
        unit_match = _UNIT_PATTERN.match(text, match.end("end"))
        unit_text = unit_match.group("unit") if unit_match else None
        unit, multiplier = _normalize_unit(unit_text, match.start(), text)
        for endpoint in ("start", "end"):
            number = _decimal_value(match.group(endpoint))
            if number is not None:
                value = number * multiplier
                facts.add(NumericFact(format(value.normalize(), "f"), unit))
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
        facts.add(NumericFact(format(normalized_value.normalize(), "f"), unit))
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
