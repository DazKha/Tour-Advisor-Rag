"""Factual retrieval scoped to backend-resolved tour codes."""


def retrieve_evidence(
    standalone_query: str,
    tour_codes: list[str],
    store,
    *,
    comparison: bool = False,
) -> list:
    if not tour_codes:
        return []
    tour_filter = tour_codes[0] if len(tour_codes) == 1 else {"$in": tour_codes}
    return store.similarity_search(
        standalone_query,
        k=10 if comparison else 6,
        filter={"tour_code": tour_filter},
    )
