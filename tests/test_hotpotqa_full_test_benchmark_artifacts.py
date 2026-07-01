import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _metrics(path: str) -> dict:
    payload = json.loads((ROOT / path).read_text(encoding="utf-8"))
    return payload["results"][0]["metrics"]


def test_hotpotqa_full_test_benchmark_artifacts_match_reported_metrics() -> None:
    hybrid = _metrics("evaluation/results/hotpotqa_full/test_full/tv_hybrid_test_full.json")
    bridge = _metrics(
        "evaluation/results/hotpotqa_full/test_full/tv_bridge_title_entities_rrf_beam1_terms6_test_full.json"
    )

    assert hybrid["queries"] == 7405
    assert bridge["queries"] == 7405
    assert hybrid["full_support_recall@10"] == 0.5175
    assert bridge["full_support_recall@10"] == 0.6008
    assert hybrid["ndcg@10"] == 0.7001
    assert bridge["ndcg@10"] == 0.712
