from typing import get_type_hints

from langchain_core.documents import Document

from vietravel_rag.agent.nodes import resolve_tour_node, retrieve_node
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


def test_retrieval_includes_summary_and_only_adds_exact_full_itinerary_when_requested():
    tour_summary = summary("tour-a", "Tour A")
    knowledge = Document("Giá tour", metadata={"chunk_id": "price-a", "tour_code": "tour-a"})
    calls = []

    class Retriever:
        def retrieve(self, query, tour_codes, *, comparison=False):
            calls.append((query, tour_codes, comparison))
            return [knowledge]

        def get_full_itinerary(self, tour_code):
            calls.append(("full", tour_code))
            return Document(
                "Ngày 1...",
                metadata={"document_type": "full_itinerary", "tour_code": tour_code},
            )

    ordinary = retrieve_node(
        {
            "query_analysis": analysis(),
            "active_tour_codes": ["tour-a"],
            "tour_summaries": [tour_summary],
        },
        Retriever(),
    )
    calls_after_ordinary = list(calls)
    itinerary = retrieve_node(
        {
            "query_analysis": analysis("itinerary", query="Lịch trình tour A"),
            "active_tour_codes": ["tour-a"],
            "tour_summaries": [tour_summary],
        },
        Retriever(),
    )

    assert ordinary["retrieved_chunks"] == [knowledge, tour_summary]
    assert not any(call[0] == "full" for call in calls_after_ordinary if isinstance(call, tuple))
    assert itinerary["retrieved_chunks"][-1].metadata["document_type"] == "full_itinerary"


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


def test_recommendation_and_explicit_full_program_add_full_itinerary():
    tour_summary = summary("tour-a")
    full = Document(
        "Toàn bộ ngày",
        metadata={"document_type": "full_itinerary", "tour_code": "tour-a"},
    )

    class Retriever:
        def retrieve(self, query, tour_codes, *, comparison=False):
            return []

        def get_full_itinerary(self, tour_code):
            assert tour_code == "tour-a"
            return full

    for query_analysis in (
        analysis("recommend_tour", query="Tư vấn tour A"),
        analysis("price", query="Cho tôi toàn bộ chương trình tour A"),
    ):
        result = retrieve_node(
            {
                "query_analysis": query_analysis,
                "active_tour_codes": ["tour-a"],
                "tour_summaries": [tour_summary],
            },
            Retriever(),
        )
        assert full in result["retrieved_chunks"]


def test_resolver_outputs_are_declared_in_langgraph_state_contract():
    candidate = summary("tour-a", "Tour A")
    result = resolve_tour_node({"query_analysis": analysis()}, lambda query: [candidate])

    assert set(result).issubset(get_type_hints(AgentState))
    assert result["tour_candidates"] == [candidate]
    assert result["tour_summaries"] == [candidate]
    assert result["route"] == "retrieve"
