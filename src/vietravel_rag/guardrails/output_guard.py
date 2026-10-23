"""Thin citation and prohibited-claim checks for generated tour answers."""

from __future__ import annotations

import re
from collections.abc import Iterable

from langchain_core.documents import Document

from vietravel_rag.models import TourAnswer

_UNSUPPORTED_ANSWER = "Mình chưa tìm thấy căn cứ phù hợp trong tài liệu tour để trả lời."

_PROHIBITED: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:stk|số\s+tài\s+khoản|tài\s+khoản\s+(?:ngân\s+hàng|số)|chuyển\s+khoản\s+vào|bank\s+account)\b", re.IGNORECASE),
    re.compile(r"\b(?:chắc\s+chắn\s+(?:được\s+cấp|đậu)\s+visa|đảm\s+bảo\s+(?:đậu|được\s+cấp)\s+visa|visa\s+chắc\s+chắn)\b", re.IGNORECASE),
    re.compile(r"\b(?:chắc\s+chắn\s+còn\s+chỗ|còn\s+chỗ\s+(?:hôm\s+nay|ngày\s+này)|đã\s+xác\s+nhận\s+còn\s+chỗ|guaranteed\s+availability)\b", re.IGNORECASE),
    re.compile(r"\b(?:giá\s+(?:tour\s+)?(?:hiện\s+(?:tại|nay)|hôm\s+nay|mới\s+nhất)|khuyến\s+mãi\s+hiện\s+đang\s+áp\s+dụng)\b", re.IGNORECASE),
    re.compile(r"\b(?:nên\s+(?:ngừng|dừng|bắt\s+đầu|tăng|giảm)\s+(?:uống\s+)?thuốc|hãy\s+(?:ngừng|dừng|uống)\s+thuốc|ngừng\s+uống\s+thuốc)\b", re.IGNORECASE),
    re.compile(r"\b(?:đã\s+(?:hủy|hoàn\s+tất\s+hủy|xử\s+lý\s+yêu\s+cầu)|yêu\s+cầu\s+hủy.{0,40}đã\s+được\s+xử\s+lý|đã\s+hoàn\s+tiền|refund\s+completed)\b", re.IGNORECASE),
    re.compile(r"\b(?:đảm\s+bảo\s+hoàn\s+tiền|chắc\s+chắn\s+được\s+bồi\s+thường|guaranteed\s+compensation)\b", re.IGNORECASE),
)


def validate_answer(answer: TourAnswer, approved_chunks: Iterable[Document]) -> TourAnswer:
    """Reject unsafe claims and citations outside the approved evidence set."""
    if any(pattern.search(answer.answer) for pattern in _PROHIBITED):
        return answer.model_copy(update={
            "status": "escalate",
            "answer": "Yêu cầu này cần được nhân viên Vietravel hoặc chuyên gia phù hợp hỗ trợ trực tiếp.",
            "citation_ids": [],
        })

    approved_ids = {
        str(chunk.metadata["chunk_id"])
        for chunk in approved_chunks
        if chunk.metadata.get("chunk_id") is not None
    }
    if any(citation_id not in approved_ids for citation_id in answer.citation_ids):
        return answer.model_copy(update={
            "status": "unsupported", "answer": _UNSUPPORTED_ANSWER, "citation_ids": []
        })
    if answer.status in {"answered", "conflict"} and not answer.citation_ids:
        return answer.model_copy(update={
            "status": "unsupported", "answer": _UNSUPPORTED_ANSWER, "citation_ids": []
        })
    return answer
