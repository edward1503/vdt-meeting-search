from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.evaluation.openai_paraphrase_validation import validate_and_select


DEFAULT_CANDIDATES = Path("artifacts/hotpotqa_full/paraphrase/openai_generation/openai_paraphrase_candidates.tsv")
DEFAULT_OUTPUT_DIR = Path("artifacts/hotpotqa_full/paraphrase/validated")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate OpenAI paraphrase candidates and select benchmark inputs.")
    parser.add_argument("--input", type=Path, default=DEFAULT_CANDIDATES, help="OpenAI candidates TSV path.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Directory for accepted/rejected/selection artifacts.")
    parser.add_argument("--expected-per-profile", type=int, default=200, help="Required accepted rows per profile for complete benchmark inputs.")
    args = parser.parse_args()

    summary = validate_and_select(args.input, args.output_dir, expected_per_profile=args.expected_per_profile)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
