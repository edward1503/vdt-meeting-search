from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.evaluation.openai_paraphrase_merge import merge_candidate_files


RUN_DIR = Path("artifacts/hotpotqa_full/paraphrase/openai_generation")
DEFAULT_INPUTS = [
    RUN_DIR / "openai_paraphrase_candidates.tsv",
    RUN_DIR / "openai_paraphrase_regeneration_candidates.tsv",
]
DEFAULT_OUTPUT_TSV = RUN_DIR / "openai_paraphrase_candidates_merged.tsv"
DEFAULT_OUTPUT_JSONL = RUN_DIR / "openai_paraphrase_candidates_merged.jsonl"


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge original and regenerated OpenAI paraphrase candidate TSVs.")
    parser.add_argument("--input", action="append", type=Path, default=[], help="Candidate TSV path. May be repeated.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_TSV, help="Merged candidate TSV path.")
    parser.add_argument("--jsonl-output", type=Path, default=DEFAULT_OUTPUT_JSONL, help="Merged candidate JSONL path.")
    args = parser.parse_args()

    inputs = args.input or DEFAULT_INPUTS
    count = merge_candidate_files(inputs, args.output, args.jsonl_output)
    print(f"merged {count} rows -> {args.output}")
    print(f"wrote jsonl -> {args.jsonl_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
