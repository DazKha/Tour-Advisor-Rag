from app import build_session_config, render_citation_label


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
