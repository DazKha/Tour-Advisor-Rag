from langchain_core.documents import Document

from vietravel_rag.retrieval.retriever import retrieve_evidence


class RecordingStore:
    def __init__(self):
        self.query = None
        self.search_kwargs = None

    def similarity_search(self, query, k=4, filter=None):
        self.query = query
        self.search_kwargs = {"k": k, "filter": filter}
        tour_code = filter["tour_code"]
        return [
            Document(
                page_content="Hành lý",
                metadata={"tour_code": tour_code, "section_type": "included"},
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
    assert store.search_kwargs == {"k": 10, "filter": {"tour_code": {"$in": ["tour-a", "tour-b"]}}}
