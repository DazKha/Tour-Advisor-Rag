"""Streamlit chat demo for the grounded Vietravel tour assistant."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import streamlit as st
from langchain_chroma import Chroma
from pydantic import ValidationError
from streamlit.errors import StreamlitSecretNotFoundError

from vietravel_rag.agent.graph import build_graph, invoke_turn
from vietravel_rag.config import Settings
from vietravel_rag.llm import get_chat_model, get_embeddings
from vietravel_rag.retrieval.index import (
    CATALOG_COLLECTION,
    KNOWLEDGE_COLLECTION,
    build_collections,
)
from vietravel_rag.retrieval.resolver import get_full_itinerary, resolve_tours
from vietravel_rag.retrieval.retriever import retrieve_evidence


class MissingTourIndexError(RuntimeError):
    """Raised when local reviewed data or the persisted tour index is unavailable."""


def load_settings() -> Settings:
    """Load Community Cloud secrets when present, falling back to environment and .env."""
    names = {
        "DEEPSEEK_API_KEY",
        "GEMINI_API_KEY",
        "DEEPSEEK_BASE_URL",
        "LLM_MODEL",
        "EMBEDDING_MODEL",
        "EMBEDDING_OUTPUT_DIMENSIONALITY",
        "CHROMA_PERSIST_DIR",
    }
    try:
        secrets = st.secrets
        values = {name: secrets[name] for name in names if name in secrets}
    except StreamlitSecretNotFoundError:
        values = {}
    return Settings(**values)


def _open_stores(settings: Settings):
    """Open application-owned Chroma collections using the configured Gemini embeddings."""
    persist_dir = Path(settings.chroma_persist_dir)
    embeddings = get_embeddings(settings)
    catalog_store = Chroma(
        collection_name=CATALOG_COLLECTION,
        embedding_function=embeddings,
        persist_directory=str(persist_dir),
    )
    knowledge_store = Chroma(
        collection_name=KNOWLEDGE_COLLECTION,
        embedding_function=embeddings,
        persist_directory=str(persist_dir),
    )
    return catalog_store, knowledge_store


def _jsonl_record_count(path: Path) -> int:
    with path.open(encoding="utf-8") as handle:
        return sum(bool(line.strip()) for line in handle)


def ensure_index_ready(
    settings: Settings,
    *,
    catalog_path: Path = Path("data/processed/tour_catalog.jsonl"),
    chunks_path: Path = Path("data/processed/tour_chunks.jsonl"),
    required_files: list[Path] | None = None,
):
    """Open a matching index or build it once from reviewed JSONL artifacts."""
    required = required_files or [catalog_path, chunks_path]
    if not all(path.is_file() for path in required):
        raise MissingTourIndexError

    expected_catalog = _jsonl_record_count(catalog_path)
    expected_chunks = _jsonl_record_count(chunks_path)
    catalog_store, knowledge_store = _open_stores(settings)
    counts_match = (
        catalog_store._collection.count() == expected_catalog
        and knowledge_store._collection.count() == expected_chunks
    )
    if not counts_match:
        build_collections(
            settings,
            catalog_path=catalog_path,
            chunks_path=chunks_path,
        )
        catalog_store, knowledge_store = _open_stores(settings)

    if (
        catalog_store._collection.count() != expected_catalog
        or knowledge_store._collection.count() != expected_chunks
        or expected_catalog == 0
        or expected_chunks == 0
    ):
        raise MissingTourIndexError
    return catalog_store, knowledge_store


def render_citation_label(metadata: dict[str, Any]) -> str:
    """Format a compact source label from a document's safe citation metadata."""
    tour_name = str(metadata.get("tour_name") or "Tài liệu tour")
    section = str(metadata.get("section_title") or "Nguồn")
    start = metadata.get("page_start")
    end = metadata.get("page_end")
    if start is None:
        page = "Không rõ trang"
    elif end is None or str(start) == str(end):
        page = f"Trang {start}"
    else:
        page = f"Trang {start}–{end}"
    return f"{tour_name} · {section} · {page}"


