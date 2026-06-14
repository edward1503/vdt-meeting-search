from __future__ import annotations

from src.core.config import Settings
from types import SimpleNamespace


def test_api_exposes_es_iterative_hybrid_method():
    from src.api import main

    assert 'es_iterative_hybrid' in main.ES_METHODS
    assert main.ES_METHOD_MAP['es_iterative_hybrid'] == 'iterative_hybrid'


def test_settings_exposes_elasticsearch_defaults():
    settings = Settings()

    assert settings.elasticsearch_url == "http://localhost:9200"
    assert settings.elasticsearch_index == "hotpotqa_docs_current"
    assert settings.embedding_model == "BAAI/bge-small-en-v1.5"

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

def test_load_benchmark_result_reads_json(tmp_path):
    from src.api import main

    result_file = tmp_path / "benchmark.json"
    result_file.write_text('{"config":{"queries":1},"results":[{"method":"es_bm25"}]}', encoding="utf-8")

    assert main.load_benchmark_result(result_file) == {
        "config": {"queries": 1},
        "results": [{"method": "es_bm25"}],
    }


def test_api_exposes_turbovec_methods_and_settings():
    from src.api import main

    settings = Settings()

    assert {"tv_dense", "tv_hybrid", "tv_filtered_hybrid"}.issubset(main.METHODS)
    assert settings.turbovec_bit_width == 4
    assert settings.turbovec_dim == 384
    assert settings.hybrid_bm25_k == 100
    assert settings.hybrid_dense_k == 100
