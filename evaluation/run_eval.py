"""Evaluate meeting-level retrieval on QMSum qrels."""

from __future__ import annotations

import argparse
import math
import time
from pathlib import Path

from src.indexing.bulk_index import DEFAULT_INDEX
from src.preprocessing.jsonl import read_jsonl
from src.search.hybrid import search_meetings
from src.core.config import settings


def run_eval(
    queries_path: Path,
    qrels_path: Path,
    index_name: str = DEFAULT_INDEX,
    es_host: str = settings.es_host,
    mode: str = "hybrid",
    top_k: int = 10,
    limit: int | None = None,
    source: str | None = "qmsum",
) -> dict:
    queries = list(read_jsonl(queries_path))
    if limit:
        queries = queries[:limit]
    relevant_by_query: dict[str, set[str]] = {}
    for qrel in read_jsonl(qrels_path):
        relevant_by_query.setdefault(qrel["query_id"], set()).add(qrel["meeting_id"])

    recall_hits = 0
    reciprocal_ranks = []
    ndcgs = []
    latencies = []
    evaluated = 0
    for query in queries:
        relevant = relevant_by_query.get(query["query_id"], set())
        if not relevant:
            continue
        start = time.perf_counter()
        response = search_meetings(
            query=query["query"],
            index_name=index_name,
            es_host=es_host,
            mode=mode,
            top_k=top_k,
            source=source,
        )
        latencies.append((time.perf_counter() - start) * 1000)
        ranked_ids = [item["meeting_id"] for item in response["results"]]
        evaluated += 1
        hit_rank = next((idx + 1 for idx, mid in enumerate(ranked_ids) if mid in relevant), None)
        if hit_rank:
            recall_hits += 1
            reciprocal_ranks.append(1.0 / hit_rank)
            ndcgs.append(1.0 / math.log2(hit_rank + 1))
        else:
            reciprocal_ranks.append(0.0)
            ndcgs.append(0.0)

    latencies_sorted = sorted(latencies)
    return {
        "mode": mode,
        "top_k": top_k,
        "queries": evaluated,
        f"recall@{top_k}": recall_hits / evaluated if evaluated else 0.0,
        "mrr": sum(reciprocal_ranks) / evaluated if evaluated else 0.0,
        f"ndcg@{top_k}": sum(ndcgs) / evaluated if evaluated else 0.0,
        "latency_p50_ms": _percentile(latencies_sorted, 50),
        "latency_p95_ms": _percentile(latencies_sorted, 95),
    }


def _percentile(values: list[float], percentile: int) -> float | None:
    if not values:
        return None
    index = min(len(values) - 1, max(0, math.ceil(percentile / 100 * len(values)) - 1))
    return values[index]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries", type=Path, default=Path("data/processed/qmsum_queries.jsonl"))
    parser.add_argument("--qrels", type=Path, default=Path("data/processed/qrels.jsonl"))
    parser.add_argument("--index", default=DEFAULT_INDEX)
    parser.add_argument("--es-host", default=settings.es_host)
    parser.add_argument("--mode", choices=["bm25", "semantic", "hybrid"], default="hybrid")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--source", default="qmsum")
    args = parser.parse_args()
    print(run_eval(
        queries_path=args.queries,
        qrels_path=args.qrels,
        index_name=args.index,
        es_host=args.es_host,
        mode=args.mode,
        top_k=args.top_k,
        limit=args.limit,
        source=args.source,
    ))


if __name__ == "__main__":
    main()
