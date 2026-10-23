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
