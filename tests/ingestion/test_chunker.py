import json
from pathlib import Path

import pytest

from vietravel_rag.ingestion.chunker import chunk_tour
from vietravel_rag.ingestion.aggregates import build_catalog
from vietravel_rag.ingestion.pdf_extract import extract_pdf_pages
from vietravel_rag.ingestion.sources import TOUR_SOURCES


ROOT = Path(__file__).resolve().parents[2]
DANANG = next(source for source in TOUR_SOURCES if source.tour_code == "danang-central-5d4n")
DANANG_PDF = ROOT / "raw_data" / DANANG.source_file


@pytest.fixture(scope="module")
def all_chunks():
    chunks = []
    for source in TOUR_SOURCES:
        chunks.extend(chunk_tour(source, extract_pdf_pages(ROOT / "raw_data" / source.source_file)))
    return chunks


@pytest.fixture(scope="module")
def danang_chunks(all_chunks):
    return [chunk for chunk in all_chunks if chunk.tour_code == DANANG.tour_code]


def test_price_table_and_footnotes_are_atomic(danang_chunks):
    price_chunks = [chunk for chunk in danang_chunks if chunk.section_type == "price"]
    assert len(price_chunks) == 1
    assert "Người lớn" in price_chunks[0].content
    assert "Trẻ em" in price_chunks[0].content
    assert "ĐÀ NẴNG - SƠN TRÀ" not in price_chunks[0].content


def test_itinerary_is_one_ordered_chunk_per_day(danang_chunks):
    days = [chunk for chunk in danang_chunks if chunk.section_type == "itinerary"]
    assert days
    assert [chunk.chunk_index for chunk in days] == list(range(1, len(days) + 1))


def test_baggage_conflict_survives_chunking(danang_chunks):
    text = "\n".join(chunk.content for chunk in danang_chunks)
    assert "23kg" in text and "10kg" in text
    assert "20kg" in text and "7kg" in text


def test_chunk_provenance_matches_its_tour_source(all_chunks):
    source_by_code = {source.tour_code: source for source in TOUR_SOURCES}
    assert all(
        chunk.source_file == source_by_code[chunk.tour_code].source_file
        and chunk.tour_name == source_by_code[chunk.tour_code].tour_name
        for chunk in all_chunks
    )


def test_danang_baggage_conflict_uses_stable_ids(danang_chunks):
    ids = {chunk.chunk_id for chunk in danang_chunks}
    assert "danang-central-5d4n_included_01" in ids
    assert "danang-central-5d4n_registration_notes_01" in ids


def test_catalog_contains_exact_ordered_itinerary_aggregation(danang_chunks):
    records = build_catalog(DANANG, danang_chunks)
    assert [record.document_type for record in records] == ["tour_summary", "full_itinerary"]
    days = sorted((chunk for chunk in danang_chunks if chunk.section_type == "itinerary"), key=lambda c: c.chunk_index)
    assert records[1].source_chunk_ids == [chunk.chunk_id for chunk in days]
    assert records[1].content == "\n\n".join(chunk.content for chunk in days)
    assert all(alias in records[0].content for alias in DANANG.aliases)


def test_registration_notes_split_at_list_boundaries_and_keep_page_provenance(danang_chunks):
    registration = [chunk for chunk in danang_chunks if chunk.section_type == "registration_notes"]
    assert len(registration) > 1
    assert all(len(chunk.content) <= 1800 for chunk in registration)
    baggage = next(chunk for chunk in registration if "20kg" in chunk.content)
    assert baggage.chunk_id == "danang-central-5d4n_registration_notes_01"
    assert 4 in baggage.page_texts
    assert "20kg" in baggage.page_texts[4] and "7kg" in baggage.page_texts[4]


def test_china_visa_requirements_are_not_mislabeled_as_force_majeure(all_chunks):
    china = [chunk for chunk in all_chunks if chunk.tour_code == "china-lijiang-dali-shangrila"]
    visa = [chunk for chunk in china if chunk.section_type == "visa"]
    force_majeure = [chunk for chunk in china if chunk.section_type == "force_majeure"]
    assert visa
    assert all("ĐIỀU KIỆN XIN VISA" not in chunk.content for chunk in force_majeure)
    assert all("Ghi chú" not in chunk.content for chunk in force_majeure)
    assert all(len(chunk.content) > 100 for chunk in force_majeure)
    assert all(len(chunk.content) <= 1800 for chunk in visa)


def test_each_tour_has_separate_standard_and_holiday_cancellation_units(all_chunks):
    standard = [chunk for chunk in all_chunks if chunk.section_type == "cancellation_standard"]
    holiday = [chunk for chunk in all_chunks if chunk.section_type == "cancellation_holiday"]
    assert len(standard) == len(holiday) == 4
    assert all("Các điều kiện hủy tour đối với ngày lễ, Tết" not in chunk.section_title + chunk.content for chunk in standard)
    assert all("Các điều kiện hủy tour đối với ngày thường" not in chunk.content for chunk in holiday)
    assert all("Các điều kiện hủy tour đối với ngày lễ, Tết" in chunk.section_title for chunk in holiday)
    assert all("%" in chunk.content for chunk in holiday)


def test_chunking_report_records_four_reviewed_holiday_chunks():
    report = json.loads((ROOT / "data" / "processed" / "chunking_report.json").read_text(encoding="utf-8"))
    assert report["reviewed_chunk_counts"]["cancellation_holiday"] == 4
