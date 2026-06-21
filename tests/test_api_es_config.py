from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.core.config import Settings


def test_build_metadata_filters_omits_empty_request_fields():
    from src.api import main

    request = main.SearchRequest(
        query='Who connects Alpha and Beta?',
        author='Nguyen An',
        created_at_from='2024-01-01',
        modified_at_to='2024-02-15',
    )

    assert main.build_metadata_filters(request) == {
        'author': 'Nguyen An',
        'created_at_from': '2024-01-01',
        'modified_at_to': '2024-02-15',
    }


def test_search_cache_key_includes_metadata_filters():
    from src.api import main

    base_key = main.build_search_cache_key(index='idx', query='q', method='es_bm25', top_k=5)
    filtered_key = main.build_search_cache_key(
        index='idx',
        query='q',
        method='es_bm25',
        top_k=5,
        metadata_filters={'author': 'Nguyen An'},
    )

    assert base_key != filtered_key


def test_search_es_bm25_passes_metadata_filters_and_returns_metadata(monkeypatch):
    from src.api import main

    captured = {}

    class FakeESRetriever:
        def search(self, query, method, top_k, metadata_filters=None):
            captured['search'] = (query, method, top_k, metadata_filters)
            return [
                {
                    'doc_id': 'd1',
                    'title': 'Doc 1',
                    'text': 'body',
                    'url': '',
                    'score': 2.0,
                    'source': 'bm25',
                    'author': 'Nguyen An',
                    'created_at': '2024-01-01',
                    'modified_at': '2024-01-02',
                }
            ]

    class FakeHistoryStore:
        def record_search(self, **kwargs):
            return 321

    monkeypatch.setattr(main, 'read_search_cache', lambda cache_key: None)
    monkeypatch.setattr(main, 'write_search_cache', lambda cache_key, payload: None)
    monkeypatch.setattr(main, 'get_history_store', lambda: FakeHistoryStore())
    monkeypatch.setattr(main, 'find_support_doc_ids', lambda query, query_id=None: [])
    monkeypatch.setattr(main, 'get_es_retriever', lambda: FakeESRetriever())

    response = main.search(
        main.SearchRequest(query='Who connects Alpha and Beta?', method='es_bm25', top_k=1, author='Nguyen An')
    )

    assert captured['search'] == ('Who connects Alpha and Beta?', 'bm25', 1, {'author': 'Nguyen An'})
    assert response['metadata_filters'] == {'author': 'Nguyen An'}
    assert response['metadata_filter_scope'] == 'hard_prefilter'
    assert response['results'][0]['author'] == 'Nguyen An'
    assert response['results'][0]['created_at'] == '2024-01-01'
    assert response['results'][0]['modified_at'] == '2024-01-02'


def test_search_rejects_tv_dense_with_metadata_filters():
    from fastapi import HTTPException

    from src.api import main

    with pytest.raises(HTTPException) as exc_info:
        main.search(main.SearchRequest(query='Who connects Alpha and Beta?', method='tv_dense', top_k=1, author='Nguyen An'))

    assert exc_info.value.status_code == 400


def test_search_tv_hybrid_with_metadata_filters_routes_to_filtered_hybrid(monkeypatch):
    from src.api import main

    calls = []

    class FakeTVRetriever:
        last_timing_ms = {'bm25': 1.0, 'turbovec': 2.0, 'fusion': 3.0}

        def search(self, query, method, top_k, bm25_k=100, dense_k=100, rrf_k=60, metadata_filters=None):
            calls.append((query, method, top_k, metadata_filters))
            return [
                {
                    'doc_id': 'd1',
                    'title': 'Doc 1',
                    'text': 'body',
                    'url': '',
                    'score': 1.0,
                    'source': 'bm25+dense',
                    'author': 'Nguyen An',
                }
            ]

    class FakeHistoryStore:
        def record_search(self, **kwargs):
            return 654

    monkeypatch.setattr(main, 'read_search_cache', lambda cache_key: None)
    monkeypatch.setattr(main, 'write_search_cache', lambda cache_key, payload: None)
    monkeypatch.setattr(main, 'get_history_store', lambda: FakeHistoryStore())
    monkeypatch.setattr(main, 'find_support_doc_ids', lambda query, query_id=None: [])
    monkeypatch.setattr(main, 'get_tv_retriever', lambda: FakeTVRetriever())

    response = main.search(
        main.SearchRequest(query='Who connects Alpha and Beta?', method='tv_hybrid', top_k=1, author='Nguyen An')
    )

    assert calls == [('Who connects Alpha and Beta?', 'tv_filtered_hybrid', 1, {'author': 'Nguyen An'})]
    assert response['method'] == 'tv_filtered_hybrid'
    assert response['requested_method'] == 'tv_hybrid'
    assert response['metadata_filters'] == {'author': 'Nguyen An'}
    assert response['metadata_filter_scope'] == 'hard_prefilter'
    assert response['results'][0]['author'] == 'Nguyen An'


