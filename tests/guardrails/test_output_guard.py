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


def test_numeric_unit_swap_from_weight_to_percent_is_rejected():
    result = validate_answer(
        answer("Hành lý xách tay 10%/khách.", ["baggage"]),
        [chunk("baggage", "Hành lý xách tay 10kg/khách")],
    )

    assert result.status == "unsupported"


def test_numeric_unit_swap_from_percent_to_people_is_rejected():
    result = validate_answer(
        answer("Trẻ em tính 75 khách giá người lớn.", ["child-price"]),
        [chunk("child-price", "Trẻ em tính 75% giá người lớn")],
    )

    assert result.status == "unsupported"


def test_day_and_night_duration_units_are_not_interchangeable():
    result = validate_answer(
        answer("Tour kéo dài 10 ngày.", ["duration"]),
        [chunk("duration", "Tour kéo dài 10 đêm")],
    )

    assert result.status == "unsupported"


def test_currency_units_are_not_interchangeable():
    result = validate_answer(
        answer("Chi phí là 10 USD.", ["cost"]),
        [chunk("cost", "Chi phí là 10 VND")],
    )

    assert result.status == "unsupported"


def test_equivalent_currency_symbol_and_code_are_accepted():
    result = validate_answer(
        answer("Chi phí là $10.", ["cost"]),
        [chunk("cost", "Chi phí là 10 USD")],
    )

    assert result.status == "answered"


def test_equivalent_date_formats_are_accepted():
    result = validate_answer(
        answer("Ngày khởi hành là 2026-10-23.", ["date"]),
        [chunk("date", "Ngày khởi hành 23/10/2026")],
    )

    assert result.status == "answered"


def test_invalid_calendar_date_is_rejected():
    result = validate_answer(
        answer("Ngày khởi hành là 2026-02-31.", ["date"]),
        [chunk("date", "Ngày khởi hành 31/02/2026")],
    )

    assert result.status == "unsupported"


def test_shared_range_unit_applies_to_both_numeric_endpoints():
    result = validate_answer(
        answer("Tour kéo dài từ 10 ngày đến 13 ngày.", ["duration"]),
        [chunk("duration", "Tour kéo dài 10-13 ngày")],
    )

    assert result.status == "answered"


def test_vietnamese_hour_synonym_is_normalized():
    result = validate_answer(
        answer("Chương trình di chuyển trong 2 giờ.", ["time"]),
        [chunk("time", "Chương trình di chuyển trong 2 tiếng")],
    )

    assert result.status == "answered"


def test_age_range_propagates_shared_age_unit_to_both_endpoints():
    result = validate_answer(
        answer("Trẻ từ 5 tuổi đến dưới 12 tuổi được áp dụng mức giá này.", ["child"]),
        [chunk("child", "Trẻ từ 5 đến dưới 12 tuổi được áp dụng mức giá này")],
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
