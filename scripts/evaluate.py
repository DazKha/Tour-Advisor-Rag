"""Run deterministic and Ragas evaluation for the Vietravel assistant."""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler

from vietravel_rag.agent.graph import build_graph, invoke_turn
from vietravel_rag.config import Settings
from vietravel_rag.evaluation.metrics import cost_summary, extract_contexts, score_cases
from vietravel_rag.llm import get_chat_model, get_embeddings
from vietravel_rag.retrieval.index import CATALOG_COLLECTION, KNOWLEDGE_COLLECTION
from vietravel_rag.retrieval.resolver import get_full_itinerary, resolve_tours
from vietravel_rag.retrieval.retriever import retrieve_evidence

PRICE_SOURCE = "https://api-docs.deepseek.com/quick_start/pricing/"
DEFAULT_DATASET = Path("data/eval/eval_cases.jsonl")
RAGAS_METRICS = {
    "context_precision": "llm_context_precision_with_reference",
    "context_recall": "context_recall",
    "faithfulness": "faithfulness",
    "answer_relevancy": "answer_relevancy",
    "answer_correctness": "answer_correctness",
}


def load_cases(path: str | Path) -> list[dict]:
    """Load JSONL cases without changing their reviewed contents."""
    rows = []
    with Path(path).open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL at line {line_number}") from exc
    return rows


def validate_cases(cases: list[dict], valid_chunk_ids: set[str]) -> list[str]:
    """Validate exact case distribution, stable fields, tours, and context references."""
    errors = []
    required = {
        "factual": 10,
        "itinerary": 5,
        "multi_turn_ambiguous": 5,
        "insufficient_conflict": 4,
        "realtime_high_risk": 3,
        "injection_offtopic": 3,
    }
    distribution = Counter(case.get("category") for case in cases)
    if len(cases) != 30:
        errors.append(f"expected 30 cases, found {len(cases)}")
    if distribution != Counter(required):
        errors.append(f"category distribution mismatch: {dict(distribution)}")
    seen = set()
    for case in cases:
        case_id = str(case.get("case_id", "<missing>"))
        if case_id in seen:
            errors.append(f"duplicate case_id {case_id}")
        seen.add(case_id)
        for key in ("turns", "expected_intent", "expected_tour_codes", "expected_status", "reference"):
            if key not in case or case.get(key) is None or case.get(key) == "":
                errors.append(f"{case_id}: missing {key}")
        for chunk_id in case.get("reference_context_ids", []):
            if chunk_id not in valid_chunk_ids:
                errors.append(f"{case_id}: unknown reference context ID {chunk_id}")
    return errors


class UsageHandler(BaseCallbackHandler):
    """Collect integer token usage from real LangChain model responses."""

    def __init__(self) -> None:
        self.input_tokens = 0
        self.output_tokens = 0

    def on_llm_end(self, response, **kwargs) -> None:
        usage: dict[str, Any] = {}
        llm_output = getattr(response, "llm_output", None) or {}
        usage.update(llm_output.get("token_usage") or {})
        generations = getattr(response, "generations", []) or []
        for group in generations:
            for generation in group:
                message_usage = getattr(getattr(generation, "message", None), "usage_metadata", None)
                if message_usage:
                    usage.update(message_usage)
        self.input_tokens += int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0)
        self.output_tokens += int(
            usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0
        )


