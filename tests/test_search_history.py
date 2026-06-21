from pathlib import Path

from src.api.history import SearchHistoryStore


def test_search_history_store_records_lists_and_clears(tmp_path: Path) -> None:
    store = SearchHistoryStore(tmp_path / "history.sqlite3")
    store.init_db()

    first_id = store.record_search(
        query="Who wrote Hamlet?",
        method="es_bm25",
        top_k=5,
        latency_ms=12.5,
        cache_hit=False,
        results=[
            {"doc_id": "d1", "title": "Hamlet", "score": 2.5, "rank": 1},
            {"doc_id": "d2", "title": "William Shakespeare", "score": 1.5, "rank": 2},
        ],
        support_doc_ids=["d2"],
    )
    second_id = store.record_search(
        query="What is Paris?",
        method="tv_hybrid",
        top_k=10,
        latency_ms=33.2,
        cache_hit=True,
        results=[{"doc_id": "d3", "title": "Paris", "score": 3.5, "rank": 1}],
        support_doc_ids=[],
    )

    rows = store.list_history(limit=10)

    assert [row["id"] for row in rows] == [second_id, first_id]
    assert rows[0]["query"] == "What is Paris?"
    assert rows[0]["method"] == "tv_hybrid"
    assert rows[0]["top_k"] == 10
    assert rows[0]["result_count"] == 1
    assert rows[0]["top_docs"] == [{"doc_id": "d3", "title": "Paris", "score": 3.5, "rank": 1}]
    assert rows[1]["support_doc_ids"] == ["d2"]

    detail = store.get_history(first_id)
    assert detail is not None
    assert detail["query"] == "Who wrote Hamlet?"

    assert store.clear_history() == 2
    assert store.list_history(limit=10) == []


def test_history_store_records_dataset_id(tmp_path: Path) -> None:
    store = SearchHistoryStore(tmp_path / "history.sqlite3")
    store.init_db()

    history_id = store.record_search(
        dataset_id="vimqa",
        query="Hà Nội là thủ đô của nước nào?",
        method="es_bm25",
        top_k=10,
        latency_ms=12.5,
        cache_hit=False,
        results=[{"doc_id": "vimqa_ctx_1", "title": "VimQA context", "score": 1.0, "rank": 1}],
        support_doc_ids=["vimqa_ctx_1"],
    )

    row = store.get_history(history_id)

    assert row is not None
    assert row["dataset_id"] == "vimqa"


def test_history_store_backfills_dataset_id_for_existing_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "history.sqlite3"
    store = SearchHistoryStore(db_path)
    store.init_db()

    with store._connect() as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(query_history)").fetchall()}

    assert "dataset_id" in columns
