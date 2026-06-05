from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any


WORD_RANGE_RE = re.compile(r"id\(([^)]+)\)(?:\.\.id\(([^)]+)\))?")


@dataclass(frozen=True)
class WordToken:
    idx: int
    text: str
    start: float | None
    end: float | None
    is_punctuation: bool


def load_meetings(raw_dir: Path) -> list[dict[str, Any]]:
    """Load AMI XML data, falling back to simple JSON raw files for local demos."""
    ami_dir = _find_ami_dir(raw_dir)
    if ami_dir:
        return parse_ami(ami_dir)

    json_files = sorted(raw_dir.glob("*.json")) + sorted(raw_dir.glob("*.jsonl"))
    meetings: list[dict[str, Any]] = []
    for path in json_files:
        meetings.extend(_load_json_meetings(path))
    if meetings:
        return meetings

    raise FileNotFoundError(
        f"No AMI corpus or raw JSON meetings found in {raw_dir}. "
        "Place AMI folders with corpusResources/words/segments there, or use sample_meetings.json."
    )


def parse_ami(ami_dir: Path) -> list[dict[str, Any]]:
    meetings_xml = ami_dir / "corpusResources" / "meetings.xml"
    words_dir = ami_dir / "words"
    segments_dir = ami_dir / "segments"
    if not meetings_xml.exists():
        raise FileNotFoundError(f"AMI meetings.xml not found: {meetings_xml}")
    if not words_dir.exists() or not segments_dir.exists():
        raise FileNotFoundError("AMI words/segments directories are required")

    metadata = _parse_meeting_metadata(meetings_xml)
    words_by_key: dict[tuple[str, str], list[WordToken]] = {}
    for path in sorted(words_dir.glob("*.words.xml")):
        meeting_id, agent = _meeting_agent_from_name(path.name, ".words.xml")
        if meeting_id and agent:
            words_by_key[(meeting_id, agent)] = _parse_words(path)

    turns_by_meeting: dict[str, list[dict[str, Any]]] = {raw_id: [] for raw_id in metadata}
    for path in sorted(segments_dir.glob("*.segments.xml")):
        raw_id, agent = _meeting_agent_from_name(path.name, ".segments.xml")
        if not raw_id or not agent:
            continue
        words = words_by_key.get((raw_id, agent), [])
        if not words:
            continue
        speaker_meta = metadata.get(raw_id, {}).get("speakers", {}).get(agent, {})
        speaker = speaker_meta.get("global_name") or agent
        role = speaker_meta.get("role")
        for segment in _parse_segments(path, words):
            if not segment["text"]:
                continue
            turns_by_meeting.setdefault(raw_id, []).append(
                {
                    "speaker": speaker,
                    "speaker_agent": agent,
                    "speaker_role": role,
                    "text": segment["text"],
                    "time_start": segment["time_start"],
                    "time_end": segment["time_end"],
                }
            )

    meetings: list[dict[str, Any]] = []
    for raw_id, meta in sorted(metadata.items()):
        turns = sorted(
            turns_by_meeting.get(raw_id, []),
            key=lambda item: (item.get("time_start") is None, item.get("time_start") or 0.0),
        )
        if not turns:
            continue
        participants = sorted(
            {speaker.get("global_name") for speaker in meta["speakers"].values() if speaker.get("global_name")}
        )
        meetings.append(
            {
                "meeting_id": f"ami_{raw_id}",
                "raw_meeting_id": raw_id,
                "source": "ami",
                "title": f"AMI {raw_id}",
                "date": _normalize_date(meta.get("date")),
                "participants": participants,
                "turns": turns,
                "metadata": {
                    "meeting_type": meta.get("type"),
                    "visibility": meta.get("visibility"),
                    "split": meta.get("seen_type"),
                },
            }
        )
    return meetings


def _find_ami_dir(raw_dir: Path) -> Path | None:
    if not raw_dir.exists():
        return None
    data_dir = raw_dir.parent
    candidates = [
        raw_dir,
        *[path for path in raw_dir.iterdir() if path.is_dir()],
        *[path for path in data_dir.iterdir() if path.is_dir()],
    ]
    for candidate in candidates:
        if (candidate / "corpusResources" / "meetings.xml").exists():
            return candidate
    return None


def _load_json_meetings(path: Path) -> list[dict[str, Any]]:
    if path.suffix == ".jsonl":
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    else:
        data = json.loads(path.read_text(encoding="utf-8"))
        records = data if isinstance(data, list) else data.get("meetings", [])
    return [_normalize_json_meeting(record) for record in records]