def response_status_label(status: str) -> str:
    """Translate internal response statuses into concise, display-only Vietnamese labels."""
    labels = {
        "answered": "Đã trả lời",
        "clarification_needed": "Cần làm rõ",
        "conflict": "Có thông tin chưa thống nhất",
        "unsupported": "Chưa có đủ thông tin",
        "escalate": "Cần nhân viên Vietravel hỗ trợ",
    }
    return labels.get(status, "Không xác định")


def format_response_markdown(content: str) -> str:
    """Convert only line-leading Unicode bullets into spaced CommonMark list items."""
    if "•" not in content:
        return content

    lines = content.split("\n")
    first_bullet_index = None
    for index, line in enumerate(lines):
        leading = line[: len(line) - len(line.lstrip(" \t"))]
        remainder = line[len(leading) :]
        if remainder.startswith("•"):
            if first_bullet_index is None:
                first_bullet_index = index
            lines[index] = f"{leading}- {remainder[1:].lstrip()}"

    if first_bullet_index and lines[first_bullet_index - 1].strip():
        lines.insert(first_bullet_index, "")
    return "\n".join(lines)


def build_session_config(session_id: str) -> dict[str, dict[str, str]]:
    """Build the stable LangGraph checkpoint config for one browser session."""
    return {"configurable": {"thread_id": session_id}}


def reset_conversation(session_state) -> None:
    """Clear visible conversation state and isolate the next turn in a fresh graph thread."""
    session_state.messages = []
    session_state.active_tour_codes = []
    session_state.session_id = str(uuid.uuid4())


class _TourRetriever:
    def __init__(self, catalog_store, knowledge_store):
        self.catalog_store = catalog_store
        self.knowledge_store = knowledge_store

    def retrieve(self, query: str, tour_codes: list[str], *, comparison: bool = False):
        return retrieve_evidence(query, tour_codes, self.knowledge_store, comparison=comparison)

    def get_full_itinerary(self, tour_code: str):
        return get_full_itinerary(tour_code, self.catalog_store)

    def get_adjacent_itinerary(self, tour_code: str, chunk_index: int):
        result = self.knowledge_store.get(
            where={
                "$and": [
                    {"tour_code": tour_code},
                    {"section_type": "itinerary"},
                    {"chunk_index": chunk_index},
                ]
            }
        )
        if not result.get("ids"):
            return None
        from langchain_core.documents import Document

        return Document(
            page_content=result["documents"][0],
            metadata=result["metadatas"][0],
            id=result["ids"][0],
        )


@st.cache_resource(show_spinner="Đang kết nối dữ liệu tour…")
def load_graph_resources():
    """Create provider clients and persistent Chroma stores once per app process."""
    settings = load_settings()
    required_files = [
        Path("data/processed/tour_catalog.jsonl"),
        Path("data/processed/tour_chunks.jsonl"),
        Path("data/processed/conflicts.json"),
        Path("data/processed/sales_guidance.json"),
    ]
    catalog_store, knowledge_store = ensure_index_ready(settings, required_files=required_files)
    catalog_store.relevance_floor = settings.tour_resolution_relevance_floor
    catalog_store.relevance_margin = settings.tour_resolution_margin
    retriever = _TourRetriever(catalog_store, knowledge_store)
    graph = build_graph(
        {
            "model": get_chat_model(settings),
            "resolver": lambda query, *, references=None: resolve_tours(
                query, catalog_store, references=references
            ),
            "retriever": retriever,
            "conflicts": "data/processed/conflicts.json",
            "sales_guidance": "data/processed/sales_guidance.json",
        }
    )
    return graph


def _safe_source(doc: Any) -> dict[str, Any]:
    metadata = getattr(doc, "metadata", {}) or {}
    # Explicit allowlist: never render provider settings, credentials, or arbitrary metadata.
    safe_keys = (
        "tour_name",
        "section_title",
        "page_start",
        "page_end",
        "chunk_id",
        "section_type",
        "document_type",
        "authority",
        "similarity",
        "score",
    )
    safe_metadata = {key: metadata[key] for key in safe_keys if metadata.get(key) is not None}
    content = metadata.get("content") or getattr(doc, "page_content", "")
    return {"metadata": safe_metadata, "content": str(content)}


