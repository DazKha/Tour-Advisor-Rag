#!/usr/bin/env python3
"""Build reviewed, deterministic tour corpus artifacts from the four official PDFs."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vietravel_rag.ingestion.aggregates import build_catalog
from vietravel_rag.ingestion.chunker import chunk_tour
from vietravel_rag.ingestion.pdf_extract import extract_pdf_pages
from vietravel_rag.ingestion.sales_guidance import build_sales_guidance
from vietravel_rag.ingestion.sources import TOUR_SOURCES
from vietravel_rag.ingestion.validation import validate_corpus

OUTPUT = ROOT / "data" / "processed"
SALES_FILE = ROOT / "reference" / "Kich_ban_sale_tu_van_tour_20_tinh_huong.xlsx"


def write_jsonl(path: Path, values: list[object]) -> None:
    path.write_text("".join(json.dumps(value.model_dump(), ensure_ascii=False) + "\n" for value in values), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-artifacts", action="store_true")
    args = parser.parse_args()
    if not args.build_artifacts:
        parser.error("pass --build-artifacts")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    all_chunks, all_catalog = [], []
    for source in TOUR_SOURCES:
        pages = extract_pdf_pages(ROOT / "raw_data" / source.source_file)
        chunks = chunk_tour(source, pages)
        all_chunks.extend(chunks)
        all_catalog.extend(build_catalog(source, chunks))
    sales_guidance = build_sales_guidance(SALES_FILE)
    danang = [c for c in all_chunks if c.tour_code == "danang-central-5d4n"]
    danang_ids = {c.chunk_id for c in danang}
    claim_ids = ("danang-central-5d4n_included_01", "danang-central-5d4n_registration_notes_01")
    if not set(claim_ids) <= danang_ids:
        raise SystemExit("Required conflict chunk IDs are missing; refusing to write conflict record")
    conflicts = [{
        "tour_code": "danang-central-5d4n",
        "topic": "baggage",
        "claims": [
            {"text": "Hành lý ký gửi 23kg, xách tay 10kg/khách", "page": 3, "chunk_id": claim_ids[0]},
            {"text": "xách tay dưới 7kg/1khách", "page": 4, "chunk_id": claim_ids[1]},
        ],
        "resolution": "require_human_confirmation",
    }]
    validation = validate_corpus(all_chunks, all_catalog, sales_guidance, conflicts)
    if validation["status"] != "PASS":
        raise SystemExit(json.dumps(validation, ensure_ascii=False, indent=2))
    write_jsonl(OUTPUT / "tour_chunks.jsonl", all_chunks)
    write_jsonl(OUTPUT / "tour_catalog.jsonl", all_catalog)
    (OUTPUT / "sales_guidance.json").write_text(json.dumps(sales_guidance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUTPUT / "conflicts.json").write_text(json.dumps(conflicts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    section_counts = Counter(c.section_type for c in all_chunks)
    oversized = [{"chunk_id": c.chunk_id, "section_type": c.section_type, "characters": len(c.content)}
                 for c in all_chunks if len(c.content) > 1800]
    registration_groups = {}
    for source in TOUR_SOURCES:
        units = [c for c in all_chunks if c.tour_code == source.tour_code and c.section_type == "registration_notes"]
        registration_groups[source.tour_code] = {
            "chunk_ids": [c.chunk_id for c in units],
            "character_counts": [len(c.content) for c in units],
            "split_at_list_or_subsection_boundaries": len(units) > 1,
        }
    report = {
        "validation": validation,
        "source_count": len(TOUR_SOURCES),
        "page_counts": {s.tour_code: len(extract_pdf_pages(ROOT / "raw_data" / s.source_file)) for s in TOUR_SOURCES},
        "section_counts": dict(sorted(section_counts.items())),
        "reviewed_sections": ["price", "child_price", "baggage in included and registration_notes", "payment", "cancellation_standard", "cancellation_holiday"],
        "reviewed_chunk_counts": {kind: section_counts.get(kind, 0) for kind in ("price", "child_price", "payment", "cancellation_standard", "cancellation_holiday")},
        "baggage_claims_reviewed": 2,
        "oversized_semantic_units": oversized,
        "semantic_unit_limit_chars": 1800,
        "registration_semantic_splits": registration_groups,
        "oversized_review_decisions": [
            {
                "chunk_id": item["chunk_id"],
                "decision": (
                    "retain as one day-level semantic unit"
                    if item["section_type"] == "itinerary"
                    else "retain the complete cancellation schedule as one atomic policy unit"
                    if item["section_type"] in {"cancellation_standard", "cancellation_holiday"}
                    else "retain because no source list or subsection boundary can split this unit without breaking it"
                ),
                "page_range": next(f"{c.page_start}-{c.page_end}" for c in all_chunks if c.chunk_id == item["chunk_id"]),
            }
            for item in oversized
        ],
        "removed_content": ["confirmed bottom-of-page labels matching the one-based page number", "Xem chương trình tour UI text", "exact duplicate text blocks at identical coordinates"],
        "source_conflicts_preserved": ["Đà Nẵng baggage claims on pages 3 and 4"],
        "sales_guidance_scenario_count": len(sales_guidance),
    }
    (OUTPUT / "chunking_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", **validation, "section_counts": report["section_counts"], "artifacts": 5}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
