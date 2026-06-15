from __future__ import annotations

import json
import re
from typing import Any
from urllib import request

TOKEN_RE = re.compile(r"[A-Za-z0-9]+")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def build_index_body(dims: int, shards: int = 1) -> dict[str, Any]:
    return {
        "settings": {"number_of_shards": shards, "number_of_replicas": 0, "refresh_interval": "-1"},
        "mappings": {
            "properties": {
                "doc_id": {"type": "keyword"},
                "title": {"type": "text"},
                "text": {"type": "text"},
                "url": {"type": "keyword"},
                "content": {"type": "text"},
                "embedding": {"type": "dense_vector", "dims": dims, "similarity": "cosine"},
            }
        },
    }


def bulk_action(index: str, row: dict[str, Any], embedding: list[float]) -> dict[str, Any]:
    return {
        "_index": index,
        "_id": row["doc_id"],
        "doc_id": row["doc_id"],
        "title": row.get("title", ""),
        "text": row.get("text", ""),
        "url": row.get("url", ""),
        "content": row.get("content", ""),
        "embedding": embedding,
    }

def build_bm25_index_body(shards: int = 1) -> dict[str, Any]:
    return {
        "settings": {"number_of_shards": shards, "number_of_replicas": 0, "refresh_interval": "-1"},
        "mappings": {
            "properties": {
                "numeric_id": {"type": "long"},
                "doc_id": {"type": "keyword"},
                "title": {"type": "text"},
                "text": {"type": "text"},
                "url": {"type": "keyword"},
                "content": {"type": "text"},
            }
        },
    }


def bm25_bulk_action(index: str, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "_index": index,
        "_id": row["doc_id"],
        "numeric_id": int(row["numeric_id"]),
        "doc_id": row["doc_id"],
        "title": row.get("title", ""),
        "text": row.get("text", ""),
        "url": row.get("url", ""),
        "content": row.get("content", ""),
    }

def build_bm25_query(query: str, top_k: int) -> dict[str, Any]:
    return {
        "size": top_k,
        "track_total_hits": False,
        "_source": ["numeric_id", "doc_id", "title", "text", "url"],
        "query": {"multi_match": {"query": query, "fields": ["title^2", "content"]}},
    }


def build_knn_query(vector: list[float], top_k: int, num_candidates: int) -> dict[str, Any]:
    return {
        "_source": ["numeric_id", "doc_id", "title", "text", "url"],
        "knn": {"field": "embedding", "query_vector": vector, "k": top_k, "num_candidates": num_candidates},
    }


def fuse_rrf(rankings: list[list[dict[str, Any]]], top_k: int, rrf_k: int = 60) -> list[dict[str, Any]]:
    scores: dict[str, float] = {}
    docs: dict[str, dict[str, Any]] = {}
    sources: dict[str, set[str]] = {}
    for ranking in rankings:
        for rank, hit in enumerate(ranking, start=1):
            doc_id = str(hit["doc_id"])
            docs.setdefault(doc_id, hit)
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (rrf_k + rank)
            if hit.get("source"):
                sources.setdefault(doc_id, set()).add(str(hit["source"]))
    fused = []
    for doc_id, score in sorted(scores.items(), key=lambda item: item[1], reverse=True)[:top_k]:
        hit = {**docs[doc_id], "score": score}
        if doc_id in sources:
            hit["source"] = "+".join(sorted(sources[doc_id]))
        fused.append(hit)
    return fused