def test_api_exposes_only_bm25_es_method():
    from src.api import main

    assert main.ES_METHODS == {"es_bm25"}
    assert main.ES_METHOD_MAP == {"es_bm25": "bm25"}
    assert "es_bm25" in main.METHODS
    assert {"es_dense", "es_hybrid", "es_iterative_hybrid"}.isdisjoint(main.METHODS)


def test_settings_exposes_elasticsearch_defaults():
    settings = Settings()

    assert settings.dataset_id == "beir/hotpotqa/dev"
    assert settings.elasticsearch_url == "http://localhost:9200"
    assert settings.elasticsearch_index == "hotpotqa_docs_current"
    assert settings.embedding_model == "BAAI/bge-small-en-v1.5"


def test_api_uses_full_hotpotqa_query_source():
    from src.api import main

    payload = main.stats()

    assert payload["dataset_id"] == "beir/hotpotqa/dev"
    assert "nano" not in main.QUERY_EXAMPLES_PATH.name.lower()
    assert main.QUERY_EXAMPLES_PATH.exists()


def test_load_query_examples_reads_supported_doc_ids(tmp_path):
    from src.api import main

    query_file = tmp_path / "queries.tsv"
    query_file.write_text(
        "query_id\tquery\tsupport_doc_ids\n"
        "q1\tWho connects Alpha and Beta?\td1,d2\n",
        encoding="utf-8",
    )

    rows = main.load_query_examples(query_file)

    assert rows == [
        {
            "query_id": "q1",
            "query": "Who connects Alpha and Beta?",
            "support_doc_ids": ["d1", "d2"],
            "support_doc_count": 2,
        }
    ]


def test_load_query_examples_accepts_vimqa_query_tsv(tmp_path):
    from src.api import main

    query_file = tmp_path / "vimqa_queries.tsv"
    query_file.write_text(
        "query_id\tsource_query_id\tquery\tsplit\tanswer\n"
        "vimqa_test_000001\tvimqa_test_000001\tHà Nội là gì?\ttest\tthủ đô\n",
        encoding="utf-8",
    )
    qrels_file = tmp_path / "vimqa_qrels.tsv"
    qrels_file.write_text(
        "query_id\tdoc_id\trelevance\n"
        "vimqa_test_000001\tvimqa_ctx_abc\t1\n",
        encoding="utf-8",
    )

    rows = main.load_query_examples_from_files(query_file=query_file, qrels_file=qrels_file)

    assert rows == [
        {
            "query_id": "vimqa_test_000001",
            "query": "Hà Nội là gì?",
            "support_doc_ids": ["vimqa_ctx_abc"],
            "support_doc_count": 1,
            "split": "test",
            "answer": "thủ đô",
        }
    ]


def test_find_support_doc_ids_uses_dataset_profile(monkeypatch):
    from src.api import main
    from src.api.dataset_profiles import get_dataset_profile

    monkeypatch.setattr(
        main,
        "get_dataset_query_examples",
        lambda profile_id: [
            {"query_id": "vimqa_test_000001", "query": "Hà Nội là gì?", "support_doc_ids": ["vimqa_ctx_abc"]}
        ],
    )

    support = main.find_support_doc_ids_for_profile(
        get_dataset_profile("vimqa"),
        query="different text",
        query_id="vimqa_test_000001",
    )

    assert support == ["vimqa_ctx_abc"]


