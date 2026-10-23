from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from vietravel_rag.agent.nodes import analyze_query
from vietravel_rag.models import QueryAnalysis


class FakeStructuredModel:
    def __init__(self, response):
        self.response = response
        self.schema = None
        self.messages = None

    def with_structured_output(self, schema):
        self.schema = schema
        return self

    def invoke(self, messages):
        self.messages = messages
        return self.response


def test_follow_up_inherits_active_tour_and_uses_structured_analysis():
    model = FakeStructuredModel(
        QueryAnalysis(
            intent="child_price",
            tour_references=["Bangkok – Pattaya"],
            standalone_query="Giá trẻ em 8 tuổi của tour Bangkok – Pattaya là bao nhiêu?",
        )
    )
    state = {
        "messages": [
            HumanMessage(content="Tour Thái Lan giá bao nhiêu?"),
            AIMessage(content="Mình sẽ kiểm tra theo tài liệu tour."),
            HumanMessage(content="Bé 8 tuổi thì sao?"),
        ],
        "active_tour_codes": ["thailand-bangkok-pattaya"],
    }

    result = analyze_query(state, model)

    assert model.schema is QueryAnalysis
    assert result["query_analysis"].intent == "child_price"
    assert "Bangkok" in result["query_analysis"].standalone_query
    assert any(isinstance(message, SystemMessage) for message in model.messages)
    assert model.messages[-1].content == "Bé 8 tuổi thì sao?"
    assert "thailand-bangkok-pattaya" in model.messages[0].content


def test_explicit_tour_reference_is_preserved_and_no_tour_is_not_invented():
    model = FakeStructuredModel(
        QueryAnalysis(
            intent="baggage",
            tour_references=[],
            standalone_query="Hành lý của tour miền Tây được mang bao nhiêu?",
        )
    )

    result = analyze_query(
        {"messages": [HumanMessage(content="Hành lý của tour miền Tây thế nào?")]}, model
    )

    assert result["query_analysis"].tour_references == ["miền Tây"]
    prompt = model.messages[0].content
    assert "never invent tour codes" in prompt.casefold()
    assert "or answer the user" in prompt.casefold()


def test_uninferable_tour_reference_stays_empty():
    model = FakeStructuredModel(
        QueryAnalysis(
            intent="general",
            tour_references=[],
            standalone_query="Bạn có thể giúp gì về các tour?",
        )
    )

    result = analyze_query(
        {"messages": [HumanMessage(content="Bạn có thể giúp gì?")]}, model
    )

    assert result["query_analysis"].tour_references == []
