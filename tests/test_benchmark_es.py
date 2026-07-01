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

def test_map_es_method_accepts_title_aware_bm25():
    assert map_es_method("es_bm25_title") == "bm25_title"

def test_iterative_variant_method_mapping():
    assert map_es_method('es_iterative_title') == 'iterative_title'
    assert map_es_method('es_iterative_sentence') == 'iterative_sentence'
    assert map_es_method('es_iterative_fast') == 'iterative_fast'


def test_run_benchmark_uses_query_file_override(monkeypatch, tmp_path):
    calls = []
    query_file = tmp_path / 'queries.tsv'
    query_file.write_text(
        'variant_query_id\tsource_query_id\tratio\tvariant_index\tquery\tchanged_terms\tactual_change_ratio\n'
        'q1::syn020::v1\tq1\t0.20\t1\tparaphrased query\tfamous->notable\t0.2500\n',
        encoding='utf-8',
    )

    class FakeDataset:
        def queries_iter(self):
            yield SimpleNamespace(query_id='q1', text='original query')

        def qrels_iter(self):
            yield SimpleNamespace(query_id='q1', doc_id='d1', relevance=1)

    class FakeRetriever:
        def __init__(self, **kwargs):
            pass

        def search(self, query, method, top_k, candidate_k=100, rrf_k=60):
            calls.append(query)
            return [{'doc_id': 'd1', 'score': 1.0}]

    monkeypatch.setattr(benchmark_es, '_load_ir_dataset', lambda dataset_id: FakeDataset())
    monkeypatch.setattr(benchmark_es, '_client', lambda url: object())
    monkeypatch.setattr(benchmark_es, 'ElasticsearchRetriever', FakeRetriever)

    result = benchmark_es.run_benchmark(
        dataset_id='dataset',
        index='idx',
        methods=['es_bm25'],
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
        query_file=query_file,
    )

    assert calls == ['paraphrased query']
    assert result['config']['queries'] == 1
    assert result['config']['query_file'] == str(query_file)

def test_run_benchmark_uses_qrels_file_with_query_file(monkeypatch, tmp_path):
    calls = []
    query_file = tmp_path / 'queries.tsv'
    qrels_file = tmp_path / 'qrels.tsv'
    query_file.write_text(
        'variant_query_id\tsource_query_id\tratio\tvariant_index\tquery\tchanged_terms\tactual_change_ratio\n'
        'q1\tq1\t0.00\t0\toriginal query\t\t0.0000\n',
        encoding='utf-8',
    )
    qrels_file.write_text('query_id\tdoc_id\trelevance\nq1\td1\t1\n', encoding='utf-8')

    class FakeDataset:
        def queries_iter(self):
            yield SimpleNamespace(query_id='ignored', text='ignored')

        def qrels_iter(self):
            raise AssertionError('qrels_iter should not be called when qrels_file is provided')

    class FakeRetriever:
        def __init__(self, **kwargs):
            pass

        def search(self, query, method, top_k, candidate_k=100, rrf_k=60):
            calls.append(query)
            return [{'doc_id': 'd1', 'score': 1.0}]

    monkeypatch.setattr(benchmark_es, '_load_ir_dataset', lambda dataset_id: FakeDataset())
    monkeypatch.setattr(benchmark_es, '_client', lambda url: object())
    monkeypatch.setattr(benchmark_es, 'ElasticsearchRetriever', FakeRetriever)

    result = benchmark_es.run_benchmark(
        dataset_id='dataset',
        index='idx',
        methods=['es_bm25'],
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
        query_file=query_file,
        qrels_file=qrels_file,
    )

    assert calls == ['original query']
    assert result['config']['queries'] == 1
    assert result['config']['qrels_file'] == str(qrels_file)
    assert result['results'][0]['metrics']['recall@10'] == 1.0

def test_run_benchmark_accepts_dataset_query_file_with_query_id_header(monkeypatch, tmp_path):
    query_file = tmp_path / "queries.tsv"
    qrels_file = tmp_path / "qrels.tsv"
    query_file.write_text("query_id\tsource_query_id\tquery\nq1\tq1\tHà Nội là gì?\n", encoding="utf-8")
    qrels_file.write_text("query_id\tdoc_id\trelevance\nq1\td1\t1\n", encoding="utf-8")

    class FakeRetriever:
        def search(self, query, method, top_k, candidate_k=100, rrf_k=60):
            return [{"doc_id": "d1", "score": 1.0}]

    monkeypatch.setattr(benchmark_es, "build_retriever", lambda *args, **kwargs: FakeRetriever())

    result = benchmark_es.run_benchmark(
        dataset_id="vimqa/all",
        index="idx",
        methods=["es_bm25"],
        top_k=10,
        max_queries=None,
        url="http://example.invalid",
        model_name="model",
        num_candidates=100,
        candidate_k=10,
        rrf_k=60,
        first_hop_k=5,
        second_hop_k=10,
        context_chars=256,
        run_dir=tmp_path,
        query_file=query_file,
        qrels_file=qrels_file,
    )

    assert result["config"]["queries"] == 1
    assert result["results"][0]["metrics"]["recall@10"] == 1.0


