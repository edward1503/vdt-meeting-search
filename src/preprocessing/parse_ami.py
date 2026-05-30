"""Parse AMI manual annotation XML into normalized meeting records."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


WORD_RANGE_RE = re.compile(r"id\(([^)]+)\)(?:\.\.id\(([^)]+)\))?")


@dataclass(frozen=True)
class WordToken:
    idx: int
    text: str
    start: float | None
    end: float | None
    is_punctuation: bool


def parse_ami(ami_dir: Path) -> list[dict]:
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

    turns_by_meeting: dict[str, list[dict]] = {raw_id: [] for raw_id in metadata}
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
            text = segment["text"]
            if not text:
                continue
            turns_by_meeting.setdefault(raw_id, []).append({
                "speaker": speaker,
                "speaker_agent": agent,
                "speaker_role": role,
                "text": text,
                "time_start": segment["time_start"],
                "time_end": segment["time_end"],
            })

    meetings: list[dict] = []
    for raw_id, meta in sorted(metadata.items()):
        turns = sorted(
            turns_by_meeting.get(raw_id, []),
            key=lambda item: (item.get("time_start") is None, item.get("time_start") or 0.0),
        )
        if not turns:
            continue
        participants = []
        for speaker in meta["speakers"].values():
            name = speaker.get("global_name")
            if name:
                participants.append(name)
        meetings.append({
            "meeting_id": f"ami_{raw_id}",
            "raw_meeting_id": raw_id,
            "source": "ami",
            "split": meta.get("seen_type"),
            "title": f"AMI {raw_id}",
            "date": _normalize_date(meta.get("date")),
            "start_time": _normalize_time(meta.get("start_time")),
            "duration": _to_float(meta.get("duration")),
            "participants": sorted(set(participants)),
            "turns": turns,
            "metadata": {
                "domain": "ami",
                "topic": None,
                "topics": [],
                "is_derived_topic": False,
                "meeting_type": meta.get("type"),
                "visibility": meta.get("visibility"),
            },
        })
    return meetings


def _parse_meeting_metadata(path: Path) -> dict[str, dict]:
    root = ET.parse(path).getroot()
    meetings: dict[str, dict] = {}
    for meeting in root.iter():
        if _local_name(meeting.tag) != "meeting":
            continue
        raw_id = meeting.attrib.get("observation")
        if not raw_id:
            continue
        speakers: dict[str, dict] = {}
        for child in meeting:
            if _local_name(child.tag) != "speaker":
                continue
            agent = child.attrib.get("nxt_agent")
            if not agent:
                continue
            speakers[agent] = {
                "global_name": child.attrib.get("global_name"),
                "role": child.attrib.get("role"),
                "channel": child.attrib.get("channel"),
            }
        meetings[raw_id] = {
            "date": meeting.attrib.get("dateOnly"),
            "start_time": meeting.attrib.get("startTime"),
            "duration": meeting.attrib.get("duration"),
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
        words.append(WordToken(
            idx=idx,
            text=text,
            start=_to_float(elem.attrib.get("starttime")),
            end=_to_float(elem.attrib.get("endtime")),
            is_punctuation=elem.attrib.get("punc") == "true",
        ))
    return sorted(words, key=lambda token: token.idx)


def _parse_segments(path: Path, words: list[WordToken]) -> list[dict]:
    root = ET.parse(path).getroot()
    word_by_idx = {word.idx: word for word in words}
    segments: list[dict] = []
    for elem in root:
        if _local_name(elem.tag) != "segment":
            continue
        selected: list[WordToken] = []
        for child in elem:
            if _local_name(child.tag) != "child":
                continue
            href = child.attrib.get("href", "")
            match = WORD_RANGE_RE.search(href)
            if not match:
                continue
            start_idx = _word_index(match.group(1))
            end_idx = _word_index(match.group(2) or match.group(1))
            if start_idx is None or end_idx is None:
                continue
            for idx in range(start_idx, end_idx + 1):
                word = word_by_idx.get(idx)
                if word:
                    selected.append(word)
        if not selected:
            continue
        text = _join_tokens(selected)
        start = _to_float(elem.attrib.get("transcriber_start"))
        end = _to_float(elem.attrib.get("transcriber_end"))
        if start is None:
            starts = [word.start for word in selected if word.start is not None]
            start = min(starts) if starts else None
        if end is None:
            ends = [word.end for word in selected if word.end is not None]
            end = max(ends) if ends else None
        segments.append({"text": text, "time_start": start, "time_end": end})
    return segments


def _join_tokens(tokens: list[WordToken]) -> str:
    out = ""
    no_space_before = set(".,?!:;%)]}")
    no_space_after = set("([{")
    for token in tokens:
        text = token.text
        if not out:
            out = text
        elif token.is_punctuation or text in no_space_before:
            out += text
        elif out[-1] in no_space_after:
            out += text
        else:
            out += f" {text}"
    return " ".join(out.split())


def _meeting_agent_from_name(name: str, suffix: str) -> tuple[str | None, str | None]:
    if not name.endswith(suffix):
        return None, None
    stem = name.removesuffix(suffix)
    parts = stem.split(".")
    if len(parts) != 2:
        return None, None
    return parts[0], parts[1]


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


def _normalize_time(value: str | None) -> str | None:
    if not value:
        return None
    return value.replace("h", ":")


def _to_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

