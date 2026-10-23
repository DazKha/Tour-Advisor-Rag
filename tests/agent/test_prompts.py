import re

from vietravel_rag.agent.prompts import (
    ANSWER_GENERATION_SYSTEM_PROMPT,
    QUERY_ANALYSIS_SYSTEM_PROMPT,
)


def test_answer_prompt_sets_consultant_voice_and_shows_three_vietnamese_examples():
    prompt = ANSWER_GENERATION_SYSTEM_PROMPT

    assert "polite Vietnamese consultant" in prompt
    assert "Answer the question directly" in prompt
    assert "summarize only relevant" in prompt
    assert "Use anh/chị sparingly" in prompt
    assert "Factual answer" in prompt and "Itinerary answer" in prompt and "Conflict answer" in prompt
    assert "Dạ," in prompt
    assert "Never use the Unicode bullet character •" in prompt
    assert "CommonMark" in prompt and "- " in prompt and "blank line before a list" in prompt
    assert "one itinerary day per line" in prompt
    assert "Do not begin every answer with ‘Theo tài liệu’" in prompt
    assert "23kg" in prompt and "20kg" in prompt and "10kg" in prompt and "7kg" in prompt
    assert "Căn cước công dân" not in prompt


def test_query_analysis_distinguishes_documented_dates_from_live_availability_follow_up():
    prompt = QUERY_ANALYSIS_SYSTEM_PROMPT.casefold()

    assert "documented departure and return dates" in prompt
    assert "live seat availability" in prompt
    assert "current/live capacity" in prompt
    assert "whether the tour can be booked now" in prompt
    assert "“đi từ ngày mấy đến ngày mấy?”" in prompt
    assert "bangkok–pattaya schedule question" in prompt
    assert 'intent `itinerary`' in prompt


def test_factual_few_shot_price_is_grounded_in_its_paired_evidence_and_question():
    match = re.search(
        r'Factual answer: Evidence: “(?P<evidence>.*?)” User question: '
        r'“(?P<question>.*?)” Assistant answer: “(?P<answer>.*?)”',
        ANSWER_GENERATION_SYSTEM_PROMPT,
        re.DOTALL,
    )

    assert match is not None
    assert "danang-central-5d4n_price_01" in match["evidence"]
    assert "8,990,000₫" in match["evidence"]
    assert match["question"] == "Giá tour Đà Nẵng cho người lớn bao nhiêu?"
    assert "8,990,000₫" in match["answer"]


def test_itinerary_few_shot_pairs_evidence_and_question_with_grounded_commonmark_route():
    match = re.search(
        r'Itinerary answer: Illustrative evidence: “(?P<evidence>.*?)” User question: '
        r'“(?P<question>.*?)” Assistant answer: “(?P<answer>.*?)”',
        ANSWER_GENERATION_SYSTEM_PROMPT,
        re.DOTALL,
    )

    assert match is not None
    assert "danang-central-5d4n_itinerary_01" in match["evidence"]
    assert "Sơn Trà" in match["evidence"] and "Phố Cổ Hội An" in match["evidence"]
    assert match["question"] == "Lịch trình ngày đầu của tour Đà Nẵng gồm những gì?"
    assert "\\n" not in match["answer"]
    assert "\n- **Ngày 1 – TP. Hồ Chí Minh – Đà Nẵng – Sơn Trà – Phố Cổ Hội An:**" in match["answer"]


def test_itinerary_conflict_example_answers_supported_route_before_conflict_note():
    match = re.search(
        r'Itinerary conflict answer: Illustrative evidence: “(?P<evidence>.*?)” User question: '
        r'“(?P<question>.*?)” Assistant answer: “(?P<answer>.*?)”',
        ANSWER_GENERATION_SYSTEM_PROMPT,
        re.DOTALL,
    )

    assert match is not None
    assert "danang-central-5d4n_itinerary_01" in match["evidence"]
    assert "danang-central-5d4n_included_01" in match["evidence"]
    assert "danang-central-5d4n_registration_notes_01" in match["evidence"]
    assert match["question"] == "Lịch trình ngày đầu và hạn mức hành lý của tour Đà Nẵng ra sao?"
    answer = match["answer"]
    route_index = answer.index("- **Ngày 1 –")
    heading_index = answer.index("**Điểm anh/chị nên lưu ý**")
    assert route_index < heading_index
    assert "\n\n**Điểm anh/chị nên lưu ý**\n\n" in answer
    assert "Hai phần tài liệu ghi mức hành lý khác nhau" in answer
    assert "lịch trình có thể linh hoạt" not in answer


def test_answer_prompt_limits_itinerary_caveats_to_supported_evidence():
    assert "Do not append generic caveats such as `lịch trình có thể linh hoạt`" in (
        ANSWER_GENERATION_SYSTEM_PROMPT
    )


def test_answer_prompt_requires_question_focused_grounded_output():
    prompt = ANSWER_GENERATION_SYSTEM_PROMPT
    assert "Use only evidence needed to answer the user's exact question" in prompt
    assert "Do not summarize unrelated retrieved chunks" in prompt
    assert "Every factual claim and number must be supported" in prompt
    assert "Prefer one short paragraph" in prompt
    assert "Cite every chunk used for the answer" in prompt


def test_conflict_few_shot_pairs_illustrative_evidence_and_uses_natural_wording():
    match = re.search(
        r'Conflict answer: Evidence: “(?P<evidence>.*?)” User question: '
        r'“(?P<question>.*?)” Assistant answer: “(?P<answer>.*?)”',
        ANSWER_GENERATION_SYSTEM_PROMPT,
        re.DOTALL,
    )

    assert match is not None
    assert "23kg" in match["evidence"] and "20kg" in match["evidence"]
    assert match["question"] == "Hành lý ký gửi của tour Đà Nẵng quy định ra sao?"
    assert "điểm anh/chị nên lưu ý" in match["answer"]
    assert "Dạ, Điểm" not in match["answer"]
    assert "•" not in match["answer"]
