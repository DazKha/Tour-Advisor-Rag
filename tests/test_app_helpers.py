from types import SimpleNamespace

from langchain_core.messages import AIMessage

import app
from app import build_session_config, render_citation_label
from vietravel_rag.agent.graph import build_graph
from vietravel_rag.models import QueryAnalysis


def test_citation_label_contains_tour_section_and_page():
    assert render_citation_label(
        {
            "tour_name": "Bangkok – Pattaya",
            "section_title": "Giá trẻ em",
            "page_start": 4,
            "page_end": 4,
        }
    ) == "Bangkok – Pattaya · Giá trẻ em · Trang 4"


def test_citation_label_shows_a_page_range():
    assert render_citation_label(
        {
            "tour_name": "Bangkok – Pattaya",
            "section_title": "Lịch trình",
            "page_start": 5,
            "page_end": 6,
        }
    ) == "Bangkok – Pattaya · Lịch trình · Trang 5–6"


def test_response_status_label_maps_known_statuses_for_display():
    assert app.response_status_label("answered") == "Đã trả lời"
    assert app.response_status_label("clarification_needed") == "Cần làm rõ"
    assert app.response_status_label("conflict") == "Có thông tin chưa thống nhất"
    assert app.response_status_label("unsupported") == "Chưa có đủ thông tin"
    assert app.response_status_label("escalate") == "Cần nhân viên Vietravel hỗ trợ"


def test_response_status_label_uses_safe_fallback_for_unknown_status():
    assert app.response_status_label("unexpected") == "Không xác định"


def test_format_response_markdown_converts_line_leading_bullets_and_adds_spacing():
    content = "Các điểm chính:\n• Ngày 1: Tham quan.\n• Ngày 2: Nghỉ ngơi."

    assert app.format_response_markdown(content) == (
        "Các điểm chính:\n\n- Ngày 1: Tham quan.\n- Ngày 2: Nghỉ ngơi."
    )


def test_format_response_markdown_preserves_existing_markdown():
    content = "Các điểm chính:\n\n- Ngày 1: Tham quan.\n- Ngày 2: Nghỉ ngơi."

    assert app.format_response_markdown(content) == content


def test_format_response_markdown_keeps_embedded_bullet_in_prose():
    content = "Lưu ý • vui lòng xác nhận trước ngày khởi hành."

    assert app.format_response_markdown(content) == content


def test_session_config_reuses_the_same_graph_thread_id():
    first = build_session_config("session-abc")
    second = build_session_config("session-abc")

    assert first == {"configurable": {"thread_id": "session-abc"}}
    assert second == first


def test_second_ui_turn_includes_the_prior_assistant_answer_in_graph_history(monkeypatch):
    class AnalysisModel:
        def __init__(self):
            self.analysis_messages = []

        def with_structured_output(self, schema):
            return self

        def invoke(self, messages):
            self.analysis_messages.append(list(messages))
            return QueryAnalysis(
                intent="general", tour_references=[], standalone_query="Thông tin chung về tour"
            )

    model = AnalysisModel()
    graph = build_graph(
        {
            "model": model,
            "resolver": lambda query: [],
            "retriever": lambda query, tour_codes, comparison=False: [],
            "conflicts": [],
            "sales_guidance": [],
        }
    )
    session_state = SimpleNamespace(
        messages=[],
        active_tour_codes=[],
        session_id="stable-ui-session",
    )
    monkeypatch.setattr(app.st, "session_state", session_state)

    app._run_turn(graph, "Bạn hỗ trợ thông tin gì về tour?")
    first_answer = session_state.messages[-1]["content"]
    app._run_turn(graph, "Còn chính sách tour thì sao?")

    second_turn_history = model.analysis_messages[1]
    assert any(
        isinstance(message, AIMessage) and message.content == first_answer
        for message in second_turn_history
    )


def test_reset_rotates_thread_id_and_clears_visible_conversation(monkeypatch):
    state = SimpleNamespace(
        messages=[{"role": "assistant", "content": "old answer"}],
        active_tour_codes=["old-tour"],
        session_id="old-session",
    )
    monkeypatch.setattr(app.uuid, "uuid4", lambda: "new-session")

    app.reset_conversation(state)

    assert state.messages == []
    assert state.active_tour_codes == []
    assert state.session_id == "new-session"
    assert build_session_config(state.session_id) == {
        "configurable": {"thread_id": "new-session"}
    }


def test_ensure_index_rebuilds_from_processed_jsonl_when_counts_are_stale(tmp_path, monkeypatch):
    catalog_path = tmp_path / "catalog.jsonl"
    chunks_path = tmp_path / "chunks.jsonl"
    catalog_path.write_text('{"record_id":"tour-a"}\n', encoding="utf-8")
    chunks_path.write_text('{"chunk_id":"chunk-a"}\n{"chunk_id":"chunk-b"}\n', encoding="utf-8")

    class Store:
        def __init__(self, count):
            self._collection = type("Collection", (), {"count": lambda self: count})()

    stores = iter([(Store(0), Store(0)), (Store(1), Store(2))])
    monkeypatch.setattr(app, "_open_stores", lambda settings: next(stores))
    rebuilt = []
    monkeypatch.setattr(app, "build_collections", lambda settings, **kwargs: rebuilt.append(settings))

    result = app.ensure_index_ready(
        object(),
        catalog_path=catalog_path,
        chunks_path=chunks_path,
        required_files=[catalog_path, chunks_path],
    )

    assert len(rebuilt) == 1
    assert result[0]._collection.count() == 1
    assert result[1]._collection.count() == 2


def test_ensure_index_skips_embedding_work_when_counts_match(tmp_path, monkeypatch):
    catalog_path = tmp_path / "catalog.jsonl"
    chunks_path = tmp_path / "chunks.jsonl"
    catalog_path.write_text('{"record_id":"tour-a"}\n', encoding="utf-8")
    chunks_path.write_text('{"chunk_id":"chunk-a"}\n', encoding="utf-8")

    class Store:
        def __init__(self, count):
            self._collection = type("Collection", (), {"count": lambda self: count})()

    expected = (Store(1), Store(1))
    monkeypatch.setattr(app, "_open_stores", lambda settings: expected)
    monkeypatch.setattr(
        app,
        "build_collections",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected rebuild")),
    )

    result = app.ensure_index_ready(
        object(),
        catalog_path=catalog_path,
        chunks_path=chunks_path,
        required_files=[catalog_path, chunks_path],
    )

    assert result == expected


def test_settings_loads_provider_keys_from_streamlit_secrets(monkeypatch):
    monkeypatch.setattr(
        app.st,
        "secrets",
        {"DEEPSEEK_API_KEY": "key-a", "GEMINI_API_KEY": "key-b"},
    )

    settings = app.load_settings()

    assert settings.deepseek_api_key == "key-a"
    assert settings.gemini_api_key == "key-b"
