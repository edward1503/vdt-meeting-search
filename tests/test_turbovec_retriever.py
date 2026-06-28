from __future__ import annotations

import numpy as np

from src.retrieval.turbovec_retriever import ElasticsearchNumericDocStore
from src.retrieval.turbovec_retriever import TurboVecHybridRetriever


def test_numeric_docstore_hydration_includes_metadata_fields():
    captured = {}

    class FakeES:
        def search(self, index, body):
            captured['index'] = index
            captured['body'] = body
            return {
                'hits': {
                    'hits': [
                        {
                            '_id': 'd1',
                            '_source': {
                                'numeric_id': 1,
                                'doc_id': 'd1',
                                'title': 'T',
                                'text': 'Body',
                                'url': '',
                                'author': 'Nguyen An',
                                'created_at': '2024-01-01',
                                'modified_at': '2024-01-02',
                            },
                        }
                    ]
                }
            }

    docstore = ElasticsearchNumericDocStore(FakeES(), 'idx')

    docs = docstore.hydrate_by_numeric_ids([1])

    assert {'author', 'created_at', 'modified_at'}.issubset(set(captured['body']['_source']))
    assert docs[0]['author'] == 'Nguyen An'
    assert docs[0]['created_at'] == '2024-01-01'
    assert docs[0]['modified_at'] == '2024-01-02'


def test_tv_filtered_hybrid_passes_metadata_filters_to_bm25():
    captured = {}

    class FakeESRetriever:
        def search(self, query, method, top_k, candidate_k=100, rrf_k=60, metadata_filters=None):
            captured['metadata_filters'] = metadata_filters
            return [{'doc_id': 'd1', 'numeric_id': 1, 'title': 'A', 'source': 'bm25'}]

    class FakeTVIndex:
        def search(self, queries, k, allowlist=None):
            return np.array([[0.9]], dtype=np.float32), np.array([[1]], dtype=np.uint64)

    class FakeEmbedder:
        def encode(self, texts, normalize_embeddings, convert_to_numpy):
            return np.array([[1.0, 0.0]], dtype=np.float32)

    class FakeDocStore:
        def hydrate_by_numeric_ids(self, numeric_ids):
            return [{'doc_id': 'd1', 'numeric_id': 1, 'title': 'A'}]

    retriever = TurboVecHybridRetriever(
        bm25_retriever=FakeESRetriever(),
        tv_index=FakeTVIndex(),
        embedder=FakeEmbedder(),
        docstore=FakeDocStore(),
    )

    retriever.search(
        'query',
        method='tv_filtered_hybrid',
        top_k=1,
        bm25_k=5,
        dense_k=5,
        metadata_filters={'author': 'Nguyen An'},
    )

    assert captured['metadata_filters'] == {'author': 'Nguyen An'}


def test_tv_filtered_hybrid_with_metadata_filters_returns_empty_when_allowlist_is_empty():
    class FakeESRetriever:
        def search(self, query, method, top_k, candidate_k=100, rrf_k=60, metadata_filters=None):
            return [{'doc_id': 'd1', 'title': 'A', 'source': 'bm25'}]

    class FakeTVIndex:
        def search(self, queries, k, allowlist=None):
            raise AssertionError('dense search should not run when metadata-filtered allowlist is empty')

    retriever = TurboVecHybridRetriever(
        bm25_retriever=FakeESRetriever(),
        tv_index=FakeTVIndex(),
        embedder=object(),
        docstore=object(),
    )

    hits = retriever.search(
        'query',
        method='tv_filtered_hybrid',
        top_k=2,
        bm25_k=2,
        dense_k=5,
        metadata_filters={'author': 'Nguyen An'},
    )

    assert hits == []


