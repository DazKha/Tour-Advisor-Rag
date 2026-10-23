import json
from pathlib import Path

import pytest

from vietravel_rag.ingestion.aggregates import build_catalog
from vietravel_rag.ingestion.chunker import chunk_tour
from vietravel_rag.ingestion.pdf_extract import extract_pdf_pages
from vietravel_rag.ingestion.sources import TOUR_SOURCES
from vietravel_rag.ingestion.validation import validate_corpus

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def corpus():
    chunks = []
    catalog = []
    for source in TOUR_SOURCES:
        source_chunks = chunk_tour(source, extract_pdf_pages(ROOT / "raw_data" / source.source_file))
        chunks.extend(source_chunks)
        catalog.extend(build_catalog(source, source_chunks))
    conflict = [{
        "tour_code": "danang-central-5d4n", "topic": "baggage",
        "claims": [
            {"text": "Hành lý ký gửi 23kg, xách tay 10kg/khách", "page": 3, "chunk_id": "danang-central-5d4n_included_01"},
            {"text": "xách tay dưới 7kg/1khách", "page": 4, "chunk_id": "danang-central-5d4n_registration_notes_01"},
        ],
        "customer_summary": (
            "• Hành lý ký gửi 23kg, xách tay 10kg/khách.\n"
            "• Hành lý ký gửi 20kg/1 khách, xách tay dưới 7kg/1 khách."
        ),
        "resolution": "require_human_confirmation",
    }]
    return chunks, catalog, conflict


def test_validation_reports_missing_factual_metadata():
    result = validate_corpus([], [])
    assert result["status"] == "FAIL"
    assert any("Price table must remain atomic" in error for error in result["errors"])
    assert result["unclassified_sections"] == 0


def test_validator_detects_tour_identity_mixing(corpus):
    chunks, catalog, conflicts = corpus
    source = TOUR_SOURCES[1]
    chunk = next(c for c in chunks if c.tour_code == TOUR_SOURCES[0].tour_code)
    mixed = chunk.model_copy(update={"content": chunk.content + "\n" + source.tour_name})
    result = validate_corpus([mixed if c.chunk_id == chunk.chunk_id else c for c in chunks], catalog, [], conflicts)
    assert any("Cross-tour content" in error for error in result["errors"])


def test_validator_rejects_split_price_table(corpus):
    chunks, catalog, conflicts = corpus
    price = next(c for c in chunks if c.tour_code == "danang-central-5d4n" and c.section_type == "price")
    truncated = price.model_copy(update={"content": price.content.split("Trẻ em", 1)[0]})
    spill = price.model_copy(update={
        "chunk_id": "danang-central-5d4n_tour_overview_99",
        "section_type": "tour_overview",
        "section_title": "Giá dịch vụ (tiếp tục)",
        "content": "Trẻ em (Từ 5 - 11 tuổi) 6,742,500₫",
    })
    changed = [truncated if c.chunk_id == price.chunk_id else c for c in chunks] + [spill]
    result = validate_corpus(changed, catalog, [], conflicts)
    assert any("Price table must remain atomic" in error for error in result["errors"])


def test_validator_rejects_factual_leakage_in_sales_guidance(corpus):
    chunks, catalog, conflicts = corpus
    guidance = [{
        "scenario_id": 1, "intent": "price",
        "response_structure": "Tour giá 9,990,000₫, khởi hành 26/03/2027, giảm 10%",
        "required_action": "Ask which tour.", "prohibited_actions": [],
    }]
    result = validate_corpus(chunks, catalog, guidance, conflicts)
    assert any("Sales guidance contains factual commercial data" in error for error in result["errors"])


@pytest.mark.parametrize("text", [
    "Tour giá 1,990,000",
    "Tour còn chỗ.",
    "Thanh toán 7-10 ngày trước khởi hành.",
])
def test_sales_guidance_detector_catches_unqualified_price_availability_and_policy_terms(text):
    chunks, catalog, conflicts = ([], [], [])
    guidance = [{
        "scenario_id": 1, "intent": "general", "response_structure": text,
        "required_action": "Ask which tour.", "prohibited_actions": [],
    }]
    result = validate_corpus(chunks, catalog, guidance, conflicts)
    assert any("Sales guidance contains factual commercial data" in error for error in result["errors"])


def test_validator_requires_conflict_claim_text_on_exact_cited_page(corpus):
    chunks, catalog, conflicts = corpus
    bad = json.loads(json.dumps(conflicts, ensure_ascii=False))
    # Page 3 is within the chunk's 3-4 range, but this claim appears only on page 4.
    bad[0]["claims"][1]["page"] = 3
    result = validate_corpus(chunks, catalog, [], bad)
    assert any("Conflict claim is not present on cited source page" in error for error in result["errors"])


