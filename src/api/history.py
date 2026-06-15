from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class SearchHistoryStore:
    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)

    def init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS query_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                    query TEXT NOT NULL,
                    method TEXT NOT NULL,
                    top_k INTEGER NOT NULL,
                    latency_ms REAL NOT NULL,
                    cache_hit INTEGER NOT NULL,
                    result_count INTEGER NOT NULL,
                    top_docs_json TEXT NOT NULL,
                    support_doc_ids_json TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def record_search(
        self,
        *,
        query: str,
        method: str,
        top_k: int,
        latency_ms: float,
        cache_hit: bool,
        results: list[dict[str, Any]],
        support_doc_ids: list[str],
    ) -> int:
        top_docs = [
            {
                "doc_id": str(item.get("doc_id", "")),
                "title": str(item.get("title", "")),
                "score": float(item.get("score", 0.0)),
                "rank": int(item.get("rank", index)),
            }
            for index, item in enumerate(results[:top_k], start=1)
        ]
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO query_history (
                    query, method, top_k, latency_ms, cache_hit, result_count, top_docs_json, support_doc_ids_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    query,
                    method,
                    top_k,
                    latency_ms,
                    1 if cache_hit else 0,
                    len(results),
                    json.dumps(top_docs, ensure_ascii=False),
                    json.dumps(support_doc_ids, ensure_ascii=False),
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def list_history(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM query_history
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def get_history(self, history_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM query_history WHERE id = ?", (history_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    def clear_history(self) -> int:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM query_history")
            conn.commit()
            return int(cursor.rowcount)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": int(row["id"]),
            "created_at": str(row["created_at"]),
            "query": str(row["query"]),
            "method": str(row["method"]),
            "top_k": int(row["top_k"]),
            "latency_ms": float(row["latency_ms"]),
            "cache_hit": bool(row["cache_hit"]),
            "result_count": int(row["result_count"]),
            "top_docs": json.loads(row["top_docs_json"]),
            "support_doc_ids": json.loads(row["support_doc_ids_json"]),
        }