def test_tv_hybrid_fuses_bm25_and_dense_and_preserves_hydrated_order():
    class FakeESRetriever:
        def search(self, query, method, top_k, candidate_k=100, rrf_k=60):
            assert method == "bm25"
            return [
                {"doc_id": "d1", "numeric_id": 1, "title": "A", "source": "bm25"},
                {"doc_id": "d2", "numeric_id": 2, "title": "B", "source": "bm25"},
            ]

    class FakeTVIndex:
        def search(self, queries, k, allowlist=None):
            assert queries.shape == (1, 2)
            return np.array([[0.9, 0.8]], dtype=np.float32), np.array([[2, 3]], dtype=np.uint64)

    class FakeEmbedder:
        def encode(self, texts, normalize_embeddings, convert_to_numpy):
            assert texts == ["query"]
            return np.array([[1.0, 0.0]], dtype=np.float32)

    class FakeDocStore:
        def hydrate_by_numeric_ids(self, numeric_ids):
            docs = {
                2: {"doc_id": "d2", "numeric_id": 2, "title": "B"},
                3: {"doc_id": "d3", "numeric_id": 3, "title": "C"},
                1: {"doc_id": "d1", "numeric_id": 1, "title": "A"},
            }
            return [docs[int(numeric_id)] for numeric_id in numeric_ids]

    retriever = TurboVecHybridRetriever(
        bm25_retriever=FakeESRetriever(),
        tv_index=FakeTVIndex(),
        embedder=FakeEmbedder(),
        docstore=FakeDocStore(),
    )

    hits = retriever.search("query", method="tv_hybrid", top_k=2, bm25_k=2, dense_k=2, rrf_k=30)

    assert [hit["doc_id"] for hit in hits] == ["d2", "d1"]
    assert hits[0]["source"] == "bm25+dense"

def test_tv_hybrid_rerank_reuses_cached_reranker_for_same_model(monkeypatch):
    constructed = []

    class FakeESRetriever:
        def search(self, query, method, top_k, candidate_k=100, rrf_k=60):
            assert method == "bm25"
            return [{"doc_id": "d1", "title": "BM25", "text": "text", "score": 1.0, "source": "bm25"}]

    class FakeReranker:
        def __init__(self, model_name):
            constructed.append(model_name)

        def predict(self, pairs):
            return [2.0 for _ in pairs]

    retriever = TurboVecHybridRetriever(
        bm25_retriever=FakeESRetriever(),
        tv_index=object(),
        embedder=object(),
        docstore=object(),
    )
    monkeypatch.setattr("src.retrieval.turbovec_retriever.CrossEncoderReranker", FakeReranker)
    monkeypatch.setattr(
        retriever,
        "_search_dense",
        lambda query, top_k: [{"doc_id": "d2", "title": "Dense", "text": "text", "score": 0.9, "source": "dense"}],
    )

    retriever.search_hybrid_rerank("query", top_k=1, candidate_k=2, reranker_model="fake-model")
    retriever.search_hybrid_rerank("query", top_k=1, candidate_k=2, reranker_model="fake-model")

    assert constructed == ["fake-model"]

def test_tv_filtered_hybrid_uses_bm25_numeric_ids_as_turbovec_allowlist():
    calls = []

    class FakeESRetriever:
        def search(self, query, method, top_k, candidate_k=100, rrf_k=60):
            assert query == "query"
            assert method == "bm25"
            assert top_k == 4
            return [
                {"doc_id": "d2", "numeric_id": 2, "title": "B", "source": "bm25"},
                {"doc_id": "d1", "numeric_id": 1, "title": "A", "source": "bm25"},
                {"doc_id": "missing-id", "title": "Missing", "source": "bm25"},
                {"doc_id": "d2-duplicate", "numeric_id": 2, "title": "Dup", "source": "bm25"},
            ]

    class FakeTVIndex:
        def search(self, queries, k, allowlist=None):
            calls.append({"k": k, "allowlist": allowlist})
            assert queries.shape == (1, 2)
            return np.array([[0.9, 0.8]], dtype=np.float32), np.array([[2, 1]], dtype=np.uint64)

    class FakeEmbedder:
        def encode(self, texts, normalize_embeddings, convert_to_numpy):
            assert texts == ["query"]
            assert normalize_embeddings is True
            assert convert_to_numpy is True
            return np.array([[1.0, 0.0]], dtype=np.float32)

    class FakeDocStore:
        def hydrate_by_numeric_ids(self, numeric_ids):
            docs = {
                1: {"doc_id": "d1", "numeric_id": 1, "title": "A"},
                2: {"doc_id": "d2", "numeric_id": 2, "title": "B"},
            }
            return [docs[int(numeric_id)] for numeric_id in numeric_ids]

    retriever = TurboVecHybridRetriever(
        bm25_retriever=FakeESRetriever(),
        tv_index=FakeTVIndex(),
        embedder=FakeEmbedder(),
        docstore=FakeDocStore(),
    )

    hits = retriever.search("query", method="tv_filtered_hybrid", top_k=2, bm25_k=4, dense_k=10, rrf_k=30)

    assert calls[0]["k"] == 2
    assert calls[0]["allowlist"].dtype == np.uint64
    assert calls[0]["allowlist"].tolist() == [2, 1]
    assert [hit["doc_id"] for hit in hits] == ["d2", "d1"]
    assert hits[0]["source"] == "bm25+dense"
    assert "allowlist" in retriever.last_timing_ms

