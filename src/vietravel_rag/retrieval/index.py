"""Build the two application-owned persistent Chroma collections."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import chromadb
from langchain_chroma import Chroma

from vietravel_rag.config import Settings
from vietravel_rag.llm import get_embeddings

CATALOG_COLLECTION = "tour_catalog"
KNOWLEDGE_COLLECTION = "tour_knowledge"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _metadata(record: dict[str, Any]) -> dict[str, str | int | float | bool]:
    result: dict[str, str | int | float | bool] = {}
    for key, value in record.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            result[key] = value
        else:
            result[key] = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return result


def _replace_collection(
    client, name: str, records: list[dict[str, Any]], id_field: str, embeddings
) -> Chroma:
    if name in {collection.name for collection in client.list_collections()}:
        client.delete_collection(name)
    store = Chroma(
        collection_name=name,
        embedding_function=embeddings,
        client=client,
        collection_metadata={"hnsw:space": "cosine"},
    )
    if records:
        store.add_texts(
            texts=[record["embedding_text"] for record in records],
            metadatas=[_metadata(record) for record in records],
            ids=[record[id_field] for record in records],
        )
    return store


def build_collections(
    settings: Settings,
    *,
    embeddings=None,
    catalog_path: Path | str = "data/processed/tour_catalog.jsonl",
    chunks_path: Path | str = "data/processed/tour_chunks.jsonl",
):
    """Replace only tour_catalog and tour_knowledge under the configured directory."""
    persist_dir = Path(settings.chroma_persist_dir)
    persist_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(persist_dir))
    embeddings = embeddings or get_embeddings(settings)
    catalog = _read_jsonl(Path(catalog_path))
    chunks = _read_jsonl(Path(chunks_path))
    catalog_store = _replace_collection(
        client, CATALOG_COLLECTION, catalog, "record_id", embeddings
    )
    knowledge_store = _replace_collection(
        client, KNOWLEDGE_COLLECTION, chunks, "chunk_id", embeddings
    )
    catalog_store.relevance_floor = settings.tour_resolution_relevance_floor
    catalog_store.relevance_margin = settings.tour_resolution_margin
    return catalog_store, knowledge_store
