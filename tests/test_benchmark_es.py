from __future__ import annotations

from types import SimpleNamespace

from src.evaluation import benchmark_es
from src.evaluation.benchmark_es import map_es_method, trec_line


def test_run_benchmark_records_and_passes_rrf_k(monkeypatch, tmp_path):
    calls = []

    class FakeDataset:
        def queries_iter(self):
            yield SimpleNamespace(query_id='q1', text='query')

        def qrels_iter(self):
            yield SimpleNamespace(query_id='q1', doc_id='d1', relevance=1)

    class FakeRetriever:
        def __init__(self, **kwargs):
            pass

        def search(self, query, method, top_k, candidate_k=100, rrf_k=60):
            calls.append({'candidate_k': candidate_k, 'rrf_k': rrf_k, 'method': method})
            return [{'doc_id': 'd1', 'score': 1.0}]

    monkeypatch.setattr(benchmark_es, '_load_ir_dataset', lambda dataset_id: FakeDataset())
    monkeypatch.setattr(benchmark_es, '_client', lambda url: object())
    monkeypatch.setattr(benchmark_es, 'ElasticsearchRetriever', FakeRetriever)

    result = benchmark_es.run_benchmark(
        dataset_id='dataset',
        index='idx',
        methods=['es_hybrid'],
        top_k=10,
        max_queries=None,
        url='http://localhost:9200',
        model_name='model',
        num_candidates=100,
        candidate_k=20,
        rrf_k=7,
        first_hop_k=5,
        second_hop_k=10,
        context_chars=256,
        run_dir=tmp_path,
    )

    assert result['config']['rrf_k'] == 7
    assert calls == [{'candidate_k': 20, 'rrf_k': 7, 'method': 'hybrid'}]


def test_run_benchmark_calls_iterative_hybrid_with_hop_config(monkeypatch, tmp_path):
    calls = []

    class FakeDataset:
        def queries_iter(self):
            yield SimpleNamespace(query_id='q1', text='query')

        def qrels_iter(self):
            yield SimpleNamespace(query_id='q1', doc_id='d1', relevance=1)

    class FakeRetriever:
        def __init__(self, **kwargs):
            pass

        def search_iterative_hybrid(
            self,
            query,
            top_k,
            candidate_k=100,
            rrf_k=60,
            first_hop_k=5,
            second_hop_k=10,
            context_chars=256,
        ):
            calls.append(
                {
                    'query': query,
                    'top_k': top_k,
                    'candidate_k': candidate_k,
                    'rrf_k': rrf_k,
                    'first_hop_k': first_hop_k,
                    'second_hop_k': second_hop_k,
                    'context_chars': context_chars,
                }
            )
            return [{'doc_id': 'd1', 'score': 1.0}]

    monkeypatch.setattr(benchmark_es, '_load_ir_dataset', lambda dataset_id: FakeDataset())
    monkeypatch.setattr(benchmark_es, '_client', lambda url: object())
    monkeypatch.setattr(benchmark_es, 'ElasticsearchRetriever', FakeRetriever)

    result = benchmark_es.run_benchmark(
        dataset_id='dataset',
        index='idx',
        methods=['es_iterative_hybrid'],
        top_k=10,
        max_queries=None,
        url='http://localhost:9200',
        model_name='model',
        num_candidates=100,
        candidate_k=20,
        rrf_k=7,
        first_hop_k=3,
        second_hop_k=4,
        context_chars=128,
        run_dir=tmp_path,
    )

    assert result['config']['first_hop_k'] == 3
    assert calls == [
        {
            'query': 'query',
            'top_k': 10,
            'candidate_k': 20,
            'rrf_k': 7,
            'first_hop_k': 3,
            'second_hop_k': 4,
            'context_chars': 128,
        }
    ]

def test_trec_line_is_stable():
    assert trec_line('q1', 'd1', 3, 0.25, 'es_hybrid') == 'q1 Q0 d1 3 0.250000 es_hybrid'


def test_map_es_method_strips_prefix():
    assert map_es_method('es_bm25') == 'bm25'
    assert map_es_method('es_dense') == 'dense'
    assert map_es_method('es_hybrid') == 'hybrid'
    assert map_es_method('es_iterative_hybrid') == 'iterative_hybrid'
