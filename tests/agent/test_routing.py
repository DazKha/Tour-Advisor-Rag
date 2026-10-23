from typing import get_type_hints

from langchain_core.documents import Document

from vietravel_rag.agent.nodes import direct_response_node, resolve_tour_node, retrieve_node
from vietravel_rag.models import AgentState, QueryAnalysis


def analysis(intent="price", refs=None, query="Giá tour bao nhiêu?"):
    return QueryAnalysis(
        intent=intent,
        tour_references=refs or [],
        standalone_query=query,
    )


def summary(code, name=None):
    return Document(
        page_content=f"Tóm tắt {name or code}",
        metadata={
            "tour_code": code,
            "tour_name": name or code,
            "document_type": "tour_summary",
        },
    )


def test_off_topic_and_general_route_without_tour_search():
    calls = []

    def resolver(query):
        calls.append(query)
        return []

    off_topic = resolve_tour_node({"query_analysis": analysis("off_topic")}, resolver)
    general = resolve_tour_node({"query_analysis": analysis("general")}, resolver)

    assert off_topic["route"] == "safe_response"
    assert general["route"] == "general"
    assert calls == []


def test_general_route_returns_a_purposeful_capability_response():
    result = direct_response_node({"route": "general"})

    assert result["response"]["status"] == "answered"
    assert "lịch trình" in result["response"]["answer"].casefold()


def test_general_response_replaces_a_previous_turn_response():
    result = direct_response_node({
        "route": "general",
        "input_decision": "continue",
        "response": {
            "status": "answered",
            "answer": "Giá tour là 8.990.000đ.",
            "citation_ids": ["old-price"],
            "conflicts": [],
        },
    })

    assert "lịch trình" in result["response"]["answer"].casefold()
    assert result["response"]["citation_ids"] == []


def test_one_candidate_updates_active_tour_and_multiple_require_clarification():
    one = summary("thailand-bangkok-pattaya", "Bangkok")
    two = summary("danang-central-5d4n", "Đà Nẵng")

    resolved = resolve_tour_node(
        {"query_analysis": analysis(), "active_tour_codes": []}, lambda query: [one]
    )
    ambiguous = resolve_tour_node(
        {"query_analysis": analysis(), "active_tour_codes": []}, lambda query: [one, two]
    )

    assert resolved["route"] == "retrieve"
    assert resolved["active_tour_codes"] == ["thailand-bangkok-pattaya"]
    assert ambiguous["route"] == "clarification"
    assert [doc.metadata["tour_code"] for doc in ambiguous["tour_candidates"]] == [
        "thailand-bangkok-pattaya",
        "danang-central-5d4n",
    ]


def test_resolver_receives_explicit_references_when_supported():
    candidate = summary("thailand-bangkok-pattaya")
    calls = []

    def resolver(query, *, references):
        calls.append((query, references))
        return [candidate]

    result = resolve_tour_node(
        {
            "query_analysis": analysis(
                refs=["Bangkok – Pattaya", "Bangkok"],
                query="Giá tour Bangkok – Pattaya bao nhiêu?",
            )
        },
        resolver,
    )

    assert result["route"] == "retrieve"
    assert calls == [("Giá tour Bangkok – Pattaya bao nhiêu?", ["Bangkok – Pattaya", "Bangkok"])]


def test_legacy_one_argument_resolver_remains_compatible():
    candidate = summary("thailand-bangkok-pattaya")
    calls = []

    def resolver(query):
        calls.append(query)
        return [candidate]

    result = resolve_tour_node(
        {"query_analysis": analysis(refs=["Bangkok"], query="Giá Bangkok bao nhiêu?")},
        resolver,
    )

    assert result["route"] == "retrieve"
    assert calls == ["Giá Bangkok bao nhiêu?"]


def test_resolver_internal_type_error_is_not_retried_as_legacy_signature():
    calls = []

    def resolver(query, *, references):
        calls.append((query, references))
        raise TypeError("failure inside resolver")

    try:
        resolve_tour_node({"query_analysis": analysis(refs=["Bangkok"])}, resolver)
    except TypeError as error:
        assert str(error) == "failure inside resolver"
    else:
        raise AssertionError("resolver TypeError should propagate")

    assert len(calls) == 1


def test_explicit_two_tour_comparison_resolves_with_both_candidates():
    candidates = [summary("tour-a"), summary("tour-b")]

    result = resolve_tour_node(
        {
            "query_analysis": analysis(
                "compare_tours",
                refs=["tour A", "tour B"],
                query="So sánh tour A với tour B",
            )
        },
        lambda query: candidates,
    )

    assert result["route"] == "retrieve"
    assert result["active_tour_codes"] == ["tour-a", "tour-b"]


def test_unresolved_pronoun_with_multiple_active_tours_requires_clarification():
    result = resolve_tour_node(
        {
            "query_analysis": analysis(query="Tour đó bao nhiêu?"),
            "active_tour_codes": ["tour-a", "tour-b"],
        },
        lambda query: [],
    )

    assert result["route"] == "clarification"


