import json
from pathlib import Path

import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from vietravel_rag.config import Settings
from vietravel_rag.retrieval.index import build_collections
from vietravel_rag.retrieval.resolver import get_full_itinerary, resolve_tours
from vietravel_rag.retrieval.resolver import ItineraryLookupError


class FakeEmbeddings(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    @staticmethod
    def _embed(text: str) -> list[float]:
        text = text.casefold()
        terms = ("bà nà", "bangkok", "miền trung", "nhật bản")
        if text.startswith("tour miền trung"):
            return [0.0, 0.0, 1.0, 0.0]
        return [float(term in text) for term in terms]


@pytest.fixture
def catalog_store(tmp_path: Path):
    catalog = tmp_path / "catalog.jsonl"
    chunks = tmp_path / "chunks.jsonl"
    records = []
    for code, name, tags in (
        ("danang-central-5d4n", "Đà Nẵng Hội An Huế", "tour Bà Nà miền Trung"),
        ("mekong-my-tho-ben-tre-can-tho", "Miền Tây", "tour miền Trung Việt Nam"),
        ("thailand-bangkok-pattaya", "Bangkok Pattaya", "tour Bangkok Thailand"),
        ("china-lijiang-dali-shangrila", "Trung Quốc", "tour Trung Quốc"),
    ):
        records.extend(
            [
                {
                    "record_id": f"{code}_tour_summary",
                    "tour_code": code,
                    "tour_name": name,
                    "document_type": "tour_summary",
                    "content": name,
                    "embedding_text": f"{name} {tags}",
                    "source_chunk_ids": [],
                },
                {
                    "record_id": f"{code}_full_itinerary",
                    "tour_code": code,
                    "tour_name": name,
                    "document_type": "full_itinerary",
                    "content": f"Lịch trình {name}",
                    "embedding_text": f"{name} lịch trình {tags}",
                    "source_chunk_ids": [],
                },
            ]
        )
    catalog.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records), encoding="utf-8"
    )
    chunks.write_text("", encoding="utf-8")
    settings = Settings(
        deepseek_api_key="d",
        gemini_api_key="g",
        chroma_persist_dir=str(tmp_path / "db"),
        _env_file=None,
    )
    return build_collections(
        settings, embeddings=FakeEmbeddings(), catalog_path=catalog, chunks_path=chunks
    )[0]


def test_catalog_search_excludes_full_itinerary(catalog_store):
    matches = resolve_tours("tour Bà Nà", catalog_store, limit=3)
    assert all(doc.metadata["document_type"] == "tour_summary" for doc in matches)
    assert matches[0].metadata["tour_code"] == "danang-central-5d4n"


def test_bangkok_resolves_to_thailand(catalog_store):
    matches = resolve_tours("Bangkok", catalog_store, limit=3)
    assert matches[0].metadata["tour_code"] == "thailand-bangkok-pattaya"


def test_broad_region_query_returns_candidates_for_clarification(catalog_store):
    matches = resolve_tours("tour miền Trung", catalog_store, limit=3)
    assert len(matches) > 1


def test_unsupported_japan_query_is_not_found(catalog_store):
    assert resolve_tours("tour Nhật Bản", catalog_store, limit=3) == []


def test_below_floor_runner_up_still_prevents_near_tie_auto_resolution():
    top = Document("top match", metadata={"tour_code": "tour-a", "document_type": "tour_summary"})
    runner_up = Document(
        "runner-up", metadata={"tour_code": "tour-b", "document_type": "tour_summary"}
    )

    class RankedStore:
        relevance_floor = 0.65
        relevance_margin = 0.10

        def similarity_search_with_relevance_scores(self, query, *, k, filter):
            return [(top, 0.66), (runner_up, 0.60)]

    matches = resolve_tours("ambiguous tour", RankedStore())

    assert [doc.metadata["tour_code"] for doc in matches] == ["tour-a", "tour-b"]


def test_full_itinerary_uses_exact_lookup(catalog_store):
    doc = get_full_itinerary("thailand-bangkok-pattaya", catalog_store)
    assert doc.metadata["document_type"] == "full_itinerary"
    assert doc.metadata["tour_code"] == "thailand-bangkok-pattaya"


def test_full_itinerary_requires_exactly_one_record(catalog_store):
    with pytest.raises(ItineraryLookupError):
        get_full_itinerary("unknown", catalog_store)
