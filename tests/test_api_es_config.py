from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.core.config import Settings


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