def test_build_query_examples_joins_queries_and_qrels():
    from src.api import main

    rows = main.build_query_examples(
        queries=[SimpleNamespace(query_id="q1", text="Question one"), SimpleNamespace(query_id="q2", text="Question two")],
        qrels=[
            SimpleNamespace(query_id="q1", doc_id="d1", relevance=1),
            SimpleNamespace(query_id="q1", doc_id="d2", relevance=1),
            SimpleNamespace(query_id="q2", doc_id="d3", relevance=0),
        ],
    )

    assert rows == [
        {"query_id": "q1", "query": "Question one", "support_doc_ids": ["d1", "d2"], "support_doc_count": 2},
        {"query_id": "q2", "query": "Question two", "support_doc_ids": [], "support_doc_count": 0},
    ]


def test_queries_endpoint_paginates_and_filters(monkeypatch):
    from src.api import main

    rows = [
        {"query_id": "q1", "query": "Alpha bridge question", "support_doc_ids": ["d1"], "support_doc_count": 1},
        {"query_id": "q2", "query": "Beta unrelated", "support_doc_ids": ["d2"], "support_doc_count": 1},
        {"query_id": "q3", "query": "Gamma alpha support", "support_doc_ids": ["d3"], "support_doc_count": 1},
    ]
    monkeypatch.setattr(main, "get_query_examples", lambda: rows)

    payload = main.queries(limit=1, offset=1, search="alpha")

    assert payload == {
        "count": 1,
        "total": 2,
        "limit": 1,
        "offset": 1,
        "queries": [rows[2]],
    }


def test_datasets_endpoint_lists_profiles():
    from src.api import main

    payload = main.datasets()

    assert payload["default_dataset_id"] == "hotpotqa"
    assert [item["id"] for item in payload["datasets"]] == ["hotpotqa", "vimqa"]


def test_dataset_stats_returns_profile_runtime_fields():
    from src.api import main

    payload = main.dataset_stats("vimqa")

    assert payload["dataset_profile"]["id"] == "vimqa"
    assert payload["dataset_id"] == "vimqa/all"
    assert payload["index"] == "vimqa_all_dense_bkai_current"
    assert payload["methods"] == ["es_bm25", "es_dense", "es_hybrid"]
    assert payload["default_search_method"] == "es_bm25"
    assert payload["primary_metric"] == "recall@10"


def test_dataset_queries_uses_profile(monkeypatch):
    from src.api import main

    monkeypatch.setattr(
        main,
        "get_dataset_query_examples",
        lambda profile_id: [
            {"query_id": "v1", "query": "Hà Nội là gì?", "support_doc_ids": ["ctx1"], "support_doc_count": 1, "answer": "thủ đô"}
        ],
    )

    payload = main.dataset_queries("vimqa", limit=10, offset=0, search="")

    assert payload["dataset_id"] == "vimqa"
    assert payload["queries"][0]["query_id"] == "v1"
    assert payload["queries"][0]["answer"] == "thủ đô"


def test_dataset_benchmarks_combines_vimqa_result_files(tmp_path, monkeypatch):
    from src.api import main
    from src.api.dataset_profiles import DatasetProfile

    bm25 = tmp_path / "bm25.json"
    dense = tmp_path / "dense.json"
    bm25.write_text(
        '{"config":{"dataset_id":"vimqa/all","queries":2},"results":[{"method":"es_bm25","metrics":{"recall@10":0.9,"mrr@10":0.8,"ndcg@10":0.85,"queries":2}}]}',
        encoding="utf-8",
    )
    dense.write_text(
        '{"config":{"dataset_id":"vimqa/all","queries":2},"results":[{"method":"es_dense","metrics":{"recall@10":0.7,"mrr@10":0.6,"ndcg@10":0.65,"queries":2}}]}',
        encoding="utf-8",
    )
    profile = DatasetProfile(
        id="vimqa",
        label="VimQA Retrieval Proxy",
        language="vi",
        task_type="single-context retrieval",
        dataset_id="vimqa/all",
        index="vimqa_all_dense_bkai_current",
        methods=("es_bm25", "es_dense"),
        default_method="es_bm25",
        dense_backend="elasticsearch_dense_vector",
        embedding_model="bkai",
        vector_dims=768,
        query_file=None,
        qrels_file=None,
        benchmark_files=(bm25, dense),
        readiness="ready",
        supports_metadata_filters=False,
        primary_metric="recall@10",
    )
    monkeypatch.setattr(main, "get_dataset_profile", lambda dataset_id: profile)

    payload = main.dataset_benchmarks("vimqa")

    assert payload["current"]["config"]["dataset_id"] == "vimqa/all"
    assert [row["method"] for row in payload["current"]["results"]] == ["es_bm25", "es_dense"]


