from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.ingest_eda import IngestEdaAccumulator, render_ingest_markdown


def main() -> None:
    parser = argparse.ArgumentParser(description="EDA for designing HotpotQA full-corpus Elasticsearch ingest")
    parser.add_argument("--dataset", default="beir/hotpotqa", help="Corpus dataset id")
    parser.add_argument(
        "--split-dataset",
        action="append",
        default=["beir/hotpotqa/train", "beir/hotpotqa/dev", "beir/hotpotqa/test"],
        help="Query/qrel split dataset id. Can be repeated.",
    )
    parser.add_argument("--sample-docs", type=int, default=100_000, help="Docs to inspect. Use --all-docs for full scan.")
    parser.add_argument("--all-docs", action="store_true", help="Inspect all documents")
    parser.add_argument("--skip-docs", action="store_true", help="Only collect metadata and split counts")
    parser.add_argument("--embedding-dims", type=int, default=384)
    parser.add_argument("--shard-target-gb", type=float, default=30)
    parser.add_argument("--staging-docs-per-file", type=int, default=50_000)
    parser.add_argument("--bulk-target-mb", type=float, default=10)
    parser.add_argument("--progress-every", type=int, default=10_000)
    parser.add_argument("--output", type=Path, default=Path("evaluation/results/hotpotqa_full_ingest_eda.json"))
    parser.add_argument("--markdown-output", type=Path, default=Path("docs/data/hotpotqa_full_ingest_eda.md"))
    args = parser.parse_args()

    report = run_eda(args)
    text = json.dumps(report, indent=2, ensure_ascii=False)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.write_text(render_ingest_markdown(report), encoding="utf-8")
    print(text)


def run_eda(args: argparse.Namespace) -> dict[str, Any]:
    import ir_datasets

    started = time.perf_counter()
    dataset = ir_datasets.load(args.dataset)
    metadata = {
        "has_docs": dataset.has_docs(),
        "has_queries": dataset.has_queries(),
        "has_qrels": dataset.has_qrels(),
        "docs_count": _safe_count(dataset, "docs_count"),
        "queries_count": _safe_count(dataset, "queries_count"),
        "qrels_count": _safe_count(dataset, "qrels_count"),
    }
    report: dict[str, Any] = {
        "dataset_id": args.dataset,
        "metadata": metadata,
        "splits": [_split_metadata(dataset_id) for dataset_id in args.split_dataset],
    }

    if args.skip_docs:
        report["documents"] = {"skipped": True, "skip_reason": "--skip-docs was used; document length/source profile was not scanned"}
    else:
        limit = None if args.all_docs else args.sample_docs
        accumulator = IngestEdaAccumulator()
        docs_started = time.perf_counter()
        for doc in _take(dataset.docs_iter(), limit):
            accumulator.add(doc)
            if args.progress_every and accumulator.iterated % args.progress_every == 0:
                elapsed = max(1e-9, time.perf_counter() - docs_started)
                print(
                    f"docs={accumulator.iterated:,} elapsed={elapsed:.1f}s rate={accumulator.iterated / elapsed:.1f}/s",
                    file=sys.stderr,
                    flush=True,
                )
        report["documents"] = accumulator.summary(
            total_docs=metadata.get("docs_count") if args.all_docs else metadata.get("docs_count"),
            embedding_dims=args.embedding_dims,
            shard_target_gb=args.shard_target_gb,
            staging_docs_per_file=args.staging_docs_per_file,
            bulk_target_mb=args.bulk_target_mb,
        )
        report["documents"]["docs_elapsed_sec"] = round(time.perf_counter() - docs_started, 3)
        if limit is not None:
            report["documents"]["sample_docs_limit"] = limit
    report["elapsed_sec"] = round(time.perf_counter() - started, 3)
    return report


def _split_metadata(dataset_id: str) -> dict[str, Any]:
    import ir_datasets

    dataset = ir_datasets.load(dataset_id)
    return {
        "dataset_id": dataset_id,
        "has_queries": dataset.has_queries(),
        "has_qrels": dataset.has_qrels(),
        "queries_count": _safe_count(dataset, "queries_count"),
        "qrels_count": _safe_count(dataset, "qrels_count"),
    }


def _safe_count(dataset: Any, method_name: str) -> int | str | None:
    try:
        return getattr(dataset, method_name)()
    except AttributeError:
        return None
    except Exception as exc:  # pragma: no cover - depends on local cache/download state.
        return f"ERROR: {type(exc).__name__}: {str(exc)[:200]}"


def _take(items: Iterable[Any], limit: int | None):
    for idx, item in enumerate(items):
        if limit is not None and idx >= limit:
            break
        yield item


if __name__ == "__main__":
    main()
