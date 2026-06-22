from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_SCENARIOS: list[dict[str, Any]] = [
    {
        "name": "content_only_anarchism",
        "mode": "content_only",
        "query": "Anarchism",
        "method": "es_bm25",
        "filters": {},
    },
    {
        "name": "author_nguyen_an",
        "mode": "metadata_filtered",
        "query": "Anarchism",
        "method": "es_bm25",
        "filters": {"author": "Nguyen An"},
    },
    {
        "name": "created_january_2024",
        "mode": "metadata_filtered",
        "query": "Anarchism",
        "method": "es_bm25",
        "filters": {"created_at_from": "2024-01-01", "created_at_to": "2024-01-31"},
    },
    {
        "name": "modified_mid_january_2024",
        "mode": "metadata_filtered",
        "query": "Anarchism",
        "method": "es_bm25",
        "filters": {"modified_at_from": "2024-01-10", "modified_at_to": "2024-01-20"},
    },
    {
        "name": "hybrid_author_created_january",
        "mode": "metadata_content_hybrid",
        "query": "Anarchism",
        "method": "tv_hybrid",
        "filters": {"author": "Nguyen An", "created_at_from": "2024-01-01", "created_at_to": "2024-01-31"},
    },
]


def build_metadata_demo_report(
    metadata_dir: Path,
    output_path: Path,
    scenarios: list[dict[str, Any]] | None = None,
    sample_size: int = 3,
) -> dict[str, Any]:
    manifest = _read_manifest(metadata_dir)
    baseline_docs = int(manifest.get("docs_written") or 0)
    selected_scenarios = scenarios or DEFAULT_SCENARIOS
    scenario_summaries, counted_docs = _summarize_scenarios(
        selected_scenarios,
        _iter_metadata_rows(metadata_dir),
        baseline_docs=baseline_docs,
        sample_size=sample_size,
    )
    if baseline_docs == 0:
        baseline_docs = counted_docs

    report = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "metadata_dir": str(metadata_dir),
        "synthetic": bool(manifest.get("synthetic", True)),
        "metadata_fields": manifest.get("metadata_fields", ["author", "created_at", "modified_at"]),
        "embedding_text_policy": manifest.get(
            "embedding_text_policy",
            "unchanged content-only text; synthetic metadata is not embedded",
        ),
        "baseline_docs": baseline_docs,
        "counted_docs": counted_docs,
        "scenario_count": len(selected_scenarios),
        "scenarios": scenario_summaries,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def _read_manifest(metadata_dir: Path) -> dict[str, Any]:
    manifest_path = metadata_dir / "manifest.json"
    if not manifest_path.exists():
        return {}
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _iter_metadata_rows(metadata_dir: Path) -> Iterable[dict[str, Any]]:
    for path in sorted(metadata_dir.glob("docs-*.jsonl")):
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    yield json.loads(line)


def _summarize_scenarios(
    scenarios: list[dict[str, Any]],
    rows: Iterable[dict[str, Any]],
    baseline_docs: int,
    sample_size: int,
) -> tuple[list[dict[str, Any]], int]:
    states = [
        {
            "scenario": scenario,
            "filters": dict(scenario.get("filters") or {}),
            "matched_docs": 0,
            "sample_results": [],
        }
        for scenario in scenarios
    ]
    counted_docs = 0
    started = perf_counter()
    for row in rows:
        counted_docs += 1
        for state in states:
            if _matches_filters(row, state["filters"]):
                state["matched_docs"] += 1
                if len(state["sample_results"]) < sample_size:
                    state["sample_results"].append(_sample_row(row))
    elapsed_ms = round((perf_counter() - started) * 1000, 4)
    effective_baseline = baseline_docs or counted_docs

    summaries = []
    for state in states:
        scenario = state["scenario"]
        filters = state["filters"]
        matched_docs = effective_baseline if not filters else state["matched_docs"]
        narrowing_pct = 0.0 if effective_baseline == 0 else round((1 - (matched_docs / effective_baseline)) * 100, 4)
        method = str(scenario.get("method") or "es_bm25")
        summaries.append(
            {
                "name": scenario["name"],
                "mode": scenario["mode"],
                "query": scenario.get("query", ""),
                "method": method,
                "effective_method": _effective_method(method, filters),
                "metadata_filter_scope": "hard_prefilter" if filters else "none",
                "filters": filters,
                "baseline_docs": effective_baseline,
                "matched_docs": matched_docs,
                "narrowing_pct": narrowing_pct,
                "count_elapsed_ms": elapsed_ms,
                "latency_observation": "one-pass offline metadata count in milliseconds; search latency is covered by the US-S4-006 API smoke proof",
                "sample_results": state["sample_results"],
            }
        )
    return summaries, counted_docs


def _matches_filters(row: dict[str, Any], filters: dict[str, Any]) -> bool:
    author = filters.get("author")
    if author and row.get("author") != author:
        return False
    for field in ("created_at", "modified_at"):
        value = str(row.get(field, ""))
        from_value = filters.get(f"{field}_from")
        to_value = filters.get(f"{field}_to")
        if from_value and value < str(from_value):
            return False
        if to_value and value > str(to_value):
            return False
    return True


def _effective_method(method: str, filters: dict[str, Any]) -> str:
    if filters and method == "tv_hybrid":
        return "tv_filtered_hybrid"
    return method


def _sample_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "doc_id": row.get("doc_id"),
        "numeric_id": row.get("numeric_id"),
        "title": row.get("title"),
        "author": row.get("author"),
        "created_at": row.get("created_at"),
        "modified_at": row.get("modified_at"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Sprint 4 synthetic metadata demo scenario evidence")
    parser.add_argument("--metadata-dir", type=Path, default=Path("artifacts/hotpotqa_full/metadata"))
    parser.add_argument("--output", type=Path, default=Path("evaluation/results/hotpotqa_full/metadata/scenario_summary.json"))
    args = parser.parse_args()

    report = build_metadata_demo_report(metadata_dir=args.metadata_dir, output_path=args.output)
    print(json.dumps({"output": str(args.output), "scenario_count": report["scenario_count"]}, indent=2))


if __name__ == "__main__":
    main()
