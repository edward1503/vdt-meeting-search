from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
from typing import Any

from src.core.config import ROOT_DIR
from src.search.llm_query import LLMUnavailable
from src.search.prompt_methods import METHODS
from src.search.searcher import MeetingSearcher


def benchmark_prompt_search(qrels_path: Path, top_k: int, methods: list[str]) -> dict[str, Any]:
    searcher = MeetingSearcher()
    qrels = json.loads(qrels_path.read_text(encoding="utf-8"))
    results = []
    for method in methods:
        results.append(_benchmark_method(searcher, qrels, top_k, method))
    return {
        "config": {
            "qrels": str(qrels_path),
            "top_k": top_k,
            "queries": len(qrels),
            "methods": methods,
            "scope": "AMI current index",
        },
        "results": results,
    }


def _benchmark_method(searcher: MeetingSearcher, qrels: list[dict[str, Any]], top_k: int, method: str) -> dict[str, Any]:
    latencies = []
    precision_total = 0.0
    recall_total = 0.0
    reciprocal_total = 0.0
    sample_results = []

    for item in qrels:
        relevant = set(item["relevant_meeting_ids"])
        start = time.perf_counter()
        try:
            response = searcher.search(item["query"], top_k=top_k, method=method)
        except LLMUnavailable as exc:
            return {"method": method, "status": "skipped", "reason": str(exc)}
        latencies.append((time.perf_counter() - start) * 1000)
        returned = [result["meeting_id"] for result in response["results"]]
        hits = [meeting_id for meeting_id in returned if meeting_id in relevant]
        precision_total += len(hits) / max(1, top_k)
        recall_total += len(hits) / max(1, len(relevant))
        reciprocal_total += next(
            (1 / rank for rank, meeting_id in enumerate(returned, start=1) if meeting_id in relevant),
            0.0,
        )
        if len(sample_results) < 3:
            sample_results.append({"query": item["query"], "returned": returned, "relevant": sorted(relevant)})

    count = max(1, len(qrels))
    return {
        "method": method,
        "status": "ok",
        "precision@k": round(precision_total / count, 4),
        "recall@k": round(recall_total / count, 4),
        "mrr@k": round(reciprocal_total / count, 4),
        "latency_avg_ms": round(statistics.fmean(latencies), 4),
        "latency_p50_ms": round(_percentile(latencies, 50), 4),
        "latency_p95_ms": round(_percentile(latencies, 95), 4),
        "queries": len(qrels),
        "sample_results": sample_results,
    }


def _percentile(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, round((percentile / 100) * (len(ordered) - 1))))
    return ordered[idx]


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark prompt-based meeting search methods")
    parser.add_argument("--qrels", type=Path, default=ROOT_DIR / "data" / "eval" / "ami_qrels.json")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--methods", default=",".join(METHODS))
    parser.add_argument("--output", type=Path, default=ROOT_DIR / "evaluation" / "results" / "prompt_search_benchmark_ami.json")
    args = parser.parse_args()
    methods = [method.strip() for method in args.methods.split(",") if method.strip()]
    result = benchmark_prompt_search(args.qrels, args.top_k, methods)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()