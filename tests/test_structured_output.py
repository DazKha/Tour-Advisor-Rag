import json

import pytest
from langchain_core.documents import Document
from langchain_core.exceptions import OutputParserException
from langchain_core.messages import SystemMessage

from vietravel_rag.agent.graph import build_graph
from vietravel_rag.agent.prompts import ANSWER_GENERATION_SYSTEM_PROMPT
from vietravel_rag.agent.structured_output import invoke_deepseek_json
from vietravel_rag.models import QueryAnalysis, TourAnswer


class DeepSeekJsonModeModel:
    """A production-like double requiring JSON mode and an explicit prompt schema."""

    def __init__(self):
        self.responses = [
            QueryAnalysis(
                intent="price",
                tour_references=[],
                standalone_query="Giá tour Bangkok – Pattaya",
            ),
            TourAnswer(
                status="answered",
                answer="Giá tour là 8.990.000đ.",
                citation_ids=["price-1"],
                conflicts=[],
            ),
        ]
        self.schemas = []
        self.current_schema = None

    def with_structured_output(self, schema, *, method):
        assert method == "json_mode"
        self.schemas.append(schema)
        self.current_schema = schema
        return self

    def invoke(self, messages):
        prompt = "\n".join(
            message.content for message in messages if isinstance(message, SystemMessage)
        )
        assert "json" in prompt
        schema = json.dumps(self.current_schema.model_json_schema(), ensure_ascii=False, separators=(",", ":"))
        assert schema in prompt
        return self.responses.pop(0)


class PriceRetriever:
    def __init__(self):
        self.chunk = Document(
            page_content="Giá tour 8.990.000đ",
            metadata={
                "chunk_id": "price-1",
                "content": "Giá tour 8.990.000đ",
                "tour_code": "thailand-bangkok-pattaya",
                "tour_name": "Bangkok – Pattaya",
                "section_title": "Giá tour",
                "section_type": "price",
                "document_type": "knowledge",
                "authority": "official_tour_pdf",
                "page_start": 4,
                "page_end": 4,
            },
        )

    def retrieve(self, query, tour_codes, *, comparison=False):
        return [self.chunk]


def test_graph_uses_json_mode_and_embeds_exact_contract_for_all_schemas():
    model = DeepSeekJsonModeModel()
    tour = Document(
        page_content="Bangkok – Pattaya",
        metadata={"tour_code": "thailand-bangkok-pattaya", "document_type": "tour_summary"},
    )
    graph = build_graph(
        {
            "model": model,
            "resolver": lambda query: [tour],
            "retriever": PriceRetriever(),
            "conflicts": [],
            "sales_guidance": [],
        }
    )

    result = graph.invoke(
        {"messages": ["Giá tour Bangkok – Pattaya bao nhiêu?"]},
        {"configurable": {"thread_id": "deepseek-json-contract"}},
    )

    assert result["response"]["status"] == "answered"
    assert result["response"]["citation_ids"] == ["price-1"]
    assert model.schemas == [QueryAnalysis, TourAnswer]


class ParserFailureThenSuccessModel:
    def __init__(self):
        self.invoke_count = 0

    def with_structured_output(self, schema, *, method):
        assert method == "json_mode"
        self.schema = schema
        return self

    def invoke(self, messages):
        self.invoke_count += 1
        if self.invoke_count == 1:
            raise OutputParserException("malformed JSON")
        return TourAnswer(
            status="answered",
            answer="Giá tour là 8.990.000đ.",
            citation_ids=["price-1"],
            conflicts=[],
        )


def test_structured_output_retries_one_parser_failure_then_returns_valid_model():
    model = ParserFailureThenSuccessModel()
    answer, attempts = invoke_deepseek_json(
        model,
        TourAnswer,
        ANSWER_GENERATION_SYSTEM_PROMPT,
        [SystemMessage(content="evidence")],
    )
    assert answer.status == "answered"
    assert attempts == 2
    assert model.invoke_count == 2


def test_structured_output_does_not_retry_provider_failures():
    class ProviderFailureModel(ParserFailureThenSuccessModel):
        def invoke(self, messages):
            self.invoke_count += 1
            raise RuntimeError("provider unavailable")

    model = ProviderFailureModel()
    with pytest.raises(RuntimeError, match="provider unavailable"):
        invoke_deepseek_json(
            model,
            TourAnswer,
            ANSWER_GENERATION_SYSTEM_PROMPT,
            [SystemMessage(content="evidence")],
        )
    assert model.invoke_count == 1
