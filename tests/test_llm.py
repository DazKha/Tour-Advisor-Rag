import math

import pytest

from vietravel_rag.config import Settings
from vietravel_rag.llm import get_chat_model, get_embeddings


def test_chat_model_factory_passes_deepseek_configuration_without_network():
    received = {}

    def factory(**kwargs):
        received.update(kwargs)
        return object()

    settings = Settings(
        deepseek_api_key="deepseek-test",
        deepseek_base_url="https://example.test/v1",
        llm_model="test-chat",
        gemini_api_key="gemini-test",
        _env_file=None,
    )

    get_chat_model(settings, factory=factory)

    assert received == {
        "model": "test-chat",
        "api_key": "deepseek-test",
        "base_url": "https://example.test/v1",
        "temperature": 0,
    }


def test_embedding_factory_is_injectable_without_network():
    calls = []

    class FakeProvider:
        def __init__(self, **kwargs):
            self.options = kwargs

        def embed_documents(self, texts, *, task_type, output_dimensionality):
            calls.append(("documents", task_type, output_dimensionality))
            return [[3.0, 4.0] + [0.0] * 766 for _ in texts]

        def embed_query(self, text, *, task_type, output_dimensionality):
            calls.append(("query", task_type, output_dimensionality))
            return [0.0, 2.0] + [0.0] * 766

    settings = Settings(
        deepseek_api_key="deepseek-test",
        gemini_api_key="gemini-test",
        _env_file=None,
    )

    embeddings = get_embeddings(settings, factory=FakeProvider)
    document_vectors = embeddings.embed_documents(["tour data"])
    query_vector = embeddings.embed_query("tour query")

    assert embeddings.provider.options == {
        "model": "gemini-embedding-001",
        "google_api_key": "gemini-test",
        "output_dimensionality": 768,
    }
    assert len(document_vectors[0]) == 768
    assert document_vectors[0][:2] == pytest.approx([0.6, 0.8])
    assert math.sqrt(sum(value * value for value in document_vectors[0])) == pytest.approx(1.0)
    assert len(query_vector) == 768
    assert query_vector[:2] == pytest.approx([0.0, 1.0])
    assert math.sqrt(sum(value * value for value in query_vector)) == pytest.approx(1.0)
    assert calls == [
        ("documents", "RETRIEVAL_DOCUMENT", 768),
        ("query", "RETRIEVAL_QUERY", 768),
    ]