def _normalize_json_meeting(record: dict[str, Any]) -> dict[str, Any]:
    turns = record.get("turns")
    if not turns:
        text = record.get("transcript") or record.get("text") or record.get("summary") or ""
        turns = [{"speaker": None, "speaker_role": None, "text": text, "time_start": None, "time_end": None}]
    meeting_id = record.get("meeting_id") or record.get("id")
    return {
        "meeting_id": str(meeting_id),
        "raw_meeting_id": record.get("raw_meeting_id") or meeting_id,
        "source": record.get("source", "json"),
        "title": record.get("title") or f"Meeting {meeting_id}",
        "date": record.get("date"),
        "participants": record.get("participants", []),
        "turns": turns,
        "metadata": record.get("metadata", {}),
    }


def _parse_meeting_metadata(path: Path) -> dict[str, dict[str, Any]]:
    root = ET.parse(path).getroot()
    meetings: dict[str, dict[str, Any]] = {}
    for meeting in root.iter():
        if _local_name(meeting.tag) != "meeting":
            continue
        raw_id = meeting.attrib.get("observation")
        if not raw_id:
            continue
        speakers: dict[str, dict[str, str | None]] = {}
        for child in meeting:
            if _local_name(child.tag) != "speaker":
                continue
            agent = child.attrib.get("nxt_agent")
            if agent:
                speakers[agent] = {
                    "global_name": child.attrib.get("global_name"),
                    "role": child.attrib.get("role"),
                    "channel": child.attrib.get("channel"),
                }
        meetings[raw_id] = {
            "date": meeting.attrib.get("dateOnly"),
            "type": meeting.attrib.get("type"),
            "visibility": meeting.attrib.get("visibility"),
            "seen_type": meeting.attrib.get("seen_type"),
            "speakers": speakers,
        }
    return meetings


def _parse_words(path: Path) -> list[WordToken]:
    root = ET.parse(path).getroot()
    words: list[WordToken] = []
    for elem in root:
        if _local_name(elem.tag) != "w":
            continue
        word_id = _nite_id(elem)
        idx = _word_index(word_id)
        text = "".join(elem.itertext()).strip()
        if idx is None or not text:
            continue
        words.append(
            WordToken(
                idx=idx,
                text=text,
                start=_to_float(elem.attrib.get("starttime")),
                end=_to_float(elem.attrib.get("endtime")),
                is_punctuation=elem.attrib.get("punc") == "true",
            )
        )
    return sorted(words, key=lambda token: token.idx)


def _parse_segments(path: Path, words: list[WordToken]) -> list[dict[str, Any]]:
    root = ET.parse(path).getroot()
    word_by_idx = {word.idx: word for word in words}
    segments: list[dict[str, Any]] = []
    for elem in root:
        if _local_name(elem.tag) != "segment":
            continue
        selected: list[WordToken] = []
        for child in elem:
            if _local_name(child.tag) != "child":
                continue
            match = WORD_RANGE_RE.search(child.attrib.get("href", ""))
            if not match:
                continue
            start_idx = _word_index(match.group(1))
            end_idx = _word_index(match.group(2) or match.group(1))
            if start_idx is None or end_idx is None:
                continue
            selected.extend(word_by_idx[idx] for idx in range(start_idx, end_idx + 1) if idx in word_by_idx)
        if selected:
            starts = [word.start for word in selected if word.start is not None]
            ends = [word.end for word in selected if word.end is not None]
            segments.append(
                {
                    "text": _join_tokens(selected),
                    "time_start": _to_float(elem.attrib.get("transcriber_start")) or (min(starts) if starts else None),
                    "time_end": _to_float(elem.attrib.get("transcriber_end")) or (max(ends) if ends else None),
                }
            )
    return segments


def _join_tokens(tokens: list[WordToken]) -> str:
    out = ""
    no_space_before = set(".,?!:;%)]}")
    no_space_after = set("([{")
    for token in tokens:
        if not out:
            out = token.text
        elif token.is_punctuation or token.text in no_space_before:
            out += token.text
        elif out[-1] in no_space_after:
            out += token.text
        else:
            out += f" {token.text}"
    return " ".join(out.split())


def _meeting_agent_from_name(name: str, suffix: str) -> tuple[str | None, str | None]:
    if not name.endswith(suffix):
        return None, None
    parts = name.removesuffix(suffix).split(".")
    return (parts[0], parts[1]) if len(parts) == 2 else (None, None)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _nite_id(elem: ET.Element) -> str | None:
    for key, value in elem.attrib.items():
        if key.endswith("}id") or key == "nite:id" or key == "id":
            return value
    return None


def _word_index(word_id: str | None) -> int | None:
    if not word_id:
        return None
    match = re.search(r"words(\d+)$", word_id)
    return int(match.group(1)) if match else None


def _normalize_date(value: str | None) -> str | None:
    if not value:
        return None
    parts = value.split("-")
    if len(parts) == 3 and len(parts[2]) == 4:
        day, month, year = parts
        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    return value


def _to_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