def test_method_mapping_accepts_turbovec_methods():
    assert benchmark_es.classify_method("es_bm25") == "es"
    assert benchmark_es.classify_method("tv_dense") == "turbovec"
    assert benchmark_es.classify_method("tv_hybrid") == "turbovec"


def test_run_benchmark_with_query_and_qrels_files_does_not_load_ir_dataset(monkeypatch, tmp_path):
    query_file = tmp_path / "queries.tsv"
    qrels_file = tmp_path / "qrels.tsv"
    query_file.write_text("variant_query_id\tsource_query_id\tquery\nq1\tq1\tcustom query\n", encoding="utf-8")
    qrels_file.write_text("query_id\tdoc_id\trelevance\nq1\td1\t1\n", encoding="utf-8")

    monkeypatch.setattr(benchmark_es, "_load_ir_dataset", lambda dataset_id: (_ for _ in ()).throw(AssertionError("should not load ir_datasets")))

    class FakeRetriever:
        def search(self, query, method, top_k, **kwargs):
            assert method == "tv_dense"
            return [{"doc_id": "d1", "score": 1.0}]

    monkeypatch.setattr(benchmark_es, "build_retriever", lambda *args, **kwargs: FakeRetriever())

    result = benchmark_es.run_benchmark(
        dataset_id="dataset",
        index="idx",
        methods=["tv_dense"],
        top_k=10,
        max_queries=None,
        url="http://localhost:9200",
        model_name="model",
        num_candidates=100,
        candidate_k=20,
        rrf_k=7,
        first_hop_k=5,
        second_hop_k=10,
        context_chars=256,
        run_dir=tmp_path,
        query_file=query_file,
        qrels_file=qrels_file,
    )

    assert result["config"]["queries"] == 1
    assert result["results"][0]["metrics"]["recall@10"] == 1.0

def test_run_benchmark_dispatches_tv_two_hop_bridge_rrf(monkeypatch, tmp_path):
    calls = []

    class FakeDataset:
        def queries_iter(self):
            yield SimpleNamespace(query_id="q1", text="query")

        def qrels_iter(self):
            yield SimpleNamespace(query_id="q1", doc_id="d1", relevance=1)

    class FakeRetriever:
        def search_two_hop_bridge_rrf(self, query, top_k, hop1_top_k, hop2_top_k, beam_size, max_bridge_terms, candidate_k, rrf_k):
            calls.append(
                {
                    "query": query,
                    "top_k": top_k,
                    "hop1_top_k": hop1_top_k,
                    "hop2_top_k": hop2_top_k,
                    "beam_size": beam_size,
                    "max_bridge_terms": max_bridge_terms,
                    "candidate_k": candidate_k,
                    "rrf_k": rrf_k,
                }
            )
            return [{"doc_id": "d1", "score": 1.0, "chain_rank": 1, "chain_doc_ids": ["d1"], "hop": 1}]

    monkeypatch.setattr(benchmark_es, "_load_ir_dataset", lambda dataset_id: FakeDataset())
    monkeypatch.setattr(benchmark_es, "build_retriever", lambda *args, **kwargs: FakeRetriever())

    result = benchmark_es.run_benchmark(
        dataset_id="dataset",
        index="idx",
        methods=["tv_two_hop_bridge_rrf"],
        top_k=10,
        max_queries=None,
        url="http://localhost:9200",
        model_name="model",
        num_candidates=100,
        candidate_k=20,
        rrf_k=7,
        first_hop_k=3,
        second_hop_k=4,
        context_chars=128,
        run_dir=tmp_path,
        beam_size=2,
        max_bridge_terms=6,
    )

    assert calls == [
        {
            "query": "query",
            "top_k": 10,
            "hop1_top_k": 3,
            "hop2_top_k": 4,
            "beam_size": 2,
            "max_bridge_terms": 6,
            "candidate_k": 20,
            "rrf_k": 7,
        }
    ]
    assert result["config"]["beam_size"] == 2
    assert result["config"]["max_bridge_terms"] == 6
    assert result["results"][0]["metrics"]["chain_recall@1"] == 1.0

