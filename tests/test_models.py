import pytest
from pydantic import ValidationError

from vietravel_rag.models import QueryAnalysis, TourAnswer


def test_query_analysis_accepts_follow_up_rewrite():
    value = QueryAnalysis(
        intent="child_price",
        tour_references=["Bangkok – Pattaya"],
        standalone_query="Giá trẻ em 8 tuổi của tour Bangkok – Pattaya là bao nhiêu?",
    )

    assert value.intent == "child_price"


def test_tour_answer_rejects_unknown_status():
    with pytest.raises(ValidationError):
        TourAnswer(status="maybe", answer="", citation_ids=[], conflicts=[])
