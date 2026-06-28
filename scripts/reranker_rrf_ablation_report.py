from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.ranking_diagnostics import load_qrels_tsv, load_trec_run


def compare_full_support_wins(
    qrels: dict[str, set[str]],
    rrf_run: dict[str, list[dict[str, Any]]],
    rerank_run: dict[str, list[dict[str, Any]]],
    target_k: int,
) -> dict[str, int]:
    summary = {
        "queries": 0,
        "rrf_only_success": 0,
        "reranker_only_success": 0,
        "both_success": 0,
        "both_fail": 0,
        "net_reranker_wins": 0,
    }

    for query_id, relevant in sorted(qrels.items()):
        if query_id not in rrf_run or query_id not in rerank_run:
            continue
        summary["queries"] += 1
        rrf_success = _full_support_success(rrf_run[query_id], relevant, target_k)
        rerank_success = _full_support_success(rerank_run[query_id], relevant, target_k)

        if rrf_success and rerank_success:
            summary["both_success"] += 1
        elif rrf_success:
            summary["rrf_only_success"] += 1
        elif rerank_success:
            summary["reranker_only_success"] += 1
        else:
            summary["both_fail"] += 1

    summary["net_reranker_wins"] = summary["reranker_only_success"] - summary["rrf_only_success"]
    return summary


