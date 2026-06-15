from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULT_DIR = ROOT / "evaluation" / "results" / "hotpotqa_full"
RUN_DIR = ROOT / "evaluation" / "runs" / "hotpotqa_full"


def load_result(name: str) -> dict:
    path = RESULT_DIR / name
    if not path.exists():
        raise AssertionError(f"missing result file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def method_metrics(result: dict, method: str) -> dict:
    for row in result.get("results", []):
        if row.get("method") == method:
            return row["metrics"]
    raise AssertionError(f"missing method {method} in result")


def assert_queries(result: dict, expected: int = 200) -> None:
    actual = int(result.get("config", {}).get("queries", 0))
    if actual != expected:
        raise AssertionError(f"expected {expected} queries, got {actual}")


def assert_min_metric(metrics: dict, name: str, minimum: float) -> None:
    actual = float(metrics[name])
    if actual < minimum:
        raise AssertionError(f"{name} expected >= {minimum}, got {actual}")


def assert_trec_exists(path: Path) -> None:
    if not path.exists():
        raise AssertionError(f"missing TREC run file: {path}")
    if path.stat().st_size == 0:
        raise AssertionError(f"empty TREC run file: {path}")


def main() -> None:
    primary = load_result("tv_full_200.json")
    assert_queries(primary)

    bm25 = method_metrics(primary, "es_bm25")
    dense = method_metrics(primary, "tv_dense")
    hybrid = method_metrics(primary, "tv_hybrid")
    assert_min_metric(bm25, "full_support_recall@10", 0.36)
    assert_min_metric(dense, "full_support_recall@10", 0.51)
    assert_min_metric(hybrid, "full_support_recall@10", 0.54)

    for name in ["tune_k50_rrf30.json", "tune_k200_rrf30.json", "tune_k100_rrf60.json"]:
        result = load_result(name)
        assert_queries(result)
        metrics = method_metrics(result, "tv_hybrid")
        assert_min_metric(metrics, "full_support_recall@10", 0.53)

    for name in [
        "es_bm25_beir_hotpotqa_dev_top10.trec",
        "tv_dense_beir_hotpotqa_dev_top10.trec",
        "tv_hybrid_beir_hotpotqa_dev_top10.trec",
        "tune_k50_rrf30/tv_hybrid_beir_hotpotqa_dev_top10.trec",
        "tune_k200_rrf30/tv_hybrid_beir_hotpotqa_dev_top10.trec",
        "tune_k100_rrf60/tv_hybrid_beir_hotpotqa_dev_top10.trec",
    ]:
        assert_trec_exists(RUN_DIR / name)

    print(
        json.dumps(
            {
                "status": "ok",
                "queries": primary["config"]["queries"],
                "bm25_full_support_recall@10": bm25["full_support_recall@10"],
                "tv_dense_full_support_recall@10": dense["full_support_recall@10"],
                "tv_hybrid_full_support_recall@10": hybrid["full_support_recall@10"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
