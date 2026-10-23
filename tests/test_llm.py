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
        openai_api_key="openai-test",
    )

    get_chat_model(settings, factory=factory)

    assert received == {
        "model": "test-chat",
        "api_key": "deepseek-test",
        "base_url": "https://example.test/v1",
        "temperature": 0,
    }


def test_embedding_factory_is_injectable_without_network():
    received = {}

    def factory(**kwargs):
        received.update(kwargs)
        return object()

    settings = Settings(
        deepseek_api_key="deepseek-test",
        openai_api_key="openai-test",
        embedding_model="fake-embedding-model",
    )

    get_embeddings(settings, factory=factory)

    assert received == {"model": "fake-embedding-model", "api_key": "openai-test"}
