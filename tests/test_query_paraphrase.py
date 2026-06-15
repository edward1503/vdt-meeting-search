from __future__ import annotations

import json

from src.evaluation.query_paraphrase import (
    ParaphraseConfig,
    make_query_variants,
    write_variants_jsonl,
    write_variants_tsv,
)
from src.evaluation.compare_paraphrase import summarize_metric_deltas


def test_make_query_variants_is_deterministic():
    query = 'What occupations do both Ian Hunter and Rob Thomas have?'
    config = ParaphraseConfig(ratios=[0.4], variants_per_ratio=2, seed=7)

    first = make_query_variants('q1', query, config)
    second = make_query_variants('q1', query, config)

    assert first == second
    assert [item.variant_query_id for item in first] == ['q1::syn040::v1', 'q1::syn040::v2']


def test_make_query_variants_preserves_named_entities():
    query = 'What occupations do both Ian Hunter and Rob Thomas have?'
    config = ParaphraseConfig(ratios=[0.6], variants_per_ratio=1, seed=3)

    [variant] = make_query_variants('q1', query, config)

    assert 'Ian Hunter' in variant.query
    assert 'Rob Thomas' in variant.query
    assert variant.source_query_id == 'q1'
    assert variant.ratio == 0.6


def test_make_query_variants_changes_some_eligible_words():
    query = 'What city did the famous scientist visit after the important conference?'
    config = ParaphraseConfig(ratios=[0.5], variants_per_ratio=1, seed=11)

    [variant] = make_query_variants('q2', query, config)

    assert variant.query != query
    assert variant.changed_terms
    assert 0.0 < variant.actual_change_ratio <= 1.0


def test_write_variants_outputs_tsv_and_jsonl(tmp_path):
    config = ParaphraseConfig(ratios=[0.2], variants_per_ratio=1, seed=5)
    variants = make_query_variants('q1', 'What famous city did the scientist visit?', config)
    tsv_path = tmp_path / 'variants.tsv'
    jsonl_path = tmp_path / 'variants.jsonl'

    write_variants_tsv(variants, tsv_path)
    write_variants_jsonl(variants, jsonl_path)

    header = 'variant_query_id\tsource_query_id\tratio\tvariant_index\tquery\tchanged_terms\tactual_change_ratio'
    assert tsv_path.read_text(encoding='utf-8').splitlines()[0] == header
    record = json.loads(jsonl_path.read_text(encoding='utf-8').splitlines()[0])
    assert record['source_query_id'] == 'q1'
    assert record['variant_query_id'].startswith('q1::syn020::v')


def test_summarize_metric_deltas():
    baseline = {'results': [{'method': 'es_bm25', 'metrics': {'recall@10': 0.5, 'full_support_recall@10': 0.2}}]}
    variant = {'results': [{'method': 'es_bm25', 'metrics': {'recall@10': 0.4, 'full_support_recall@10': 0.1}}]}

    rows = summarize_metric_deltas(baseline, {'syn020': variant}, metrics=['recall@10', 'full_support_recall@10'])

    assert rows == [
        {'condition': 'syn020', 'method': 'es_bm25', 'metric': 'recall@10', 'baseline': 0.5, 'variant': 0.4, 'delta': -0.1},
        {'condition': 'syn020', 'method': 'es_bm25', 'metric': 'full_support_recall@10', 'baseline': 0.2, 'variant': 0.1, 'delta': -0.1},
    ]
