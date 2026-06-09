from __future__ import annotations

import csv
import json
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

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
def get_es_retriever() -> ElasticsearchRetriever:
    from elasticsearch import Elasticsearch

    return ElasticsearchRetriever(
        es=Elasticsearch(settings.elasticsearch_url, request_timeout=120),
        index=settings.elasticsearch_index,
        model_name=settings.embedding_model,
        num_candidates=settings.elasticsearch_num_candidates,
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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/stats")
def stats() -> dict[str, Any]:
    return {
        "backend": "elasticsearch",
        "index": settings.elasticsearch_index,
        "methods": sorted(ES_METHODS),
    }


@app.get("/queries")
def queries() -> dict[str, Any]:
    rows = get_query_examples()
    return {"count": len(rows), "queries": rows}


@app.get("/benchmark")
def benchmark() -> dict[str, Any]:
    return get_benchmark_result()


@app.post("/search")
def search(request: SearchRequest) -> dict[str, Any]:
    method = request.method.strip().lower()
    if method not in METHODS:
        raise HTTPException(status_code=400, detail=f"Unknown method: {request.method}")

    start = time.perf_counter()
    hits = get_es_retriever().search(request.query, ES_METHOD_MAP[method], request.top_k)
    latency_ms = round((time.perf_counter() - start) * 1000, 4)
    return {
        "query": request.query,
        "method": method,
        "top_k": request.top_k,
        "latency_ms": latency_ms,
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