def _documents(path: str) -> list[dict]:
    with Path(path).open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _graph(settings: Settings):
    from langchain_chroma import Chroma

    persist_dir = Path(settings.chroma_persist_dir)
    embeddings = get_embeddings(settings)
    catalog = Chroma(
        collection_name=CATALOG_COLLECTION,
        embedding_function=embeddings,
        persist_directory=str(persist_dir),
    )
    knowledge = Chroma(
        collection_name=KNOWLEDGE_COLLECTION,
        embedding_function=embeddings,
        persist_directory=str(persist_dir),
    )
    if catalog._collection.count() == 0 or knowledge._collection.count() == 0:
        raise RuntimeError("persisted retrieval collections are empty")
    catalog.relevance_floor = settings.tour_resolution_relevance_floor
    catalog.relevance_margin = settings.tour_resolution_margin

    class Retriever:
        def retrieve(self, query, tour_codes, *, intent=None, comparison=False):
            return retrieve_evidence(
                query, tour_codes, knowledge, intent=intent, comparison=comparison
            )

        def get_full_itinerary(self, tour_code):
            return get_full_itinerary(tour_code, catalog)

        def get_adjacent_itinerary(self, tour_code, chunk_index):
            from langchain_core.documents import Document

            result = knowledge.get(
                where={
                    "$and": [
                        {"tour_code": tour_code},
                        {"section_type": "itinerary"},
                        {"chunk_index": chunk_index},
                    ]
                }
            )
            if not result.get("ids"):
                return None
            return Document(
                page_content=result["documents"][0],
                metadata=result["metadatas"][0],
                id=result["ids"][0],
            )

    return build_graph(
        {
            "model": get_chat_model(settings),
            "resolver": lambda query, *, references=None: resolve_tours(
                query, catalog, references=references
            ),
            "retriever": Retriever(),
            "conflicts": "data/processed/conflicts.json",
            "sales_guidance": "data/processed/sales_guidance.json",
        }
    )


def ragas_records(cases: list[dict], results: list[dict]) -> list[dict]:
    """Adapt completed runs to Ragas 0.3 collections-style fields plus context IDs."""
    return [
        {
            "user_input": result["user_input"],
            "retrieved_contexts": result["retrieved_contexts"],
            "reference_contexts": result["reference_contexts"],
            "retrieved_context_ids": result["retrieved_context_ids"],
            "response": result["answer"],
            "reference": case.get("reference", ""),
        }
        for case, result in zip(cases, results, strict=True)
    ]


def summarize_ragas_rows(rows: list[dict]) -> dict:
    """Aggregate finite Ragas scores and derive report-facing quality rates."""
    metrics = {}
    finite_by_metric = {}
    for name, column in RAGAS_METRICS.items():
        finite = [
            float(row[column])
            for row in rows
            if isinstance(row.get(column), (int, float))
            and math.isfinite(float(row[column]))
        ]
        finite_by_metric[name] = finite
        metrics[name] = {
            "finite_cases": len(finite),
            "total_cases": len(rows),
            "mean": round(sum(finite) / len(finite), 6) if finite else None,
        }

    faithfulness = finite_by_metric["faithfulness"]
    report_metrics = {
        "accuracy": metrics["answer_correctness"]["mean"],
        "unsupported_claim_rate": (
            round(1.0 - metrics["faithfulness"]["mean"], 6)
            if metrics["faithfulness"]["mean"] is not None
            else None
        ),
        "cases_with_unsupported_claim_rate": (
            round(sum(score < 1.0 for score in faithfulness) / len(faithfulness), 6)
            if faithfulness
            else None
        ),
    }
    return {
        "metrics": metrics,
        "report_metrics": report_metrics,
    }


def run_ragas(cases: list[dict], results: list[dict], settings: Settings) -> dict:
    """Run Ragas 0.3 metrics using DeepSeek judge and Gemini embeddings."""
    from ragas import EvaluationDataset, evaluate
    from ragas.metrics import (
        AnswerCorrectness,
        Faithfulness,
        LLMContextPrecisionWithReference,
        LLMContextRecall,
        ResponseRelevancy,
    )

    records = ragas_records(cases, results)
    sample_fields = {
        "user_input",
        "retrieved_contexts",
        "reference_contexts",
        "response",
        "reference",
    }
    dataset = EvaluationDataset.from_list(
        [{key: value for key, value in record.items() if key in sample_fields} for record in records]
    )
    llm = get_chat_model(settings)
    embeddings = get_embeddings(settings)
    usage = UsageHandler()
    metrics = [
        LLMContextPrecisionWithReference(),
        LLMContextRecall(),
        Faithfulness(),
        ResponseRelevancy(),
        AnswerCorrectness(),
    ]
    evaluation = evaluate(
        dataset,
        metrics=metrics,
        llm=llm,
        embeddings=embeddings,
        callbacks=[usage],
        show_progress=False,
        raise_exceptions=False,
    )
    metric_rows = evaluation.to_pandas().to_dict(orient="records")
    return {
        "version": package_version("ragas"),
        "judge_model": settings.llm_model,
        "judge_provider": "DeepSeek OpenAI-compatible chat endpoint",
        "judge_model_self_evaluation": True,
        "metric_rows": metric_rows,
        "summary": summarize_ragas_rows(metric_rows),
        "fields": sorted(records[0]) if records else [],
        "judge_usage": {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
        },
    }


