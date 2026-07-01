from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


Run = dict[str, list[dict[str, Any]]]
Qrels = dict[str, set[str]]


def load_qrels_tsv(path: Path) -> Qrels:
    qrels: Qrels = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            query_id = str(row.get("query_id", "")).strip()
            if not query_id:
                continue
            support_doc_ids = str(row.get("support_doc_ids", "")).strip()
            if support_doc_ids:
                qrels[query_id] = {doc_id.strip() for doc_id in support_doc_ids.split(",") if doc_id.strip()}
                continue

            doc_id = str(row.get("doc_id", "")).strip()
            relevance = float(row.get("relevance", 1.0) or 0.0)
            if doc_id and relevance > 0:
                qrels.setdefault(query_id, set()).add(doc_id)
    return {query_id: doc_ids for query_id, doc_ids in qrels.items() if doc_ids}


def load_trec_run(path: Path) -> Run:
    run: Run = {}
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            parts = stripped.split()
            if len(parts) != 6:
                raise ValueError(f"Invalid TREC line at {path}:{line_number}: {line.rstrip()}")
            query_id, _, doc_id, rank, score, method = parts
            run.setdefault(query_id, []).append(
                {
                    "doc_id": doc_id,
                    "rank": int(rank),
                    "score": float(score),
                    "method": method,
                }
            )

    for hits in run.values():
        hits.sort(key=lambda item: item["rank"])
    return run


def analyze_runs(qrels: Qrels, runs: dict[str, Run], *, target_k: int = 10, candidate_depth: int = 100) -> dict[str, Any]:
    per_query: dict[str, dict[str, Any]] = {}
    methods: dict[str, Any] = {}
    run_query_ids = {query_id for run in runs.values() for query_id in run}
    evaluated_qrels = {query_id: relevant for query_id, relevant in qrels.items() if query_id in run_query_ids}

    for method, run in runs.items():
        full_support_at_k_values: list[float] = []
        any_support_at_k_values: list[float] = []
        candidate_recall_values: list[float] = []
        first_relevant_ranks: list[int] = []
        buckets = {"candidate_ranked_low": 0, "missing_candidate": 0, "partial_candidate_support": 0, "success": 0}

        for query_id, relevant in sorted(evaluated_qrels.items()):
            hits = run.get(query_id, [])
            top_hits = hits[:target_k]
            candidate_hits = hits[:candidate_depth]
            top_doc_ids = [str(hit["doc_id"]) for hit in top_hits]
            candidate_doc_ids = [str(hit["doc_id"]) for hit in candidate_hits]
            candidate_doc_set = set(candidate_doc_ids)
            top_doc_set = set(top_doc_ids)
            relevant_in_top = relevant & top_doc_set
            relevant_in_candidates = relevant & candidate_doc_set
            full_support_at_k = 1.0 if relevant.issubset(top_doc_set) else 0.0
            any_support_at_k = 1.0 if relevant_in_top else 0.0
            candidate_recall = len(relevant_in_candidates) / max(1, len(relevant))
            first_rank = _first_relevant_rank(hits, relevant)

            if full_support_at_k:
                bucket = "success"
            elif relevant.issubset(candidate_doc_set):
                bucket = "candidate_ranked_low"
            elif relevant_in_candidates:
                bucket = "partial_candidate_support"
            else:
                bucket = "missing_candidate"

            buckets[bucket] += 1
            full_support_at_k_values.append(full_support_at_k)
            any_support_at_k_values.append(any_support_at_k)
            candidate_recall_values.append(candidate_recall)
            if first_rank is not None:
                first_relevant_ranks.append(first_rank)

            per_query.setdefault(query_id, {})[method] = {
                "bucket": bucket,
                "relevant_doc_ids": sorted(relevant),
                "relevant_in_top_k": sorted(relevant_in_top),
                "relevant_in_candidates": sorted(relevant_in_candidates),
                "first_relevant_rank": first_rank,
            }

        methods[method] = {
            "queries": len(evaluated_qrels),
            "target_k": target_k,
            "candidate_depth": candidate_depth,
            "full_support_at_k": round(_mean(full_support_at_k_values), 4),
            "any_support_at_k": round(_mean(any_support_at_k_values), 4),
            "candidate_recall_at_depth": round(_mean(candidate_recall_values), 4),
            "mean_first_relevant_rank": round(_mean([float(rank) for rank in first_relevant_ranks]), 4),
            "failure_buckets": buckets,
        }

    return {
        "config": {"target_k": target_k, "candidate_depth": candidate_depth, "queries": len(evaluated_qrels)},
        "methods": methods,
        "per_query": per_query,
    }


