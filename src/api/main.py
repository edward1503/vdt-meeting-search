from __future__ import annotations

import csv
import hashlib
import json
import logging
import threading
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib import request as urlrequest

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.api.dataset_profiles import DatasetProfile, get_dataset_profile, list_dataset_profiles
from src.api.history import SearchHistoryStore

from src.core.config import settings
from src.retrieval.elasticsearch_retriever import ElasticsearchRetriever
from src.retrieval.metadata_query_parser import ParsedMetadataQuery, parse_metadata_query
from src.retrieval.turbovec_retriever import TurboVecHybridRetriever

ROOT_DIR = Path(__file__).resolve().parents[2]
QUERY_EXAMPLES_PATH = ROOT_DIR / "evaluation" / "results" / "hotpotqa_full_dev_queries.tsv"
FULL_BENCHMARK_RESULT_PATH = ROOT_DIR / "evaluation" / "results" / "hotpotqa_full" / "tv_full_200.json"
FILTERED_BENCHMARK_RESULT_PATH = ROOT_DIR / "evaluation" / "results" / "hotpotqa_full" / "tv_filtered_full_200.json"
LEGACY_BENCHMARK_RESULT_PATH = ROOT_DIR / "evaluation" / "results" / "es_nano_iterative.json"

ES_METHODS = {"es_bm25"}
TV_METHODS = {"tv_dense", "tv_hybrid", "tv_filtered_hybrid", "tv_bridge_title_entities_rrf"}
DENSE_METHODS = {"tv_dense", "tv_hybrid", "tv_filtered_hybrid", "es_dense", "es_hybrid"}
ES_METHOD_MAP = {
    "es_bm25": "bm25",
}
METHODS = ES_METHODS | TV_METHODS
logger = logging.getLogger("uvicorn.error")

def profile_uses_remote_embedding(profile: DatasetProfile) -> bool:
    return profile.dense_backend == "turbovec" or any(method in DENSE_METHODS for method in profile.methods)

def embedding_service_url_for_profile(profile: DatasetProfile) -> str:
    return settings.embedding_service_url if profile_uses_remote_embedding(profile) else ""

def embedding_model_id_for_profile(profile: DatasetProfile) -> str:
    return "" if profile.id == "hotpotqa" else profile.id

def embedding_health_url(service_url: str) -> str:
    base = service_url.rstrip("/")
    if base.endswith("/embed"):
        base = base[:-len("/embed")]
    return f"{base}/health" if base else ""

