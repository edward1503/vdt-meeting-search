"""Create the Elasticsearch index and bulk-index processed chunks."""

from __future__ import annotations

import argparse
from pathlib import Path

from elasticsearch import Elasticsearch, helpers

from src.core.config import settings
from src.embedding.model import embed_texts
from src.preprocessing.jsonl import read_jsonl


DEFAULT_INDEX = "meeting_chunks"


def create_index(es: Elasticsearch, index_name: str = DEFAULT_INDEX, recreate: bool = False) -> None:
    if recreate and es.indices.exists(index=index_name):
        es.indices.delete(index=index_name)
    if es.indices.exists(index=index_name):
        return
    es.indices.create(
        index=index_name,
        mappings={
            "properties": {
                "chunk_id": {"type": "keyword"},
                "meeting_id": {"type": "keyword"},
                "raw_meeting_id": {"type": "keyword"},
                "source": {"type": "keyword"},
                "split": {"type": "keyword"},
                "title": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "date": {"type": "date", "ignore_malformed": True},
                "start_time": {"type": "keyword"},
                "content_text": {"type": "text"},
                "metadata_text": {"type": "text"},
                "speakers": {"type": "keyword"},
                "speaker_agents": {"type": "keyword"},
                "speaker_roles": {"type": "keyword"},
                "time_start": {"type": "float"},
                "time_end": {"type": "float"},
                "token_count": {"type": "integer"},
                "content_embedding": {
                    "type": "dense_vector",
                    "dims": settings.embedding_dim,
                    "index": True,
                    "similarity": "cosine",
                },
                "metadata_embedding": {
                    "type": "dense_vector",
                    "dims": settings.embedding_dim,
                    "index": True,
                    "similarity": "cosine",
                },
            }
        },
    )


def index_chunk_docs(
    es: Elasticsearch,
    chunks: list[dict],
    index_name: str = DEFAULT_INDEX,
    batch_size: int = 64,
) -> int:
    """Embed (content + metadata) and bulk-index a list of chunk dicts. Returns count."""
    total = 0
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start:start + batch_size]
        vectors = embed_texts([chunk["content_text"] for chunk in batch], batch_size=batch_size)
        meta_vectors = embed_texts([chunk.get("metadata_text") or "" for chunk in batch], batch_size=batch_size)
        actions = []
        for chunk, vector, meta_vector in zip(batch, vectors, meta_vectors, strict=True):
            doc = dict(chunk)
            doc["content_embedding"] = vector
            doc["metadata_embedding"] = meta_vector
            actions.append({
                "_index": index_name,
                "_id": chunk["chunk_id"],
                "_source": doc,
            })
        helpers.bulk(es, actions)
        total += len(actions)
    return total


def delete_meeting(es: Elasticsearch, meeting_id: str, index_name: str = DEFAULT_INDEX) -> int:
    """Delete all chunks of a meeting. Returns number of deleted documents."""
    result = es.delete_by_query(
        index=index_name,
        query={"term": {"meeting_id": meeting_id}},
        refresh=True,
        ignore=[404],
    )
    return result.get("deleted", 0)


def index_chunks(
    chunks_path: Path,
    index_name: str = DEFAULT_INDEX,
    es_host: str = settings.es_host,
    recreate: bool = False,
    batch_size: int = 64,
    source_filter: str | None = None,
) -> int:
    chunks = list(read_jsonl(chunks_path))
    if source_filter:
        chunks = [chunk for chunk in chunks if chunk.get("source") == source_filter]

    es = Elasticsearch(es_host, request_timeout=60)
    try:
        create_index(es, index_name=index_name, recreate=recreate)
        total = index_chunk_docs(es, chunks, index_name=index_name, batch_size=batch_size)
        print(f"Indexed {total}/{len(chunks)} chunks into {index_name}")
        es.indices.refresh(index=index_name)
        return total
    finally:
        es.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunks", type=Path, default=Path("data/processed/chunks.jsonl"))
    parser.add_argument("--index", default=DEFAULT_INDEX)
    parser.add_argument("--es-host", default=settings.es_host)
    parser.add_argument("--recreate", action="store_true")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--source", choices=["qmsum", "ami"], default=None)
    args = parser.parse_args()
    total = index_chunks(
        chunks_path=args.chunks,
        index_name=args.index,
        es_host=args.es_host,
        recreate=args.recreate,
        batch_size=args.batch_size,
        source_filter=args.source,
    )
    print(f"indexed_chunks: {total}")


if __name__ == "__main__":
    main()
