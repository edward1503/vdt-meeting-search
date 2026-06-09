from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.staging import write_staging_shards


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage HotpotQA docs into JSONL shards")
    parser.add_argument("--dataset", default="beir/hotpotqa")
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/hotpotqa_full/staging"))
    parser.add_argument("--docs-per-file", type=int, default=50_000)
    parser.add_argument("--max-docs", type=int, default=None)
    args = parser.parse_args()

    import ir_datasets

    docs = ir_datasets.load(args.dataset).docs_iter()
    if args.max_docs is not None:
        docs = _take(docs, args.max_docs)
    print(json.dumps({"dataset": args.dataset, **write_staging_shards(docs, args.output_dir, args.docs_per_file)}, indent=2))


def _take(items, limit: int):
    for idx, item in enumerate(items):
        if idx >= limit:
            break
        yield item


if __name__ == "__main__":
    main()
