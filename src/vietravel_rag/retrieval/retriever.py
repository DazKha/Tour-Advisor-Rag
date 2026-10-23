"""Factual retrieval scoped to backend-resolved tour codes."""

from langchain_core.documents import Document

_INTENT_SECTIONS: dict[str, tuple[str, ...]] = {
    "price": ("price",),
    "child_price": ("child_price", "price"),
    "itinerary": ("itinerary", "tour_overview"),
    "included": ("included",),
    "excluded": ("excluded",),
    "baggage": ("included", "registration_notes"),
    "payment": ("payment", "registration_notes"),
    "cancellation": ("cancellation_standard", "cancellation_holiday"),
    "visa": ("visa", "registration_notes"),
}


def sections_for_intent(intent: str) -> tuple[str, ...] | None:
    """Return the knowledge sections relevant to an intent, when known."""
    return _INTENT_SECTIONS.get(intent)


def retrieve_all_itinerary_chunks(tour_code: str, store) -> list[Document]:
    """Fetch every citable itinerary knowledge chunk for an exact tour code."""
    result = store.get(
        where={
            "$and": [
                {"tour_code": tour_code},
                {"document_type": "knowledge"},
                {"section_type": "itinerary"},
            ]
        }
    )
    chunks = [
        Document(page_content=content, metadata=metadata, id=identifier)
        for identifier, content, metadata in zip(
            result.get("ids", []),
            result.get("documents", []),
            result.get("metadatas", []),
            strict=True,
        )
    ]
    return sorted(chunks, key=lambda chunk: int(chunk.metadata.get("chunk_index", 0)))


def retrieve_evidence(
    standalone_query: str,
    tour_codes: list[str],
    store,
    *,
    intent: str | None = None,
    comparison: bool = False,
) -> list:
    if not tour_codes:
        return []
    tour_filter = tour_codes[0] if len(tour_codes) == 1 else {"$in": tour_codes}
    sections = sections_for_intent(intent or "")
    query_filter = {"tour_code": tour_filter}
    if sections:
        query_filter = {
            "$and": [
                {"tour_code": tour_filter},
                {"section_type": {"$in": list(sections)}},
            ]
        }
    limit = 10 if comparison else (4 if sections else 6)
    return store.similarity_search(
        standalone_query,
        k=limit,
        filter=query_filter,
    )
