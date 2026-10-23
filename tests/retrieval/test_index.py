import json
from pathlib import Path

from langchain_core.embeddings import Embeddings

from vietravel_rag.config import Settings
from vietravel_rag.retrieval.index import build_collections


class FakeEmbeddings(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    @staticmethod
    def _embed(text: str) -> list[float]:
        words = set(text.casefold().split())
        return [
            float(len(words & group))
            for group in ({"bà", "nà", "đà"}, {"bangkok", "thailand"}, {"bãi", "biển"})
        ]


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def test_build_collections_embed_embedding_text_and_keep_content_metadata(tmp_path: Path):
    catalog = tmp_path / "catalog.jsonl"
    chunks = tmp_path / "chunks.jsonl"
    _write_jsonl(
        catalog,
        [
            {
                "record_id": "danang-summary",
                "tour_code": "danang-central-5d4n",
                "tour_name": "Đà Nẵng",
                "document_type": "tour_summary",
                "content": "Nội dung sạch",
                "embedding_text": "Đà Nẵng Bà Nà",
                "source_chunk_ids": [],
            }
        ],
    )
    _write_jsonl(
        chunks,
        [
            {
                "chunk_id": "baggage-01",
                "tour_code": "danang-central-5d4n",
                "tour_name": "Đà Nẵng",
                "document_type": "knowledge",
                "section_type": "included",
                "section_title": "Hành lý",
                "page_start": 3,
                "page_end": 3,
                "source_file": "tour.pdf",
                "authority": "official_tour_pdf",
                "content": "Nội dung trích dẫn",
                "embedding_text": "Đà Nẵng Bà Nà hành lý",
                "page_texts": {"3": "x"},
            }
        ],
    )

    catalog_store, knowledge_store = build_collections(
        Settings(deepseek_api_key="d", openai_api_key="o", chroma_persist_dir=str(tmp_path / "db")),
        embeddings=FakeEmbeddings(),
        catalog_path=catalog,
        chunks_path=chunks,
    )

    catalog_doc = catalog_store.get_by_ids(["danang-summary"])[0]
    chunk_doc = knowledge_store.get_by_ids(["baggage-01"])[0]
    assert catalog_doc.page_content == "Đà Nẵng Bà Nà"
    assert catalog_doc.metadata["content"] == "Nội dung sạch"
    assert catalog_doc.metadata["document_type"] == "tour_summary"
    assert chunk_doc.metadata["content"] == "Nội dung trích dẫn"
    assert chunk_doc.metadata["page_start"] == 3


def test_rebuilding_replaces_only_the_two_owned_collections(tmp_path: Path):
    import chromadb

    catalog = tmp_path / "catalog.jsonl"
    chunks = tmp_path / "chunks.jsonl"
    _write_jsonl(
        catalog,
        [
            {
                "record_id": "fresh",
                "tour_code": "tour-a",
                "tour_name": "A",
                "document_type": "tour_summary",
                "content": "A",
                "embedding_text": "Bà Nà",
                "source_chunk_ids": [],
            }
        ],
    )
    _write_jsonl(chunks, [])
    settings = Settings(
        deepseek_api_key="d", openai_api_key="o", chroma_persist_dir=str(tmp_path / "db")
    )
    first_catalog, _ = build_collections(
        settings, embeddings=FakeEmbeddings(), catalog_path=catalog, chunks_path=chunks
    )
    first_catalog.add_texts(["stale"], ids=["stale"])
    client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    external = client.create_collection("external_collection")
    external.add(ids=["keep"], embeddings=[[1.0, 0.0, 0.0]], documents=["keep"])

    second_catalog, _ = build_collections(
        settings, embeddings=FakeEmbeddings(), catalog_path=catalog, chunks_path=chunks
    )

    assert second_catalog._collection.get()["ids"] == ["fresh"]
    assert "external_collection" in {collection.name for collection in client.list_collections()}
    assert client.get_collection("external_collection").get()["ids"] == ["keep"]
