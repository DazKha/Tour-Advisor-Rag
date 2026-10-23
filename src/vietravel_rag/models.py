"""Shared data contracts for ingestion and answer generation."""

from __future__ import annotations

from typing import Literal, TypedDict

from langchain_core.documents import Document

from pydantic import BaseModel, Field


class PageText(BaseModel):
    page_number: int
    text: str


class TourSource(BaseModel):
    tour_code: str
    tour_name: str
    source_file: str
    aliases: list[str]


class ChunkRecord(BaseModel):
    chunk_id: str
    tour_code: str
    tour_name: str
    document_type: Literal["knowledge"] = "knowledge"
    section_type: str
    section_title: str
    page_start: int
    page_end: int
    parent_section_id: str | None = None
    chunk_index: int = 0
    source_file: str
    authority: Literal["official_tour_pdf"] = "official_tour_pdf"
    content: str
    embedding_text: str
    page_texts: dict[int, str] = Field(default_factory=dict)


class CatalogRecord(BaseModel):
    record_id: str
    tour_code: str
    tour_name: str
    document_type: Literal["tour_summary", "full_itinerary"]
    content: str
    embedding_text: str
    source_chunk_ids: list[str]


class QueryAnalysis(BaseModel):
    intent: Literal[
        "price",
        "child_price",
        "compare_tours",
        "recommend_tour",
        "itinerary",
        "included",
        "excluded",
        "baggage",
        "payment",
        "cancellation",
        "visa",
        "health",
        "availability",
        "complaint",
        "general",
        "off_topic",
    ]
    tour_references: list[str]
    standalone_query: str


class EvidenceAssessment(BaseModel):
    status: Literal["sufficient", "conflict", "insufficient", "realtime_required", "high_risk"]
    approved_chunk_ids: list[str]
    reason: str


class TourAnswer(BaseModel):
    status: Literal["answered", "clarification_needed", "conflict", "unsupported", "escalate"]
    answer: str
    citation_ids: list[str]
    conflicts: list[str]
    follow_up: str | None = None


class AgentState(TypedDict, total=False):
    messages: list
    query_analysis: QueryAnalysis | dict | None
    route: Literal["safe_response", "general", "clarification", "unsupported", "retrieve"] | None
    tour_candidates: list[Document]
    tour_summaries: list[Document]
    active_tour_codes: list[str]
    retrieved_chunks: list[Document]
    evidence_status: str | None
    last_intent: str | None
    last_citation_ids: list[str]
    response: dict | None