class ElasticsearchRetriever:
    def __init__(
        self,
        es: Any,
        index: str,
        model_name: str,
        num_candidates: int = 1000,
        model: Any | None = None,
        embedding_service_url: str = "",
        embedding_timeout_seconds: int = 30,
    ) -> None:
        self.es = es
        self.index = index
        self.model_name = model_name
        self.model = model
        self.num_candidates = num_candidates
        self.embedding_service_url = embedding_service_url.rstrip("/")
        self.embedding_timeout_seconds = embedding_timeout_seconds

    def search(self, query: str, method: str, top_k: int, candidate_k: int = 100, rrf_k: int = 60) -> list[dict[str, Any]]:
        if method == "bm25":
            return self._search_body(build_bm25_query(query, top_k), "bm25")
        if method == "dense":
            return self._search_dense(query, top_k, self.num_candidates)
        if method == "hybrid":
            return fuse_rrf(
                [
                    self.search(query, "bm25", candidate_k),
                    self._search_dense(query, candidate_k, max(candidate_k, self.num_candidates)),
                ],
                top_k,
                rrf_k=rrf_k,
            )
        if method == "iterative_hybrid":
            return self.search_iterative_hybrid(query, top_k, candidate_k=candidate_k, rrf_k=rrf_k)
        raise ValueError(f"Unknown method: {method}")

    def search_iterative_hybrid(
        self,
        query: str,
        top_k: int,
        candidate_k: int = 100,
        rrf_k: int = 60,
        first_hop_k: int = 5,
        second_hop_k: int = 10,
        context_chars: int = 256,
        expansion_mode: str = "context",
        dedupe_hop2: bool = True,
    ) -> list[dict[str, Any]]:
        hop1_hits = self.search(query, "hybrid", first_hop_k, candidate_k=candidate_k, rrf_k=rrf_k)
        rankings: list[list[dict[str, Any]]] = [hop1_hits]
        hop_labels: dict[str, int] = {str(hit["doc_id"]): 1 for hit in hop1_hits}
        seen_hop1_doc_ids = set(hop_labels)

        for hit in hop1_hits:
            expanded_query = self._expand_query(query, hit, context_chars, expansion_mode=expansion_mode)
            hop2_hits = self.search(expanded_query, "hybrid", second_hop_k, candidate_k=candidate_k, rrf_k=rrf_k)
            if dedupe_hop2:
                hop2_hits = [hop2_hit for hop2_hit in hop2_hits if str(hop2_hit["doc_id"]) not in seen_hop1_doc_ids]
            rankings.append(hop2_hits)
            for hop2_hit in hop2_hits:
                hop_labels.setdefault(str(hop2_hit["doc_id"]), 2)

        fused = fuse_rrf(rankings, top_k, rrf_k=rrf_k)
        for hit in fused:
            hit["hop"] = hop_labels.get(str(hit["doc_id"]), 2)
            hit["source"] = f"iterative_{hit.get('source', 'hybrid')}"
        return fused

    def _expand_query(self, query: str, hit: dict[str, Any], context_chars: int, expansion_mode: str = "context") -> str:
        title = str(hit.get("title", "") or "")
        text = str(hit.get("text", "") or "").replace("\n", " ")
        if expansion_mode == "context":
            parts = [query, title, text[:context_chars]]
        elif expansion_mode == "title":
            parts = [query, title]
        elif expansion_mode == "sentence":
            parts = [query, title, self._select_sentence(query, text)]
        else:
            raise ValueError(f"Unknown expansion mode: {expansion_mode}")
        return " ".join(part for part in parts if part)

    def _select_sentence(self, query: str, text: str) -> str:
        sentences = [sentence.strip().rstrip(".") for sentence in SENTENCE_RE.split(text) if sentence.strip()]
        if not sentences:
            return ""
        query_terms = {token.lower() for token in TOKEN_RE.findall(query)}
        return max(sentences, key=lambda sentence: self._sentence_overlap_score(query_terms, sentence))

    def _sentence_overlap_score(self, query_terms: set[str], sentence: str) -> tuple[int, int]:
        sentence_terms = {token.lower() for token in TOKEN_RE.findall(sentence)}
        return (len(query_terms & sentence_terms), len(sentence_terms))

    def _search_dense(self, query: str, top_k: int, num_candidates: int) -> list[dict[str, Any]]:
        return self._search_body(build_knn_query(self._embed_query(query), top_k, num_candidates), "dense")

    def _embed_query(self, query: str) -> list[float]:
        if self.embedding_service_url:
            return self._embed_query_remote(query)
        return _vector_to_list(self._model().encode([query], normalize_embeddings=True, convert_to_numpy=True)[0])

    def _embed_query_remote(self, query: str) -> list[float]:
        payload = json.dumps({"text": query}, separators=(",", ":")).encode("utf-8")
        req = request.Request(
            self.embedding_service_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=self.embedding_timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
        return [float(value) for value in body["embedding"]]

    def _search_body(self, body: dict[str, Any], source: str) -> list[dict[str, Any]]:
        response = self.es.search(index=self.index, body=body)
        hits = []
        for hit in response.get("hits", {}).get("hits", []):
            src = hit.get("_source", {})
            result = {
                "doc_id": src.get("doc_id", hit.get("_id", "")),
                "title": src.get("title", ""),
                "text": src.get("text", ""),
                "url": src.get("url", ""),
                "score": float(hit.get("_score", 0.0)),
                "source": source,
            }
            if "numeric_id" in src and src["numeric_id"] is not None:
                result["numeric_id"] = int(src["numeric_id"])
            hits.append(result)
        return hits

    def _model(self) -> Any:
        if self.model is None:
            from sentence_transformers import SentenceTransformer

            self.model = SentenceTransformer(self.model_name)
        return self.model


def _vector_to_list(vector: Any) -> list[float]:
    if hasattr(vector, "astype"):
        vector = vector.astype(float)
    if hasattr(vector, "tolist"):
        return [float(value) for value in vector.tolist()]
    return [float(value) for value in vector]

