"""Deterministic tour-level retrieval aggregates."""

from __future__ import annotations

import re

from vietravel_rag.models import CatalogRecord, ChunkRecord, TourSource


def build_catalog(source: TourSource, chunks: list[ChunkRecord]) -> list[CatalogRecord]:
    days = sorted((c for c in chunks if c.section_type == "itinerary"), key=lambda c: c.chunk_index)
    indices = [c.chunk_index for c in days]
    if indices != list(range(1, len(days) + 1)):
        raise ValueError(f"Itinerary indices are not contiguous for {source.tour_code}")
    day_titles = [re.sub(r"^Ngày\s+\d+\s*:\s*", "", c.section_title, flags=re.I) for c in days]
    duration = f"{len(days)} ngày {max(0, len(days) - 1)} đêm" if days else ""
    aliases = ", ".join(source.aliases)
    summary = "\n".join(part for part in [source.tour_name, duration, "Lộ trình: " + "; ".join(day_titles), "Từ khóa: " + aliases] if part)
    full = "\n\n".join(day.content for day in days)
    return [
        CatalogRecord(record_id=f"{source.tour_code}_tour_summary", tour_code=source.tour_code, tour_name=source.tour_name,
                      document_type="tour_summary", content=summary,
                      embedding_text=f"{source.tour_name} ({source.tour_code})\nTóm tắt tour\n{summary}", source_chunk_ids=[]),
        CatalogRecord(record_id=f"{source.tour_code}_full_itinerary", tour_code=source.tour_code, tour_name=source.tour_name,
                      document_type="full_itinerary", content=full,
                      embedding_text=f"{source.tour_name} ({source.tour_code})\nLịch trình đầy đủ\n{full}",
                      source_chunk_ids=[c.chunk_id for c in days]),
    ]
