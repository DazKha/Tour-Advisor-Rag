from vietravel_rag.agent.prompts import ANSWER_GENERATION_SYSTEM_PROMPT


def test_answer_prompt_sets_consultant_voice_and_shows_three_vietnamese_examples():
    prompt = ANSWER_GENERATION_SYSTEM_PROMPT

    assert "polite Vietnamese consultant" in prompt
    assert "Answer the question directly" in prompt
    assert "summarize only relevant" in prompt
    assert "Use anh/chị sparingly" in prompt
    assert "Factual answer" in prompt and "Itinerary answer" in prompt and "Conflict answer" in prompt
    assert "Dạ," in prompt
    assert "•" in prompt
    assert "23kg" in prompt and "20kg" in prompt and "10kg" in prompt and "7kg" in prompt
    assert "Căn cước công dân" not in prompt
