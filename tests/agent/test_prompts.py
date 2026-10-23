import re

from vietravel_rag.agent.prompts import ANSWER_GENERATION_SYSTEM_PROMPT


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


def test_itinerary_few_shot_uses_literal_newlines_and_commonmark_items():
    match = re.search(
        r'Itinerary answer:.*?Assistant answer: “(?P<answer>.*?)”',
        ANSWER_GENERATION_SYSTEM_PROMPT,
        re.DOTALL,
    )

    assert match is not None
    assert "\\n" not in match["answer"]
    assert "\n- Ngày 1:" in match["answer"]
    assert "\n- Ngày 2:" in match["answer"]


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
    assert "Điểm anh/chị nên lưu ý" in match["answer"]
    assert "•" not in match["answer"]