def test_tv_filtered_hybrid_falls_back_to_broad_dense_when_allowlist_is_empty():
    calls = []

    class FakeESRetriever:
        def search(self, query, method, top_k, candidate_k=100, rrf_k=60):
            return [
                {"doc_id": "d1", "title": "A", "source": "bm25"},
                {"doc_id": "d2", "numeric_id": None, "title": "B", "source": "bm25"},
            ]

    class FakeTVIndex:
        def search(self, queries, k, allowlist=None):
            calls.append({"k": k, "allowlist": allowlist})
            return np.array([[0.7]], dtype=np.float32), np.array([[3]], dtype=np.uint64)

    class FakeEmbedder:
        def encode(self, texts, normalize_embeddings, convert_to_numpy):
            return np.array([[1.0, 0.0]], dtype=np.float32)

    class FakeDocStore:
        def hydrate_by_numeric_ids(self, numeric_ids):
            return [{"doc_id": "d3", "numeric_id": 3, "title": "C"}]

    retriever = TurboVecHybridRetriever(
        bm25_retriever=FakeESRetriever(),
        tv_index=FakeTVIndex(),
        embedder=FakeEmbedder(),
        docstore=FakeDocStore(),
    )

    hits = retriever.search("query", method="tv_filtered_hybrid", top_k=2, bm25_k=2, dense_k=5, rrf_k=30)

    assert calls == [{"k": 5, "allowlist": None}]
    assert [hit["doc_id"] for hit in hits] == ["d1", "d3"]

def test_remote_embedding_client_returns_2d_float32_vector(monkeypatch):
    from src.retrieval.turbovec_retriever import RemoteEmbeddingClient

    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"embedding":[0.25,0.75]}'

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["body"] = req.data
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("src.retrieval.turbovec_retriever.request.urlopen", fake_urlopen)

    client = RemoteEmbeddingClient("http://embedding:8010/embed", timeout_seconds=7)
    vector = client.encode(["hello"], normalize_embeddings=True, convert_to_numpy=True)

    assert captured["url"] == "http://embedding:8010/embed"
    assert captured["body"] == b'{"text":"hello"}'
    assert captured["timeout"] == 7
    assert vector.dtype == np.float32
    assert vector.shape == (1, 2)
    assert vector.tolist() == [[0.25, 0.75]]

def test_turbovec_from_paths_uses_remote_embedder_when_url_is_configured(monkeypatch):
    import sys

    from src.retrieval import turbovec_retriever

    class FakeIdMapIndex:
        @staticmethod
        def load(path):
            return {"loaded": path}

    class FakeTurboVecModule:
        IdMapIndex = FakeIdMapIndex

    monkeypatch.setitem(sys.modules, "turbovec", FakeTurboVecModule())

    retriever = turbovec_retriever.TurboVecHybridRetriever.from_paths(
        bm25_retriever=object(),
        es=object(),
        index="hotpotqa_full_bm25_current",
        tv_index_path="/app/artifacts/hotpotqa_full/turbovec/hotpotqa_bge_small_4bit.tvim",
        model_name="BAAI/bge-small-en-v1.5",
        embedding_service_url="http://host.docker.internal:8010/embed",
        embedding_timeout_seconds=9,
    )

    assert isinstance(retriever.embedder, turbovec_retriever.RemoteEmbeddingClient)
    assert retriever.embedder.embedding_service_url == "http://host.docker.internal:8010/embed"
    assert retriever.embedder.timeout_seconds == 9