def normalize_loaded_dim(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

def build_search_cache_key(
    *,
    dataset_id: str = "hotpotqa",
    index: str,
    model: str = settings.embedding_model,
    query: str,
    method: str,
    top_k: int,
    query_id: str | None = None,
    metadata_filters: dict[str, str] | None = None,
    effective_query: str | None = None,
    semantic_metadata: bool = False,
) -> str:
    payload = json.dumps(
        {
            'dataset_id': dataset_id,
            'effective_query': (effective_query or query).strip(),
            'index': index,
            'method': method,
            'metadata_filters': metadata_filters or {},
            'model': model,
            'query': query.strip(),
            'query_id': (query_id or '').strip(),
            'semantic_metadata': semantic_metadata,
            'top_k': top_k,
        },
        sort_keys=True,
        separators=(',', ':'),
    )
    digest = hashlib.sha256(payload.encode('utf-8')).hexdigest()
    return f'search:v3:{digest}'

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
    query_id: str | None = None
    query: str = Field(min_length=1)
    method: str = Field(default=settings.default_search_method)
    top_k: int = Field(default=10, ge=1, le=50)
    semantic_metadata: bool = False
    author: str | None = None
    created_at_from: str | None = None
    created_at_to: str | None = None
    modified_at_from: str | None = None
    modified_at_to: str | None = None


def build_metadata_filters(request: SearchRequest) -> dict[str, str]:
    filters = {}
    for field in ('author', 'created_at_from', 'created_at_to', 'modified_at_from', 'modified_at_to'):
        value = getattr(request, field, None)
        if value:
            filters[field] = value
    return filters


@dataclass(frozen=True)
class SearchExecutionPlan:
    original_query: str
    effective_query: str
    metadata_filters: dict[str, str]
    parsed_query: ParsedMetadataQuery | None = None


def build_search_execution_plan(request: SearchRequest) -> SearchExecutionPlan:
    manual_filters = build_metadata_filters(request)
    if not request.semantic_metadata:
        return SearchExecutionPlan(
            original_query=request.query,
            effective_query=request.query,
            metadata_filters=manual_filters,
        )

    parsed = parse_metadata_query(request.query)
    final_filters = {**parsed.metadata_filters, **manual_filters}
    effective_query = parsed.content_query.strip() or request.query
    return SearchExecutionPlan(
        original_query=request.query,
        effective_query=effective_query,
        metadata_filters=final_filters,
        parsed_query=parsed,
    )


def request_with_query(request: SearchRequest, query: str) -> SearchRequest:
    if hasattr(request, "model_copy"):
        return request.model_copy(update={"query": query})
    return request.copy(update={"query": query})


def effective_search_method(method: str, metadata_filters: dict[str, str]) -> str:
    if metadata_filters and method == 'tv_hybrid':
        return 'tv_filtered_hybrid'
    return method


@lru_cache(maxsize=1)
def get_history_store() -> SearchHistoryStore:
    store = SearchHistoryStore(settings.history_db_path)
    store.init_db()
    return store


def find_support_doc_ids_for_profile(profile: DatasetProfile, query: str, query_id: str | None = None) -> list[str]:
    normalized_query_id = (query_id or "").strip()
    if normalized_query_id:
        for row in get_dataset_query_examples(profile.id):
            if str(row.get("query_id", "")).strip() == normalized_query_id:
                return [str(doc_id) for doc_id in row.get("support_doc_ids", [])]

    normalized = query.strip().lower()
    if not normalized:
        return []
    for row in get_dataset_query_examples(profile.id):
        if str(row.get("query", "")).strip().lower() == normalized:
            return [str(doc_id) for doc_id in row.get("support_doc_ids", [])]
    return []

def find_support_doc_ids(query: str, query_id: str | None = None) -> list[str]:
    normalized_query_id = (query_id or "").strip()
    if normalized_query_id:
        for row in get_query_examples():
            if str(row.get("query_id", "")).strip() == normalized_query_id:
                return [str(doc_id) for doc_id in row.get("support_doc_ids", [])]

    normalized = query.strip().lower()
    if not normalized:
        return []
    for row in get_query_examples():
        if str(row.get("query", "")).strip().lower() == normalized:
            return [str(doc_id) for doc_id in row.get("support_doc_ids", [])]
    return []

def build_support_summary(support_doc_ids: list[str], result_doc_ids: list[str]) -> dict[str, Any]:
    support_set = set(support_doc_ids)
    matched_doc_ids = [doc_id for doc_id in result_doc_ids if doc_id in support_set]
    missing_doc_ids = [doc_id for doc_id in support_doc_ids if doc_id not in set(matched_doc_ids)]
    total_count = len(support_doc_ids)
    matched_count = len(matched_doc_ids)
    return {
        "available": total_count > 0,
        "support_doc_ids": support_doc_ids,
        "matched_doc_ids": matched_doc_ids,
        "missing_doc_ids": missing_doc_ids,
        "matched_count": matched_count,
        "total_count": total_count,
        "recall_at_k": round(matched_count / total_count, 4) if total_count else None,
    }

def timing_ms(latency_breakdown_ms: dict[str, float] | None, *keys: str) -> float | None:
    if latency_breakdown_ms is None:
        return None
    for key in keys:
        if key in latency_breakdown_ms:
            return round(float(latency_breakdown_ms[key]), 4)
    return None

def trace_step(step: str, label: str, elapsed_ms: float | None, summary: str) -> dict[str, Any]:
    return {
        "step": step,
        "label": label,
        "status": "completed",
        "elapsed_ms": elapsed_ms,
        "summary": summary,
    }

def build_retrieval_trace(
    *,
    execution_plan: SearchExecutionPlan,
    effective_method: str,
    latency_ms: float,
    latency_breakdown_ms: dict[str, float] | None,
    support_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    metadata_summary = (
        f"{len(execution_plan.metadata_filters)} metadata filter(s) applied"
        if execution_plan.metadata_filters
        else "No metadata filters"
    )
    trace = [
        trace_step(
            "metadata_parse",
            "Parse query / metadata intent",
            None,
            metadata_summary,
        )
    ]

    if effective_method in {"es_bm25", "tv_hybrid", "tv_filtered_hybrid"}:
        trace.append(
            trace_step(
                "bm25",
                "Elasticsearch BM25 search",
                timing_ms(latency_breakdown_ms, "bm25") if latency_breakdown_ms else round(float(latency_ms), 4),
                "Keyword candidate retrieval",
            )
        )

    if effective_method in TV_METHODS:
        trace.append(
            trace_step(
                "query_embedding",
                "BGE query embedding",
                timing_ms(latency_breakdown_ms, "embed", "embedding", "query_embedding"),
                "Query text converted to vector",
            )
        )

    if effective_method in {"tv_dense", "tv_hybrid", "tv_filtered_hybrid"}:
        trace.append(
            trace_step(
                "dense",
                "TurboVec dense search",
                timing_ms(latency_breakdown_ms, "turbovec", "dense"),
                "Vector candidate retrieval",
            )
        )

    if effective_method in {"tv_hybrid", "tv_filtered_hybrid"}:
        trace.append(
            trace_step(
                "fusion",
                "RRF fusion",
                timing_ms(latency_breakdown_ms, "fusion", "rrf"),
                "BM25 and dense rankings fused",
            )
        )

    if effective_method == "tv_bridge_title_entities_rrf":
        trace.extend(
            [
                trace_step(
                    "bridge_first_hop",
                    "Bridge first-hop retrieval",
                    timing_ms(latency_breakdown_ms, "hop1", "first_hop"),
                    "Initial evidence candidates retrieved",
                ),
                trace_step(
                    "bridge_second_hop",
                    "Bridge second-hop retrieval",
                    timing_ms(latency_breakdown_ms, "hop2", "second_hop"),
                    "Follow-up candidates retrieved from title/entity terms",
                ),
            ]
        )

    trace.append(
        trace_step(
            "hydration",
            "Hydrate documents",
            timing_ms(latency_breakdown_ms, "hydrate", "hydration"),
            "Loaded title, content, and metadata",
        )
    )

    support_summary_text = (
        f"Found {support_summary['matched_count']}/{support_summary['total_count']} gold support docs"
        if support_summary["available"]
        else "Gold support unavailable"
    )
    trace.append(trace_step("support_overlay", "Support overlay", None, support_summary_text))
    return trace

@lru_cache(maxsize=8)
def get_es_retriever_for_profile(profile_id: str) -> ElasticsearchRetriever:
    from elasticsearch import Elasticsearch

    profile = get_dataset_profile(profile_id)
    return ElasticsearchRetriever(
        es=Elasticsearch(settings.elasticsearch_url, request_timeout=120),
        index=profile.index,
        model_name=profile.embedding_model,
        num_candidates=settings.elasticsearch_num_candidates,
        embedding_service_url=embedding_service_url_for_profile(profile),
        embedding_timeout_seconds=settings.embedding_timeout_seconds,
        embedding_model_id=embedding_model_id_for_profile(profile),
    )


def get_es_retriever() -> ElasticsearchRetriever:
    return get_es_retriever_for_profile("hotpotqa")



@lru_cache(maxsize=2)
def get_tv_retriever_for_profile(profile_id: str) -> TurboVecHybridRetriever:
    if profile_id != "hotpotqa":
        raise HTTPException(status_code=400, detail=f"TurboVec is not configured for dataset {profile_id}")
    from elasticsearch import Elasticsearch

    profile = get_dataset_profile("hotpotqa")
    es = Elasticsearch(settings.elasticsearch_url, request_timeout=120)
    return TurboVecHybridRetriever.from_paths(
        bm25_retriever=get_es_retriever_for_profile("hotpotqa"),
        es=es,
        index=profile.index,
        tv_index_path=str(settings.turbovec_index_path),
        model_name=profile.embedding_model,
        embedding_service_url=settings.embedding_service_url,
        embedding_timeout_seconds=settings.embedding_timeout_seconds,
        embedding_model_id=embedding_model_id_for_profile(profile),
    )


@lru_cache(maxsize=1)
def get_tv_retriever() -> TurboVecHybridRetriever:
    return get_tv_retriever_for_profile("hotpotqa")

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

def load_qrels_tsv(path: Path | None) -> dict[str, list[str]]:
    if path is None or not path.exists():
        return {}
    qrels: dict[str, list[str]] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            query_id = str(row.get("query_id", "")).strip()
            doc_id = str(row.get("doc_id", "")).strip()
            relevance = float(row.get("relevance") or 1.0)
            if query_id and doc_id and relevance > 0:
                qrels.setdefault(query_id, []).append(doc_id)
    return qrels

def load_query_examples_from_files(query_file: Path, qrels_file: Path | None = None) -> list[dict[str, Any]]:
    qrels_by_query = load_qrels_tsv(qrels_file)
    with query_file.open("r", encoding="utf-8", newline="") as handle:
        rows = []
        for row in csv.DictReader(handle, delimiter="\t"):
            query_id = str(row.get("query_id") or row.get("variant_query_id") or "").strip()
            query_text = str(row.get("query") or row.get("original_query") or "").strip()
            support_doc_ids = qrels_by_query.get(query_id)
            if support_doc_ids is None:
                support_doc_ids = [doc_id.strip() for doc_id in row.get("support_doc_ids", "").split(",") if doc_id.strip()]
            item = {
                "query_id": query_id,
                "query": query_text,
                "support_doc_ids": support_doc_ids,
                "support_doc_count": len(support_doc_ids),
            }
            if row.get("split"):
                item["split"] = row["split"]
            if row.get("answer"):
                item["answer"] = row["answer"]
            rows.append(item)
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


def load_benchmark_result(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_benchmark_dashboard(full_result: dict[str, Any], filtered_result: dict[str, Any], legacy_result: dict[str, Any]) -> dict[str, Any]:
    current_order = ["es_bm25", "tv_dense", "tv_filtered_hybrid", "tv_hybrid"]
    rows_by_method = {
        str(row.get("method", "")): row
        for row in [*full_result.get("results", []), *filtered_result.get("results", [])]
    }
    current_results = [rows_by_method[method] for method in current_order if method in rows_by_method]
    full_config = dict(full_result.get("config", {}))
    filtered_config = dict(filtered_result.get("config", {}))
    current_config = {
        **full_config,
        "methods": [row.get("method") for row in current_results],
        "queries": int(full_config.get("queries") or full_config.get("max_queries") or 0),
        "corpus_doc_count": 5233329,
        "project_stage": "Sprint 3 full-corpus pilot",
        "benchmark_scope": "Full HotpotQA corpus with a 200-query dev pilot run",
        "paper_comparable": False,
        "paper_protocol": "Run full beir/hotpotqa/test with 7,405 queries for BEIR/paper comparison.",
    }
    if filtered_config.get("candidate_k") is not None:
        current_config["filtered_candidate_k"] = filtered_config.get("candidate_k")

    return {
        "current": {
            "title": "Current Full-Corpus Benchmark",
            "subtitle": "Project-progress snapshot on full HotpotQA corpus; not a paper-comparable full test run yet.",
            "config": current_config,
            "results": current_results,
        },
        "legacy": {
            "title": "Legacy Nano / Elasticsearch Benchmarks",
            "subtitle": "Earlier small-corpus Elasticsearch history kept for project context only.",
            "config": legacy_result.get("config", {}),
            "results": legacy_result.get("results", []),
        },
        "results": current_results,
    }


@lru_cache(maxsize=8)
def get_dataset_query_examples(profile_id: str) -> list[dict[str, Any]]:
    profile = get_dataset_profile(profile_id)
    if profile.query_file is not None and profile.query_file.exists():
        return load_query_examples_from_files(profile.query_file, profile.qrels_file)
    if profile.id == "hotpotqa":
        try:
            return load_dataset_query_examples(profile.dataset_id)
        except Exception:
            return load_query_examples(profile.query_file or QUERY_EXAMPLES_PATH)
    return []

@lru_cache(maxsize=1)
def get_query_examples() -> list[dict[str, Any]]:
    return get_dataset_query_examples("hotpotqa")


@lru_cache(maxsize=1)
def get_benchmark_result() -> dict[str, Any]:
    return build_benchmark_dashboard(
        load_benchmark_result(FULL_BENCHMARK_RESULT_PATH),
        load_benchmark_result(FILTERED_BENCHMARK_RESULT_PATH),
        load_benchmark_result(LEGACY_BENCHMARK_RESULT_PATH),
    )


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


def infer_runtime_profile(index: str, turbovec_index_path: Path) -> str:
    index_text = index.lower()
    path_text = str(turbovec_index_path).lower()
    if "full" in index_text or "hotpotqa_full" in path_text:
        return "full"
    if "100k" in index_text or "100k" in path_text:
        return "100k"
    if "nano" in index_text or "nano" in path_text:
        return "nano"
    if "smoke" in index_text or "smoke" in path_text:
        return "smoke"
    return "custom"


def infer_corpus_doc_count(index: str) -> int | None:
    index_text = index.lower()
    if "full" in index_text:
        return 5233329
    if "100k" in index_text:
        return 100000
    if "nano" in index_text:
        return 5090
    if "smoke" in index_text:
        return 1000
    return None

def benchmark_query_count_for_profile(profile: DatasetProfile) -> int | None:
    counts = []
    for path in profile.benchmark_files:
        if not path.exists():
            continue
        try:
            result = load_benchmark_result(path)
        except Exception:
            continue
        config = result.get("config", {})
        config_count = config.get("queries") or config.get("max_queries")
        if config_count:
            counts.append(int(config_count))
        for row in result.get("results", []):
            row_count = row.get("metrics", {}).get("queries")
            if row_count:
                counts.append(int(row_count))
    return max(counts) if counts else None


@app.get("/datasets")
def datasets() -> dict[str, Any]:
    return {
        "default_dataset_id": "hotpotqa",
        "datasets": [profile.to_public_dict() for profile in list_dataset_profiles()],
    }


def resolve_dataset_profile(dataset_id: str) -> DatasetProfile:
    try:
        return get_dataset_profile(dataset_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown dataset: {dataset_id}") from None


@app.get("/datasets/{dataset_id}/stats")
def dataset_stats(dataset_id: str) -> dict[str, Any]:
    profile = resolve_dataset_profile(dataset_id)
    return {
        "backend": "elasticsearch",
        "index": profile.index,
        "methods": list(profile.methods),
        "dataset_id": profile.dataset_id,
        "dataset_profile": profile.to_public_dict(),
        "default_search_method": profile.default_method,
        "embedding_model": profile.embedding_model,
        "embedding_service_url": embedding_service_url_for_profile(profile),
        "num_candidates": settings.elasticsearch_num_candidates,
        "search_cache_ttl_seconds": settings.search_cache_ttl_seconds,
        "history_db_path": str(settings.history_db_path),
        "turbovec_index_path": str(settings.turbovec_index_path) if profile.dense_backend == "turbovec" else None,
        "turbovec_dim": settings.turbovec_dim if profile.dense_backend == "turbovec" else None,
        "turbovec_bit_width": settings.turbovec_bit_width if profile.dense_backend == "turbovec" else None,
        "runtime_profile": profile.id,
        "corpus_doc_count": infer_corpus_doc_count(profile.index) or (3623 if profile.id == "vimqa" else None),
        "benchmark_query_count": benchmark_query_count_for_profile(profile),
        "primary_metric": profile.primary_metric,
    }


@app.get("/datasets/{dataset_id}/embedding-health")
def dataset_embedding_health(dataset_id: str) -> dict[str, Any]:
    profile = resolve_dataset_profile(dataset_id)
    service_url = embedding_service_url_for_profile(profile)
    model_id = embedding_model_id_for_profile(profile) or "hotpotqa"
    expected_dim = profile.vector_dims
    payload: dict[str, Any] = {
        "dataset_id": profile.id,
        "model_id": model_id,
        "model": profile.embedding_model,
        "expected_dim": expected_dim,
        "loaded_dim": None,
        "status": "not_configured",
        "service_url": service_url,
        "device": None,
        "torch_cuda_available": False,
        "loaded_models": {},
    }
    health_url = embedding_health_url(service_url)
    if not health_url:
        return payload

    try:
        timeout = min(settings.embedding_timeout_seconds, 5)
        with urlrequest.urlopen(health_url, timeout=timeout) as response:
            service_health = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        payload["status"] = "offline"
        payload["error"] = str(exc)
        return payload

    loaded_models = service_health.get("loaded_models") or {}
    loaded_dim = normalize_loaded_dim(loaded_models.get(model_id))
    payload.update(
        {
            "status": "ready" if expected_dim is not None and loaded_dim == expected_dim else "warming",
            "loaded_dim": loaded_dim,
            "device": service_health.get("device"),
            "torch_cuda_available": bool(service_health.get("torch_cuda_available")),
            "loaded_models": loaded_models,
        }
    )
    return payload


@app.get("/datasets/{dataset_id}/queries")
def dataset_queries(
    dataset_id: str,
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    search: str = "",
) -> dict[str, Any]:
    profile = resolve_dataset_profile(dataset_id)
    payload = paginate_query_examples(get_dataset_query_examples(profile.id), limit=limit, offset=offset, search=search)
    payload["dataset_id"] = profile.id
    return payload


def build_dataset_benchmark_dashboard(profile: DatasetProfile) -> dict[str, Any]:
    loaded = [load_benchmark_result(path) for path in profile.benchmark_files if path.exists()]
    rows = []
    config: dict[str, Any] = {
        "dataset_id": profile.dataset_id,
        "index": profile.index,
        "primary_metric": profile.primary_metric,
    }
    for result in loaded:
        config.update(result.get("config", {}))
        rows.extend(result.get("results", []))
    rows_by_method = {str(row.get("method", "")): row for row in rows}
    ordered_methods = [method for method in profile.methods if method in rows_by_method]
    ordered_rows = [rows_by_method[method] for method in ordered_methods]
    query_count = benchmark_query_count_for_profile(profile)
    config.update(
        {
            "dataset_id": profile.dataset_id,
            "index": profile.index,
            "methods": ordered_methods,
            "queries": query_count,
            "primary_metric": profile.primary_metric,
            "benchmark_scope": "Full VimQA query set with 9,044 labeled queries" if profile.id == "vimqa" else "Dataset-scoped benchmark artifact",
            "paper_comparable": False,
        }
    )
    return {
        "current": {
            "title": f"{profile.label} Benchmark",
            "subtitle": "Dataset-scoped project evidence; not a leaderboard claim.",
            "config": config,
            "results": ordered_rows,
        },
        "legacy": {"title": "Legacy Benchmarks", "subtitle": "No legacy section for this dataset.", "config": {}, "results": []},
        "results": ordered_rows,
    }


@app.get("/datasets/{dataset_id}/benchmarks")
def dataset_benchmarks(dataset_id: str) -> dict[str, Any]:
    profile = resolve_dataset_profile(dataset_id)
    if profile.id == "hotpotqa":
        return get_benchmark_result()
    return build_dataset_benchmark_dashboard(profile)


@app.get("/stats")
def stats() -> dict[str, Any]:
    return dataset_stats("hotpotqa")


def query_row_matches(row: dict[str, Any], search: str) -> bool:
    value = search.strip().lower()
    if not value:
        return True
    query_id = str(row.get("query_id", "")).lower()
    query_text = str(row.get("query", "")).lower()
    support_doc_ids = [str(doc_id).lower() for doc_id in row.get("support_doc_ids", [])]
    return value in query_id or value in query_text or any(value in doc_id for doc_id in support_doc_ids)


def paginate_query_examples(rows: list[dict[str, Any]], limit: int = 10, offset: int = 0, search: str = "") -> dict[str, Any]:
    bounded_limit = max(1, min(int(limit), 100))
    bounded_offset = max(0, int(offset))
    filtered_rows = [row for row in rows if query_row_matches(row, search)]
    page_rows = filtered_rows[bounded_offset : bounded_offset + bounded_limit]
    return {
        "count": len(page_rows),
        "total": len(filtered_rows),
        "limit": bounded_limit,
        "offset": bounded_offset,
        "queries": page_rows,
    }


@app.get("/queries")
def queries(
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    search: str = "",
) -> dict[str, Any]:
    return paginate_query_examples(get_query_examples(), limit=limit, offset=offset, search=search)


@app.get("/benchmark")
def benchmark() -> dict[str, Any]:
    return dataset_benchmarks("hotpotqa")


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


def run_profile_search(
    profile: DatasetProfile,
    request: SearchRequest,
    effective_method: str,
    metadata_filters: dict[str, str],
) -> tuple[list[dict[str, Any]], dict[str, float] | None, float]:
    start = time.perf_counter()
    latency_breakdown_ms: dict[str, float] | None = None
    if effective_method in TV_METHODS:
        tv_retriever = get_tv_retriever() if profile.id == "hotpotqa" else get_tv_retriever_for_profile(profile.id)
        if effective_method == "tv_bridge_title_entities_rrf":
            hits = tv_retriever.search_bridge_title_entities_rrf(
                request.query,
                request.top_k,
                beam_size=1,
                max_bridge_terms=6,
                candidate_k=settings.hybrid_bm25_k,
                rrf_k=settings.rrf_k,
            )
            latency_breakdown_ms = {key: round(float(value), 4) for key, value in tv_retriever.last_timing_ms.items()}
            return hits, latency_breakdown_ms, round((time.perf_counter() - start) * 1000, 4)
        search_kwargs = {
            "bm25_k": settings.hybrid_bm25_k,
            "dense_k": settings.hybrid_dense_k,
            "rrf_k": settings.rrf_k,
        }
        if metadata_filters:
            search_kwargs["metadata_filters"] = metadata_filters
        hits = tv_retriever.search(request.query, effective_method, request.top_k, **search_kwargs)
        latency_breakdown_ms = {key: round(float(value), 4) for key, value in tv_retriever.last_timing_ms.items()}
    else:
        es_method = ES_METHOD_MAP.get(effective_method, effective_method.removeprefix("es_"))
        es_retriever = get_es_retriever() if profile.id == "hotpotqa" else get_es_retriever_for_profile(profile.id)
        hits = es_retriever.search(
            request.query,
            es_method,
            request.top_k,
            metadata_filters=metadata_filters or None,
        )
    return hits, latency_breakdown_ms, round((time.perf_counter() - start) * 1000, 4)


def build_search_response(
    profile: DatasetProfile,
    request: SearchRequest,
    execution_plan: SearchExecutionPlan,
    requested_method: str,
    effective_method: str,
    hits: list[dict[str, Any]],
    support_doc_ids: list[str],
    latency_ms: float,
    latency_breakdown_ms: dict[str, float] | None,
    metadata_filters: dict[str, str],
) -> dict[str, Any]:
    support_set = set(support_doc_ids)
    results = []
    for rank, hit in enumerate(hits, start=1):
        result = {
            "doc_id": str(hit.get("doc_id", "")),
            "title": hit.get("title", ""),
            "text": str(hit.get("text", ""))[:800],
            "url": hit.get("url", ""),
            "score": float(hit.get("score", 0.0)),
            "rank": rank,
            "source": hit.get("source", ES_METHOD_MAP.get(effective_method, effective_method)),
            "hop": int(hit.get("hop", 1)),
            "is_support": str(hit.get("doc_id", "")) in support_set,
        }
        for field in ("author", "created_at", "modified_at", "source_split", "answer"):
            if field in hit and hit[field] is not None:
                result[field] = hit[field]
        results.append(result)
    support_summary = build_support_summary(support_doc_ids, [result["doc_id"] for result in results])
    response = {
        "dataset_id": profile.id,
        "query_id": request.query_id,
        "query": execution_plan.original_query,
        "effective_query": execution_plan.effective_query,
        "semantic_metadata": request.semantic_metadata,
        "method": effective_method,
        "top_k": request.top_k,
        "latency_ms": latency_ms,
        "cache_hit": False,
        "support": support_summary,
        "retrieval_trace": build_retrieval_trace(
            execution_plan=execution_plan,
            effective_method=effective_method,
            latency_ms=latency_ms,
            latency_breakdown_ms=latency_breakdown_ms,
            support_summary=support_summary,
        ),
        "results": results,
    }
    if effective_method != requested_method:
        response["requested_method"] = requested_method
    if metadata_filters:
        response["metadata_filters"] = metadata_filters
        response["metadata_filter_scope"] = "hard_prefilter"
    if execution_plan.parsed_query is not None:
        response["parsed_query"] = execution_plan.parsed_query.to_dict()
    if latency_breakdown_ms is not None:
        response["latency_breakdown_ms"] = latency_breakdown_ms
    return response


@app.post("/datasets/{dataset_id}/search")
def dataset_search(dataset_id: str, request: SearchRequest) -> dict[str, Any]:
    profile = resolve_dataset_profile(dataset_id)
    method = request.method.strip().lower()
    execution_plan = build_search_execution_plan(request)
    metadata_filters = execution_plan.metadata_filters
    search_request = request_with_query(request, execution_plan.effective_query)
    hidden_hotpotqa_method = profile.id == "hotpotqa" and method in METHODS
    if method not in profile.methods and not hidden_hotpotqa_method:
        raise HTTPException(status_code=400, detail=f"Unknown method for dataset {profile.id}: {request.method}")
    if metadata_filters and not profile.supports_metadata_filters:
        raise HTTPException(status_code=400, detail=f"Dataset {profile.id} does not support metadata filters")
    if metadata_filters and method == "tv_dense":
        raise HTTPException(status_code=400, detail="tv_dense does not support metadata filters")

    effective_method = effective_search_method(method, metadata_filters)
    cache_key = build_search_cache_key(
        dataset_id=profile.id,
        index=profile.index,
        model=profile.embedding_model,
        query=request.query,
        method=method,
        top_k=request.top_k,
        query_id=request.query_id,
        metadata_filters=metadata_filters,
        effective_query=execution_plan.effective_query,
        semantic_metadata=request.semantic_metadata,
    )
    cached = read_search_cache(cache_key)
    if cached is not None:
        support_doc_ids = cached.get("support", {}).get("support_doc_ids") or find_support_doc_ids_for_profile(profile, cached["query"], cached.get("query_id"))
        cached["history_id"] = get_history_store().record_search(
            dataset_id=profile.id,
            query=cached["query"],
            method=cached["method"],
            top_k=int(cached["top_k"]),
            latency_ms=float(cached["latency_ms"]),
            cache_hit=True,
            results=cached["results"],
            support_doc_ids=support_doc_ids,
        )
        return cached

    hits, latency_breakdown_ms, latency_ms = run_profile_search(profile, search_request, effective_method, metadata_filters)
    support_doc_ids = find_support_doc_ids(request.query, request.query_id) if profile.id == "hotpotqa" else find_support_doc_ids_for_profile(profile, request.query, request.query_id)
    response = build_search_response(profile, request, execution_plan, method, effective_method, hits, support_doc_ids, latency_ms, latency_breakdown_ms, metadata_filters)
    write_search_cache(cache_key, response)
    response["history_id"] = get_history_store().record_search(
        dataset_id=profile.id,
        query=response["query"],
        method=response["method"],
        top_k=int(response["top_k"]),
        latency_ms=float(response["latency_ms"]),
        cache_hit=False,
        results=response["results"],
        support_doc_ids=support_doc_ids,
    )
    return response


@app.post("/search")
def search(request: SearchRequest) -> dict[str, Any]:
    try:
        return dataset_search("hotpotqa", request)
    except HTTPException as exc:
        if exc.status_code == 400 and str(exc.detail).startswith("Unknown method for dataset hotpotqa:"):
            raise HTTPException(status_code=400, detail=f"Unknown method: {request.method}") from None
        raise