def test_dataset_search_routes_vimqa_bm25_to_profile_index(monkeypatch):
    from src.api import main

    captured = {}

    class FakeESRetriever:
        def __init__(self, index):
            self.index = index

        def search(self, query, method, top_k, candidate_k=100, metadata_filters=None):
            captured["search"] = (self.index, query, method, top_k, metadata_filters)
            return [{"doc_id": "vimqa_ctx_1", "title": "VimQA context", "text": "body", "url": "", "score": 1.0, "source": "bm25"}]

    class FakeHistoryStore:
        def record_search(self, **kwargs):
            captured["history"] = kwargs
            return 987

    monkeypatch.setattr(main, "read_search_cache", lambda cache_key: None)
    monkeypatch.setattr(main, "write_search_cache", lambda cache_key, payload: captured.setdefault("cache_payload", payload))
    monkeypatch.setattr(main, "get_history_store", lambda: FakeHistoryStore())
    monkeypatch.setattr(main, "find_support_doc_ids_for_profile", lambda profile, query, query_id=None: ["vimqa_ctx_1"])
    monkeypatch.setattr(main, "get_es_retriever_for_profile", lambda profile_id: FakeESRetriever(main.get_dataset_profile(profile_id).index))

    response = main.dataset_search("vimqa", main.SearchRequest(query="Hà Nội là gì?", query_id="vimqa_test_000001", method="es_bm25", top_k=1))

    assert captured["search"] == ("vimqa_all_dense_bkai_current", "Hà Nội là gì?", "bm25", 1, None)
    assert captured["history"]["dataset_id"] == "vimqa"
    assert response["dataset_id"] == "vimqa"
    assert response["support"]["matched_doc_ids"] == ["vimqa_ctx_1"]


def test_dataset_search_rejects_turbovec_method_for_vimqa():
    from fastapi import HTTPException
    from src.api import main

    with pytest.raises(HTTPException) as exc_info:
        main.dataset_search("vimqa", main.SearchRequest(query="Hà Nội là gì?", method="tv_hybrid", top_k=1))

    assert exc_info.value.status_code == 400
    assert "Unknown method for dataset vimqa" in exc_info.value.detail


def test_legacy_search_delegates_to_hotpotqa(monkeypatch):
    from src.api import main

    captured = {}

    def fake_dataset_search(dataset_id, request):
        captured["dataset_id"] = dataset_id
        return {"dataset_id": dataset_id, "query": request.query, "results": []}

    monkeypatch.setattr(main, "dataset_search", fake_dataset_search)

    response = main.search(main.SearchRequest(query="Who connects Alpha and Beta?", method="es_bm25"))

    assert captured["dataset_id"] == "hotpotqa"
    assert response["dataset_id"] == "hotpotqa"

def test_find_support_doc_ids_prefers_query_id(monkeypatch):
    from src.api import main

    monkeypatch.setattr(
        main,
        "get_query_examples",
        lambda: [
            {"query_id": "q1", "query": "Original question", "support_doc_ids": ["d1", "d2"]},
            {"query_id": "q2", "query": "Question two", "support_doc_ids": ["d3"]},
        ],
    )

    assert main.find_support_doc_ids("paraphrased text", query_id="q1") == ["d1", "d2"]
    assert main.find_support_doc_ids("Question two") == ["d3"]