def test_elasticsearch_retriever_remote_embedding_includes_model_id(monkeypatch):
    import json

    from src.retrieval.elasticsearch_retriever import ElasticsearchRetriever

    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"embedding":[0.1,0.2,0.3]}'

    def fake_urlopen(req, timeout):
        captured["body"] = json.loads(req.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("src.retrieval.elasticsearch_retriever.request.urlopen", fake_urlopen)

    retriever = ElasticsearchRetriever(
        es=object(),
        index="vimqa_all_dense_bkai_current",
        model_name="bkai-foundation-models/vietnamese-bi-encoder",
        embedding_service_url="http://embedding:8010/embed",
        embedding_timeout_seconds=11,
        embedding_model_id="vimqa",
    )

    assert retriever._embed_query("xin chao") == [0.1, 0.2, 0.3]
    assert captured["body"] == {"text": "xin chao", "model_id": "vimqa"}
    assert captured["timeout"] == 11

def test_tv_two_hop_bridge_rrf_builds_bridge_queries_and_returns_chain_metadata(monkeypatch):
    retriever = TurboVecHybridRetriever(
        bm25_retriever=object(),
        tv_index=object(),
        embedder=object(),
        docstore=object(),
    )
    calls = []

    def fake_search(query, method, top_k, bm25_k=100, dense_k=100, rrf_k=60, candidate_k=None, **kwargs):
        calls.append({"query": query, "method": method, "top_k": top_k, "candidate_k": candidate_k, "rrf_k": rrf_k})
        if len(calls) == 1:
            return [
                {"doc_id": "bridge", "numeric_id": 1, "title": "Bridge Title", "text": "alpha beta gamma", "score": 0.9, "source": "bm25+dense"},
                {"doc_id": "other", "numeric_id": 2, "title": "Other", "text": "delta", "score": 0.8, "source": "bm25+dense"},
            ]
        return [
            {"doc_id": "answer", "numeric_id": 3, "title": "Answer", "text": "answer text", "score": 0.7, "source": "bm25+dense"},
            {"doc_id": "bridge", "numeric_id": 1, "title": "Bridge Title", "text": "duplicate", "score": 0.6, "source": "bm25+dense"},
        ]

    monkeypatch.setattr(retriever, "search", fake_search)

    hits = retriever.search_two_hop_bridge_rrf(
        "original question",
        top_k=3,
        hop1_top_k=2,
        hop2_top_k=2,
        beam_size=1,
        max_bridge_terms=2,
        candidate_k=20,
        rrf_k=30,
    )

    assert calls[0] == {"query": "original question", "method": "tv_hybrid", "top_k": 2, "candidate_k": 20, "rrf_k": 30}
    assert calls[1]["query"] == "original question Bridge Title alpha beta"
    assert [hit["doc_id"] for hit in hits[:2]] == ["bridge", "answer"]
    assert hits[0]["chain_rank"] == 1
    assert hits[0]["chain_doc_ids"] == ["bridge", "answer"]
    assert hits[1]["hop"] == 2

def test_bridge_query_terms_skip_query_terms_and_dedupe():
    retriever = TurboVecHybridRetriever(bm25_retriever=None, tv_index=None, embedder=None, docstore=None)
    hit = {"title": "Bridge Bridge Title", "text": "original alpha alpha beta gamma"}

    query = retriever._build_bridge_query("original question", hit, max_bridge_terms=3)

    assert query == "original question Bridge Bridge Title alpha beta gamma"
