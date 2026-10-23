from vietravel_rag.ingestion.validation import validate_corpus


def test_validation_reports_missing_factual_metadata():
    result = validate_corpus([], [])
    assert result["status"] == "FAIL"
    assert any("Price table must be atomic" in error for error in result["errors"])
    assert result["unclassified_sections"] == 0

