"""Corpus invariants checked before artifacts can be accepted."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Mapping

from vietravel_rag.ingestion.sources import TOUR_SOURCES
from vietravel_rag.models import CatalogRecord, ChunkRecord

KNOWN_SECTIONS = {
    "tour_overview", "price", "itinerary", "included", "excluded", "child_price", "payment",
    "registration_notes", "cancellation_standard", "cancellation_holiday", "force_majeure",
    "visa", "tour_notes", "contact",
}
REQUIRED = ("tour_code", "tour_name", "section_type", "source_file", "authority", "content", "page_start", "page_end")
_FACT_PATTERN = re.compile(
    r"(?:\b\d[\d,.]*\s*(?:₫|đồng|vnd)(?=\s|$|[,.])|\b\d{1,3}(?:[,.]\d{3})+\b|"
    r"\b\d{1,2}/\d{1,2}/\d{2,4}\b|\b\d+(?:[.,]\d+)?\s*%|"
    r"\b(?:còn|đã hết|hết)\s*(?:\d+\s*)?(?:chỗ|vé|suất)\b|"
    r"\b\d{1,3}\s*[-–]\s*\d{1,3}\s*(?:ngày|tháng|tuần)\b)",
    re.I,
)


def _normalize_claim(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).casefold().split())


def _validate_sales_guidance(guidance: list[dict] | None) -> list[str]:
    errors: list[str] = []
    if guidance is None:
        return ["Sales guidance artifact is missing"]
    for entry in guidance:
        if not isinstance(entry, Mapping) or not {"scenario_id", "intent", "response_structure", "required_action", "prohibited_actions"} <= set(entry):
            errors.append("Sales guidance entry is missing required fields")
            continue
        for field, value in entry.items():
            if field == "scenario_id":
                continue
            values = value if isinstance(value, list) else [value]
            if any(_FACT_PATTERN.search(str(item)) for item in values):
                errors.append(f"Sales guidance contains factual commercial data: scenario {entry['scenario_id']}")
                break
    return errors


def _validate_conflicts(chunks: list[ChunkRecord], conflicts: list[dict] | None) -> list[str]:
    errors: list[str] = []
    if conflicts is None:
        return ["Conflict artifact is missing"]
    by_id = {chunk.chunk_id: chunk for chunk in chunks}
    for conflict in conflicts:
        for claim in conflict.get("claims", []):
            chunk = by_id.get(claim.get("chunk_id"))
            page = claim.get("page")
            claim_text = claim.get("text", "")
            if chunk is None or chunk.tour_code != conflict.get("tour_code"):
                errors.append(f"Conflict claim references unknown or wrong-tour chunk: {claim.get('chunk_id')}")
                continue
            page_text = chunk.page_texts.get(page)
            if not page_text or _normalize_claim(claim_text) not in _normalize_claim(page_text):
                errors.append(f"Conflict claim is not present on cited source page: {claim.get('chunk_id')} page {page}")
    return errors


def validate_corpus(
    chunks: list[ChunkRecord],
    catalog: list[CatalogRecord],
    sales_guidance: list[dict] | None = None,
    conflicts: list[dict] | None = None,
) -> dict:
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
        if source is not None:
            for other in TOUR_SOURCES:
                if other.tour_code != source.tour_code and other.tour_name.casefold() in chunk.content.casefold():
                    errors.append(f"Cross-tour content in chunk {chunk.chunk_id}: {other.tour_code}")
                    break
        if chunk.page_start < 1 or chunk.page_end < chunk.page_start:
            errors.append(f"Invalid page provenance: {chunk.chunk_id}")
        if not chunk.page_texts or any(page < chunk.page_start or page > chunk.page_end for page in chunk.page_texts):
            errors.append(f"Missing or invalid page-level provenance: {chunk.chunk_id}")
        if "Kịch bản tư vấn" in chunk.content or "Kịch bản tư vấn" in chunk.embedding_text:
            errors.append(f"Spreadsheet guidance leaked into factual chunks: {chunk.chunk_id}")
    counts = Counter((c.tour_code, c.section_type) for c in chunks)
    for source in TOUR_SOURCES:
        price_chunks = [c for c in chunks if c.tour_code == source.tour_code and c.section_type == "price"]
        price_spills = [c for c in chunks if c.tour_code == source.tour_code and c.section_type != "price"
                        and "giá dịch vụ" in c.section_title.casefold()]
        if counts[(source.tour_code, "price")] != 1 or price_spills:
            errors.append(f"Price table must remain atomic: {source.tour_code}")
        elif price_chunks and not all(label in price_chunks[0].content for label in ("Người lớn", "Trẻ em")):
            errors.append(f"Price table must remain atomic: incomplete age rows for {source.tour_code}")
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
    errors.extend(_validate_sales_guidance(sales_guidance))
    errors.extend(_validate_conflicts(chunks, conflicts))
    return {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "unclassified_sections": len(unclassified),
        "chunk_count": len(chunks),
        "catalog_count": len(catalog),
    }
