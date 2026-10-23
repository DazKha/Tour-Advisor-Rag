"""Dependency-injectable model factories."""

from math import sqrt

from langchain_core.embeddings import Embeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_openai import ChatOpenAI

from vietravel_rag.config import Settings


def get_chat_model(settings: Settings, factory=ChatOpenAI):
    return factory(
        model=settings.llm_model,
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        temperature=0,
    )


class NormalizedGeminiEmbeddings(Embeddings):
    """Use Gemini's asymmetric retrieval tasks and normalize reduced vectors for Chroma."""

    def __init__(self, provider, output_dimensionality: int):
        self.provider = provider
        self.output_dimensionality = output_dimensionality

    def _normalize(self, vector: list[float]) -> list[float]:
        if len(vector) != self.output_dimensionality:
            raise ValueError(
                f"Gemini returned {len(vector)} dimensions; expected {self.output_dimensionality}"
            )
        magnitude = sqrt(sum(value * value for value in vector))
        if magnitude == 0:
            raise ValueError("Gemini returned a zero embedding vector")
        return [value / magnitude for value in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = self.provider.embed_documents(
            texts,
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=self.output_dimensionality,
        )
        return [self._normalize(vector) for vector in vectors]

    def embed_query(self, text: str) -> list[float]:
        vector = self.provider.embed_query(
            text,
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=self.output_dimensionality,
        )
        return self._normalize(vector)


def get_embeddings(settings: Settings, factory=GoogleGenerativeAIEmbeddings):
    provider = factory(
        model=settings.embedding_model,
        google_api_key=settings.gemini_api_key,
        output_dimensionality=settings.embedding_output_dimensionality,
    )
    return NormalizedGeminiEmbeddings(provider, settings.embedding_output_dimensionality)
