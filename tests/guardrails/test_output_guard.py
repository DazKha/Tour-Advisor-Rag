from langchain_core.documents import Document

from vietravel_rag.guardrails.output_guard import validate_answer
from vietravel_rag.models import TourAnswer


def chunk(chunk_id, content="Official tour fact"):
    return Document(page_content=content, metadata={"chunk_id": chunk_id, "content": content})


def answer(text, citations=None, status="answered"):
    return TourAnswer(status=status, answer=text, citation_ids=citations or [], conflicts=[])


def test_unknown_citation_is_rejected():
    result = validate_answer(answer("A possibly invented claim.", ["invented"]), [chunk("real")])

    assert result.status == "unsupported"
    assert result.answer == "Mình chưa tìm thấy căn cứ phù hợp trong tài liệu tour để trả lời."
    assert result.citation_ids == []


def test_answered_response_without_citations_is_rejected():
    result = validate_answer(answer("A possibly invented claim."), [chunk("real")])

    assert result.status == "unsupported"
    assert result.answer == "Mình chưa tìm thấy căn cứ phù hợp trong tài liệu tour để trả lời."
    assert result.citation_ids == []


def test_known_citation_allows_separator_reformatting_of_number():
    result = validate_answer(answer("The price is 8,990,000 VND.", ["price-1"]), [chunk("price-1", "Price is 8.990.000 VND")])

    assert result.status == "answered"


def test_unsupported_response_without_citations_remains_valid():
    original = answer("Insufficient evidence.", status="unsupported")

    assert validate_answer(original, []) == original


def test_each_prohibited_claim_category_escalates():
    claims = [
        "Số tài khoản là 123456.",
        "Đảm bảo đậu visa.",
        "Chắc chắn còn chỗ hôm nay.",
        "Giá tour hiện tại là 8 triệu.",
        "Bạn nên ngừng uống thuốc.",
        "Đã hoàn tiền cho bạn.",
        "Đảm bảo hoàn tiền.",
    ]

    for claim in claims:
        result = validate_answer(answer(claim, ["known"]), [chunk("known")])
        assert result.status == "escalate", claim
        assert "123456" not in result.answer
