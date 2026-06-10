from __future__ import annotations

import csv
import hashlib
import json
import logging
import threading
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.api.history import SearchHistoryStore

from src.core.config import settings
from src.retrieval.elasticsearch_retriever import ElasticsearchRetriever

ROOT_DIR = Path(__file__).resolve().parents[2]
QUERY_EXAMPLES_PATH = ROOT_DIR / "evaluation" / "results" / "nano_test_queries.tsv"
BENCHMARK_RESULT_PATH = ROOT_DIR / "evaluation" / "results" / "es_nano_iterative.json"

ES_METHODS = {"es_bm25", "es_dense", "es_hybrid", "es_iterative_hybrid"}
ES_METHOD_MAP = {
    "es_bm25": "bm25",
    "es_dense": "dense",
    "es_hybrid": "hybrid",
    "es_iterative_hybrid": "iterative_hybrid",
}
METHODS = ES_METHODS
logger = logging.getLogger("uvicorn.error")

def build_search_cache_key(*, index: str, query: str, method: str, top_k: int) -> str:
    payload = json.dumps(
        {
            "index": index,
            "method": method,
            "query": query.strip(),
            "top_k": top_k,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"search:v1:{digest}"

@lru_cache(maxsize=1)
def get_redis_client() -> Any | None:
    if not settings.redis_url:
        return None
    try:
        from redis import Redis

        return Redis.from_url(settings.redis_url, decode_responses=True)
    except Exception:
        return None

def read_search_cache(cache_key: str) -> dict[str, Any] | None:
    client = get_redis_client()
    if client is None:
        return None
    try:
        cached = client.get(cache_key)
        if not cached:
            return None
        payload = json.loads(cached)
        payload["cache_hit"] = True
        payload["latency_ms"] = 0.0
        return payload
    except Exception:
        return None

def write_search_cache(cache_key: str, payload: dict[str, Any]) -> None:
    client = get_redis_client()
    if client is None:
        return
    try:
        client.setex(cache_key, settings.search_cache_ttl_seconds, json.dumps(payload))
    except Exception:
        return

app = FastAPI(title="HotpotQA Elasticsearch Retrieval", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    method: str = Field(default="es_hybrid")
    top_k: int = Field(default=10, ge=1, le=50)


@lru_cache(maxsize=1)
def get_history_store() -> SearchHistoryStore:
    store = SearchHistoryStore(settings.history_db_path)
    store.init_db()
    return store


def find_support_doc_ids(query: str) -> list[str]:
    normalized = query.strip().lower()
    if not normalized:
        return []
    for row in get_query_examples():
        if str(row.get("query", "")).strip().lower() == normalized:
            return [str(doc_id) for doc_id in row.get("support_doc_ids", [])]
    return []

@lru_cache(maxsize=1)
def get_es_retriever() -> ElasticsearchRetriever:
    from elasticsearch import Elasticsearch

    return ElasticsearchRetriever(
        es=Elasticsearch(settings.elasticsearch_url, request_timeout=120),
        index=settings.elasticsearch_index,
        model_name=settings.embedding_model,
        num_candidates=settings.elasticsearch_num_candidates,
        embedding_service_url=settings.embedding_service_url,
        embedding_timeout_seconds=settings.embedding_timeout_seconds,
    )


def load_query_examples(path: Path = QUERY_EXAMPLES_PATH) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = []
        for row in csv.DictReader(handle, delimiter="\t"):
            support_doc_ids = [doc_id.strip() for doc_id in row.get("support_doc_ids", "").split(",") if doc_id.strip()]
            rows.append(
                {
                    "query_id": row.get("query_id", ""),
                    "query": row.get("query", ""),
                    "support_doc_ids": support_doc_ids,
                    "support_doc_count": len(support_doc_ids),
                }
            )
    return rows


def build_query_examples(queries: Any, qrels: Any) -> list[dict[str, Any]]:
    supports_by_query: dict[str, list[str]] = {}
    for qrel in qrels:
        query_id = str(getattr(qrel, "query_id"))
        relevance = float(getattr(qrel, "relevance", 1.0))
        if relevance <= 0:
            supports_by_query.setdefault(query_id, [])
            continue
        supports_by_query.setdefault(query_id, []).append(str(getattr(qrel, "doc_id")))

    rows = []
    for query in queries:
        query_id = str(getattr(query, "query_id"))
        support_doc_ids = supports_by_query.get(query_id, [])
        rows.append(
            {
                "query_id": query_id,
                "query": str(getattr(query, "text", "") or ""),
                "support_doc_ids": support_doc_ids,
                "support_doc_count": len(support_doc_ids),
            }
        )
    return rows


def load_dataset_query_examples(dataset_id: str = settings.dataset_id) -> list[dict[str, Any]]:
    import ir_datasets

    dataset = ir_datasets.load(dataset_id)
    return build_query_examples(dataset.queries_iter(), dataset.qrels_iter())


def load_benchmark_result(path: Path = BENCHMARK_RESULT_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def get_query_examples() -> list[dict[str, Any]]:
    try:
        return load_dataset_query_examples()
    except Exception:
        return load_query_examples()


@lru_cache(maxsize=1)
def get_benchmark_result() -> dict[str, Any]:
    return load_benchmark_result()


def warm_embedding_model() -> None:
    start = time.perf_counter()
    logger.info("Warming embedding model %s", settings.embedding_model)
    try:
        get_es_retriever()._embed_query("warmup")
    except Exception:
        logger.exception("Embedding model warm-up failed")
        return
    logger.info("Embedding model warm-up finished in %.2fs", time.perf_counter() - start)

@app.on_event("startup")
def start_embedding_warmup() -> None:
    if settings.warmup_embedding_model:
        thread = threading.Thread(target=warm_embedding_model, name="embedding-model-warmup", daemon=True)
        thread.start()
@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/stats")
def stats() -> dict[str, Any]:
    return {
        "backend": "elasticsearch",
        "index": settings.elasticsearch_index,
        "methods": sorted(ES_METHODS),
        "dataset_id": settings.dataset_id,
        "embedding_model": settings.embedding_model,
        "embedding_service_url": settings.embedding_service_url,
        "num_candidates": settings.elasticsearch_num_candidates,
        "search_cache_ttl_seconds": settings.search_cache_ttl_seconds,
        "history_db_path": str(settings.history_db_path),
    }


@app.get("/queries")
def queries() -> dict[str, Any]:
    rows = get_query_examples()
    return {"count": len(rows), "queries": rows}


@app.get("/benchmark")
def benchmark() -> dict[str, Any]:
    return get_benchmark_result()


@app.get("/history")
def history(limit: int = 100) -> dict[str, Any]:
    bounded_limit = max(1, min(limit, 500))
    rows = get_history_store().list_history(bounded_limit)
    return {"count": len(rows), "history": rows}

@app.get("/history/{history_id}")
def history_detail(history_id: int) -> dict[str, Any]:
    row = get_history_store().get_history(history_id)
    if row is None:
        raise HTTPException(status_code=404, detail="History entry not found")
    return row

@app.delete("/history")
def clear_history() -> dict[str, int]:
    return {"deleted": get_history_store().clear_history()}
@app.post("/search")
def search(request: SearchRequest) -> dict[str, Any]:
    method = request.method.strip().lower()
    if method not in METHODS:
        raise HTTPException(status_code=400, detail=f"Unknown method: {request.method}")

    cache_key = build_search_cache_key(
        index=settings.elasticsearch_index,
        query=request.query,
        method=method,
        top_k=request.top_k,
    )
    cached = read_search_cache(cache_key)
    if cached is not None:
        cached["history_id"] = get_history_store().record_search(
            query=cached["query"],
            method=cached["method"],
            top_k=int(cached["top_k"]),
            latency_ms=float(cached["latency_ms"]),
            cache_hit=True,
            results=cached["results"],
            support_doc_ids=find_support_doc_ids(cached["query"]),
        )
        return cached

    start = time.perf_counter()
    hits = get_es_retriever().search(request.query, ES_METHOD_MAP[method], request.top_k)
    latency_ms = round((time.perf_counter() - start) * 1000, 4)
    response = {
        "query": request.query,
        "method": method,
        "top_k": request.top_k,
        "latency_ms": latency_ms,
        "cache_hit": False,
        "results": [
            {
                "doc_id": hit.get("doc_id", ""),
                "title": hit.get("title", ""),
                "text": str(hit.get("text", ""))[:800],
                "url": hit.get("url", ""),
                "score": float(hit.get("score", 0.0)),
                "rank": rank,
                "source": hit.get("source", ES_METHOD_MAP[method]),
                "hop": int(hit.get("hop", 1)),
            }
            for rank, hit in enumerate(hits, start=1)
        ],
    }
    write_search_cache(cache_key, response)
    response["history_id"] = get_history_store().record_search(
        query=response["query"],
        method=response["method"],
        top_k=int(response["top_k"]),
        latency_ms=float(response["latency_ms"]),
        cache_hit=bool(response.get("cache_hit", False)),
        results=response["results"],
        support_doc_ids=find_support_doc_ids(response["query"]),
    )
    return response
