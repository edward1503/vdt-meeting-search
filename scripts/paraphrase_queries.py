from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.evaluation.query_paraphrase import (
    ParaphraseConfig,
    make_query_variants,
    write_variants_jsonl,
    write_variants_tsv,
)


def main() -> None:
    parser = argparse.ArgumentParser(description='Generate deterministic query paraphrase variants')
    parser.add_argument('--input', type=Path, default=Path('evaluation/results/nano_test_queries.tsv'))
    parser.add_argument('--dataset', default='nano-beir/hotpotqa')
    parser.add_argument('--limit', type=int, default=50)
    parser.add_argument('--ratios', default='0.2,0.4,0.6')
    parser.add_argument('--variants-per-ratio', type=int, default=1)
    parser.add_argument('--seed', type=int, default=13)
    parser.add_argument('--output-tsv', type=Path, default=Path('evaluation/results/query_paraphrases_50.tsv'))
    parser.add_argument('--output-jsonl', type=Path, default=Path('evaluation/results/query_paraphrases_50.jsonl'))
    args = parser.parse_args()

    ratios = [float(item.strip()) for item in args.ratios.split(',') if item.strip()]
    config = ParaphraseConfig(ratios=ratios, variants_per_ratio=args.variants_per_ratio, seed=args.seed)
    source_queries = []
    seen_query_ids = set()
    variants = []

    with args.input.open('r', encoding='utf-8', newline='') as fh:
        reader = csv.DictReader(fh, delimiter='\t')
        for idx, row in enumerate(reader):
            if idx >= args.limit:
                break
            source_queries.append((row['query_id'], row['query']))
            seen_query_ids.add(row['query_id'])

    if len(source_queries) < args.limit:
        import ir_datasets

        dataset = ir_datasets.load(args.dataset)
        for query in dataset.queries_iter():
            query_id = str(query.query_id)
            if query_id in seen_query_ids:
                continue
            source_queries.append((query_id, str(getattr(query, 'text', '') or '')))
            seen_query_ids.add(query_id)
            if len(source_queries) >= args.limit:
                break

    for query_id, query_text in source_queries[:args.limit]:
        variants.extend(make_query_variants(query_id, query_text, config))

    write_variants_tsv(variants, args.output_tsv)
    write_variants_jsonl(variants, args.output_jsonl)
    print(f'wrote {len(variants)} variants to {args.output_tsv} and {args.output_jsonl}')


if __name__ == '__main__':
    main()
