from __future__ import annotations

import argparse
import json
import re
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
    candidate_k = int(rerank_config.get("candidate_k") or rrf_config.get("candidate_k") or 0)
    queries = _query_count(paired_summary, rrf_result, rerank_result, rrf_row, rerank_row)
    scope = "smoke" if queries < 50 else "pilot"

    diag_summary = diagnostics.get("methods", {}).get("tv_hybrid", {})
    buckets = diag_summary.get("failure_buckets", {})

    lines = [
        "# Reranker vs RRF Ablation",
        "",
        f"Scope: {queries}-query {scope} ablation. This is not a paper-comparable claim; small metric deltas need a larger split before final conclusions.",
        "",
        "## Artifacts",
        "",
        f"- RRF benchmark: `{rrf_path}`",
        f"- Reranker benchmark: `{rerank_path}`",
        f"- Candidate diagnostics: `{diagnostics_path}`",
        *_artifact_path_lines(rrf_run_path, rerank_run_path),
        f"- Reranker model: `{reranker_model}`",
        f"- Candidate budget: {candidate_k}",
        "",
        "## Metric Summary",
        "",
        "| Method | Metric cutoff | Full support | Recall | MRR | nDCG | p50 latency ms | p95 latency ms | QPS |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        _metric_row(rrf_row, rrf_config),
        _metric_row(rerank_row, rerank_config),
        "",
        "## Paired Full-Support Movement",
        "",
        f"- Evaluated paired queries: {paired_summary['queries']}",
        f"- RRF-only successes: {paired_summary.get('rrf_only_success', 0)}",
        f"- Reranker-only successes: {paired_summary.get('reranker_only_success', 0)}",
        f"- Both success: {paired_summary.get('both_success', 0)}",
        f"- Both fail: {paired_summary.get('both_fail', 0)}",
        f"- net reranker wins: {paired_summary.get('net_reranker_wins', 0)}",
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
    raise ValueError(f"Missing result row for method {method}")


def _metric_row(row: dict[str, Any], config: dict[str, Any]) -> str:
    method = str(row.get("method", "unknown"))
    metrics = row.get("metrics", {})
    cutoff = _metric_cutoff(method, metrics, config)
    return "| {method} | {cutoff} | {full:.4f} | {recall:.4f} | {mrr:.4f} | {ndcg:.4f} | {p50:.4f} | {p95:.4f} | {qps:.4f} |".format(
        method=method,
        full=_metric(method, metrics, "full_support_recall", cutoff),
        recall=_metric(method, metrics, "recall", cutoff),
        mrr=_metric(method, metrics, "mrr", cutoff),
        ndcg=_metric(method, metrics, "ndcg", cutoff),
        p50=_required_metric(method, metrics, "latency_p50_ms"),
        p95=_required_metric(method, metrics, "latency_p95_ms"),
        qps=_required_metric(method, metrics, "qps"),
        cutoff=cutoff,
    )


def _artifact_path_lines(rrf_run_path: Path | None, rerank_run_path: Path | None) -> list[str]:
    lines: list[str] = []
    if rrf_run_path is not None:
        lines.append(f"- RRF TREC run: `{rrf_run_path}`")
    if rerank_run_path is not None:
        lines.append(f"- Reranker TREC run: `{rerank_run_path}`")
    return lines


def _metric(method: str, metrics: dict[str, Any], name: str, cutoff: int) -> float:
    return _required_metric(method, metrics, f"{name}@{cutoff}")


def _required_metric(method: str, metrics: dict[str, Any], key: str) -> float:
    if key not in metrics:
        raise ValueError(f"Missing metric {key} for method {method}")
    return float(metrics[key])


def _metric_cutoff(method: str, metrics: dict[str, Any], config: dict[str, Any]) -> int:
    if config.get("top_k"):
        return int(config["top_k"])
    for name in ("full_support_recall", "recall", "mrr", "ndcg"):
        for key in metrics:
            match = re.fullmatch(rf"{re.escape(name)}@(\d+)", str(key))
            if match:
                return int(match.group(1))
    raise ValueError(f"Missing metric cutoff for method {method}")


def _query_count(
    paired_summary: dict[str, int],
    rrf_result: dict[str, Any],
    rerank_result: dict[str, Any],
    rrf_row: dict[str, Any],
    rerank_row: dict[str, Any],
) -> int:
    for value in (
        paired_summary.get("queries"),
        rerank_result.get("config", {}).get("max_queries"),
        rerank_result.get("config", {}).get("queries"),
        rerank_row.get("metrics", {}).get("queries"),
        rrf_result.get("config", {}).get("queries"),
        rrf_row.get("metrics", {}).get("queries"),
    ):
        if value:
            return int(value)
    return 0


def _top_hits(hits: list[dict[str, Any]], target_k: int) -> list[dict[str, Any]]:
    if not hits or "rank" not in hits[0]:
        return hits[:target_k]
    return sorted(hits, key=lambda hit: int(hit["rank"]))[:target_k]


if __name__ == "__main__":
    main()
