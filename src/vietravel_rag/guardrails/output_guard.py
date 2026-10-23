"""Deterministic citation, factual-number, and prohibited-claim validation."""

from __future__ import annotations

import re
from collections.abc import Iterable

from langchain_core.documents import Document

from vietravel_rag.models import TourAnswer

_NUMBER = re.compile(r"(?<!\d)\d+(?:[.,/\-]\d+)*(?!\d)")
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


def _normalized_number(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    return str(int(digits)) if digits else ""


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
    supported = {_normalized_number(match.group()) for match in _NUMBER.finditer(evidence)}
    for match in _NUMBER.finditer(answer.answer):
        if _normalized_number(match.group()) not in supported:
            return _fixed("unsupported", "Mình chưa thể xác nhận con số này từ tài liệu tour.")
    return answer
