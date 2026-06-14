from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.evaluation.compare_paraphrase import summarize_metric_deltas


def main() -> None:
    parser = argparse.ArgumentParser(description='Compare paraphrase benchmark results against baseline')
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--variant', action='append', default=[], help='condition=path.json')
    parser.add_argument('--output', type=Path, default=Path('evaluation/results/paraphrase_summary.csv'))
    parser.add_argument('--metrics', default='recall@10,ndcg@10,full_support_recall@10,mrr@10,latency_p95_ms')
    args = parser.parse_args()

    baseline = json.loads(args.baseline.read_text(encoding='utf-8'))
    variants = {}
    for item in args.variant:
        condition, path = item.split('=', 1)
        variants[condition] = json.loads(Path(path).read_text(encoding='utf-8'))

    metrics = [item.strip() for item in args.metrics.split(',') if item.strip()]
    rows = summarize_metric_deltas(baseline, variants, metrics)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('w', encoding='utf-8', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=['condition', 'method', 'metric', 'baseline', 'variant', 'delta'])
        writer.writeheader()
        writer.writerows(rows)
    print(f'wrote {len(rows)} rows to {args.output}')


if __name__ == '__main__':
    main()
