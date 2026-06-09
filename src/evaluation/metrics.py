from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Any

from src.retrieval.base import SearchHit
from src.retrieval.utils import dcg


@dataclass(frozen=True)
class QueryEval:
    query_id: str
    returned: list[str]
    relevant: list[str]
    precision: float
    recall: float
    mrr: float
    ndcg: float
    full_support: float
    latency_ms: float


def evaluate_rankings(
    qrels: dict[str, dict[str, float]],
    runs: dict[str, list[SearchHit]],
    latencies_ms: dict[str, float],
    k: int,
) -> dict[str, Any]:
    per_query = []
    for query_id, relevant_scores in qrels.items():
        relevant = {doc_id for doc_id, score in relevant_scores.items() if score > 0}
        hits = runs.get(query_id, [])[:k]
        returned = [hit.doc_id for hit in hits]
        hit_flags = [1.0 if doc_id in relevant else 0.0 for doc_id in returned]
        precision = sum(hit_flags) / max(1, k)
        recall = sum(hit_flags) / max(1, len(relevant))
        mrr = next((1.0 / rank for rank, doc_id in enumerate(returned, start=1) if doc_id in relevant), 0.0)
        gains = [relevant_scores.get(doc_id, 0.0) for doc_id in returned]
        ideal_gains = sorted(relevant_scores.values(), reverse=True)[:k]
        ndcg = dcg(gains) / max(1e-9, dcg(ideal_gains))
        full_support = 1.0 if relevant and relevant.issubset(set(returned)) else 0.0
        per_query.append(
            QueryEval(
                query_id=query_id,
                returned=returned,
                relevant=sorted(relevant),
                precision=precision,
                recall=recall,
                mrr=mrr,
                ndcg=ndcg,
                full_support=full_support,
                latency_ms=latencies_ms.get(query_id, 0.0),
            )
        )

    latencies = [item.latency_ms for item in per_query]
    total_latency_sec = sum(latencies) / 1000
    return {
        f"precision@{k}": round(_mean([item.precision for item in per_query]), 4),
        f"recall@{k}": round(_mean([item.recall for item in per_query]), 4),
        f"mrr@{k}": round(_mean([item.mrr for item in per_query]), 4),
        f"ndcg@{k}": round(_mean([item.ndcg for item in per_query]), 4),
        f"full_support_recall@{k}": round(_mean([item.full_support for item in per_query]), 4),
        "latency_p50_ms": round(_percentile(latencies, 50), 4),
        "latency_p95_ms": round(_percentile(latencies, 95), 4),
        "latency_p99_ms": round(_percentile(latencies, 99), 4),
        "qps": round(len(per_query) / max(1e-9, total_latency_sec), 4),
        "queries": len(per_query),
        "per_query": [item.__dict__ for item in per_query],
    }


def _mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def _percentile(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, math.ceil((percentile / 100) * len(ordered)) - 1))
    return ordered[idx]
