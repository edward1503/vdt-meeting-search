from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.synthetic_metadata import write_metadata_shards


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate deterministic synthetic HotpotQA metadata shards")
    parser.add_argument("--staging-dir", type=Path, default=Path("artifacts/hotpotqa_full/staging"))
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/hotpotqa_full/metadata"))
    parser.add_argument("--max-files", type=int, default=None)
    args = parser.parse_args()

    manifest = write_metadata_shards(args.staging_dir, args.output_dir, max_files=args.max_files)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
