from langchain_core.documents import Document

from vietravel_rag.retrieval.retriever import (
    retrieve_all_itinerary_chunks,
    retrieve_evidence,
)


class RecordingStore:
    def __init__(self):
        self.query = None
        self.search_kwargs = None

    def similarity_search(self, query, k=4, filter=None):
        self.query = query
        self.search_kwargs = {"k": k, "filter": filter}
        tour_filter = filter
        if "$and" in filter:
            tour_filter = next(clause for clause in filter["$and"] if "tour_code" in clause)
        tour_code = tour_filter["tour_code"]
        if isinstance(tour_code, dict):
            tour_codes = set(tour_code["$in"])
        else:
            tour_codes = {tour_code}
        return [
            Document(
                page_content="Hành lý",
                metadata={"tour_code": next(iter(tour_codes)), "section_type": "included"},
            )
        ]


def test_evidence_is_scoped_to_resolved_tour():
    store = RecordingStore()
    docs = retrieve_evidence("hành lý bao nhiêu kg", ["danang-central-5d4n"], store)
    assert docs and {doc.metadata["tour_code"] for doc in docs} == {"danang-central-5d4n"}
    assert store.query == "hành lý bao nhiêu kg"
    assert store.search_kwargs == {"k": 6, "filter": {"tour_code": "danang-central-5d4n"}}


def test_comparison_returns_ten_chunks_without_section_filter():
    store = RecordingStore()
    retrieve_evidence("compare", ["tour-a", "tour-b"], store, comparison=True)
    assert store.search_kwargs == {
        "k": 10,
        "filter": {"tour_code": {"$in": ["tour-a", "tour-b"]}},
    }


def test_child_price_retrieval_filters_to_child_and_price_sections():
    store = RecordingStore()
    retrieve_evidence(
        "Trẻ 8 tuổi tính giá thế nào?",
        ["thailand-bangkok-pattaya"],
        store,
        intent="child_price",
    )
    assert store.search_kwargs == {
        "k": 4,
        "filter": {
            "$and": [
                {"tour_code": "thailand-bangkok-pattaya"},
                {"section_type": {"$in": ["child_price", "price"]}},
            ]
        },
    }


def test_itinerary_retrieval_filters_to_itinerary_sections():
    store = RecordingStore()
    retrieve_evidence(
        "Tour Đà Nẵng 5 ngày đi những đâu?",
        ["danang-central-5d4n"],
        store,
        intent="itinerary",
    )
    assert store.search_kwargs["filter"]["$and"][1] == {
        "section_type": {"$in": ["itinerary", "tour_overview"]}
    }


def test_unknown_intent_keeps_tour_scoping_without_section_filter():
    store = RecordingStore()
    retrieve_evidence("Thông tin tour", ["tour-a"], store, intent="general")
    assert store.search_kwargs == {"k": 6, "filter": {"tour_code": "tour-a"}}


def test_full_itinerary_uses_exact_citable_knowledge_chunks_in_day_order():
    class ItineraryStore:
        def get(self, *, where):
            assert where == {
                "$and": [
                    {"tour_code": "tour-a"},
                    {"document_type": "knowledge"},
                    {"section_type": "itinerary"},
                ]
            }
            return {
                "ids": ["day-2", "day-1"],
                "documents": ["Ngày 2", "Ngày 1"],
                "metadatas": [
                    {"chunk_id": "day-2", "chunk_index": 2},
                    {"chunk_id": "day-1", "chunk_index": 1},
                ],
            }

    chunks = retrieve_all_itinerary_chunks("tour-a", ItineraryStore())
    assert [chunk.metadata["chunk_id"] for chunk in chunks] == ["day-1", "day-2"]
