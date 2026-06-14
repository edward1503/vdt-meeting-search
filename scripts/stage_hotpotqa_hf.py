from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.staging import write_staging_shards


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage HotpotQA BEIR corpus from Hugging Face streaming")
    parser.add_argument("--dataset", default="BeIR/hotpotqa")
    parser.add_argument("--name", default="corpus")
    parser.add_argument("--split", default="corpus")
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/hotpotqa_100k/staging"))
    parser.add_argument("--docs-per-file", type=int, default=50_000)
    parser.add_argument("--max-docs", type=int, default=100_000)
    args = parser.parse_args()

    from datasets import load_dataset

    stream = load_dataset(args.dataset, args.name, split=args.split, streaming=True)
    docs = (
        SimpleNamespace(
            doc_id=str(row.get("_id", "")),
            title=str(row.get("title", "") or ""),
            text=str(row.get("text", "") or ""),
            url="",
        )
        for row in _take(stream, args.max_docs)
    )
    print(
        json.dumps(
            {
                "dataset": args.dataset,
                "name": args.name,
                "split": args.split,
                **write_staging_shards(docs, args.output_dir, args.docs_per_file),
            },
            indent=2,
        )
    )


def _take(items, limit: int):
    for idx, item in enumerate(items):
        if idx >= limit:
            break
        yield item


if __name__ == "__main__":
    main()
