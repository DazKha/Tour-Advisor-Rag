# Task 2 report: page-preserving extraction and section-aware chunking

## Status

Complete. All four official tour PDFs were ingested and reviewed. Corpus validation and the chunk audit pass with zero unclassified sections. Five generated artifacts are committed.

## Files changed

- `src/vietravel_rag/ingestion/__init__.py`
- `src/vietravel_rag/ingestion/sources.py`
- `src/vietravel_rag/ingestion/pdf_extract.py`
- `src/vietravel_rag/ingestion/chunker.py`
- `src/vietravel_rag/ingestion/aggregates.py`
- `src/vietravel_rag/ingestion/sales_guidance.py`
- `src/vietravel_rag/ingestion/validation.py`
- `scripts/ingest.py`
- `scripts/audit_chunks.py`
- `tests/ingestion/test_pdf_extract.py`
- `tests/ingestion/test_chunker.py`
- `tests/ingestion/test_validation.py`
- `data/processed/tour_chunks.jsonl`
- `data/processed/tour_catalog.jsonl`
- `data/processed/sales_guidance.json`
- `data/processed/conflicts.json`
- `data/processed/chunking_report.json`

The Task 1 contracts in `models.py` and `config.py` were not changed.

## Python version and environment

Python 3.13.5 in the repository-local isolated environment at `.venv/`.

## RED evidence

- `.venv/bin/python -m pytest tests/ingestion/test_pdf_extract.py tests/ingestion/test_chunker.py -v` initially failed during collection with `ModuleNotFoundError: No module named 'vietravel_rag.ingestion'`, before the ingestion package existed.
- `.venv/bin/python -m pytest tests/ingestion/test_pdf_extract.py::test_extraction_removes_tour_ui_prompt -q` failed because the extracted page still contained `Xem chương trình tour`.
- `.venv/bin/python -m pytest tests/ingestion/test_chunker.py::test_price_table_and_footnotes_are_atomic -q` failed because the price chunk also contained the all-caps route title below the table.

Each regression was followed by a minimal implementation change and a passing focused rerun.

## GREEN tests and audit

Final test command:

```text
.venv/bin/python -m pytest tests/ingestion -v
10 passed, 0 failed (7 PyMuPDF/SWIG deprecation warnings)
```

Ingestion command:

```text
.venv/bin/python scripts/ingest.py --build-artifacts
PASS; sources=4; pages=28; factual_chunks=62; catalog_records=8; unclassified_sections=0; artifacts=5
```

Audit command:

```text
.venv/bin/python scripts/audit_chunks.py
PASS; chunks=62; catalog=8; unclassified=0
```

Generated chunk section counts: 4 prices, 4 child-price sections, 4 included, 4 excluded, 4 payment, 4 standard-cancellation, 4 holiday-cancellation, 18 itinerary-day chunks, 4 tour-overview, 4 registration-notes, and 8 force-majeure units. Sales guidance contains 20 scenario objects. The curated conflict file contains one baggage conflict.

## Manual artifact review

All 4 price and 4 child-price chunks, all 4 payment chunks, all 4 standard-cancellation chunks, and all 4 holiday-cancellation chunks were inspected in the generated JSONL with their page labels checked against the PDF extraction.

- Price tables are each one page-1 chunk. The Đà Nẵng price table contains the adult 8,990,000₫ and child 6,742,500₫ entries; the route title below the table is no longer part of the price chunk.
- Child-price sections are page 3 for Đà Nẵng, page 2 for Miền Tây, and page 4 for both Thái Lan and Trung Quốc.
- Payment sections are page 3 for Đà Nẵng and Miền Tây, and page 4 for Thái Lan and Trung Quốc.
- Standard cancellation sections are page 5 for Đà Nẵng and Miền Tây, pages 5–6 for Thái Lan, and pages 6–7 for Trung Quốc.
- Holiday cancellation sections are page 6 for Đà Nẵng, page 5 for Miền Tây, page 6 for Thái Lan, and page 7 for Trung Quốc.
- The conflicting Đà Nẵng baggage statements remain intact: `danang-central-5d4n_included_01` on page 3 states “23kg ký gửi, xách tay 10kg/khách”; `danang-central-5d4n_registration_notes_01` spans pages 3–5 and retains the page-4 “xách tay dưới 7kg” and “Ký gửi 20kg” statement. The conflict record points to those exact IDs and requires human confirmation.
- No standalone `baggage` section type was emitted: each claim remains inside its source `included` or `registration_notes` section so the required stable IDs and surrounding policy context are preserved.
- The audit flags two 6,554-character registration-notes units (Đà Nẵng and Miền Tây, pages 3–5). Both were reviewed and retained as connected registration/travel-condition sections rather than split across policy context.
- Sales guidance uses only scenario IDs and intent groups from the workbook. It contains generic response structures and prohibitions, not workbook answer text, prices, dates, discounts, availability, or policy percentages. The assignment DOCX was not ingested.

## Source immutability check

The four PDFs, sales-guidance XLSX, and assignment DOCX were SHA-256 checked before the final commit and checked again afterward. All six values matched; no file under `raw_data/` or `reference/` was edited, renamed, moved, or deleted. The assignment DOCX was only included in this checksum comparison, not opened or ingested.

| Source | SHA-256 |
| --- | --- |
| Miền Tây PDF | `322e94034fa73bfc8287fb98b92ee33ecc932d709fb08c660134d6c764894ed6` |
| Đà Nẵng PDF | `e5828a2e69d687af932c940fdaafbbda8b1ed93ef71ae4d70e9aa61768b64b81` |
| Thái Lan PDF | `1e6429f7ee12b05c28d4bc21833feb5e8a6eaba1d911378c6f9b058e90b3ee5b` |
| Trung Quốc PDF | `51cbbf613e5273ca4d21fcc6994efb0b1f8e4c224ca2ec15178f89468ddbf5c1` |
| Sales-guidance XLSX | `75d09b4dca95d0db99201b18de6eea3fad41fc8161041eabcbac044ef1e7cee5` |
| Assignment DOCX | `6f25a6c07e290e6a8734a53612352910e055e2431be40a7a457b305e493df823` |

## Commit hashes

- Implementation, tests, and reviewed artifacts: `7c7114d6b3f982ff02bc31af7c3adb18e0464fa8`
- This report is committed in a follow-up documentation commit.

## Self-review

- Verified stable provenance fields and source identities on every factual chunk.
- Verified itinerary chunk indices are ordered per tour and each catalog contains exactly a summary and a full-itinerary record.
- Verified full-itinerary source chunk IDs match the ordered day chunks exactly.
- Verified all four price tables remain atomic, and the conflicting baggage claims and curated IDs are present.
- Verified generated sales guidance is separate from factual tour chunks.
- Reviewed all reported oversized units and all required commercial/policy section types.
- Rechecked generated artifact validation, audit output, and source checksums immediately before documenting completion.

## Concerns

- PyMuPDF emitted seven SWIG deprecation warnings under Python 3.13.5; extraction and all assertions completed successfully.
- Baggage content is contained in the source's included/registration sections rather than emitted as a standalone section type, by design to preserve source context and the mandated stable conflict IDs.