def test_run_benchmark_dispatches_tv_bridge_title_entities_rrf(monkeypatch, tmp_path):
    calls = []

    class FakeDataset:
        def queries_iter(self):
            yield SimpleNamespace(query_id="q1", text="query")

        def qrels_iter(self):
            yield SimpleNamespace(query_id="q1", doc_id="d1", relevance=1)

    class FakeRetriever:
        def search_bridge_title_entities_rrf(self, query, top_k, hop1_top_k, hop2_top_k, beam_size, max_bridge_terms, candidate_k, rrf_k):
            calls.append(
                {
                    "query": query,
                    "top_k": top_k,
                    "hop1_top_k": hop1_top_k,
                    "hop2_top_k": hop2_top_k,
                    "beam_size": beam_size,
                    "max_bridge_terms": max_bridge_terms,
                    "candidate_k": candidate_k,
                    "rrf_k": rrf_k,
                }
            )
            return [{"doc_id": "d1", "score": 1.0, "chain_rank": 1, "chain_doc_ids": ["d1"], "hop": 1}]

    monkeypatch.setattr(benchmark_es, "_load_ir_dataset", lambda dataset_id: FakeDataset())
    monkeypatch.setattr(benchmark_es, "build_retriever", lambda *args, **kwargs: FakeRetriever())

    result = benchmark_es.run_benchmark(
        dataset_id="dataset",
        index="idx",
        methods=["tv_bridge_title_entities_rrf"],
        top_k=10,
        max_queries=None,
        url="http://localhost:9200",
        model_name="model",
        num_candidates=100,
        candidate_k=20,
        rrf_k=7,
        first_hop_k=3,
        second_hop_k=4,
        context_chars=128,
        run_dir=tmp_path,
        beam_size=2,
        max_bridge_terms=6,
    )

    assert calls == [
        {
            "query": "query",
            "top_k": 10,
            "hop1_top_k": 3,
            "hop2_top_k": 4,
            "beam_size": 2,
            "max_bridge_terms": 6,
            "candidate_k": 20,
            "rrf_k": 7,
        }
    ]
    assert result["results"][0]["metrics"]["full_support_recall@10"] == 1.0

def test_run_benchmark_dispatches_title_aware_bm25(monkeypatch, tmp_path):
    calls = []

    class FakeDataset:
        def queries_iter(self):
            yield SimpleNamespace(query_id="q1", text="query")

        def qrels_iter(self):
            yield SimpleNamespace(query_id="q1", doc_id="d1", relevance=1)

    class FakeRetriever:
        def search(self, query, method, top_k, candidate_k=100, rrf_k=60):
            calls.append(method)
            return [{"doc_id": "d1", "score": 1.0}]

    monkeypatch.setattr(benchmark_es, "_load_ir_dataset", lambda dataset_id: FakeDataset())
    monkeypatch.setattr(benchmark_es, "build_retriever", lambda *args, **kwargs: FakeRetriever())

    result = benchmark_es.run_benchmark(
        dataset_id="dataset",
        index="idx",
        methods=["es_bm25_title"],
        top_k=10,
        max_queries=None,
        url="http://localhost:9200",
        model_name="model",
        num_candidates=100,
        candidate_k=20,
        rrf_k=7,
        first_hop_k=5,
        second_hop_k=10,
        context_chars=256,
        run_dir=tmp_path,
    )

    assert calls == ["bm25_title"]
    assert result["results"][0]["metrics"]["full_support_recall@10"] == 1.0

def test_method_mapping_accepts_tv_hybrid_rerank():
    assert benchmark_es.classify_method("tv_hybrid_rerank") == "turbovec"

def test_run_benchmark_dispatches_tv_hybrid_rerank_and_records_model(monkeypatch, tmp_path):
    calls = []

    class FakeDataset:
        def queries_iter(self):
            yield SimpleNamespace(query_id="q1", text="query")

        def qrels_iter(self):
            yield SimpleNamespace(query_id="q1", doc_id="d1", relevance=1)

    class FakeRetriever:
        def search_hybrid_rerank(self, query, top_k, candidate_k, rrf_k, reranker_model):
            calls.append(
                {
                    "query": query,
                    "top_k": top_k,
                    "candidate_k": candidate_k,
                    "rrf_k": rrf_k,
                    "reranker_model": reranker_model,
                }
            )
            return [{"doc_id": "d1", "score": 2.0, "source": "bm25+dense+rerank"}]

    monkeypatch.setattr(benchmark_es, "_load_ir_dataset", lambda dataset_id: FakeDataset())
    monkeypatch.setattr(benchmark_es, "build_retriever", lambda *args, **kwargs: FakeRetriever())

    result = benchmark_es.run_benchmark(
        dataset_id="dataset",
        index="idx",
        methods=["tv_hybrid_rerank"],
        top_k=10,
        max_queries=None,
        url="http://localhost:9200",
        model_name="model",
        num_candidates=100,
        candidate_k=25,
        rrf_k=30,
        first_hop_k=5,
        second_hop_k=10,
        context_chars=256,
        run_dir=tmp_path,
        reranker_model="fake-reranker",
    )

    assert calls == [
        {
            "query": "query",
            "top_k": 10,
            "candidate_k": 25,
            "rrf_k": 30,
            "reranker_model": "fake-reranker",
        }
    ]
    assert result["config"]["reranker_model"] == "fake-reranker"
    assert result["results"][0]["metrics"]["full_support_recall@10"] == 1.0
