"""Corpus invariants checked before artifacts can be accepted."""

from __future__ import annotations

from collections import Counter, defaultdict

from vietravel_rag.ingestion.sources import TOUR_SOURCES
from vietravel_rag.models import CatalogRecord, ChunkRecord

KNOWN_SECTIONS = {
    "tour_overview", "price", "itinerary", "included", "excluded", "child_price", "payment",
    "registration_notes", "cancellation_standard", "cancellation_holiday", "force_majeure",
}
REQUIRED = ("tour_code", "tour_name", "section_type", "source_file", "authority", "content", "page_start", "page_end")


def validate_corpus(chunks: list[ChunkRecord], catalog: list[CatalogRecord]) -> dict:
    errors: list[str] = []
    source_by_code = {source.tour_code: source for source in TOUR_SOURCES}
    unclassified = [chunk.chunk_id for chunk in chunks if chunk.section_type not in KNOWN_SECTIONS]
    if unclassified:
        errors.append(f"Unclassified sections: {unclassified}")
    for chunk in chunks:
        if any(not getattr(chunk, field, None) for field in REQUIRED):
            errors.append(f"Missing factual metadata: {chunk.chunk_id}")
        source = source_by_code.get(chunk.tour_code)
        if source is None or chunk.source_file != source.source_file or chunk.tour_name != source.tour_name:
            errors.append(f"Tour provenance mismatch: {chunk.chunk_id}")
        if chunk.page_start < 1 or chunk.page_end < chunk.page_start:
            errors.append(f"Invalid page provenance: {chunk.chunk_id}")
        if "Kịch bản tư vấn" in chunk.content or "Kịch bản tư vấn" in chunk.embedding_text:
            errors.append(f"Spreadsheet guidance leaked into factual chunks: {chunk.chunk_id}")
    counts = Counter((c.tour_code, c.section_type) for c in chunks)
    for source in TOUR_SOURCES:
        if counts[(source.tour_code, "price")] != 1:
            errors.append(f"Price table must be atomic: {source.tour_code}")
        indices = [c.chunk_index for c in chunks if c.tour_code == source.tour_code and c.section_type == "itinerary"]
        if indices != list(range(1, len(indices) + 1)):
            errors.append(f"Itinerary indices missing or duplicated: {source.tour_code}")
    by_code: defaultdict[str, list[CatalogRecord]] = defaultdict(list)
    for record in catalog:
        by_code[record.tour_code].append(record)
    for source in TOUR_SOURCES:
        days = sorted((c for c in chunks if c.tour_code == source.tour_code and c.section_type == "itinerary"), key=lambda c: c.chunk_index)
        full_records = [r for r in by_code[source.tour_code] if r.document_type == "full_itinerary"]
        if len(full_records) != 1 or full_records[0].source_chunk_ids != [c.chunk_id for c in days]:
            errors.append(f"Full itinerary does not map exactly to day chunks: {source.tour_code}")
        if len(full_records) == 1 and full_records[0].content != "\n\n".join(c.content for c in days):
            errors.append(f"Full itinerary content mismatch: {source.tour_code}")
    danang = "danang-central-5d4n"
    baggage_content = "\n".join(c.content for c in chunks if c.tour_code == danang)
    expected_ids = {"danang-central-5d4n_included_01", "danang-central-5d4n_registration_notes_01"}
    actual_ids = {c.chunk_id for c in chunks}
    if not all(term in baggage_content for term in ("23kg", "10kg", "20kg", "7kg")) or not expected_ids <= actual_ids:
        errors.append("Đà Nẵng baggage conflict claims or stable IDs are missing")
    return {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "unclassified_sections": len(unclassified),
        "chunk_count": len(chunks),
        "catalog_count": len(catalog),
    }
