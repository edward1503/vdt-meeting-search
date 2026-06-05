from __future__ import annotations

from typing import Any


def chunk_meetings(
    meetings: list[dict[str, Any]],
    chunk_size_words: int = 260,
    overlap_words: int = 60,
) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    step = max(1, chunk_size_words - overlap_words)
    for meeting in meetings:
        words: list[str] = []
        speakers: set[str] = set()
        start_time: float | None = None
        end_time: float | None = None
        for turn in meeting.get("turns", []):
            text = " ".join(str(turn.get("text") or "").split())
            if not text:
                continue
            speaker = str(turn.get("speaker") or turn.get("speaker_role") or "Unknown")
            if start_time is None:
                start_time = turn.get("time_start")
            end_time = turn.get("time_end") or end_time
            speakers.add(speaker)
            words.extend(f"{speaker}: {text}".split())

        for chunk_no, start in enumerate(range(0, len(words), step)):
            chunk_words = words[start : start + chunk_size_words]
            if not chunk_words:
                continue
            chunks.append(_make_chunk(meeting, chunk_no, chunk_words, speakers, start_time, end_time))
            if start + chunk_size_words >= len(words):
                break
    return chunks


def _make_chunk(
    meeting: dict[str, Any],
    chunk_no: int,
    words: list[str],
    speakers: set[str],
    start_time: float | None,
    end_time: float | None,
) -> dict[str, Any]:
    meeting_id = str(meeting["meeting_id"])
    return {
        "chunk_id": f"{meeting_id}::chunk_{chunk_no:04d}",
        "meeting_id": meeting_id,
        "title": meeting.get("title"),
        "date": meeting.get("date"),
        "participants": meeting.get("participants", []),
        "speakers": sorted(speakers),
        "time_start": start_time,
        "time_end": end_time,
        "text": " ".join(words),
        "source": meeting.get("source"),
        "metadata": meeting.get("metadata", {}),
    }

