"""Tour candidate resolution and exact aggregate lookup."""

from langchain_core.documents import Document


class ItineraryLookupError(LookupError):
    """Raised when an exact tour code does not identify one itinerary."""


def resolve_tours(query: str, store, limit: int = 3) -> list[Document]:
    """Return one clear summary match or multiple plausible clarification candidates."""
    scored = store.similarity_search_with_relevance_scores(
        query,
        k=limit,
        filter={"document_type": "tour_summary"},
    )
    floor = getattr(store, "relevance_floor", 0.65)
    margin = getattr(store, "relevance_margin", 0.3)
    if not scored or scored[0][1] < floor:
        return []
    if len(scored) > 1 and scored[0][1] - scored[1][1] < margin:
        return [doc for doc, _ in scored[:2]]
    return [scored[0][0]]


def get_full_itinerary(tour_code: str, store) -> Document:
    """Retrieve the itinerary only through exact tour-code and document-type metadata."""
    result = store.get(
        where={
            "$and": [
                {"tour_code": tour_code},
                {"document_type": "full_itinerary"},
            ]
        }
    )
    ids = result.get("ids", [])
    documents = result.get("documents", [])
    metadatas = result.get("metadatas", [])
    if len(ids) != 1 or len(documents) != 1 or len(metadatas) != 1:
        raise ItineraryLookupError(
            f"Expected exactly one itinerary for tour code {tour_code}; found {len(ids)}"
        )
    return Document(page_content=documents[0], metadata=metadatas[0], id=ids[0])
