from __future__ import annotations

from typing import Any

from src.api import main


def test_semantic_metadata_search_uses_effective_query_and_parsed_filters(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def fake_run_profile_search(profile, request, effective_method, metadata_filters):
        captured["query"] = request.query
        captured["effective_method"] = effective_method
        captured["metadata_filters"] = metadata_filters
        return (
            [
                {
                    "doc_id": "d1",
                    "title": "Anarchism",
                    "text": "anarchism text",
                    "url": "",
                    "score": 1.0,
                    "source": "bm25+dense",
                    "author": "Nguyen An",
                    "created_at": "2024-01-01",
                }
            ],
            None,
            12.0,
        )

    monkeypatch.setattr(main, "run_profile_search", fake_run_profile_search)
    monkeypatch.setattr(main, "read_search_cache", lambda key: None)
    monkeypatch.setattr(main, "write_search_cache", lambda key, payload: None)
    monkeypatch.setattr(main, "find_support_doc_ids", lambda query, query_id=None: [])
    monkeypatch.setattr(main.get_history_store(), "record_search", lambda **kwargs: 1)

    response = main.search(
        main.SearchRequest(
            query="find documents about anarchism by Nguyen An before 01/31/2024",
            method="tv_hybrid",
            top_k=1,
            semantic_metadata=True,
        )
    )

    assert captured["query"] == "anarchism"
    assert captured["effective_method"] == "tv_filtered_hybrid"
    assert captured["metadata_filters"] == {"author": "Nguyen An", "created_at_to": "2024-01-31"}
    assert response["query"] == "find documents about anarchism by Nguyen An before 01/31/2024"
    assert response["effective_query"] == "anarchism"
    assert response["semantic_metadata"] is True
    assert response["parsed_query"]["parsed"] is True


def test_standard_search_does_not_parse_hotpotqa_question(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def fake_run_profile_search(profile, request, effective_method, metadata_filters):
        captured["query"] = request.query
        captured["metadata_filters"] = metadata_filters
        return ([], None, 1.0)

    monkeypatch.setattr(main, "run_profile_search", fake_run_profile_search)
    monkeypatch.setattr(main, "read_search_cache", lambda key: None)
    monkeypatch.setattr(main, "write_search_cache", lambda key, payload: None)
    monkeypatch.setattr(main, "find_support_doc_ids", lambda query, query_id=None: [])
    monkeypatch.setattr(main.get_history_store(), "record_search", lambda **kwargs: 1)

    query = "Scarface Nation was a book written by an arts critic of what nationality?"
    response = main.search(main.SearchRequest(query=query, method="es_bm25", top_k=1))

    assert captured["query"] == query
    assert captured["metadata_filters"] == {}
    assert response["query"] == query
    assert response.get("parsed_query") is None


def test_manual_filters_override_parsed_filters(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def fake_run_profile_search(profile, request, effective_method, metadata_filters):
        captured["metadata_filters"] = metadata_filters
        return ([], None, 1.0)

    monkeypatch.setattr(main, "run_profile_search", fake_run_profile_search)
    monkeypatch.setattr(main, "read_search_cache", lambda key: None)
    monkeypatch.setattr(main, "write_search_cache", lambda key, payload: None)
    monkeypatch.setattr(main, "find_support_doc_ids", lambda query, query_id=None: [])
    monkeypatch.setattr(main.get_history_store(), "record_search", lambda **kwargs: 1)

    main.search(
        main.SearchRequest(
            query="find documents about anarchism by Nguyen An before 01/31/2024",
            method="es_bm25",
            top_k=1,
            semantic_metadata=True,
            author="Tran Minh",
        )
    )

    assert captured["metadata_filters"]["author"] == "Tran Minh"
    assert captured["metadata_filters"]["created_at_to"] == "2024-01-31"

def test_vimqa_semantic_metadata_search_matches_hotpotqa_execution_plan(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def fake_run_profile_search(profile, request, effective_method, metadata_filters):
        captured["dataset_id"] = profile.id
        captured["query"] = request.query
        captured["effective_method"] = effective_method
        captured["metadata_filters"] = metadata_filters
        return (
            [
                {
                    "doc_id": "vimqa_ctx_1",
                    "title": "Lịch sử Việt Nam",
                    "text": "Một đoạn văn về lịch sử Việt Nam",
                    "url": "",
                    "score": 1.0,
                    "source": "bm25",
                    "author": "Nguyen An",
                    "created_at": "2024-01-15",
                }
            ],
            None,
            8.0,
        )

    monkeypatch.setattr(main, "run_profile_search", fake_run_profile_search)
    monkeypatch.setattr(main, "read_search_cache", lambda key: None)
    monkeypatch.setattr(main, "write_search_cache", lambda key, payload: None)
    monkeypatch.setattr(main, "find_support_doc_ids_for_profile", lambda profile, query, query_id=None: [])
    monkeypatch.setattr(main.get_history_store(), "record_search", lambda **kwargs: 1)

    response = main.dataset_search(
        "vimqa",
        main.SearchRequest(
            query="tài liệu về lịch sử Việt Nam của Nguyen An trước 31/01/2024",
            method="es_bm25",
            top_k=1,
            semantic_metadata=True,
        ),
    )

    assert captured["dataset_id"] == "vimqa"
    assert captured["query"] == "lịch sử Việt Nam"
    assert captured["effective_method"] == "es_bm25"
    assert captured["metadata_filters"] == {"author": "Nguyen An", "created_at_to": "2024-01-31"}
    assert response["query"] == "tài liệu về lịch sử Việt Nam của Nguyen An trước 31/01/2024"
    assert response["effective_query"] == "lịch sử Việt Nam"
    assert response["semantic_metadata"] is True
    assert response["parsed_query"]["parsed"] is True