def write_markdown_report(analysis: dict[str, Any], path: Path) -> None:
    lines = [
        "# Sprint 5 Ranking Diagnostics",
        "",
        "This report analyzes existing ranked runs to separate candidate-generation failures from ranking failures.",
        "",
        f"Target cutoff: top-{analysis['config']['target_k']}",
        f"Candidate depth: top-{analysis['config']['candidate_depth']}",
        f"Queries: {analysis['config']['queries']}",
        "",
        "## Method Summary",
        "",
        "| Method | Full support@k | Any support@k | Candidate recall@depth | Missing candidate | Partial candidate support | Candidate ranked low | Success |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for method, summary in analysis["methods"].items():
        buckets = summary["failure_buckets"]
        lines.append(
            "| {method} | {full:.4f} | {any_:.4f} | {candidate:.4f} | {missing} | {partial} | {low} | {success} |".format(
                method=method,
                full=summary["full_support_at_k"],
                any_=summary["any_support_at_k"],
                candidate=summary["candidate_recall_at_depth"],
                missing=buckets["missing_candidate"],
                partial=buckets["partial_candidate_support"],
                low=buckets["candidate_ranked_low"],
                success=buckets["success"],
            )
        )

    lines.extend(
        [
            "",
            "## Interpretation Rule",
            "",
            "- `missing_candidate`: reranking cannot fix these queries because relevant documents are absent from the analyzed candidate depth.",
            "- `partial_candidate_support`: at least one relevant document is present, but not all required support appears by the analyzed candidate depth.",
            "- `candidate_ranked_low`: all required support appears by candidate depth, but not by the target cutoff; this is the clearest reranker-ready bucket.",
            "- `success`: all known support documents appear by the target cutoff.",
            "",
            "## Current Limitation",
            "",
            "This first-pass report uses the available top-10 TREC runs. It can identify top-10 success and missing/partial support at top-10, but it cannot yet prove candidate@50 or candidate@100 reranker readiness. A deeper run should be generated before making a final reranker decision.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze ranked retrieval runs for reranker-readiness diagnostics.")
    parser.add_argument("--qrels-tsv", type=Path, required=True, help="TSV with query_id and support_doc_ids, or query_id/doc_id/relevance.")
    parser.add_argument("--run", action="append", default=[], help="Method/run mapping in the form method=path/to/run.trec")
    parser.add_argument("--target-k", type=int, default=10)
    parser.add_argument("--candidate-depth", type=int, default=100)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    if not args.run:
        raise SystemExit("At least one --run method=path.trec value is required")

    qrels = load_qrels_tsv(args.qrels_tsv)
    runs = {_method: load_trec_run(_path) for _method, _path in (_parse_run_arg(value) for value in args.run)}
    analysis = analyze_runs(qrels, runs, target_k=args.target_k, candidate_depth=args.candidate_depth)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown_report(analysis, args.report)
    print(json.dumps({"output": str(args.output), "report": str(args.report), "methods": list(runs)}, indent=2))


def _parse_run_arg(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise ValueError(f"Run argument must be method=path: {value}")
    method, path = value.split("=", 1)
    method = method.strip()
    if not method:
        raise ValueError(f"Run argument is missing method: {value}")
    return method, Path(path)


def _first_relevant_rank(hits: list[dict[str, Any]], relevant: set[str]) -> int | None:
    for hit in hits:
        if str(hit["doc_id"]) in relevant:
            return int(hit["rank"])
    return None


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


if __name__ == "__main__":
    main()