def test_validator_rejects_empty_curated_conflict_list(corpus):
    chunks, catalog, _ = corpus
    result = validate_corpus(chunks, catalog, [], [])
    assert any("Required Đà Nẵng baggage conflict" in error for error in result["errors"])


@pytest.mark.parametrize(("field", "value"), [
    ("tour_code", "wrong-tour"),
    ("topic", "payment"),
    ("resolution", "choose_one"),
])
def test_validator_requires_exact_curated_conflict_metadata(corpus, field, value):
    chunks, catalog, conflicts = corpus
    bad = json.loads(json.dumps(conflicts, ensure_ascii=False))
    bad[0][field] = value
    bad[0]["claims"] = []
    result = validate_corpus(chunks, catalog, [], bad)
    assert any("Required Đà Nẵng baggage conflict" in error for error in result["errors"])


def test_validator_rejects_missing_required_baggage_claim(corpus):
    chunks, catalog, conflicts = corpus
    bad = json.loads(json.dumps(conflicts, ensure_ascii=False))
    bad[0]["claims"].pop()
    result = validate_corpus(chunks, catalog, [], bad)
    assert any("Required Đà Nẵng baggage conflict" in error for error in result["errors"])


def test_validator_rejects_empty_curated_customer_summary(corpus):
    chunks, catalog, conflicts = corpus
    bad = json.loads(json.dumps(conflicts, ensure_ascii=False))
    bad[0]["customer_summary"] = "  "

    result = validate_corpus(chunks, catalog, [], bad)

    assert any("customer summary" in error.casefold() for error in result["errors"])


def test_validator_rejects_changed_required_claim_text_even_if_page_contains_it(corpus):
    chunks, catalog, conflicts = corpus
    bad = json.loads(json.dumps(conflicts, ensure_ascii=False))
    bad[0]["claims"][0]["text"] = "23kg"
    result = validate_corpus(chunks, catalog, [], bad)
    assert any("Required Đà Nẵng baggage conflict" in error for error in result["errors"])


def test_validator_rejects_wrong_required_page_even_if_page_provenance_is_internally_consistent(corpus):
    chunks, catalog, conflicts = corpus
    bad = json.loads(json.dumps(conflicts, ensure_ascii=False))
    bad[0]["claims"][0]["page"] = 4
    included = next(c for c in chunks if c.chunk_id == bad[0]["claims"][0]["chunk_id"])
    page_texts = dict(included.page_texts)
    page_texts[4] = page_texts[3] + "\n" + bad[0]["claims"][0]["text"]
    forged = included.model_copy(update={"page_end": 4, "page_texts": page_texts})
    changed = [forged if c.chunk_id == included.chunk_id else c for c in chunks]
    result = validate_corpus(changed, catalog, [], bad)
    assert any("Required Đà Nẵng baggage conflict" in error for error in result["errors"])


def test_validator_rejects_wrong_required_stable_chunk_id_when_citation_is_valid(corpus):
    chunks, catalog, conflicts = corpus
    bad = json.loads(json.dumps(conflicts, ensure_ascii=False))
    source = next(c for c in chunks if c.chunk_id == bad[0]["claims"][0]["chunk_id"])
    alternate = source.model_copy(update={"chunk_id": "danang-central-5d4n_included_99"})
    bad[0]["claims"][0]["chunk_id"] = alternate.chunk_id
    result = validate_corpus(chunks + [alternate], catalog, [], bad)
    assert any("Required Đà Nẵng baggage conflict" in error for error in result["errors"])


def test_audit_rejects_absent_holiday_cancellation_chunks(corpus):
    chunks, catalog, conflicts = corpus
    changed = [chunk for chunk in chunks if chunk.section_type != "cancellation_holiday"]
    result = validate_corpus(changed, catalog, [], conflicts)
    assert any("cancellation_holiday" in error for error in result["errors"])


def test_audit_rejects_holiday_policy_merged_into_standard_chunk(corpus):
    chunks, catalog, conflicts = corpus
    standard = next(chunk for chunk in chunks if chunk.section_type == "cancellation_standard")
    holiday = next(chunk for chunk in chunks if chunk.section_type == "cancellation_holiday")
    changed = [chunk for chunk in chunks if chunk.chunk_id != holiday.chunk_id]
    changed = [
        standard.model_copy(update={"content": standard.content + "\n" + holiday.section_title + "\n" + holiday.content})
        if chunk.chunk_id == standard.chunk_id else chunk
        for chunk in changed
    ]
    result = validate_corpus(changed, catalog, [], conflicts)
    assert any("holiday" in error.casefold() and "standard" in error.casefold() for error in result["errors"])
