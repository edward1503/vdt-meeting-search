from __future__ import annotations

import json
import time
from typing import Any
from urllib import request

import numpy as np

from src.retrieval.elasticsearch_retriever import fuse_rrf


class RemoteEmbeddingClient:
    def __init__(self, embedding_service_url: str, timeout_seconds: int = 30, embedding_model_id: str = "") -> None:
        self.embedding_service_url = embedding_service_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.embedding_model_id = embedding_model_id

    def encode(self, texts: list[str], normalize_embeddings: bool = True, convert_to_numpy: bool = True) -> np.ndarray:
        if len(texts) != 1:
            raise ValueError("RemoteEmbeddingClient supports exactly one query at a time")
        body = {"text": texts[0]}
        if self.embedding_model_id:
            body["model_id"] = self.embedding_model_id
        payload = json.dumps(body, separators=(",", ":")).encode("utf-8")
        req = request.Request(
            self.embedding_service_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=self.timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
        return np.asarray([[float(value) for value in body["embedding"]]], dtype=np.float32)


class ElasticsearchNumericDocStore:
    def __init__(self, es: Any, index: str) -> None:
        self.es = es
        self.index = index

    def hydrate_by_numeric_ids(self, numeric_ids: list[int]) -> list[dict[str, Any]]:
        if not numeric_ids:
            return []
        response = self.es.search(
            index=self.index,
            body={
                "size": len(numeric_ids),
                "query": {"terms": {"numeric_id": [int(value) for value in numeric_ids]}},
                "_source": ["numeric_id", "doc_id", "title", "text", "url"],
            },
        )
        docs = {}
        for hit in response.get("hits", {}).get("hits", []):
            src = hit.get("_source", {})
            docs[int(src["numeric_id"])] = {
                "numeric_id": int(src["numeric_id"]),
                "doc_id": src.get("doc_id", hit.get("_id", "")),
                "title": src.get("title", ""),
                "text": src.get("text", ""),
                "url": src.get("url", ""),
            }
        return [docs[int(numeric_id)] for numeric_id in numeric_ids if int(numeric_id) in docs]


class TurboVecHybridRetriever:
    def __init__(self, bm25_retriever: Any, tv_index: Any, embedder: Any, docstore: Any) -> None:
        self.bm25_retriever = bm25_retriever
        self.tv_index = tv_index
        self.embedder = embedder
        self.docstore = docstore
        self.last_timing_ms: dict[str, float] = {}

    @classmethod
    def from_paths(
        cls,
        bm25_retriever: Any,
        es: Any,
        index: str,
        tv_index_path: str,
        model_name: str,
        embedding_service_url: str = "",
        embedding_timeout_seconds: int = 30,
        embedding_model_id: str = "",
    ) -> "TurboVecHybridRetriever":
        from turbovec import IdMapIndex

        if embedding_service_url:
            embedder = RemoteEmbeddingClient(
                embedding_service_url,
                timeout_seconds=embedding_timeout_seconds,
                embedding_model_id=embedding_model_id,
            )
        else:
            from sentence_transformers import SentenceTransformer

            embedder = SentenceTransformer(model_name)

        return cls(
            bm25_retriever=bm25_retriever,
            tv_index=IdMapIndex.load(tv_index_path),
            embedder=embedder,
            docstore=ElasticsearchNumericDocStore(es, index),
        )

    def search(
        self,
        query: str,
        method: str,
        top_k: int,
        bm25_k: int = 100,
        dense_k: int = 100,
        rrf_k: int = 60,
        candidate_k: int | None = None,
        **_: Any,
    ) -> list[dict[str, Any]]:
        if candidate_k is not None:
            bm25_k = candidate_k
            dense_k = candidate_k
        if method == "tv_dense":
            return self._search_dense(query, top_k)
        if method == "tv_hybrid":
            return self._search_hybrid(query, top_k, bm25_k=bm25_k, dense_k=dense_k, rrf_k=rrf_k)
        if method == "tv_filtered_hybrid":
            return self._search_filtered_hybrid(query, top_k, bm25_k=bm25_k, dense_k=dense_k, rrf_k=rrf_k)
        raise ValueError(f"Unknown TurboVec method: {method}")

    def _embed_query(self, query: str) -> np.ndarray:
        vector = self.embedder.encode([query], normalize_embeddings=True, convert_to_numpy=True)
        return np.asarray(vector, dtype=np.float32)

    def _build_allowlist(self, hits: list[dict[str, Any]]) -> np.ndarray | None:
        ids: list[int] = []
        seen: set[int] = set()
        for hit in hits:
            raw_numeric_id = hit.get("numeric_id")
            if raw_numeric_id is None:
                continue
            try:
                numeric_id = int(raw_numeric_id)
            except (TypeError, ValueError):
                continue
            if numeric_id in seen:
                continue
            seen.add(numeric_id)
            ids.append(numeric_id)
        if not ids:
            return None
        return np.asarray(ids, dtype=np.uint64)

    def _search_dense(self, query: str, top_k: int, allowlist: Any | None = None) -> list[dict[str, Any]]:
        timing: dict[str, float] = {}
        start = time.perf_counter()
        vector = self._embed_query(query)
        timing["embed"] = (time.perf_counter() - start) * 1000
        start = time.perf_counter()
        scores, ids = self.tv_index.search(vector, k=top_k, allowlist=allowlist)
        timing["turbovec"] = (time.perf_counter() - start) * 1000
        numeric_ids = [int(value) for value in ids[0].tolist()]
        score_values = [float(value) for value in scores[0].tolist()]
        start = time.perf_counter()
        docs = self.docstore.hydrate_by_numeric_ids(numeric_ids)
        timing["hydrate"] = (time.perf_counter() - start) * 1000
        docs_by_id = {int(doc["numeric_id"]): doc for doc in docs}
        hits = []
        for numeric_id, score in zip(numeric_ids, score_values):
            if numeric_id not in docs_by_id:
                continue
            hits.append({**docs_by_id[numeric_id], "score": score, "source": "dense"})
        self.last_timing_ms = timing
        return hits

    def _search_hybrid(self, query: str, top_k: int, bm25_k: int, dense_k: int, rrf_k: int) -> list[dict[str, Any]]:
        start = time.perf_counter()
        bm25_hits = self.bm25_retriever.search(query, "bm25", bm25_k)
        bm25_ms = (time.perf_counter() - start) * 1000
        dense_hits = self._search_dense(query, dense_k)
        timing = {**self.last_timing_ms, "bm25": bm25_ms}
        start = time.perf_counter()
        fused = fuse_rrf([bm25_hits, dense_hits], top_k=top_k, rrf_k=rrf_k)
        timing["fusion"] = (time.perf_counter() - start) * 1000
        self.last_timing_ms = timing
        return fused

    def _search_filtered_hybrid(self, query: str, top_k: int, bm25_k: int, dense_k: int, rrf_k: int) -> list[dict[str, Any]]:
        start = time.perf_counter()
        bm25_hits = self.bm25_retriever.search(query, "bm25", bm25_k)
        bm25_ms = (time.perf_counter() - start) * 1000

        start = time.perf_counter()
        allowlist = self._build_allowlist(bm25_hits)
        allowlist_ms = (time.perf_counter() - start) * 1000

        dense_search_k = min(dense_k, len(allowlist)) if allowlist is not None else dense_k
        dense_hits = self._search_dense(query, dense_search_k, allowlist=allowlist)
        timing = {**self.last_timing_ms, "bm25": bm25_ms, "allowlist": allowlist_ms}

        start = time.perf_counter()
        fused = fuse_rrf([bm25_hits, dense_hits], top_k=top_k, rrf_k=rrf_k)
        timing["fusion"] = (time.perf_counter() - start) * 1000
        self.last_timing_ms = timing
        return fused
