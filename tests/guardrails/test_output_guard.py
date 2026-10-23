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


def test_room_count_cannot_be_claimed_as_length():
    result = validate_answer(
        answer("Có 2 mét.", ["inventory"]),
        [chunk("inventory", "Có 2 phòng.")],
    )

    assert result.status == "unsupported"


def test_seat_count_cannot_be_claimed_as_room_count():
    result = validate_answer(
        answer("Có 3 phòng.", ["inventory"]),
        [chunk("inventory", "Có 3 chỗ.")],
    )

    assert result.status == "unsupported"


def test_reversed_numeric_range_is_rejected():
    result = validate_answer(
        answer("Tour dài từ 13 đến 10 ngày.", ["duration"]),
        [chunk("duration", "Tour dài 10-13 ngày")],
    )

    assert result.status == "unsupported"


def test_equivalent_range_wording_preserves_order():
    result = validate_answer(
        answer("Tour dài từ 10 đến 13 ngày.", ["duration"]),
        [chunk("duration", "Tour dài 10-13 ngày")],
    )

    assert result.status == "answered"


def test_dropping_strict_upper_bound_from_age_range_is_rejected():
    result = validate_answer(
        answer("Trẻ từ 5 đến 12 tuổi được áp dụng mức giá này.", ["child"]),
        [chunk("child", "Trẻ từ 5 đến dưới 12 tuổi được áp dụng mức giá này")],
    )

    assert result.status == "unsupported"


def test_dropping_strict_bound_from_scalar_age_is_rejected():
    result = validate_answer(
        answer("Trẻ 12 tuổi được áp dụng mức giá này.", ["child"]),
        [chunk("child", "Trẻ dưới 12 tuổi được áp dụng mức giá này")],
    )

    assert result.status == "unsupported"


def test_equivalent_strict_bound_synonyms_are_accepted():
    result = validate_answer(
        answer("Trẻ dưới 12 tuổi.", ["child"]),
        [chunk("child", "Children under 12 years old.")],
    )

    assert result.status == "answered"


def test_inclusive_minimum_bound_synonyms_are_accepted():
    result = validate_answer(
        answer("Ít nhất 5 khách.", ["capacity"]),
        [chunk("capacity", "At least 5 people.")],
    )

    assert result.status == "answered"


def test_inclusive_maximum_bound_synonyms_are_accepted():
    result = validate_answer(
        answer("Tối đa 5 khách.", ["capacity"]),
        [chunk("capacity", "Up to 5 people.")],
    )

    assert result.status == "answered"


def test_strict_greater_than_bound_synonyms_are_accepted():
    result = validate_answer(
        answer("Children over 5 years old.", ["child"]),
        [chunk("child", "Trẻ trên 5 tuổi.")],
    )

    assert result.status == "answered"


def test_changing_strict_range_bound_to_inclusive_is_rejected():
    result = validate_answer(
        answer("Trẻ từ 5 đến tối đa 12 tuổi.", ["child"]),
        [chunk("child", "Trẻ từ 5 đến dưới 12 tuổi")],
    )

    assert result.status == "unsupported"


def test_greater_than_start_bound_cannot_replace_from_minimum_range():
    result = validate_answer(
        answer("More than 5 to 12 years old.", ["age"]),
        [chunk("age", "From 5 to 12 years old.")],
    )

    assert result.status == "unsupported"


def test_negated_strict_phrase_is_not_misread_as_its_suffix():
    result = validate_answer(
        answer("Under 12 years old.", ["age"]),
        [chunk("age", "Not under 12 years old.")],
    )

    assert result.status == "unsupported"


def test_more_than_and_greater_than_are_equivalent_strict_bounds():
    result = validate_answer(
        answer("Greater than 5 people.", ["capacity"]),
        [chunk("capacity", "More than 5 people.")],
    )

    assert result.status == "answered"


def test_negated_minimum_synonyms_are_equivalent():
    result = validate_answer(
        answer("Không dưới 5 khách.", ["capacity"]),
        [chunk("capacity", "No less than 5 people.")],
    )

    assert result.status == "answered"


def test_negated_maximum_synonyms_are_equivalent():
    result = validate_answer(
        answer("Không quá 5 khách.", ["capacity"]),
        [chunk("capacity", "No more than 5 people.")],
    )

    assert result.status == "answered"


def test_prefix_currency_codes_match_suffix_currency_forms():
    vnd = validate_answer(
        answer("Giá 8.990.000đ.", ["price"]),
        [chunk("price", "Giá VND 8,990,000.")],
    )
    usd = validate_answer(
        answer("Giá USD 100.", ["usd-price"]),
        [chunk("usd-price", "Giá $100.")],
    )

    assert vnd.status == "answered"
    assert usd.status == "answered"


def test_comparator_vocabulary_normalizes_all_strict_synonyms():
    cases = [
        ("More than 5 people.", "Greater than 5 people."),
        ("Over 5 people.", "Above 5 people."),
        ("Trên 5 khách.", "More than 5 people."),
        ("Under 5 years old.", "Below 5 years old."),
        ("Below 5 years old.", "Dưới 5 tuổi."),
    ]

    for index, (evidence, claim) in enumerate(cases):
        result = validate_answer(answer(claim, [str(index)]), [chunk(str(index), evidence)])
        assert result.status == "answered", (evidence, claim)


def test_comparator_vocabulary_normalizes_all_inclusive_minimum_synonyms():
    cases = [
        ("At least 5 people.", "Not under 5 people."),
        ("No less than 5 people.", "Không dưới 5 khách."),
        ("Not under 5 people.", "Tối thiểu 5 khách."),
        ("Từ 5 khách.", "From 5 people."),
        ("Ít nhất 5 khách.", "At least 5 people."),
    ]

    for index, (evidence, claim) in enumerate(cases):
        result = validate_answer(answer(claim, [str(index)]), [chunk(str(index), evidence)])
        assert result.status == "answered", (evidence, claim)


def test_comparator_vocabulary_normalizes_all_inclusive_maximum_synonyms():
    cases = [
        ("At most 5 people.", "No more than 5 people."),
        ("No more than 5 people.", "Not over 5 people."),
        ("Not over 5 people.", "Không quá 5 khách."),
        ("Tối đa 5 khách.", "Up to 5 people."),
        ("Đến 5 khách.", "To 5 people."),
        ("Tới 5 khách.", "At most 5 people."),
    ]

    for index, (evidence, claim) in enumerate(cases):
        result = validate_answer(answer(claim, [str(index)]), [chunk(str(index), evidence)])
        assert result.status == "answered", (evidence, claim)


def test_range_end_accepts_negated_inclusive_maximum_synonyms():
    result = validate_answer(
        answer("Trẻ từ 5 đến tối đa 12 tuổi.", ["age"]),
        [chunk("age", "From 5 to no more than 12 years old.")],
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