def test_load_benchmark_result_reads_json(tmp_path):
    from src.api import main

    result_file = tmp_path / "benchmark.json"
    result_file.write_text('{"config":{"queries":1},"results":[{"method":"es_bm25"}]}', encoding="utf-8")

    assert main.load_benchmark_result(result_file) == {
        "config": {"queries": 1},
        "results": [{"method": "es_bm25"}],
    }


def test_build_benchmark_dashboard_combines_current_and_legacy_results():
    from src.api import main

    full = {
        "config": {"dataset_id": "beir/hotpotqa/dev", "index": "hotpotqa_full_bm25_v1", "top_k": 10, "queries": 200, "methods": ["es_bm25", "tv_dense", "tv_hybrid"]},
        "results": [
            {"method": "es_bm25", "metrics": {"recall@10": 0.6, "latency_p50_ms": 100, "queries": 200}},
            {"method": "tv_dense", "metrics": {"recall@10": 0.72, "latency_p50_ms": 500, "queries": 200}},
            {"method": "tv_hybrid", "metrics": {"recall@10": 0.75, "latency_p50_ms": 1000, "queries": 200}},
        ],
    }
    filtered = {
        "config": {"dataset_id": "beir/hotpotqa/dev", "index": "hotpotqa_full_bm25_v1", "top_k": 10, "queries": 200, "methods": ["tv_filtered_hybrid"]},
        "results": [{"method": "tv_filtered_hybrid", "metrics": {"recall@10": 0.68, "latency_p50_ms": 277, "queries": 200}}],
    }
    legacy = {"config": {"dataset_id": "nano-beir/hotpotqa", "queries": 50}, "results": [{"method": "es_hybrid", "metrics": {"recall@10": 0.91}}]}

    payload = main.build_benchmark_dashboard(full, filtered, legacy)

    assert [row["method"] for row in payload["current"]["results"]] == ["es_bm25", "tv_dense", "tv_filtered_hybrid", "tv_hybrid"]
    assert payload["current"]["config"]["project_stage"] == "Sprint 3 full-corpus pilot"
    assert payload["current"]["config"]["corpus_doc_count"] == 5233329
    assert payload["current"]["config"]["paper_comparable"] is False
    assert payload["legacy"]["title"] == "Legacy Nano / Elasticsearch Benchmarks"
    assert payload["legacy"]["results"] == legacy["results"]
    assert payload["results"] == payload["current"]["results"]
def test_api_exposes_turbovec_methods_and_settings():
    from src.api import main

    settings = Settings()
    stats_methods = set(main.stats()["methods"])

    assert {"tv_dense", "tv_hybrid", "tv_filtered_hybrid"}.issubset(main.METHODS)
    assert {"es_bm25", "tv_dense", "tv_hybrid", "tv_filtered_hybrid"}.issubset(stats_methods)
    assert {"es_dense", "es_hybrid", "es_iterative_hybrid"}.isdisjoint(stats_methods)
    assert settings.default_search_method == "tv_hybrid"
    assert main.SearchRequest(query="Who connects Alpha and Beta?").method == "tv_hybrid"
    assert settings.turbovec_bit_width == 4
    assert settings.turbovec_dim == 384
    assert settings.hybrid_bm25_k == 100
    assert settings.hybrid_dense_k == 100


def test_search_rejects_legacy_es_dense_hybrid_methods():
    from fastapi import HTTPException

    from src.api import main

    for method in ["es_dense", "es_hybrid", "es_iterative_hybrid"]:
        with pytest.raises(HTTPException) as exc_info:
            main.search(main.SearchRequest(query="Who connects Alpha and Beta?", method=method, top_k=1))

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == f"Unknown method: {method}"