def _run_cases(cases: list[dict], chunk_by_id: dict[str, dict], graph) -> list[dict]:
    output = []
    for case in cases:
        user_input = "\n".join(case["turns"])
        ref_contexts = [
            str(chunk_by_id[identifier].get("content", ""))
            for identifier in case.get("reference_context_ids", [])
        ]
        usage = UsageHandler()
        callback_graph = graph.with_config(callbacks=[usage])
        start = time.perf_counter()
        state = None
        try:
            for turn_index, turn in enumerate(case["turns"]):
                state = invoke_turn(callback_graph, turn, f"eval-{case['case_id']}")
            latency_ms = (time.perf_counter() - start) * 1000
            response = (state or {}).get("response") or {}
            analysis = (state or {}).get("query_analysis") or {}
            contexts, context_ids = extract_contexts(state or {})
            output.append(
                {
                    "case_id": case["case_id"],
                    "intent": analysis.get("intent", ""),
                    "tour_codes": list((state or {}).get("active_tour_codes", [])),
                    "status": response.get("status", ""),
                    "answer": response.get("answer", ""),
                    "citation_ids": list(response.get("citation_ids", [])),
                    "retrieved_context_ids": context_ids,
                    "retrieved_contexts": contexts,
                    "reference_contexts": ref_contexts,
                    "user_input": user_input,
                    "latency_ms": latency_ms,
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                    "generation_attempts": (state or {}).get("generation_attempts"),
                    "generation_error_type": (state or {}).get("generation_error_type"),
                }
            )
        except Exception as exc:  # noqa: BLE001 - provider exceptions vary; persist class only
            latency_ms = (time.perf_counter() - start) * 1000
            output.append(
                {
                    "case_id": case["case_id"],
                    "intent": "",
                    "tour_codes": [],
                    "status": "evaluation_error",
                    "answer": "",
                    "citation_ids": [],
                    "retrieved_context_ids": [],
                    "retrieved_contexts": [],
                    "reference_contexts": ref_contexts,
                    "user_input": user_input,
                    "latency_ms": latency_ms,
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                    "generation_attempts": (state or {}).get("generation_attempts"),
                    "generation_error_type": (state or {}).get("generation_error_type"),
                    "error_type": type(exc).__name__,
                }
            )
    return output


