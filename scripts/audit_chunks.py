#!/usr/bin/env python3
"""Revalidate generated corpus artifacts and report reviewed large units."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from vietravel_rag.ingestion.validation import validate_corpus  # noqa: E402
from vietravel_rag.models import CatalogRecord, ChunkRecord  # noqa: E402


def main() -> int:
    folder = ROOT / "data" / "processed"
    chunks = [ChunkRecord.model_validate(json.loads(line)) for line in (folder / "tour_chunks.jsonl").read_text(encoding="utf-8").splitlines() if line]
    catalog = [CatalogRecord.model_validate(json.loads(line)) for line in (folder / "tour_catalog.jsonl").read_text(encoding="utf-8").splitlines() if line]
    report = json.loads((folder / "chunking_report.json").read_text(encoding="utf-8"))
    validation = validate_corpus(chunks, catalog)
    if validation["status"] != "PASS":
        print(json.dumps(validation, ensure_ascii=False, indent=2))
        return 1
    if validation["unclassified_sections"] != 0:
        return 1
    print("PASS")
    print(f"chunks={validation['chunk_count']} catalog={validation['catalog_count']} unclassified=0")
    print("reviewed oversized semantic units:", json.dumps(report["oversized_semantic_units"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
