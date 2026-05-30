"""Evaluate meeting-level retrieval on QMSum qrels.

Hỗ trợ (theo README):
- Precision@k, Recall@k, MRR, NDCG@k, latency p50/p95.
- Đánh giá riêng theo nguồn: channel=content vs metadata (NF3).
- So sánh cấu hình: num_candidates cho kNN (NF5) qua --matrix.
"""

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
    channel: str = "content",
    num_candidates: int | None = None,
) -> dict:
    queries = list(read_jsonl(queries_path))
    if limit:
        queries = queries[:limit]
    relevant_by_query: dict[str, set[str]] = {}
    for qrel in read_jsonl(qrels_path):
        relevant_by_query.setdefault(qrel["query_id"], set()).add(qrel["meeting_id"])

    recall_hits = 0
    precisions = []
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
            channel=channel,
            num_candidates=num_candidates,
        )
        latencies.append((time.perf_counter() - start) * 1000)
        ranked_ids = [item["meeting_id"] for item in response["results"]]
        evaluated += 1
        relevant_in_topk = sum(1 for mid in ranked_ids[:top_k] if mid in relevant)
        precisions.append(relevant_in_topk / top_k)
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
        "channel": channel,
        "top_k": top_k,
        "queries": evaluated,
        f"precision@{top_k}": sum(precisions) / evaluated if evaluated else 0.0,
        f"recall@{top_k}": recall_hits / evaluated if evaluated else 0.0,
        "mrr": sum(reciprocal_ranks) / evaluated if evaluated else 0.0,
        f"ndcg@{top_k}": sum(ndcgs) / evaluated if evaluated else 0.0,
        "latency_p50_ms": _percentile(latencies_sorted, 50),
        "latency_p95_ms": _percentile(latencies_sorted, 95),
    }


def run_matrix(queries_path: Path, qrels_path: Path, **kwargs) -> list[dict]:
    """So sánh các cấu hình: bm25 / semantic / hybrid + content vs metadata channel."""
    configs = [
        {"mode": "bm25", "channel": "content"},
        {"mode": "semantic", "channel": "content"},
        {"mode": "hybrid", "channel": "content"},
        {"mode": "bm25", "channel": "metadata"},
        {"mode": "semantic", "channel": "metadata"},
        {"mode": "hybrid", "channel": "metadata"},
    ]
    results = []
    for cfg in configs:
        results.append(run_eval(queries_path, qrels_path, **cfg, **kwargs))
    return results


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
    parser.add_argument("--channel", choices=["content", "metadata"], default="content")
    parser.add_argument("--num-candidates", type=int, default=None)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--source", default="qmsum")
    parser.add_argument("--matrix", action="store_true", help="So sánh tất cả cấu hình mode x channel")
    args = parser.parse_args()

    common = dict(
        index_name=args.index,
        es_host=args.es_host,
        top_k=args.top_k,
        limit=args.limit,
        source=args.source,
    )
    if args.matrix:
        for row in run_matrix(args.queries, args.qrels, num_candidates=args.num_candidates, **common):
            print(row)
    else:
        print(run_eval(
            queries_path=args.queries,
            qrels_path=args.qrels,
            mode=args.mode,
            channel=args.channel,
            num_candidates=args.num_candidates,
            **common,
        ))


if __name__ == "__main__":
    main()