def test_unsupported_reference_routes_to_unsupported():
    result = resolve_tour_node(
        {"query_analysis": analysis(refs=["Nhật Bản"]), "active_tour_codes": []},
        lambda query: [],
    )

    assert result["route"] == "unsupported"


def test_retrieval_returns_knowledge_and_excludes_catalog_records():
    tour_summary = summary("tour-a", "Tour A")
    knowledge = Document(
        "Lịch trình ngày 1",
        metadata={
            "chunk_id": "itinerary-a-1",
            "tour_code": "tour-a",
            "document_type": "knowledge",
            "authority": "official_tour_pdf",
            "section_type": "itinerary",
        },
    )
    calls = []

    class Retriever:
        def retrieve(self, query, tour_codes, *, comparison=False):
            calls.append((query, tour_codes, comparison))
            return [knowledge]

        def get_full_itinerary(self, tour_code):
            calls.append(("full", tour_code))
            raise AssertionError("catalog aggregate must not enter RAG contexts")

    result = retrieve_node(
        {
            "query_analysis": analysis("itinerary", query="Lịch trình ngày 1 tour A"),
            "active_tour_codes": ["tour-a"],
            "tour_summaries": [tour_summary],
        },
        Retriever(),
    )
    assert result["retrieved_chunks"] == [knowledge]
    assert calls == [("Lịch trình ngày 1 tour A", ["tour-a"], False)]


def test_comparison_uses_ten_retrieval_limit_and_adjacent_day_uses_last_citation():
    day_two = Document(
        "Ngày 2",
        metadata={"chunk_id": "day-2", "tour_code": "tour-a", "section_type": "itinerary", "chunk_index": 2},
    )
    day_three = Document(
        "Ngày 3",
        metadata={"chunk_id": "day-3", "tour_code": "tour-a", "section_type": "itinerary", "chunk_index": 3},
    )
    comparison_calls = []

    class Retriever:
        def retrieve(self, query, tour_codes, *, comparison=False):
            comparison_calls.append((tour_codes, comparison))
            return []

        def get_adjacent_itinerary(self, tour_code, chunk_index):
            assert (tour_code, chunk_index) == ("tour-a", 3)
            return day_three

    retrieve_node(
        {"query_analysis": analysis("compare_tours"), "active_tour_codes": ["tour-a", "tour-b"]},
        Retriever(),
    )
    adjacent = retrieve_node(
        {
            "query_analysis": analysis(query="Ngày tiếp theo thì sao?"),
            "active_tour_codes": ["tour-a"],
            "last_citation_ids": ["day-2"],
            "retrieved_chunks": [day_two],
        },
        Retriever(),
    )

    assert comparison_calls == [(["tour-a", "tour-b"], True), (["tour-a"], False)]
    assert day_three in adjacent["retrieved_chunks"]


def test_recommendation_and_full_program_do_not_add_catalog_aggregates():
    tour_summary = summary("tour-a")
    day_chunks = [
        Document(
            f"Ngày {index}",
            metadata={
                "chunk_id": f"day-{index}",
                "tour_code": "tour-a",
                "document_type": "knowledge",
                "authority": "official_tour_pdf",
                "section_type": "itinerary",
                "chunk_index": index,
            },
        )
        for index in range(1, 6)
    ]
    calls = []

    class Retriever:
        def retrieve(self, query, tour_codes, *, comparison=False):
            return []

        def get_all_itinerary_chunks(self, tour_code):
            calls.append(tour_code)
            return day_chunks

    recommender = Retriever()
    recommendation = retrieve_node(
        {
            "query_analysis": analysis("recommend_tour", query="Tư vấn tour A"),
            "active_tour_codes": ["tour-a"],
            "tour_summaries": [tour_summary],
        },
        recommender,
    )
    specific_day = retrieve_node(
        {
            "query_analysis": analysis("itinerary", query="Ngày nào đi Bà Nà?"),
            "active_tour_codes": ["tour-a"],
            "tour_summaries": [tour_summary],
        },
        recommender,
    )
    full_program = retrieve_node(
        {
            "query_analysis": analysis(
                "itinerary", query="Tour Đà Nẵng 5 ngày đi những đâu?"
            ),
            "active_tour_codes": ["tour-a"],
            "tour_summaries": [tour_summary],
        },
        recommender,
    )

    assert recommendation["retrieved_chunks"] == []
    assert specific_day["retrieved_chunks"] == []
    assert full_program["retrieved_chunks"] == day_chunks
    assert calls == ["tour-a"]


def test_resolver_outputs_are_declared_in_langgraph_state_contract():
    candidate = summary("tour-a", "Tour A")
    result = resolve_tour_node({"query_analysis": analysis()}, lambda query: [candidate])

    assert set(result).issubset(get_type_hints(AgentState))
    assert result["tour_candidates"] == [candidate]
    assert result["tour_summaries"] == [candidate]
    assert result["route"] == "retrieve"
