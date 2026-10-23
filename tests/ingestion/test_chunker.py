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
