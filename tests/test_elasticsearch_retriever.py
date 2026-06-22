from __future__ import annotations

from src.retrieval.elasticsearch_retriever import ElasticsearchRetriever, build_bm25_index_body, bm25_bulk_action, build_bm25_query, build_index_body, build_knn_query, bulk_action, fuse_rrf



def test_build_bm25_index_body_excludes_dense_vector_and_keeps_numeric_id():
    body = build_bm25_index_body(shards=3)

    props = body["mappings"]["properties"]
    assert props["numeric_id"] == {"type": "long"}
    assert props["doc_id"] == {"type": "keyword"}
    assert props["content"] == {"type": "text"}
    assert "embedding" not in props
    assert body["settings"]["number_of_shards"] == 3

def test_bm25_index_body_can_include_metadata_fields():
    body = build_bm25_index_body(shards=2, include_metadata=True)

    props = body["mappings"]["properties"]
    assert props["author"] == {"type": "keyword"}
    assert props["created_at"] == {"type": "date"}
    assert props["modified_at"] == {"type": "date"}
    assert props["source_split"] == {"type": "keyword"}
    assert props["answer"] == {"type": "keyword"}
    assert body["settings"]["number_of_shards"] == 2

def test_build_index_body_supports_optional_vimqa_metadata_fields():
    body = build_index_body(dims=768)
    properties = body["mappings"]["properties"]

    assert properties["source_split"] == {"type": "keyword"}
    assert properties["answer"] == {"type": "keyword"}


def test_bm25_bulk_action_uses_numeric_id_and_excludes_embedding_text():
    row = {
        "numeric_id": 7,
        "doc_id": "d7",
        "title": "T",
        "text": "X",
        "url": "",
        "content": "T\nX",
        "embedding_text": "T\nX",
    }

    action = bm25_bulk_action("idx", row)

    assert action["_index"] == "idx"
    assert action["_id"] == "d7"
    assert action["numeric_id"] == 7
    assert "embedding" not in action
    assert "embedding_text" not in action

def test_bm25_bulk_action_copies_metadata_fields_when_present():
    action = bm25_bulk_action(
        "idx",
        {
            "numeric_id": 7,
            "doc_id": "d7",
            "title": "T",
            "text": "Body",
            "url": "",
            "content": "T\nBody",
            "author": "Nguyen An",
            "created_at": "2024-01-01",
            "modified_at": "2024-01-02",
            "source_split": "train,test",
            "answer": "Hà Nội",
        },
    )

    assert action["author"] == "Nguyen An"
    assert action["created_at"] == "2024-01-01"
    assert action["modified_at"] == "2024-01-02"
    assert action["source_split"] == "train,test"
    assert action["answer"] == "Hà Nội"

def test_bulk_action_preserves_optional_vimqa_metadata_fields():
    action = bulk_action(
        "idx",
        {
            "doc_id": "vimqa_ctx_1",
            "title": "VimQA context",
            "text": "Hà Nội là thủ đô Việt Nam.",
            "content": "Hà Nội là thủ đô Việt Nam.",
            "source_split": "train,test",
            "answer": "Hà Nội",
        },
        [0.1, 0.2],
    )

    assert action["source_split"] == "train,test"
    assert action["answer"] == "Hà Nội"

def test_bm25_search_preserves_numeric_id_from_source():
    class FakeES:
        def search(self, index, body):
            assert index == "idx"
            return {
                "hits": {
                    "hits": [
                        {
                            "_id": "d7",
                            "_score": 2.5,
                            "_source": {
                                "numeric_id": 7,
                                "doc_id": "d7",
                                "title": "Title",
                                "text": "Body",
                                "url": "",
                            },
                        }
                    ]
                }
            }

    retriever = ElasticsearchRetriever(es=FakeES(), index="idx", model_name="model")

    hits = retriever.search("query", "bm25", top_k=1)

    assert hits == [
        {
            "numeric_id": 7,
            "doc_id": "d7",
            "title": "Title",
            "text": "Body",
            "url": "",
            "score": 2.5,
            "source": "bm25",
        }
    ]

def test_build_bm25_query_applies_metadata_filters_in_filter_context():
    body = build_bm25_query(
        "Arthur",
        10,
        metadata_filters={
            "author": "Nguyen An",
            "created_at_from": "2024-01-01",
            "created_at_to": "2024-01-31",
            "modified_at_from": "2024-01-01",
            "modified_at_to": "2024-02-15",
        },
    )

    assert body["query"]["bool"]["must"] == [
        {"multi_match": {"query": "Arthur", "fields": ["title^2", "content"]}}
    ]
    assert {"term": {"author": "Nguyen An"}} in body["query"]["bool"]["filter"]
    assert {"range": {"created_at": {"gte": "2024-01-01", "lte": "2024-01-31"}}} in body["query"]["bool"]["filter"]
    assert {"range": {"modified_at": {"gte": "2024-01-01", "lte": "2024-02-15"}}} in body["query"]["bool"]["filter"]
    assert {"author", "created_at", "modified_at"}.issubset(set(body["_source"]))
    assert {"source_split", "answer"}.issubset(set(body["_source"]))

def test_bm25_search_accepts_metadata_filters_and_returns_metadata_fields():
    captured = {}

    class FakeES:
        def search(self, index, body):
            captured["index"] = index
            captured["body"] = body
            return {
                "hits": {
                    "hits": [
                        {
                            "_id": "d1",
                            "_score": 2.0,
                            "_source": {
                                "numeric_id": 1,
                                "doc_id": "d1",
                                "title": "T",
                                "text": "Body",
                                "url": "",
                                "author": "Nguyen An",
                                "created_at": "2024-01-01",
                                "modified_at": "2024-01-02",
                            },
                        }
                    ]
                }
            }

    retriever = ElasticsearchRetriever(es=FakeES(), index="idx", model_name="model")

    hits = retriever.search("Arthur", "bm25", 1, metadata_filters={"author": "Nguyen An"})

    assert captured["index"] == "idx"
    assert captured["body"]["query"]["bool"]["filter"] == [{"term": {"author": "Nguyen An"}}]
    assert hits[0]["author"] == "Nguyen An"
    assert hits[0]["created_at"] == "2024-01-01"
    assert hits[0]["modified_at"] == "2024-01-02"

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

