"""Input screening and privacy-safe redaction helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class InputDecision:
    route: str
    message: str | None = None


_INJECTION = re.compile(
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?"
    r"|ignore\s+(all\s+)?rules?"
    r"|ignore\s+(all\s+)?instructions?"
    r"|bỏ qua\s+(mọi\s+)?(chỉ dẫn|quy tắc|hướng dẫn)"
    r"|tiết lộ\s+(system prompt|chỉ dẫn hệ thống)"
    r"|reveal\s+(the\s+)?(system prompt|hidden instructions)"
    r"|forget\s+(all\s+)?(previous|prior)\s+instructions?",
    re.IGNORECASE,
)
_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE = re.compile(r"(?<!\w)(?:\+?84|0)(?:[ .-]?\d){8,10}(?!\w)")
_LONG_DIGITS = re.compile(r"(?<!\d)(?:\d[ .-]?){9,}(?!\d)")


def validate_input(text: str) -> InputDecision:
    """Return a safe route for empty, oversized, or injection-like input."""
    if not text or not text.strip():
        return InputDecision("clarification", "Bạn muốn hỏi thông tin nào về tour?")
    if len(text) > 2000:
        return InputDecision("clarification", "Vui lòng gửi câu hỏi ngắn hơn (tối đa 2.000 ký tự).")
    if _INJECTION.search(text):
        return InputDecision(
            "safe_response",
            "Mình chỉ có thể hỗ trợ thông tin tour dựa trên tài liệu được cung cấp.",
        )
    return InputDecision("continue")


def redact_pii(text: str) -> str:
    """Mask emails, Vietnamese phone numbers, and long digit sequences."""
    redacted = _EMAIL.sub("[REDACTED_EMAIL]", text)
    redacted = _PHONE.sub("[REDACTED_PHONE]", redacted)
    return _LONG_DIGITS.sub("[REDACTED_NUMBER]", redacted)
