"""Validation checks for processed meeting-search artifacts."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from src.preprocessing.jsonl import read_jsonl


def validate_processed(out_dir: Path) -> dict:
    meetings_path = out_dir / "meetings.jsonl"
    chunks_path = out_dir / "chunks.jsonl"
    queries_path = out_dir / "qmsum_queries.jsonl"
    qrels_path = out_dir / "qrels.jsonl"
    for path in (meetings_path, chunks_path, queries_path, qrels_path):
        if not path.exists():
            raise FileNotFoundError(f"Missing processed artifact: {path}")

    meetings = list(read_jsonl(meetings_path))
    chunks = list(read_jsonl(chunks_path))
    queries = list(read_jsonl(queries_path))
    qrels = list(read_jsonl(qrels_path))

    meeting_ids = [meeting.get("meeting_id") for meeting in meetings]
    duplicates = [mid for mid, count in Counter(meeting_ids).items() if count > 1]
    if duplicates:
        raise ValueError(f"Duplicate meeting_id values: {duplicates[:10]}")
    meeting_id_set = set(meeting_ids)
    query_id_set = {query.get("query_id") for query in queries}

    for meeting in meetings:
        if not meeting.get("meeting_id") or not meeting.get("raw_meeting_id"):
            raise ValueError("Every meeting needs meeting_id and raw_meeting_id")
        if not meeting.get("source"):
            raise ValueError(f"Meeting missing source: {meeting.get('meeting_id')}")
        if not meeting.get("turns"):
            raise ValueError(f"Meeting has no turns: {meeting.get('meeting_id')}")

    for chunk in chunks:
        if not chunk.get("text"):
            raise ValueError(f"Chunk has empty text: {chunk.get('chunk_id')}")
        if chunk.get("meeting_id") not in meeting_id_set:
            raise ValueError(f"Chunk points to unknown meeting: {chunk.get('chunk_id')}")

    for qrel in qrels:
        if qrel.get("query_id") not in query_id_set:
            raise ValueError(f"Qrel points to unknown query: {qrel.get('query_id')}")
        if qrel.get("meeting_id") not in meeting_id_set:
            raise ValueError(f"Qrel points to unknown meeting: {qrel.get('meeting_id')}")

    source_counts = Counter(meeting.get("source") for meeting in meetings)
    if source_counts.get("qmsum", 0) == 0 or source_counts.get("ami", 0) == 0:
        raise ValueError("Processed meetings must include both qmsum and ami records")

    return {
        "meetings": len(meetings),
        "chunks": len(chunks),
        "queries": len(queries),
        "qrels": len(qrels),
        "sources": dict(source_counts),
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, default=Path("data/processed"))
    args = parser.parse_args()
    print(validate_processed(args.out_dir))

