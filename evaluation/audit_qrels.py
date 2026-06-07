from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.core.config import ROOT_DIR, settings
from src.search.prompt_methods import STOPWORDS, tokenize
from src.search.searcher import MeetingSearcher


def audit_qrels(qrels_path: Path, methods: list[str], top_k: int) -> dict[str, Any]:
    qrels = json.loads(qrels_path.read_text(encoding="utf-8"))
    chunks = _read_jsonl(settings.index_dir / "chunks.jsonl")
    meeting_texts: dict[str, str] = {}
    for chunk in chunks:
        meeting_id = str(chunk["meeting_id"])
        meeting_texts[meeting_id] = meeting_texts.get(meeting_id, "") + " " + chunk.get("text", "")
    existing_meetings = set(meeting_texts)

    validation = []
    lexical_coverages = []
    for idx, item in enumerate(qrels):
        relevant = [str(meeting_id) for meeting_id in item["relevant_meeting_ids"]]
        missing = [meeting_id for meeting_id in relevant if meeting_id not in existing_meetings]
        query_terms = [term for term in tokenize(item["query"]) if term not in STOPWORDS and len(term) > 2]
        coverage = _relevant_term_coverage(query_terms, relevant, meeting_texts)
        lexical_coverages.append(coverage)
        validation.append(
            {
                "index": idx,
                "query": item["query"],
                "relevant_count": len(relevant),
                "missing_relevant_ids": missing,
                "query_terms": query_terms,
                "relevant_term_coverage": round(coverage, 4),
                "bucket": "original_10" if idx < 10 else "added_10",
            }
        )

    searcher = MeetingSearcher()
    method_results = []
    for method in methods:
        method_results.append(_evaluate_buckets(searcher, qrels, method, top_k))

    return {
        "qrels": str(qrels_path),
        "queries": len(qrels),
        "top_k": top_k,
        "relevant_per_query": sorted(set(len(item["relevant_meeting_ids"]) for item in qrels)),
        "missing_relevant_ids": [item for item in validation if item["missing_relevant_ids"]],
        "lexical_coverage_avg": round(sum(lexical_coverages) / max(1, len(lexical_coverages)), 4),
        "lexical_coverage_original_10": round(sum(lexical_coverages[:10]) / max(1, len(lexical_coverages[:10])), 4),
        "lexical_coverage_added_10": round(sum(lexical_coverages[10:]) / max(1, len(lexical_coverages[10:])), 4),
        "method_results": method_results,
        "query_audit": validation,
        "notes": [
            "The first 10 queries are the original MVP set and may be biased toward embedding results.",
            "The added 10 queries were labeled from corpus/chunk content inspection, not from embedding top results.",
            "This is still not a blind human-labeled benchmark; treat it as a stronger smoke test, not final quality evidence.",
        ],
    }


def _evaluate_buckets(searcher: MeetingSearcher, qrels: list[dict[str, Any]], method: str, top_k: int) -> dict[str, Any]:
    buckets = {
        "all_20": qrels,
        "original_10": qrels[:10],
        "added_10": qrels[10:],
    }
    return {
        "method": method,
        "buckets": {name: _evaluate(searcher, items, method, top_k) for name, items in buckets.items()},
    }


def _evaluate(searcher: MeetingSearcher, qrels: list[dict[str, Any]], method: str, top_k: int) -> dict[str, float]:
    precision_total = 0.0
    recall_total = 0.0
    reciprocal_total = 0.0
    for item in qrels:
        relevant = set(item["relevant_meeting_ids"])
        results = searcher.search(item["query"], top_k=top_k, method=method)["results"]
        returned = [result["meeting_id"] for result in results]
        hits = [meeting_id for meeting_id in returned if meeting_id in relevant]
        precision_total += len(hits) / max(1, top_k)
        recall_total += len(hits) / max(1, len(relevant))
        reciprocal_total += next((1 / rank for rank, meeting_id in enumerate(returned, start=1) if meeting_id in relevant), 0.0)
    count = max(1, len(qrels))
    return {
        "precision@k": round(precision_total / count, 4),
        "recall@k": round(recall_total / count, 4),
        "mrr@k": round(reciprocal_total / count, 4),
        "queries": len(qrels),
    }


def _relevant_term_coverage(query_terms: list[str], relevant: list[str], meeting_texts: dict[str, str]) -> float:
    if not query_terms or not relevant:
        return 0.0
    combined = " ".join(meeting_texts.get(meeting_id, "") for meeting_id in relevant).lower()
    hits = sum(1 for term in query_terms if term in combined)
    return hits / len(query_terms)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit AMI qrels for basic validity and bias signals")
    parser.add_argument("--qrels", type=Path, default=ROOT_DIR / "data" / "eval" / "ami_qrels.json")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--methods", default="embedding,multi_query_rrf,llm_multi_query_rrf")
    parser.add_argument("--output", type=Path, default=ROOT_DIR / "evaluation" / "results" / "qrels_bias_audit_ami.json")
    args = parser.parse_args()
    methods = [method.strip() for method in args.methods.split(",") if method.strip()]
    result = audit_qrels(args.qrels, methods, args.top_k)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()