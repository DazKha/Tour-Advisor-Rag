"""Tour candidate resolution and exact aggregate lookup."""

import unicodedata

from langchain_core.documents import Document


def _normalize_reference(value: str) -> str:
    """Normalize Unicode, punctuation, and spacing for source-name matching."""
    value = unicodedata.normalize("NFKD", value).casefold().replace("đ", "d")
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = "".join(" " if unicodedata.category(char).startswith("P") else char for char in value)
    return " ".join(value.split())


def _explicit_tour_codes(references: list[str]) -> list[str] | None:
    """Map unambiguous extracted references to source tour codes, if possible."""
    from vietravel_rag.ingestion.sources import TOUR_SOURCES

    resolved: list[str] = []
    for reference in references:
        normalized = _normalize_reference(reference)
        if not normalized:
            return None
        padded_reference = f" {normalized} "
        matches = []
        for source in TOUR_SOURCES:
            names = [source.tour_name, *source.aliases]
            if any(
                f" {_normalize_reference(name)} " in padded_reference
                or padded_reference.strip() in f" {_normalize_reference(name)} "
                for name in names
            ):
                matches.append(source.tour_code)
        if len(matches) != 1:
            return None
        if matches[0] not in resolved:
            resolved.append(matches[0])
    return resolved or None


def _get_exact_summaries(tour_codes: list[str], store) -> list[Document] | None:
    documents: list[Document] = []
    for tour_code in tour_codes:
        result = store.get(
            where={
                "$and": [
                    {"tour_code": tour_code},
                    {"document_type": "tour_summary"},
                ]
            }
        )
        ids = result.get("ids", [])
        contents = result.get("documents", [])
        metadatas = result.get("metadatas", [])
        if len(ids) != 1 or len(contents) != 1 or len(metadatas) != 1:
            return None
        documents.append(Document(page_content=contents[0], metadata=metadatas[0], id=ids[0]))
    return documents


class ItineraryLookupError(LookupError):
    """Raised when an exact tour code does not identify one itinerary."""


def resolve_tours(
    query: str,
    store,
    limit: int = 3,
    *,
    references: list[str] | None = None,
) -> list[Document]:
    """Return one clear summary match or multiple plausible clarification candidates."""
    if references:
        tour_codes = _explicit_tour_codes(references)
        if tour_codes:
            exact = _get_exact_summaries(tour_codes, store)
            if exact is not None:
                return exact

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
