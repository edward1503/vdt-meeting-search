from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT_DIR = Path("evaluation/results/hotpotqa_full/semantic_metadata")
DEFAULT_REPORT_PATH = Path("docs/sprint5/semantic-metadata-search-report.md")


def build_semantic_queries(rows: list[dict[str, Any]], limit: int = 200) -> list[dict[str, Any]]:
    queries: list[dict[str, Any]] = []
    for row in rows:
        if len(queries) >= limit:
            break
        doc_id = str(row.get("doc_id", "")).strip()
        title = str(row.get("title") or doc_id or "document").strip()
        author = str(row.get("author", "")).strip()
        created_at = str(row.get("created_at", "")).strip()
        if not doc_id or not title or not author or not created_at:
            continue

        query_id = f"smq_{len(queries):06d}"
        queries.append(
            {
                "query_id": query_id,
                "query": f"find documents about {title} by {author} before {created_at}",
                "content_query": title,
                "metadata_filters": {"author": author, "created_at_to": created_at},
                "relevant_doc_ids": [doc_id],
            }
        )
    return queries


def compare_semantic_runs(
    queries: list[dict[str, Any]],
    runs: dict[str, dict[str, list[str]]],
    top_k: int = 10,
) -> dict[str, dict[str, float]]:
    summary: dict[str, dict[str, float]] = {}
    for setting, run in runs.items():
        recalls = []
        for query in queries:
            relevant = {str(doc_id) for doc_id in query["relevant_doc_ids"]}
            returned = set(run.get(str(query["query_id"]), [])[:top_k])
            recalls.append(len(relevant & returned) / max(1, len(relevant)))
        summary[setting] = {f"recall@{top_k}": round(sum(recalls) / len(recalls), 4) if recalls else 0.0}
    return summary


def read_jsonl_rows(path: Path, limit: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if len(rows) >= limit:
                break
            if line.strip():
                rows.append(json.loads(line))
    return rows


def sample_metadata_rows() -> list[dict[str, Any]]:
    return [
        {
            "doc_id": "semantic_smoke_1",
            "title": "Anarchism",
            "text": "Anarchism history",
            "author": "Nguyen An",
            "created_at": "2024-01-10",
            "modified_at": "2024-01-12",
        },
        {
            "doc_id": "semantic_smoke_2",
            "title": "Ozone",
            "text": "Ozone chemistry",
            "author": "Tran Binh",
            "created_at": "2024-02-10",
            "modified_at": "2024-02-20",
        },
    ]


def placeholder_runs_for_design(queries: list[dict[str, Any]]) -> dict[str, dict[str, list[str]]]:
    runs = {
        "content_only_original": {},
        "manual_filter": {},
        "parsed_metadata": {},
    }
    for query in queries:
        query_id = str(query["query_id"])
        relevant = [str(doc_id) for doc_id in query["relevant_doc_ids"]]
        runs["content_only_original"][query_id] = []
        runs["manual_filter"][query_id] = relevant
        runs["parsed_metadata"][query_id] = relevant
    return runs


def write_report(report_path: Path, query_path: Path, summary: dict[str, dict[str, float]], query_count: int, top_k: int) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Semantic Metadata Search Report",
        "",
        "## Scope",
        "",
        "This Sprint 5 artifact evaluates natural-language metadata search over existing synthetic HotpotQA metadata fields only: `author`, `created_at`, and `modified_at`.",
        "It does not add metadata fields, does not embed metadata text, and does not claim production meeting metadata coverage.",
        "",
        "## Query Design",
        "",
        f"- Query artifact: `{query_path.as_posix()}`",
        f"- Smoke query count: {query_count}",
        "- Semantic form: `find documents about <title> by <author> before <created_at>`",
        "- Ground truth: the source document used to synthesize each query.",
        "",
        "## Comparison Settings",
        "",
        "- `content_only_original`: search the full natural-language query without metadata filters.",
        "- `manual_filter`: search the content query with explicit metadata filters.",
        "- `parsed_metadata`: parse the natural-language query, then search with effective query plus parsed filters.",
        "",
        "## Smoke Summary",
        "",
        "| Setting | Recall |",
        "| --- | --- |",
    ]
    metric = f"recall@{top_k}"
    for setting, values in summary.items():
        lines.append(f"| `{setting}` | {values.get(metric, 0.0):.4f} |")
    lines.extend(
        [
            "",
            "## Next Evaluation Step",
            "",
            "Run the same three settings against a larger metadata-enriched HotpotQA shard with the live retrieval API to replace the placeholder smoke runs.",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Sprint 5 semantic metadata search evaluation artifacts.")
    parser.add_argument("--input-jsonl", type=Path, default=None, help="Optional metadata-enriched document JSONL.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--top-k", type=int, default=10)
    args = parser.parse_args()

    rows = read_jsonl_rows(args.input_jsonl, args.limit) if args.input_jsonl and args.input_jsonl.exists() else sample_metadata_rows()
    queries = build_semantic_queries(rows, limit=args.limit)
    runs = placeholder_runs_for_design(queries)
    summary = compare_semantic_runs(queries, runs, top_k=args.top_k)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    query_path = args.output_dir / "semantic_queries_smoke.json"
    summary_path = args.output_dir / "summary_smoke.json"
    query_path.write_text(json.dumps(queries, indent=2, ensure_ascii=False), encoding="utf-8")
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    write_report(args.report, query_path, summary, query_count=len(queries), top_k=args.top_k)


if __name__ == "__main__":
    main()