def test_search_routes_turbovec_methods_to_turbovec_retriever(monkeypatch):
    from src.api import main

    calls = []

    class FakeTVRetriever:
        last_timing_ms = {"embed": 1.0, "bm25": 2.0, "turbovec": 3.0, "fusion": 4.0, "hydrate": 5.0}

        def search(self, query, method, top_k, bm25_k=100, dense_k=100, rrf_k=60):
            calls.append((query, method, top_k, bm25_k, dense_k, rrf_k))
            return [
                {
                    "doc_id": "d1",
                    "title": "Doc 1",
                    "text": "body",
                    "url": "",
                    "score": 1.0,
                    "source": "bm25+dense",
                }
            ]

    class FakeHistoryStore:
        def record_search(self, **kwargs):
            return 123

    monkeypatch.setattr(main, "read_search_cache", lambda cache_key: None)
    monkeypatch.setattr(main, "write_search_cache", lambda cache_key, payload: None)
    monkeypatch.setattr(main, "get_history_store", lambda: FakeHistoryStore())
    monkeypatch.setattr(main, "find_support_doc_ids", lambda query, query_id=None: [])
    monkeypatch.setattr(main, "get_tv_retriever", lambda: FakeTVRetriever())

    response = main.search(main.SearchRequest(query="Who connects Alpha and Beta?", method="tv_hybrid", top_k=1))

    assert calls == [("Who connects Alpha and Beta?", "tv_hybrid", 1, 100, 100, 60)]
    assert response["method"] == "tv_hybrid"
    assert response["history_id"] == 123
    assert response["latency_breakdown_ms"] == {"embed": 1.0, "bm25": 2.0, "turbovec": 3.0, "fusion": 4.0, "hydrate": 5.0}
    assert response["results"][0]["source"] == "bm25+dense"


def test_search_returns_support_summary_and_marks_support_hits(monkeypatch):
    from src.api import main

    captured_history = {}

    class FakeTVRetriever:
        last_timing_ms = {"embed": 1.0, "turbovec": 2.0}

        def search(self, query, method, top_k, bm25_k=100, dense_k=100, rrf_k=60):
            return [
                {"doc_id": "d2", "title": "Support", "text": "body", "url": "", "score": 2.0, "source": "bm25+dense"},
                {"doc_id": "d9", "title": "Distractor", "text": "body", "url": "", "score": 1.0, "source": "bm25+dense"},
            ]

    class FakeHistoryStore:
        def record_search(self, **kwargs):
            captured_history.update(kwargs)
            return 456

    monkeypatch.setattr(main, "read_search_cache", lambda cache_key: None)
    monkeypatch.setattr(main, "write_search_cache", lambda cache_key, payload: None)
    monkeypatch.setattr(main, "get_history_store", lambda: FakeHistoryStore())
    monkeypatch.setattr(main, "get_tv_retriever", lambda: FakeTVRetriever())
    monkeypatch.setattr(
        main,
        "get_query_examples",
        lambda: [{"query_id": "q1", "query": "Original question", "support_doc_ids": ["d1", "d2"]}],
    )

    response = main.search(main.SearchRequest(query="paraphrased question", query_id="q1", method="tv_hybrid", top_k=2))

    assert response["query_id"] == "q1"
    assert response["support"] == {
        "available": True,
        "support_doc_ids": ["d1", "d2"],
        "matched_doc_ids": ["d2"],
        "missing_doc_ids": ["d1"],
        "matched_count": 1,
        "total_count": 2,
        "recall_at_k": 0.5,
    }
    assert [hit["is_support"] for hit in response["results"]] == [True, False]
    assert captured_history["support_doc_ids"] == ["d1", "d2"]


def test_stats_exposes_turbovec_runtime_path():
    from src.api import main

    payload = main.stats()

    assert "turbovec_index_path" in payload
    assert "default_search_method" in payload
    assert "corpus_doc_count" in payload
    assert "runtime_profile" in payload


def test_get_tv_retriever_passes_embedding_service_settings(monkeypatch):
    from src.api import main

    captured = {}

    class FakeElasticsearch:
        def __init__(self, *args, **kwargs):
            pass

    class FakeTV:
        @classmethod
        def from_paths(cls, **kwargs):
            captured.update(kwargs)
            return "tv"

    main.get_tv_retriever.cache_clear()
    monkeypatch.setattr("elasticsearch.Elasticsearch", FakeElasticsearch)
    monkeypatch.setattr(main, "TurboVecHybridRetriever", FakeTV)

    assert main.get_tv_retriever() == "tv"
    assert captured["embedding_service_url"] == main.settings.embedding_service_url
    assert captured["embedding_timeout_seconds"] == main.settings.embedding_timeout_seconds
