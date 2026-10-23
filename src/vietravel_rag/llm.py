"""Dependency-injectable model factories."""

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from vietravel_rag.config import Settings


def get_chat_model(settings: Settings, factory=ChatOpenAI):
    return factory(
        model=settings.llm_model,
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        temperature=0,
    )


def get_embeddings(settings: Settings, factory=OpenAIEmbeddings):
    return factory(model=settings.embedding_model, api_key=settings.openai_api_key)
