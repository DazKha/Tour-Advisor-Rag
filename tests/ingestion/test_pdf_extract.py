from pathlib import Path

import pytest

from vietravel_rag.ingestion.pdf_extract import extract_pdf_pages


ROOT = Path(__file__).resolve().parents[2]
DANANG_PDF = ROOT / "raw_data" / "Đà Nẵng - Sơn Trà - KDL Bà Nà - Cầu Vàng - Hội An - La Vang - Động Phong Nha & Thiên Đường - Huế (Khách sạn 4_ trọn tour).pdf"


@pytest.fixture(scope="module")
def danang_pages():
    return extract_pdf_pages(DANANG_PDF)


def test_extraction_preserves_page_numbers_and_first_page_price(danang_pages):
    assert danang_pages[0].page_number == 1
    assert "8,990,000" in danang_pages[0].text


def test_extraction_keeps_baggage_claims_on_their_source_pages(danang_pages):
    by_page = {page.page_number: page.text for page in danang_pages}
    assert "23kg" in by_page[3] and "10kg" in by_page[3]
    assert "20kg" in by_page[4] and "7kg" in by_page[4]


def test_extraction_removes_tour_ui_prompt(danang_pages):
    assert all("Xem chương trình tour" not in page.text for page in danang_pages)
