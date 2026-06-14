from __future__ import annotations

from src.retrieval.elasticsearch_retriever import build_bm25_query, build_index_body, build_knn_query, bulk_action, fuse_rrf


def test_build_index_body_has_text_and_vector_fields():
    body = build_index_body(dims=384)

    assert body['settings']['refresh_interval'] == '-1'
    assert body['mappings']['properties']['doc_id']['type'] == 'keyword'
    assert body['mappings']['properties']['content']['type'] == 'text'
    assert body['mappings']['properties']['embedding'] == {
        'type': 'dense_vector',
        'dims': 384,
        'similarity': 'cosine',
    }


def test_bulk_action_uses_doc_id_as_id_and_excludes_embedding_text():
    row = {'doc_id': 'd1', 'title': 'T', 'text': 'X', 'url': '', 'content': 'T\nX', 'embedding_text': 'T\nX'}
    action = bulk_action('idx', row, [0.1, 0.2])

    assert action['_index'] == 'idx'
    assert action['_id'] == 'd1'
    assert action['doc_id'] == 'd1'
    assert action['embedding'] == [0.1, 0.2]
    assert 'embedding_text' not in action


def test_hybrid_search_accepts_rrf_k_for_fusion(monkeypatch):
    from src.retrieval.elasticsearch_retriever import ElasticsearchRetriever

    retriever = ElasticsearchRetriever(es=None, index='idx', model_name='model')
    monkeypatch.setattr(
        retriever,
        '_search_body',
        lambda body, source: [{'doc_id': 'a', 'source': source}, {'doc_id': 'b', 'source': source}],
    )
    monkeypatch.setattr(
        retriever,
        '_search_dense',
        lambda query, top_k, num_candidates: [{'doc_id': 'a', 'source': 'dense'}, {'doc_id': 'c', 'source': 'dense'}],
    )

    hits = retriever.search('query', 'hybrid', top_k=1, candidate_k=2, rrf_k=1)

    assert hits[0]['doc_id'] == 'a'
    assert hits[0]['score'] == 1.0

def test_iterative_hybrid_expands_from_first_hop_docs_and_fuses(monkeypatch):
    from src.retrieval.elasticsearch_retriever import ElasticsearchRetriever

    retriever = ElasticsearchRetriever(es=None, index='idx', model_name='model')
    calls = []

    def fake_search(query, method, top_k, candidate_k=100, rrf_k=60):
        calls.append({'query': query, 'method': method, 'top_k': top_k, 'candidate_k': candidate_k, 'rrf_k': rrf_k})
        if len(calls) == 1:
            return [
                {'doc_id': 'bridge', 'title': 'Bridge Title', 'text': 'Bridge context text', 'source': 'hybrid'},
                {'doc_id': 'other', 'title': 'Other', 'text': 'Other context', 'source': 'hybrid'},
            ]
        return [{'doc_id': 'answer', 'title': 'Answer', 'text': 'Answer context', 'source': 'hybrid'}]

    monkeypatch.setattr(retriever, 'search', fake_search)

    hits = retriever.search_iterative_hybrid(
        'original question',
        top_k=2,
        candidate_k=20,
        rrf_k=7,
        first_hop_k=2,
        second_hop_k=3,
        context_chars=12,
    )

    assert calls[0] == {'query': 'original question', 'method': 'hybrid', 'top_k': 2, 'candidate_k': 20, 'rrf_k': 7}
    assert calls[1]['query'] == 'original question Bridge Title Bridge conte'
    assert calls[1]['method'] == 'hybrid'
    assert calls[1]['top_k'] == 3
    assert [hit['doc_id'] for hit in hits] == ['answer', 'bridge']
    assert hits[0]['hop'] == 2
    assert hits[1]['hop'] == 1

def test_expand_query_title_only_uses_question_and_title():
    from src.retrieval.elasticsearch_retriever import ElasticsearchRetriever

    retriever = ElasticsearchRetriever(es=None, index='idx', model_name='model')
    hit = {'title': 'Bridge Title', 'text': 'Sentence one. Sentence two.'}

    expanded = retriever._expand_query('original question', hit, context_chars=256, expansion_mode='title')

    assert expanded == 'original question Bridge Title'

