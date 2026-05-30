"""Parse the official QMSum repository layout into normalized meetings/qrels."""

from __future__ import annotations

import json
from pathlib import Path


SPLITS = ("train", "val", "test")
DOMAINS = ("Academic", "Product", "Committee")


def build_domain_map(qmsum_data_dir: Path) -> dict[str, str]:
    domain_by_raw_id: dict[str, str] = {}
    for domain in DOMAINS:
        domain_dir = qmsum_data_dir / domain
        if not domain_dir.exists():
            continue
        for split in SPLITS + ("all",):
            split_dir = domain_dir / split
            if not split_dir.exists():
                continue
            for path in split_dir.glob("*.json"):
                domain_by_raw_id[path.stem] = domain.lower()
    return domain_by_raw_id


def parse_qmsum(qmsum_data_dir: Path) -> tuple[list[dict], list[dict], list[dict]]:
    """Return normalized meetings, natural-language queries, and qrels."""
    all_dir = qmsum_data_dir / "ALL"
    if not all_dir.exists():
        raise FileNotFoundError(f"QMSum ALL directory not found: {all_dir}")

    domain_by_raw_id = build_domain_map(qmsum_data_dir)
    meetings: list[dict] = []
    queries: list[dict] = []
    qrels: list[dict] = []

    for split in SPLITS:
        split_dir = all_dir / split
        if not split_dir.exists():
            raise FileNotFoundError(f"QMSum split directory not found: {split_dir}")

        for path in sorted(split_dir.glob("*.json")):
            raw_id = path.stem
            meeting_id = f"qmsum_{raw_id}"
            with path.open("r", encoding="utf-8") as f:
                raw = json.load(f)

            turns = []
            participants: list[str] = []
            seen_participants: set[str] = set()
            for turn in raw.get("meeting_transcripts", []):
                speaker = _clean_text(turn.get("speaker")) or None
                text = _clean_text(turn.get("content"))
                if not text:
                    continue
                if speaker and speaker not in seen_participants:
                    participants.append(speaker)
                    seen_participants.add(speaker)
                turns.append({
                    "speaker": speaker,
                    "speaker_agent": None,
                    "speaker_role": None,
                    "text": text,
                    "time_start": None,
                    "time_end": None,
                })

            topics = [_clean_text(t.get("topic")) for t in raw.get("topic_list", [])]
            topics = [topic for topic in topics if topic]
            domain = domain_by_raw_id.get(raw_id)
            title = f"QMSum {raw_id}"
            if topics:
                title = f"{title}: {topics[0]}"

            meetings.append({
                "meeting_id": meeting_id,
                "raw_meeting_id": raw_id,
                "source": "qmsum",
                "split": split,
                "title": title,
                "date": None,
                "start_time": None,
                "duration": None,
                "participants": participants,
                "turns": turns,
                "metadata": {
                    "domain": domain,
                    "topic": "; ".join(topics) if topics else None,
                    "topics": topics,
                    "is_derived_topic": bool(topics),
                },
            })

            query_items = []
            for idx, item in enumerate(raw.get("specific_query_list", [])):
                query_items.append(("specific", idx, item))
            for idx, item in enumerate(raw.get("general_query_list", [])):
                query_items.append(("general", idx, item))

            for query_type, idx, item in query_items:
                query_text = _clean_text(item.get("query"))
                if not query_text:
                    continue
                query_id = f"qmsum_{raw_id}_{query_type}_{idx:03d}"
                queries.append({
                    "query_id": query_id,
                    "query": query_text,
                    "source": "qmsum",
                    "meeting_id": meeting_id,
                    "raw_meeting_id": raw_id,
                    "split": split,
                    "query_type": query_type,
                    "answer": _clean_text(item.get("answer")) or None,
                    "relevant_text_span": item.get("relevant_text_span"),
                })
                qrels.append({
                    "query_id": query_id,
                    "meeting_id": meeting_id,
                    "raw_meeting_id": raw_id,
                    "relevance": 1,
                })

    return meetings, queries, qrels


def _clean_text(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())