def _render_message(message: dict[str, Any]) -> None:
    with st.chat_message(message["role"]):
        if message["role"] == "assistant":
            st.caption(f"Trạng thái: {response_status_label(message.get('status', 'answered'))}")
            st.markdown(format_response_markdown(message["content"]))
        else:
            st.markdown(message["content"])
        for index, source in enumerate(message.get("sources", [])):
            metadata = source["metadata"]
            with st.expander(render_citation_label(metadata)):
                st.text(source["content"])
                debug = {
                    key: metadata[key]
                    for key in ("chunk_id", "section_type", "document_type", "authority", "similarity", "score")
                    if metadata.get(key) is not None
                }
                if debug:
                    st.caption("Thông tin nguồn")
                    st.json(debug)


def _init_state() -> None:
    defaults = {
        "messages": [],
        "active_tour_codes": [],
        "session_id": str(uuid.uuid4()),
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _run_turn(graph, prompt: str) -> None:
    st.session_state.messages.append({"role": "user", "content": prompt, "sources": []})
    state = invoke_turn(graph, prompt, st.session_state.session_id)
    response = state.get("response") or {}
    cited = set(response.get("citation_ids", []))
    docs = state.get("retrieved_chunks", [])
    sources = [
        _safe_source(doc)
        for doc in docs
        if (getattr(doc, "metadata", {}) or {}).get("chunk_id") in cited
    ]
    st.session_state.active_tour_codes = list(state.get("active_tour_codes", []))
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": response.get("answer", "Mình chưa thể trả lời lúc này."),
            "status": response.get("status", "unsupported"),
            "sources": sources,
        }
    )


def main() -> None:
    st.set_page_config(page_title="Vietravel Tour Assistant", page_icon="✈️")
    _init_state()
    st.title("Vietravel Tour Assistant")
    st.caption("Thông tin trả lời chỉ dựa trên bộ tài liệu tour đã được cung cấp.")
    st.info("Tình trạng chỗ và việc đặt tour cần nhân viên Vietravel xác nhận.")

    if st.button("Làm mới cuộc trò chuyện"):
        reset_conversation(st.session_state)
        st.rerun()

    suggestions = [
        ("Hỏi lịch trình", "Lịch trình tour Bangkok – Pattaya gồm những điểm nào?"),
        ("Hỏi giá trẻ em", "Giá trẻ em của tour Bangkok – Pattaya như thế nào?"),
        ("Hỏi hành lý", "Hành lý ký gửi của tour Đà Nẵng quy định ra sao?"),
    ]
    columns = st.columns(len(suggestions))
    selected_prompt = None
    for column, (label, prompt) in zip(columns, suggestions, strict=True):
        if column.button(label):
            selected_prompt = prompt

    for message in st.session_state.messages:
        _render_message(message)

    try:
        graph = load_graph_resources()
    except MissingTourIndexError:
        st.error("Chưa có chỉ mục tour. Hãy hoàn tất bước chuẩn bị dữ liệu trước khi chạy bản demo.")
        return
    except ValidationError:
        st.error("Thiếu cấu hình dịch vụ. Hãy kiểm tra các thiết lập cần thiết mà không chia sẻ khóa bí mật.")
        return
    except Exception:  # noqa: BLE001 - initialization errors are intentionally shown without details.
        # Provider/config details may contain sensitive values; never render exception text.
        st.error("Chưa thể khởi tạo dịch vụ. Kiểm tra cấu hình API và dữ liệu ứng dụng, không chia sẻ khóa bí mật.")
        return

    prompt = selected_prompt or st.chat_input("Nhập câu hỏi về tour…")
    if prompt:
        with st.chat_message("user"):
            st.markdown(prompt)
        try:
            _run_turn(graph, prompt)
        except Exception:  # noqa: BLE001 - chat failures must not expose provider diagnostics in the UI.
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": "Mình chưa thể xử lý yêu cầu lúc này. Vui lòng thử lại sau.",
                    "status": "unsupported",
                    "sources": [],
                }
            )
        st.rerun()


if __name__ == "__main__":
    main()