def test_expand_query_sentence_uses_best_overlap_sentence():
    from src.retrieval.elasticsearch_retriever import ElasticsearchRetriever

    retriever = ElasticsearchRetriever(es=None, index='idx', model_name='model')
    hit = {'title': 'Bridge Title', 'text': 'Unrelated opening. Ada Lovelace wrote notes about the Analytical Engine.'}

    expanded = retriever._expand_query('Who wrote notes for the Analytical Engine?', hit, context_chars=256, expansion_mode='sentence')

    assert expanded == 'Who wrote notes for the Analytical Engine? Bridge Title Ada Lovelace wrote notes about the Analytical Engine'

def test_iterative_hybrid_dedupes_hop2_docs(monkeypatch):
    from src.retrieval.elasticsearch_retriever import ElasticsearchRetriever

    retriever = ElasticsearchRetriever(es=None, index='idx', model_name='model')
    calls = []

    def fake_search(query, method, top_k, candidate_k=100, rrf_k=60):
        calls.append({'query': query, 'method': method, 'top_k': top_k})
        if len(calls) == 1:
            return [{'doc_id': 'bridge', 'title': 'Bridge', 'text': 'Bridge text', 'source': 'hybrid'}]
        return [
            {'doc_id': 'bridge', 'title': 'Bridge', 'text': 'Bridge text again', 'source': 'hybrid'},
            {'doc_id': 'answer', 'title': 'Answer', 'text': 'Answer text', 'source': 'hybrid'},
        ]

    monkeypatch.setattr(retriever, 'search', fake_search)

    hits = retriever.search_iterative_hybrid(
        'question',
        top_k=2,
        candidate_k=10,
        rrf_k=30,
        first_hop_k=1,
        second_hop_k=2,
        context_chars=256,
        expansion_mode='title',
        dedupe_hop2=True,
    )

    assert [hit['doc_id'] for hit in hits] == ['bridge', 'answer']
    assert len({hit['doc_id'] for hit in hits}) == len(hits)


def test_query_builders_and_rrf_are_stable():
    assert build_bm25_query('ada', 5)['query']['multi_match']['fields'] == ['title^2', 'content']
    assert build_knn_query([0.1, 0.2], 5, 50)['knn']['num_candidates'] == 50

    fused = fuse_rrf([[{'doc_id': 'a'}, {'doc_id': 'b'}], [{'doc_id': 'b'}, {'doc_id': 'c'}]], top_k=3)
    assert [hit['doc_id'] for hit in fused] == ['b', 'a', 'c']


def test_dense_search_uses_embedding_service_when_configured(monkeypatch):
    from io import BytesIO
    from src.retrieval import elasticsearch_retriever as module
    from src.retrieval.elasticsearch_retriever import ElasticsearchRetriever

    requests = []

    class FakeResponse:
        def __enter__(self):
            return BytesIO(b'{"embedding":[0.1,0.2,0.3]}')

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_urlopen(request, timeout):
        requests.append({"url": request.full_url, "body": request.data.decode("utf-8"), "timeout": timeout})
        return FakeResponse()

    monkeypatch.setattr(module.request, "urlopen", fake_urlopen)

    class FakeES:
        def search(self, index, body):
            assert index == "idx"
            assert body["knn"]["query_vector"] == [0.1, 0.2, 0.3]
            return {"hits": {"hits": [{"_id": "d1", "_score": 1.0, "_source": {"doc_id": "d1", "title": "T"}}]}}

    retriever = ElasticsearchRetriever(
        es=FakeES(),
        index="idx",
        model_name="model",
        embedding_service_url="http://embedding.local/embed",
    )

    hits = retriever.search("hello", "dense", top_k=1)

    assert hits[0]["doc_id"] == "d1"
    assert requests == [{"url": "http://embedding.local/embed", "body": '{"text":"hello"}', "timeout": 30}]
