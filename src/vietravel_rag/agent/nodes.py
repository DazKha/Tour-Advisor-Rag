"""Injectable query analysis, tour routing, and evidence retrieval nodes."""

from __future__ import annotations

import re
from collections.abc import Sequence
from inspect import Parameter, signature
from typing import Any

from langchain_core.documents import Document
from langchain_core.messages import RemoveMessage, SystemMessage

from vietravel_rag.agent.prompts import (
    ANSWER_GENERATION_SYSTEM_PROMPT,
    QUERY_ANALYSIS_SYSTEM_PROMPT,
)
from vietravel_rag.agent.structured_output import deepseek_json_output
from vietravel_rag.guardrails.input_guard import validate_input
from vietravel_rag.guardrails.output_guard import validate_answer
from vietravel_rag.models import AgentState, QueryAnalysis, TourAnswer

_PRONOUNS = re.compile(r"\b(tour\s+đó|tour\s+này|tour\s+kia|chuyến\s+đó)\b", re.IGNORECASE)
_ADJACENT = re.compile(r"\b(ngày\s+tiếp theo|ngày\s+trước đó|ngày\s+kế tiếp|ngày\s+trước)\b", re.IGNORECASE)
_PREVIOUS = re.compile(r"\b(ngày\s+trước đó|ngày\s+trước)\b", re.IGNORECASE)
_FULL_PROGRAM = re.compile(
    r"(toàn bộ chương trình|chương trình đầy đủ|lịch trình đầy đủ|trọn chương trình|full itinerary)",
    re.IGNORECASE,
)
_CURRENT_PRICE = re.compile(
    r"\b(?:hiện\s+(?:tại|nay)|mới\s+nhất|hôm\s+nay|ngày\s+này|đang\s+áp\s+dụng|"
    r"khuyến\s+mãi|ưu\s+đãi|promotion|current\s+price|today)\b",
    re.IGNORECASE,
)
_EXECUTE_CANCEL = re.compile(
    r"\b(?:tôi\s+muốn|hãy|giúp\s+(?:tôi|mình)|thực\s+hiện|xử\s+lý)\b.{0,30}"
    r"\b(?:hủy\s+(?:tour|chuyến)|cancel)\b"
    r"|\b(?:hủy\s+(?:tour|chuyến))\b.{0,30}\b(?:giúp\s+(?:tôi|mình)|ngay|thực\s+hiện|xử\s+lý)\b"
    r"|\b(?:cancel\s+my\s+(?:tour|booking)|refund\s+my)\b",
    re.IGNORECASE,
)
_FINANCIAL_ACTION = re.compile(
    r"\b(?:số\s+tài\s+khoản|tài\s+khoản\s+ngân\s+hàng|chuyển\s+khoản|thanh\s+toán\s+giúp)\b",
    re.IGNORECASE,
)
_VISA_GUARANTEE = re.compile(
    r"\b(?:đảm\s+bảo|chắc\s+chắn|bảo\s+đảm).{0,30}\b(?:visa|thị\s+thực)\b"
    r"|\b(?:visa|thị\s+thực).{0,30}\b(?:đậu|được\s+cấp|chắc\s+chắn)\b",
    re.IGNORECASE,
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
    structured_model, output_prompt = deepseek_json_output(
        model, QueryAnalysis, QUERY_ANALYSIS_SYSTEM_PROMPT
    )
    analysis = structured_model.invoke(
        [SystemMessage(content=f"{output_prompt}\n\n{context}"), *messages]
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


def _resolve(resolver, query: str, references: list[str] | None = None) -> list[Document]:
    if callable(resolver):
        try:
            parameters = signature(resolver).parameters.values()
        except (TypeError, ValueError):
            parameters = ()
        supports_references = any(
            parameter.name == "references" or parameter.kind == Parameter.VAR_KEYWORD
            for parameter in parameters
        )
        if supports_references:
            return list(resolver(query, references=references or []))
        return list(resolver(query))
    from vietravel_rag.retrieval.resolver import resolve_tours

    return list(resolve_tours(query, resolver, references=references))


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

    candidates = _resolve(resolver, analysis.standalone_query, analysis.tour_references)
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


def _as_document(chunk: Any) -> Document:
    if isinstance(chunk, Document):
        return chunk
    metadata = dict(chunk.get("metadata", {}))
    metadata.setdefault("chunk_id", chunk.get("chunk_id"))
    metadata.setdefault("content", chunk.get("content", chunk.get("text", "")))
    return Document(page_content=metadata["content"], metadata=metadata)


def input_guard_node(state: AgentState) -> dict[str, Any]:
    all_messages = list(state.get("messages", []))
    discarded = all_messages[:-10]
    messages = all_messages[-10:]
    latest = _content(messages[-1]) if messages else ""
    decision = validate_input(latest)
    removals = [RemoveMessage(id=message.id) for message in discarded if getattr(message, "id", None)]
    result: dict[str, Any] = {"messages": [*removals, *messages], "input_decision": decision.route}
    if decision.message:
        result["input_message"] = decision.message
        status = "escalate" if decision.route == "safe_response" else "clarification_needed"
        result["response"] = TourAnswer(
            status=status, answer=decision.message, citation_ids=[], conflicts=[]
        ).model_dump()
    return result


def conflict_guard(state: AgentState, conflicts: list[dict]) -> dict[str, Any]:
    """Apply reviewed source conflicts before free-form evidence selection."""
    analysis = _analysis(state)
    topics = {"baggage": "baggage", "price": "price", "child_price": "child_price"}
    topic = topics.get(analysis.intent)
    if not topic:
        return {"evidence_status": None}
    codes = set(state.get("active_tour_codes", []))
    for record in conflicts:
        if record.get("topic") != topic or record.get("tour_code") not in codes:
            continue
        by_id = {
            str(doc.metadata.get("chunk_id")): doc
            for doc in state.get("retrieved_chunks", [])
            if doc.metadata.get("chunk_id")
            and doc.metadata.get("authority") == "official_tour_pdf"
            and doc.metadata.get("document_type") == "knowledge"
        }
        chosen: list[Document] = []
        for claim in record.get("claims", []):
            chunk_id = str(claim.get("chunk_id", ""))
            doc = by_id.get(chunk_id)
            if doc is None:
                content = str(claim.get("text", ""))
                doc = Document(
                    page_content=content,
                    metadata={
                        "chunk_id": chunk_id,
                        "content": content,
                        "tour_code": record["tour_code"],
                        "authority": "official_tour_pdf",
                        "page_start": claim.get("page"),
                        "page_end": claim.get("page"),
                        "document_type": "knowledge",
                    },
                )
            chosen.append(doc)
        if len(chosen) >= 2:
            return {
                "retrieved_chunks": [*state.get("retrieved_chunks", []), *[
                    doc for doc in chosen if doc not in state.get("retrieved_chunks", [])
                ]],
                "evidence_status": "conflict",
                "approved_chunk_ids": [str(doc.metadata["chunk_id"]) for doc in chosen],
                "approved_chunks": chosen,
                "conflict_description": str(record.get("topic", "Mâu thuẫn trong tài liệu")),
                "conflict_customer_summary": record.get("customer_summary"),
            }
    return {"evidence_status": None}


def prepare_evidence(state: AgentState) -> dict[str, Any]:
    """Apply deterministic routing and expose only official knowledge chunks."""
    if state.get("evidence_status") == "conflict":
        chunks = [
            doc for doc in state.get("approved_chunks", [])
            if doc.metadata.get("authority") == "official_tour_pdf"
            and doc.metadata.get("document_type") == "knowledge"
        ]
        if len(chunks) >= 2:
            ids = [str(doc.metadata["chunk_id"]) for doc in chunks[:2]]
            conflict_answer = TourAnswer(
                status="conflict", answer="", citation_ids=ids, conflicts=["Nguồn tài liệu có nội dung mâu thuẫn."]
            )
            return {
                "approved_chunk_ids": ids,
                "approved_chunks": chunks[:2],
                "draft_response": conflict_answer.model_dump(),
            }
        return {
            "evidence_status": "insufficient",
            "approved_chunk_ids": [],
            "approved_chunks": [],
        }
    analysis = _analysis(state)
    if analysis.intent == "availability" or (
        analysis.intent in {"price", "child_price"} and _CURRENT_PRICE.search(analysis.standalone_query)
    ):
        return {"evidence_status": "realtime_required", "approved_chunk_ids": [], "approved_chunks": []}
    high_risk = (
        analysis.intent in {"health", "complaint"}
        or (analysis.intent == "visa" and bool(_VISA_GUARANTEE.search(analysis.standalone_query)))
        or (analysis.intent == "payment" and bool(_FINANCIAL_ACTION.search(analysis.standalone_query)))
        or (analysis.intent == "cancellation" and bool(_EXECUTE_CANCEL.search(analysis.standalone_query)))
    )
    if high_risk:
        return {"evidence_status": "high_risk", "approved_chunk_ids": [], "approved_chunks": []}

    chunks = [
        _as_document(chunk)
        for chunk in state.get("retrieved_chunks", [])
        if chunk.metadata.get("authority") == "official_tour_pdf"
        and chunk.metadata.get("document_type") == "knowledge"
    ]
    approved_ids = [str(doc.metadata["chunk_id"]) for doc in chunks if doc.metadata.get("chunk_id")]
    return {
        "evidence_status": "conflict" if state.get("evidence_status") == "conflict" else ("sufficient" if chunks else "insufficient"),
        "approved_chunk_ids": approved_ids,
        "approved_chunks": chunks,
    }


def generate_answer(state: AgentState, model) -> dict[str, Any]:
    """Generate one structured answer from approved evidence, without retrying failures."""
    status = state.get("evidence_status")
    analysis = _analysis(state)
    if status == "realtime_required":
        answer = TourAnswer(
            status="escalate",
            answer="Dạ, em chưa thể kiểm tra chỗ trống hoặc giá hiện hành theo thời gian thực. Anh/chị vui lòng liên hệ Vietravel để được xác nhận ạ.",
            citation_ids=[], conflicts=[],
        )
        return {"response": answer.model_dump()}
    if status == "high_risk":
        answer = TourAnswer(
            status="escalate",
            answer="Dạ, yêu cầu này cần nhân viên Vietravel hoặc chuyên gia phù hợp hỗ trợ trực tiếp. Em chưa thể xác nhận hay thực hiện thay ạ.",
            citation_ids=[], conflicts=[],
        )
        return {"response": answer.model_dump()}
    if status == "insufficient":
        answer = TourAnswer(
            status="unsupported",
            answer="Dạ, em chưa tìm thấy đủ căn cứ trong tài liệu tour để trả lời chính xác ạ.",
            citation_ids=[], conflicts=[],
        )
        return {"response": answer.model_dump()}

    approved = list(state.get("approved_chunks", []))
    evidence = "\n\n".join(
        f"chunk_id={doc.metadata.get('chunk_id')} | page={doc.metadata.get('page_start', '')}\n"
        f"{doc.metadata.get('content', doc.page_content)}"
        for doc in approved
    )
    guidance = [
        item
        for item in state.get("sales_guidance", [])
        if item.get("intent") == analysis.intent
    ]
    context = (
        f"Intent: {analysis.intent}\nCâu hỏi: {analysis.standalone_query}\n"
        f"Trạng thái bằng chứng: {status}\nHướng dẫn giao tiếp (không phải dữ kiện): {guidance}\n"
        f"Bằng chứng đã duyệt:\n{evidence}"
    )
    try:
        structured, output_prompt = deepseek_json_output(
            model, TourAnswer, ANSWER_GENERATION_SYSTEM_PROMPT
        )
        raw = structured.invoke(
            [SystemMessage(content=output_prompt), SystemMessage(content=context)]
        )
        answer = raw if isinstance(raw, TourAnswer) else TourAnswer.model_validate(raw)
    except Exception:  # noqa: BLE001 - provider failures must become a safe, non-retried response
        answer = TourAnswer(
            status="unsupported",
            answer="Dạ, em chưa thể tạo câu trả lời có căn cứ từ tài liệu tour ạ.",
            citation_ids=[], conflicts=[],
        )
    return {"draft_response": answer.model_dump()}


def output_guard_node(state: AgentState) -> dict[str, Any]:
    draft = state.get("draft_response") or state.get("response") or {}
    answer = draft if isinstance(draft, TourAnswer) else TourAnswer.model_validate(draft)
    approved = list(state.get("approved_chunks", []))
    if state.get("evidence_status") == "conflict" and len(approved) >= 2:
        ids = [str(doc.metadata["chunk_id"]) for doc in approved[:2]]
        summary = state.get("conflict_customer_summary")
        if isinstance(summary, str) and summary.strip():
            answer_text = (
                "Dạ, tài liệu tour hiện có hai thông tin chưa thống nhất về hành lý:\n\n"
                f"{summary.strip()}\n\n"
                "Để tránh ảnh hưởng khi làm thủ tục tại sân bay, anh/chị vui lòng xác nhận lại "
                "hạn mức áp dụng với Vietravel trước ngày khởi hành ạ."
            )
        else:
            answer_text = (
                "Dạ, thông tin hành lý trong tài liệu tour chưa thống nhất. Anh/chị vui lòng "
                "xác nhận lại hạn mức áp dụng với Vietravel trước ngày khởi hành ạ."
            )
        answer = TourAnswer(
            status="conflict",
            answer=answer_text,
            citation_ids=ids,
            conflicts=["Nguồn tài liệu có nội dung mâu thuẫn."],
        )
    validated = validate_answer(answer, approved)
    return {
        "response": validated.model_dump(),
        "last_citation_ids": validated.citation_ids,
    }


def direct_response_node(state: AgentState) -> dict[str, Any]:
    if state.get("response") and state.get("input_decision") != "continue":
        return {}
    route = state.get("route")
    if route == "clarification":
        response = TourAnswer(
            status="clarification_needed",
            answer="Dạ, anh/chị muốn hỏi về tour nào ạ? Vui lòng cho em biết tên tour hoặc điểm đến nhé.",
            citation_ids=[], conflicts=[],
        )
    elif route == "safe_response":
        response = TourAnswer(
            status="escalate", answer="Dạ, em chỉ hỗ trợ thông tin liên quan đến các tour trong tài liệu ạ.",
            citation_ids=[], conflicts=[],
        )
    elif route == "general":
        response = TourAnswer(
            status="answered",
            answer=(
                "Dạ, em có thể hỗ trợ thông tin trong tài liệu về giá, lịch trình, dịch vụ bao gồm "
                "hoặc không bao gồm, hành lý, thanh toán và chính sách tour ạ."
            ),
            citation_ids=[], conflicts=[],
        )
    else:
        response = TourAnswer(
            status="unsupported", answer="Dạ, em chưa tìm thấy tour phù hợp trong dữ liệu hiện có ạ.",
            citation_ids=[], conflicts=[],
        )
    return {"response": response.model_dump()}
