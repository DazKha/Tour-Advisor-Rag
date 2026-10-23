import json
from pathlib import Path

from scripts.evaluate import load_cases, ragas_records, validate_cases
from vietravel_rag.evaluation.metrics import (
    citation_validity,
    cost_summary,
    forbidden_claim_rate,
    latency_summary,
    numeric_grounding_rate,
    score_cases,
)


def test_citation_validity():
    assert citation_validity(["a"], retrieved_ids={"a", "b"}) == 1.0
    assert citation_validity(["x"], retrieved_ids={"a", "b"}) == 0.0


def test_percentile_summary():
    summary = latency_summary([100, 200, 300, 400, 500])
    assert summary["p50_ms"] == 300
    assert summary["p95_ms"] >= 400


def test_route_status_safety_and_grounding_metrics():
    cases = [
        {
            "expected_intent": "price",
            "expected_tour_codes": ["thai"],
            "expected_status": "answered",
            "must_not_contain": ["guaranteed"],
            "reference_context_ids": ["price"],
        },
        {
            "expected_intent": "availability",
            "expected_tour_codes": ["thai"],
            "expected_status": "escalate",
            "must_not_contain": ["confirmed"],
            "reference_context_ids": [],
        },
    ]
    results = [
        {
            "intent": "price",
            "tour_codes": ["thai"],
            "status": "answered",
            "answer": "5 ngày, giá 12 triệu đồng",
            "citation_ids": ["price"],
            "retrieved_context_ids": ["price"],
            "retrieved_contexts": ["5 ngày, giá 12 triệu đồng"],
            "latency_ms": 100,
            "input_tokens": 100,
            "output_tokens": 20,
        },
        {
            "intent": "availability",
            "tour_codes": ["thai"],
            "status": "escalate",
            "answer": "Chưa xác nhận tình trạng chỗ.",
            "citation_ids": [],
            "retrieved_context_ids": [],
            "retrieved_contexts": [],
            "latency_ms": 300,
            "input_tokens": 80,
            "output_tokens": 15,
        },
    ]
    summary = score_cases(cases, results)
    assert summary["intent_accuracy"] == 1.0
    assert summary["tour_resolution_exact_match"] == 1.0
    assert summary["answer_status_accuracy"] == 1.0
    assert summary["clarification_conflict_refusal_accuracy"] == 1.0
    assert summary["citation_validity"] == 1.0
    assert summary["numeric_grounding_rate"] == 1.0
    assert summary["forbidden_claim_rate"] == 0.0


def test_cost_summary_uses_cli_prices_and_estimates_1000_questions():
    summary = cost_summary(
        [{"input_tokens": 1_000_000, "output_tokens": 500_000}],
        input_price_per_million=0.3,
        output_price_per_million=1.2,
    )
    assert summary["observed_cost_usd"] == 0.9
    assert summary["estimated_cost_per_1000_usd"] == 900.0


def test_forbidden_claim_and_numeric_rates_are_zero_for_empty_answers():
    assert forbidden_claim_rate([{"answer": ""}], [["guaranteed"]]) == 0.0
    assert numeric_grounding_rate([{"answer": ""}], [[]]) == 1.0


def test_dataset_has_required_distribution_and_only_real_reference_ids():
    cases = load_cases("data/eval/eval_cases.jsonl")
    chunks = [json.loads(line) for line in Path("data/processed/tour_chunks.jsonl").read_text(encoding="utf-8").splitlines()]
    assert validate_cases(cases, {chunk["chunk_id"] for chunk in chunks}) == []
    assert len(cases) == 30


def test_dataset_validation_reports_unknown_chunk_ids():
    errors = validate_cases(
        [{"case_id": "bad", "reference_context_ids": ["missing"]}], {"known"}
    )
    assert "bad: unknown reference context ID missing" in errors


def test_ragas_adapter_preserves_context_ids_and_standard_fields():
    records = ragas_records(
        [{"reference": "reference text"}],
        [
            {
                "user_input": "question",
                "retrieved_contexts": ["chunk text"],
                "reference_contexts": ["reference chunk"],
                "retrieved_context_ids": ["chunk_1"],
                "answer": "response",
            }
        ],
    )
    assert records[0] == {
        "user_input": "question",
        "retrieved_contexts": ["chunk text"],
        "reference_contexts": ["reference chunk"],
        "retrieved_context_ids": ["chunk_1"],
        "response": "response",
        "reference": "reference text",
    }
