"""Speaker-aware chunking for normalized meeting records."""

from __future__ import annotations

import re
from collections.abc import Iterable


TOKEN_RE = re.compile(r"\S+")


def chunk_meetings(
    meetings: Iterable[dict],
    target_tokens: int = 384,
    max_tokens: int = 512,
    overlap_tokens: int = 80,
) -> list[dict]:
    chunks: list[dict] = []
    for meeting in meetings:
        chunks.extend(_chunk_one_meeting(meeting, target_tokens, max_tokens, overlap_tokens))
    return chunks


def _chunk_one_meeting(
    meeting: dict,
    target_tokens: int,
    max_tokens: int,
    overlap_tokens: int,
) -> list[dict]:
    chunks: list[dict] = []
    current: list[dict] = []
    current_tokens = 0

    for turn in meeting.get("turns", []):
        text = (turn.get("text") or "").strip()
        if not text:
            continue
        turn_tokens = _count_tokens(text)
        if turn_tokens > max_tokens:
            if current:
                chunks.append(_build_chunk(meeting, current, len(chunks)))
                current = []
                current_tokens = 0
            for part in _split_long_turn(turn, max_tokens, overlap_tokens):
                chunks.append(_build_chunk(meeting, [part], len(chunks)))
            continue

        if current and current_tokens + turn_tokens > target_tokens:
            chunks.append(_build_chunk(meeting, current, len(chunks)))
            current = []
            current_tokens = 0

        current.append(turn)
        current_tokens += turn_tokens

    if current:
        chunks.append(_build_chunk(meeting, current, len(chunks)))

    return chunks


def _split_long_turn(turn: dict, max_tokens: int, overlap_tokens: int) -> list[dict]:
    tokens = TOKEN_RE.findall(turn.get("text") or "")
    parts: list[dict] = []
    step = max(1, max_tokens - overlap_tokens)
    for start in range(0, len(tokens), step):
        part_tokens = tokens[start:start + max_tokens]
        if not part_tokens:
            continue
        part = dict(turn)
        part["text"] = " ".join(part_tokens)
        parts.append(part)
        if start + max_tokens >= len(tokens):
            break
    return parts


def _build_chunk(meeting: dict, turns: list[dict], index: int) -> dict:
    meeting_id = meeting["meeting_id"]
    speakers = _unique([turn.get("speaker") for turn in turns if turn.get("speaker")])
    speaker_agents = _unique([turn.get("speaker_agent") for turn in turns if turn.get("speaker_agent")])
    speaker_roles = _unique([turn.get("speaker_role") for turn in turns if turn.get("speaker_role")])
    text_parts = []
    for turn in turns:
        speaker = turn.get("speaker")
        text = (turn.get("text") or "").strip()
        text_parts.append(f"{speaker}: {text}" if speaker else text)
    text = " ".join(text_parts)
    time_starts = [turn.get("time_start") for turn in turns if turn.get("time_start") is not None]
    time_ends = [turn.get("time_end") for turn in turns if turn.get("time_end") is not None]
    raw_meeting_id = meeting.get("raw_meeting_id")
    metadata_text = _metadata_text(meeting, speakers, speaker_roles)
    return {
        "chunk_id": f"{meeting_id}_{index:05d}",
        "meeting_id": meeting_id,
        "raw_meeting_id": raw_meeting_id,
        "source": meeting.get("source"),
        "split": meeting.get("split"),
        "title": meeting.get("title"),
        "date": meeting.get("date"),
        "start_time": meeting.get("start_time"),
        "text": text,
        "content_text": text,
        "metadata_text": metadata_text,
        "speakers": speakers,
        "speaker_agents": speaker_agents,
        "speaker_roles": speaker_roles,
        "time_start": min(time_starts) if time_starts else None,
        "time_end": max(time_ends) if time_ends else None,
        "token_count": _count_tokens(text),
    }


def _metadata_text(meeting: dict, speakers: list[str], roles: list[str]) -> str:
    metadata = meeting.get("metadata") or {}
    parts = [
        f"source: {meeting.get('source')}",
        f"meeting: {meeting.get('raw_meeting_id')}",
        f"title: {meeting.get('title')}",
    ]
    if meeting.get("date"):
        parts.append(f"date: {meeting.get('date')}")
    if speakers:
        parts.append(f"speakers: {' '.join(speakers)}")
    if roles:
        parts.append(f"roles: {' '.join(roles)}")
    if metadata.get("domain"):
        parts.append(f"domain: {metadata.get('domain')}")
    if metadata.get("topic"):
        parts.append(f"topic: {metadata.get('topic')}")
    return " ".join(part for part in parts if part and "None" not in part)


def _count_tokens(text: str) -> int:
    return len(TOKEN_RE.findall(text))


def _unique(values: list[str]) -> list[str]:
    seen = set()
    out = []
    for value in values:
        if value not in seen:
            out.append(value)
            seen.add(value)
    return out