def build_report(
    *,
    rrf_result: dict[str, Any],
    rerank_result: dict[str, Any],
    diagnostics: dict[str, Any],
    paired_summary: dict[str, int],
    rrf_path: Path,
    rerank_path: Path,
    diagnostics_path: Path,
    rrf_run_path: Path | None = None,
    rerank_run_path: Path | None = None,
) -> str:
    rrf_row = _result_by_method(rrf_result, "tv_hybrid")
    rerank_row = _result_by_method(rerank_result, "tv_hybrid_rerank")
    rerank_config = rerank_result.get("config", {})
    rrf_config = rrf_result.get("config", {})
    reranker_model = str(rerank_config.get("reranker_model", "unknown"))
    target_k = int(rerank_config.get("top_k") or rrf_config.get("top_k") or 10)
    candidate_k = int(rerank_config.get("candidate_k") or rrf_config.get("candidate_k") or 0)
    queries = int(paired_summary.get("queries") or rerank_config.get("max_queries") or rrf_config.get("max_queries") or 0)

    diag_summary = diagnostics.get("methods", {}).get("tv_hybrid", {})
    buckets = diag_summary.get("failure_buckets", {})

    lines = [
        "# Reranker vs RRF Ablation",
        "",
        f"Scope: {queries}-query pilot ablation. This is not a paper-comparable claim; small metric deltas need a larger split before final conclusions.",
        "",
        "## Artifacts",
        "",
        f"- RRF benchmark: `{rrf_path}`",
        f"- Reranker benchmark: `{rerank_path}`",
        f"- Candidate diagnostics: `{diagnostics_path}`",
        *_artifact_path_lines(rrf_run_path, rerank_run_path),
        f"- Reranker model: `{reranker_model}`",
        f"- Target cutoff: top-{target_k}",
        f"- Candidate budget: {candidate_k}",
        "",
        "## Metric Summary",
        "",
        f"| Method | Full support@{target_k} | Recall@{target_k} | MRR@{target_k} | nDCG@{target_k} | p50 latency ms | p95 latency ms | QPS |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        _metric_row("tv_hybrid", rrf_row.get("metrics", {}), target_k),
        _metric_row("tv_hybrid_rerank", rerank_row.get("metrics", {}), target_k),
        "",
        "## Paired Full-Support Movement",
        "",
        f"- Evaluated paired queries: {paired_summary['queries']}",
        f"- RRF-only successes: {paired_summary['rrf_only_success']}",
        f"- Reranker-only successes: {paired_summary['reranker_only_success']}",
        f"- Both success: {paired_summary['both_success']}",
        f"- Both fail: {paired_summary['both_fail']}",
        f"- net reranker wins: {paired_summary['net_reranker_wins']}",
        "",
        "## Candidate Diagnostics",
        "",
        f"- Candidate recall@depth: {float(diag_summary.get('candidate_recall_at_depth', 0.0)):.4f}",
        f"- Missing candidate: {int(buckets.get('missing_candidate', 0))}",
        f"- Partial candidate support: {int(buckets.get('partial_candidate_support', 0))}",
        f"- Candidate ranked low: {int(buckets.get('candidate_ranked_low', 0))}",
        f"- Success at target cutoff: {int(buckets.get('success', 0))}",
        "",
        "## Recommendation Rule",
        "",
        "Continue reranker work only if the reranker creates meaningful paired wins over RRF and the latency increase is acceptable for the target demo/research use case. If candidate diagnostics show many missing candidates, improve candidate generation before investing more in reranking.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a reranker-vs-RRF ablation report.")
    parser.add_argument("--rrf-result", type=Path, required=True)
    parser.add_argument("--rerank-result", type=Path, required=True)
    parser.add_argument("--diagnostics", type=Path, required=True)
    parser.add_argument("--qrels-tsv", type=Path, required=True)
    parser.add_argument("--rrf-run", type=Path, required=True)
    parser.add_argument("--rerank-run", type=Path, required=True)
    parser.add_argument("--target-k", type=int, default=10)
    parser.add_argument("--output", type=Path, default=Path("docs/sprint5/reranker-rrf-ablation-report.md"))
    args = parser.parse_args()

    rrf_result = _read_json(args.rrf_result)
    rerank_result = _read_json(args.rerank_result)
    diagnostics = _read_json(args.diagnostics)
    paired_summary = compare_full_support_wins(
        load_qrels_tsv(args.qrels_tsv),
        load_trec_run(args.rrf_run),
        load_trec_run(args.rerank_run),
        target_k=args.target_k,
    )
    report = build_report(
        rrf_result=rrf_result,
        rerank_result=rerank_result,
        diagnostics=diagnostics,
        paired_summary=paired_summary,
        rrf_path=args.rrf_result,
        rerank_path=args.rerank_result,
        diagnostics_path=args.diagnostics,
        rrf_run_path=args.rrf_run,
        rerank_run_path=args.rerank_run,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(json.dumps({"output": str(args.output), "paired": paired_summary}, indent=2))


def _full_support_success(hits: list[dict[str, Any]], relevant: set[str], target_k: int) -> bool:
    if not relevant:
        return False
    returned = {str(hit["doc_id"]) for hit in _top_hits(hits, target_k)}
    return relevant.issubset(returned)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _result_by_method(result: dict[str, Any], method: str) -> dict[str, Any]:
    for row in result.get("results", []):
        if row.get("method") == method:
            return row
    return {}


def _metric_row(method: str, metrics: dict[str, Any], target_k: int) -> str:
    return "| {method} | {full:.4f} | {recall:.4f} | {mrr:.4f} | {ndcg:.4f} | {p50:.4f} | {p95:.4f} | {qps:.4f} |".format(
        method=method,
        full=_metric(metrics, "full_support_recall", target_k),
        recall=_metric(metrics, "recall", target_k),
        mrr=_metric(metrics, "mrr", target_k),
        ndcg=_metric(metrics, "ndcg", target_k),
        p50=float(metrics.get("latency_p50_ms", 0.0)),
        p95=float(metrics.get("latency_p95_ms", 0.0)),
        qps=float(metrics.get("qps", 0.0)),
    )


def _artifact_path_lines(rrf_run_path: Path | None, rerank_run_path: Path | None) -> list[str]:
    lines: list[str] = []
    if rrf_run_path is not None:
        lines.append(f"- RRF TREC run: `{rrf_run_path}`")
    if rerank_run_path is not None:
        lines.append(f"- Reranker TREC run: `{rerank_run_path}`")
    return lines


def _metric(metrics: dict[str, Any], name: str, target_k: int) -> float:
    return float(metrics.get(f"{name}@{target_k}", metrics.get(f"{name}@10", 0.0)))


def _top_hits(hits: list[dict[str, Any]], target_k: int) -> list[dict[str, Any]]:
    if not hits or "rank" not in hits[0]:
        return hits[:target_k]
    return sorted(hits, key=lambda hit: int(hit["rank"]))[:target_k]


if __name__ == "__main__":
    main()
