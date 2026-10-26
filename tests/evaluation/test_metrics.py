import json
import math
from pathlib import Path

import pytest

from scripts.evaluate import (
    _write_json,
    evaluation_cost_summary,
    load_cases,
    ragas_records,
    summarize_ragas_rows,
    validate_cases,
)
from vietravel_rag.evaluation.metrics import (
    citation_validity,
    cost_summary,
    forbidden_claim_rate,
    latency_summary,
    numeric_grounding_rate,
    retrieval_precision_recall_at_k,
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


def test_evaluation_cost_summary_separates_generation_from_ragas_judging():
    summary = evaluation_cost_summary(
        [{"input_tokens": 1000, "output_tokens": 500}],
        {"input_tokens": 2000, "output_tokens": 1000},
        input_price_per_million=0.3,
        output_price_per_million=1.2,
    )
    assert summary["observed_cost_usd"] == 0.0009
    assert summary["generation_observed_cost_usd"] == 0.0009
    assert summary["estimated_cost_per_1000_usd"] == 0.9
    assert summary["ragas_judge_cost_usd"] == 0.0018
    assert summary["total_evaluation_cost_usd"] == 0.0027


def test_forbidden_claim_and_numeric_rates_are_zero_for_empty_answers():
    assert forbidden_claim_rate([{"answer": ""}], [["guaranteed"]]) == 0.0
    assert numeric_grounding_rate([{"answer": ""}], [[]]) == 1.0


def test_numeric_grounding_metric_compares_numeric_tokens_without_guard_parser():
    results = [{"answer": "5 days and 12 million VND"}]

    assert numeric_grounding_rate(results, [["5 days and 12 million VND"]]) == 1.0
    assert numeric_grounding_rate(results, [["5 days and 10 million VND"]]) == 0.5


@pytest.mark.parametrize(
    ("answer", "context", "expected"),
    [
        ("12 million USD", "12 million VND", 0.0),
        ("12 million USD", "USD 12 million", 1.0),
        ("under 12 years", "over 12 years", 0.0),
        ("under 12 years", "below 12 years", 1.0),
        ("2026-10-23", "2026-10-24", 0.0),
        ("2026-10-23", "23/10/2026", 1.0),
        ("8.990.000 VND", "8,990,000 VND", 1.0),
    ],
)
def test_numeric_grounding_requires_compatible_normalized_facts(answer, context, expected):
    assert numeric_grounding_rate([{"answer": answer}], [[context]]) == expected


def test_numeric_fact_units_do_not_leak_from_a_previous_value():
    assert numeric_grounding_rate([{"answer": "12 million USD and 5 years"}], [["5 years"]]) == 0.5


@pytest.mark.parametrize(
    ("answer", "context", "expected"),
    [
        ("not under 12 years", "under 12 years", 0.0),
        ("not under 12 years", "at least 12 years", 1.0),
        ("not over 12 years", "over 12 years", 0.0),
        ("not over 12 years", "at most 12 years", 1.0),
        ("not less than 12 years", "less than 12 years", 0.0),
        ("not less than 12 years", "at least 12 years", 1.0),
        ("not greater than 12 years", "greater than 12 years", 0.0),
        ("not greater than 12 years", "at most 12 years", 1.0),
    ],
)
def test_numeric_grounding_preserves_negated_comparator_semantics(answer, context, expected):
    assert numeric_grounding_rate([{"answer": answer}], [[context]]) == expected


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
        [{"case_id": "case-1", "reference": "reference text"}],
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
        "case_id": "case-1",
        "user_input": "question",
        "retrieved_contexts": ["chunk text"],
        "reference_contexts": ["reference chunk"],
        "retrieved_context_ids": ["chunk_1"],
        "response": "response",
        "reference": "reference text",
    }


def test_ragas_summary_uses_only_finite_scores_and_reports_hallucination_rates():
    rows = [
        {
            "llm_context_precision_with_reference": 0.8,
            "context_recall": 1.0,
            "faithfulness": 1.0,
            "answer_relevancy": 0.7,
            "answer_correctness": 0.9,
        },
        {
            "llm_context_precision_with_reference": 0.6,
            "context_recall": None,
            "faithfulness": 0.5,
            "answer_relevancy": 0.9,
            "answer_correctness": 0.7,
        },
    ]
    summary = summarize_ragas_rows(rows)
    assert summary["metrics"]["faithfulness"] == {
        "finite_cases": 2,
        "total_cases": 2,
        "mean": 0.75,
    }
    assert list(summary["metrics"]) == ["faithfulness"]
    assert summary["report_metrics"]["unsupported_claim_rate"] == 0.25
    assert summary["report_metrics"]["cases_with_unsupported_claim_rate"] == 0.5


def test_ragas_summary_excludes_nan_and_infinity_from_finite_counts():
    summary = summarize_ragas_rows(
        [
            {
                "llm_context_precision_with_reference": math.nan,
                "context_recall": math.inf,
                "faithfulness": -math.inf,
                "answer_relevancy": None,
                "answer_correctness": float("nan"),
            }
        ]
    )
    assert all(metric["finite_cases"] == 0 for metric in summary["metrics"].values())
    assert summary["report_metrics"] == {
        "unsupported_claim_rate": None,
        "cases_with_unsupported_claim_rate": None,
    }


def test_retrieval_precision_recall_excludes_cases_without_targets_and_deduplicates_hits():
    cases = [
        {"reference_context_ids": ["a", "b"]},
        {"reference_context_ids": []},
    ]
    results = [
        {"retrieved_context_ids": ["a", "a", "unrelated", "b"]},
        {"retrieved_context_ids": ["unrelated"]},
    ]

    summary = retrieval_precision_recall_at_k(cases, results, cutoffs=(1, 3))

    assert summary["eligible_cases"] == 1
    assert summary["excluded_cases_without_relevant_context"] == 1
    assert summary["by_k"]["1"] == {"recall": 0.5, "precision": 1.0, "cases": 1}
    assert summary["by_k"]["3"] == {"recall": 1.0, "precision": 0.666667, "cases": 1}


def test_json_writer_recursively_sanitizes_non_finite_ragas_scores(tmp_path):
    path = tmp_path / "eval_summary.json"
    _write_json(
        path,
        {"ragas": {"score": math.nan, "positive_infinity": math.inf}, "rows": [{"score": -math.inf}]},
    )
    loaded = json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=lambda value: pytest.fail(f"invalid JSON constant: {value}"),
    )
    assert loaded == {
        "ragas": {"score": None, "positive_infinity": None},
        "rows": [{"score": None}],
    }