def _write_json(path: Path, value: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_sanitize_json_value(value), ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _sanitize_json_value(value):
    """Replace non-finite floats recursively so all persisted files are strict JSON."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {key: _sanitize_json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize_json_value(item) for item in value]
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--input-price-per-million", type=float, required=True)
    parser.add_argument("--output-price-per-million", type=float, required=True)
    parser.add_argument("--price-source-url", default=PRICE_SOURCE)
    parser.add_argument("--limit", type=int, help="Run only the first N cases for a smoke check")
    parser.add_argument("--skip-ragas", action="store_true")
    parser.add_argument("--results-dir", type=Path, default=Path("results"))
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1")
    cases = load_cases(args.dataset)
    chunks = _documents("data/processed/tour_chunks.jsonl")
    valid_ids = {row["chunk_id"] for row in chunks}
    validation_errors = validate_cases(cases, valid_ids)
    if validation_errors:
        for error in validation_errors:
            print(f"dataset validation: {error}", file=sys.stderr)
        return 2
    cases = cases[: args.limit] if args.limit is not None else cases
    try:
        settings = Settings()
        graph = _graph(settings)
    except Exception as exc:  # noqa: BLE001 - fail closed with sanitized setup errors
        print(f"evaluation setup failed ({type(exc).__name__}); no result files written", file=sys.stderr)
        return 2
    rows = _run_cases(cases, {row["chunk_id"]: row for row in chunks}, graph)
    deterministic = score_cases(cases, rows)
    metadata = {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "dataset": str(args.dataset),
        "case_count_requested": len(cases),
        "case_count_completed": sum(row["status"] != "evaluation_error" for row in rows),
        "case_failures": [
            {"case_id": row["case_id"], "error_type": row["error_type"]}
            for row in rows
            if row.get("error_type")
        ],
        "pricing": {
            "input_price_per_million_usd": args.input_price_per_million,
            "output_price_per_million_usd": args.output_price_per_million,
            "source_url": args.price_source_url,
            "timestamp_utc": datetime.now(UTC).isoformat(),
        },
        "limitations": {"judge_model_self_evaluation": True},
        "metric_definitions": {
            "accuracy": "Mean Ragas Answer Correctness over finite metric scores.",
            "unsupported_claim_rate": (
                "1 minus mean Ragas Faithfulness over finite metric scores; proxy for unsupported content."
            ),
            "cases_with_unsupported_claim_rate": (
                "Fraction of finite Faithfulness cases with score below 1.0."
            ),
            "context_precision": "Ragas LLMContextPrecisionWithReference mean over finite scores.",
            "context_recall": "Ragas LLMContextRecall mean over finite scores.",
            "faithfulness": "Ragas Faithfulness mean over finite scores.",
            "answer_relevancy": "Ragas ResponseRelevancy mean over finite scores.",
            "answer_correctness": "Ragas AnswerCorrectness mean over finite scores.",
            "citation_validity": (
                "Fraction of emitted citation IDs that appear among retrieved IDs; this does not "
                "measure citation coverage or completeness."
            )
        },
    }
    ragas_result = None
    if not args.skip_ragas:
        try:
            ragas_result = run_ragas(cases, rows, settings)
        except Exception as exc:  # noqa: BLE001 - report the adapter failure class only
            metadata["ragas_error_type"] = type(exc).__name__
    deterministic.update(
        cost_summary(
            rows,
            input_price_per_million=args.input_price_per_million,
            output_price_per_million=args.output_price_per_million,
        )
    )
    judge_usage = (ragas_result or {}).get("judge_usage", {"input_tokens": 0, "output_tokens": 0})
    judge_cost = cost_summary(
        [judge_usage],
        input_price_per_million=args.input_price_per_million,
        output_price_per_million=args.output_price_per_million,
    )
    deterministic["ragas_judge_input_tokens"] = judge_usage["input_tokens"]
    deterministic["ragas_judge_output_tokens"] = judge_usage["output_tokens"]
    deterministic["observed_cost_usd"] = round(
        deterministic["observed_cost_usd"] + judge_cost["observed_cost_usd"], 8
    )
    deterministic["estimated_cost_per_1000_usd"] = round(
        deterministic["observed_cost_usd"] * 1000 / len(rows) if rows else 0.0, 8
    )
    metadata["deterministic_metrics"] = deterministic
    metadata["ragas"] = ragas_result
    _write_json(args.results_dir / "eval_results.json", rows)
    _write_json(args.results_dir / "eval_summary.json", metadata)
    print(
        json.dumps(
            {
                "case_count_requested": len(cases),
                "case_count_completed": metadata["case_count_completed"],
                "case_failures": len(metadata["case_failures"]),
                "observed_cost_usd": deterministic["observed_cost_usd"],
                "ragas_status": "skipped" if args.skip_ragas else ("completed" if ragas_result else "failed"),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
