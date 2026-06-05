from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.core.config import ROOT_DIR
from src.search.searcher import MeetingSearcher


def evaluate(qrels_path: Path, top_k: int = 10) -> dict[str, float]:
    searcher = MeetingSearcher()
    queries = json.loads(qrels_path.read_text(encoding="utf-8"))
    precision_total = 0.0
    recall_total = 0.0
    reciprocal_total = 0.0

    for item in queries:
        relevant = set(item["relevant_meeting_ids"])
        results = searcher.search(item["query"], top_k=top_k)["results"]
        returned = [result["meeting_id"] for result in results]
        hits = [meeting_id for meeting_id in returned if meeting_id in relevant]
        precision_total += len(hits) / max(1, top_k)
        recall_total += len(hits) / max(1, len(relevant))
        reciprocal_total += next((1 / rank for rank, meeting_id in enumerate(returned, start=1) if meeting_id in relevant), 0.0)

    count = max(1, len(queries))
    return {
        f"precision@{top_k}": precision_total / count,
        f"recall@{top_k}": recall_total / count,
        f"mrr@{top_k}": reciprocal_total / count,
        "queries": float(len(queries)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate meeting search")
    parser.add_argument("--qrels", type=Path, default=ROOT_DIR / "data" / "eval" / "sample_qrels.json")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.qrels, args.top_k), indent=2))


if __name__ == "__main__":
    main()

