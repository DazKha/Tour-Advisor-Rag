from langchain_core.documents import Document

from vietravel_rag.guardrails.output_guard import validate_answer
from vietravel_rag.models import TourAnswer


def chunk(chunk_id, content):
    return Document(page_content=content, metadata={"chunk_id": chunk_id, "content": content})


def answer(text, citations=None, status="answered"):
    return TourAnswer(
        status=status,
        answer=text,
        citation_ids=citations or [],
        conflicts=[],
    )


def test_unknown_citation_is_rejected():
    result = validate_answer(
        answer("Giá tour có trong tài liệu.", ["invented"]), [chunk("real", "Giá tour")]
    )

    assert result.status == "unsupported"


def test_unsupported_number_is_rejected():
    result = validate_answer(
        answer("Giá là 7.000.000đ", ["price-1"]),
        [chunk("price-1", "Giá 8.990.000đ")],
    )

    assert result.status == "unsupported"


def test_numeric_claim_accepts_normalized_separators():
    result = validate_answer(
        answer("Giá là 8,990,000đ", ["price-1"]),
        [chunk("price-1", "Giá 8.990.000đ")],
    )

    assert result.status == "answered"


def test_numeric_range_claim_matches_unicode_dash_in_source():
    result = validate_answer(
        answer("Phòng dành cho 2–3 khách.", ["room"]),
        [chunk("room", "Phòng tiêu chuẩn 2–3 khách/phòng")],
    )

    assert result.status == "answered"


def test_account_number_is_never_repeated():
    result = validate_answer(
        answer("Chuyển khoản vào tài khoản 123456789012.", ["bank"]),
        [chunk("bank", "Số tài khoản 123456789012")],
    )

    assert result.status == "escalate"
    assert "123456789012" not in result.answer


def test_bank_details_with_stk_abbreviation_are_never_repeated():
    result = validate_answer(
        answer("STK 123456789012.", ["bank"]),
        [chunk("bank", "Số tài khoản 123456789012")],
    )

    assert result.status == "escalate"
    assert "123456789012" not in result.answer


def test_visa_guarantee_is_rejected():
    result = validate_answer(
        answer("Hồ sơ này chắc chắn được cấp visa.", ["visa"]),
        [chunk("visa", "Hồ sơ xin visa cần chuẩn bị đầy đủ")],
    )

    assert result.status == "escalate"


def test_live_availability_claim_is_rejected():
    result = validate_answer(
        answer("Tour chắc chắn còn chỗ hôm nay.", ["availability"]),
        [chunk("availability", "Cần liên hệ nhân viên để kiểm tra")],
    )

    assert result.status == "escalate"


def test_medical_directive_is_rejected():
    result = validate_answer(
        answer("Bạn nên ngừng uống thuốc trước chuyến đi.", ["health"]),
        [chunk("health", "Khách có bệnh nền vui lòng tham khảo bác sĩ")],
    )

    assert result.status == "escalate"


def test_claim_that_cancellation_was_executed_is_rejected():
    result = validate_answer(
        answer("Yêu cầu hủy tour của bạn đã được xử lý.", ["cancel"]),
        [chunk("cancel", "Vui lòng liên hệ nhân viên để được hỗ trợ")],
    )

    assert result.status == "escalate"
