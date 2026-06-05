from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from src.core.config import settings
from src.retrieval.base import BackendUnavailable, RetrievalBackend


class ElasticsearchBackend(RetrievalBackend):
    name = "elasticsearch"

    def __init__(
        self,
        index_dir: Path,
        url: str = settings.elasticsearch_url,
        index_name: str = settings.elasticsearch_index,
    ) -> None:
        super().__init__(index_dir)
        self.url = url
        self.index_name = index_name
        self.client = None
        self.chunks = _read_jsonl(index_dir / "chunks.jsonl")

    def build(self, vectors: np.ndarray) -> dict[str, int | str | float]:
        client = self._client()
        dim = int(vectors.shape[1])
        if client.indices.exists(index=self.index_name):
            client.indices.delete(index=self.index_name)
        client.indices.create(
            index=self.index_name,
            mappings={
                "properties": {
                    "chunk_index": {"type": "integer"},
                    "chunk_id": {"type": "keyword"},
                    "meeting_id": {"type": "keyword"},
                    "title": {"type": "text"},
                    "date": {"type": "keyword"},
                    "participants": {"type": "keyword"},
                    "speakers": {"type": "keyword"},
                    "text": {"type": "text"},
                    "embedding": {
                        "type": "dense_vector",
                        "dims": dim,
                        "index": True,
                        "similarity": "cosine",
                    },
                }
            },
        )

        from elasticsearch.helpers import bulk

        actions = []
        for idx, (chunk, vector) in enumerate(zip(self.chunks, vectors)):
            source = {
                "chunk_index": idx,
                "chunk_id": chunk["chunk_id"],
                "meeting_id": chunk["meeting_id"],
                "title": chunk.get("title"),
                "date": chunk.get("date"),
                "participants": chunk.get("participants", []),
                "speakers": chunk.get("speakers", []),
                "time_start": chunk.get("time_start"),
                "time_end": chunk.get("time_end"),
                "text": chunk.get("text", ""),
                "embedding": vector.astype("float32").tolist(),
            }
            actions.append({"_index": self.index_name, "_id": str(idx), "_source": source})
        bulk(client, actions)
        client.indices.refresh(index=self.index_name)
        return {"backend": self.name, "vectors": int(vectors.shape[0]), "dim": dim, "index": self.index_name}

    def load(self) -> None:
        self._client()

    def search(self, query_vector: np.ndarray, top_k: int) -> tuple[np.ndarray, np.ndarray]:
        client = self._client()
        response = client.search(
            index=self.index_name,
            knn={
                "field": "embedding",
                "query_vector": query_vector[0].astype("float32").tolist(),
                "k": top_k,
                "num_candidates": max(top_k * 8, 25),
            },
            source=["chunk_index"],
            size=top_k,
        )
        hits = response.get("hits", {}).get("hits", [])
        scores = np.array([hit.get("_score", 0.0) for hit in hits], dtype="float32")
        indices = np.array([hit.get("_source", {}).get("chunk_index", int(hit["_id"])) for hit in hits], dtype="int64")
        return scores, indices

    def _client(self):
        if self.client is not None:
            return self.client
        try:
            from elasticsearch import Elasticsearch
        except Exception as exc:  # pragma: no cover
            raise BackendUnavailable(f"elasticsearch Python client is not installed: {exc}") from exc
        client = Elasticsearch(self.url, request_timeout=30)
        try:
            if not client.ping():
                raise BackendUnavailable(f"Elasticsearch is not reachable at {self.url}")
        except BackendUnavailable:
            raise
        except Exception as exc:
            raise BackendUnavailable(f"Elasticsearch is not reachable at {self.url}: {exc}") from exc
        self.client = client
        return client


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
