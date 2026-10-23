"""Injectable query analysis, tour routing, and evidence retrieval nodes."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from langchain_core.documents import Document
from langchain_core.messages import SystemMessage

from vietravel_rag.agent.prompts import QUERY_ANALYSIS_SYSTEM_PROMPT
from vietravel_rag.models import AgentState, QueryAnalysis


_PRONOUNS = re.compile(r"\b(tour\s+đó|tour\s+này|tour\s+kia|chuyến\s+đó)\b", re.I)
_ADJACENT = re.compile(r"\b(ngày\s+tiếp theo|ngày\s+trước đó|ngày\s+kế tiếp|ngày\s+trước)\b", re.I)
_PREVIOUS = re.compile(r"\b(ngày\s+trước đó|ngày\s+trước)\b", re.I)
_FULL_PROGRAM = re.compile(
    r"(toàn bộ chương trình|chương trình đầy đủ|lịch trình đầy đủ|trọn chương trình|full itinerary)",
    re.I,
)


def _content(message: Any) -> str:
    return str(getattr(message, "content", message))


def _active_tour_names(codes: Sequence[str]) -> list[str]:
    from vietravel_rag.ingestion.sources import TOUR_SOURCES

    by_code = {source.tour_code: source.tour_name for source in TOUR_SOURCES}
    return [by_code.get(code, code) for code in codes]


def _explicit_references(text: str, references: list[str]) -> list[str]:
    """Preserve literal tour aliases even if a structured model omits one."""
    from vietravel_rag.ingestion.sources import TOUR_SOURCES

    found: list[tuple[int, int, str]] = []
    for source in TOUR_SOURCES:
        for alias in [*source.aliases, source.tour_name]:
            match = re.search(re.escape(alias), text, flags=re.IGNORECASE)
            if match:
                found.append((match.start(), match.end(), text[match.start() : match.end()]))
    merged = list(references)
    accepted: list[tuple[int, int]] = []
    for start, end, literal in sorted(found, key=lambda item: (item[0], -(item[1] - item[0]))):
        if any(start < other_end and end > other_start for other_start, other_end in accepted):
            continue
        if not any(existing.casefold() == literal.casefold() for existing in merged):
            merged.append(literal)
        accepted.append((start, end))
    return merged


def analyze_query(state: AgentState, model) -> dict[str, Any]:
    """Analyze recent conversation with the injected structured-output chat model."""
    messages = list(state.get("messages", []))[-10:]
    active_codes = list(state.get("active_tour_codes", []))
    current_text = _content(messages[-1]) if messages else ""
    active = _active_tour_names(active_codes)
    context = (
        f"Các tour đang hoạt động (ngữ cảnh hội thoại, không phải mã để xuất ra): {active_codes}\n"
        f"Tên các tour tương ứng: {active}\n"
        "Phân tích tin nhắn cuối cùng; dùng các tin trước chỉ để giải quyết câu tiếp nối."
    )
    structured_model = model.with_structured_output(QueryAnalysis)
    analysis = structured_model.invoke(
        [SystemMessage(content=f"{QUERY_ANALYSIS_SYSTEM_PROMPT}\n\n{context}"), *messages]
    )
    if not isinstance(analysis, QueryAnalysis):
        analysis = QueryAnalysis.model_validate(analysis)
    analysis = analysis.model_copy(
        update={"tour_references": _explicit_references(current_text, analysis.tour_references)}
    )
    return {"query_analysis": analysis}


def _analysis(state: AgentState) -> QueryAnalysis:
    value = state.get("query_analysis")
    return value if isinstance(value, QueryAnalysis) else QueryAnalysis.model_validate(value or {})


def _resolve(resolver, query: str) -> list[Document]:
    if callable(resolver):
        return list(resolver(query))
    from vietravel_rag.retrieval.resolver import resolve_tours

    return list(resolve_tours(query, resolver))


def resolve_tour_node(state: AgentState, resolver) -> dict[str, Any]:
    """Route safe/general queries or resolve factual tour candidates."""
    analysis = _analysis(state)
    if analysis.intent == "off_topic":
        return {"route": "safe_response", "tour_candidates": []}
    if analysis.intent == "general":
        return {"route": "general", "tour_candidates": []}

    active_codes = list(state.get("active_tour_codes", []))
    if _PRONOUNS.search(analysis.standalone_query) and len(active_codes) > 1:
        return {"route": "clarification", "tour_candidates": [], "active_tour_codes": active_codes}

    candidates = _resolve(resolver, analysis.standalone_query)
    if not candidates and analysis.tour_references:
        return {"route": "unsupported", "tour_candidates": []}
    if not candidates and len(active_codes) == 1:
        cached = [
            doc for doc in state.get("tour_summaries", [])
            if doc.metadata.get("tour_code") == active_codes[0]
        ]
        if cached:
            candidates = cached
        else:
            return {"route": "clarification", "tour_candidates": []}
    if not candidates:
        return {"route": "clarification", "tour_candidates": []}
    if len(candidates) > 1:
        if analysis.intent == "compare_tours" and len(analysis.tour_references) >= 2:
            codes = [doc.metadata.get("tour_code") for doc in candidates]
            return {
                "route": "retrieve",
                "tour_candidates": candidates,
                "tour_summaries": candidates,
                "active_tour_codes": [code for code in codes if code],
                "last_intent": analysis.intent,
            }
        return {
            "route": "clarification",
            "tour_candidates": candidates,
            "active_tour_codes": [doc.metadata.get("tour_code") for doc in candidates],
        }

    tour = candidates[0]
    code = tour.metadata.get("tour_code")
    return {
        "route": "retrieve",
        "tour_candidates": candidates,
        "tour_summaries": candidates,
        "active_tour_codes": [code] if code else [],
        "last_intent": analysis.intent,
    }


def _comparison_requested(analysis: QueryAnalysis) -> bool:
    return analysis.intent == "compare_tours"


def _fetch_adjacent(retriever, tour_code: str, chunk_index: int) -> Document | None:
    if hasattr(retriever, "get_adjacent_itinerary"):
        return retriever.get_adjacent_itinerary(tour_code, chunk_index)
    if not hasattr(retriever, "get"):
        return None
    result = retriever.get(
        where={
            "$and": [
                {"tour_code": tour_code},
                {"section_type": "itinerary"},
                {"chunk_index": chunk_index},
            ]
        }
    )
    ids = result.get("ids", [])
    docs = result.get("documents", [])
    metadatas = result.get("metadatas", [])
    if not ids:
        return None
    return Document(page_content=docs[0], metadata=metadatas[0], id=ids[0])


def _adjacent_chunk(state: AgentState, retriever, analysis: QueryAnalysis) -> Document | None:
    if not _ADJACENT.search(analysis.standalone_query):
        return None
    cited_ids = set(state.get("last_citation_ids", []))
    prior = next(
        (
            doc for doc in state.get("retrieved_chunks", [])
            if doc.metadata.get("chunk_id") in cited_ids
            and doc.metadata.get("section_type") == "itinerary"
        ),
        None,
    )
    if prior is None or not prior.metadata.get("tour_code"):
        return None
    step = -1 if _PREVIOUS.search(analysis.standalone_query) else 1
    return _fetch_adjacent(
        retriever, prior.metadata["tour_code"], int(prior.metadata["chunk_index"]) + step
    )


def _retrieve(retriever, query: str, codes: list[str], comparison: bool) -> list[Document]:
    if hasattr(retriever, "retrieve"):
        return list(retriever.retrieve(query, codes, comparison=comparison))
    if callable(retriever):
        return list(retriever(query, codes, comparison=comparison))
    if hasattr(retriever, "similarity_search"):
        from vietravel_rag.retrieval.retriever import retrieve_evidence

        return list(retrieve_evidence(query, codes, retriever, comparison=comparison))
    raise TypeError("retriever must be callable or provide retrieve()")


def _full_itinerary(retriever, code: str) -> Document:
    if hasattr(retriever, "get_full_itinerary"):
        return retriever.get_full_itinerary(code)
    catalog_store = getattr(retriever, "catalog_store", None)
    if catalog_store is not None:
        from vietravel_rag.retrieval.resolver import get_full_itinerary

        return get_full_itinerary(code, catalog_store)
    raise TypeError("retriever must provide exact full-itinerary lookup")


def _document_key(document: Document) -> Any:
    return (
        getattr(document, "id", None)
        or document.metadata.get("chunk_id")
        or document.metadata.get("record_id")
        or (document.metadata.get("document_type"), document.metadata.get("tour_code"))
    )


def retrieve_node(state: AgentState, retriever) -> dict[str, Any]:
    """Fetch scoped evidence plus required catalog context and itinerary expansion."""
    analysis = _analysis(state)
    codes = list(state.get("active_tour_codes", []))
    if not codes:
        return {"retrieved_chunks": []}
    chunks = _retrieve(
        retriever,
        analysis.standalone_query,
        codes,
        comparison=_comparison_requested(analysis),
    )
    known = {_document_key(doc) for doc in chunks}
    for summary_doc in state.get("tour_summaries", state.get("tour_candidates", [])):
        if summary_doc.metadata.get("tour_code") in codes:
            key = _document_key(summary_doc)
            if key not in known:
                chunks.append(summary_doc)
                known.add(key)
    standalone = analysis.standalone_query.casefold()
    if analysis.intent in {"itinerary", "recommend_tour"} or _FULL_PROGRAM.search(standalone):
        for code in codes:
            full = _full_itinerary(retriever, code)
            key = _document_key(full)
            if key not in known:
                chunks.append(full)
                known.add(key)
    adjacent = _adjacent_chunk(state, retriever, analysis)
    if adjacent is not None:
        key = _document_key(adjacent)
        if key not in known:
            chunks.append(adjacent)
    return {"retrieved_chunks": chunks, "last_intent": analysis.intent}
