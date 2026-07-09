from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from src.data.synthetic_metadata import DISPLAY_AUTHORS


@dataclass(frozen=True)
class ParsedMetadataQuery:
    original_query: str
    content_query: str
    metadata_filters: dict[str, str] = field(default_factory=dict)
    parsed_chips: list[str] = field(default_factory=list)
    parsed: bool = False
    parser: str = "rule_based"
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


SEMANTIC_PREFIX_RE = re.compile(
    r"^\s*(?:(?:find|search|get|show)?\s*(?:all\s+)?(?:documents?|docs?)\s+(?:related\s+to|about)|(?:tài\s+liệu|văn\s+bản)\s+về)\s+",
    re.IGNORECASE,
)
DATE_RE = r"(\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2})"
AUTHOR_CUE_RE = re.compile(r"\b(?:written\s+by|authored\s+by|by|của|bởi)\b", re.IGNORECASE)


def parse_metadata_query(query: str) -> ParsedMetadataQuery:
    original = query.strip()
    if not SEMANTIC_PREFIX_RE.search(original):
        return ParsedMetadataQuery(
            original_query=original,
            content_query=original,
            warnings=["No explicit semantic metadata search pattern found."],
        )

    body = SEMANTIC_PREFIX_RE.sub("", original, count=1).strip()
    filters: dict[str, str] = {}
    warnings: list[str] = []
    chips: list[str] = []

    body, date_chips = _extract_dates(body, filters, warnings)
    chips.extend(date_chips)
    body, author, saw_author_cue = _extract_author(body)
    if author:
        filters["author"] = author
        chips.append(f"Author: {author}")
    elif saw_author_cue:
        warnings.append("Author phrase was present but did not match known synthetic authors.")
        body = _remove_unknown_author_phrase(body)

    content_query = _clean_content_query(body)
    if content_query:
        chips.insert(0, f"Content: {content_query}")
    else:
        content_query = original
        warnings.append("Parsed metadata but could not extract a stable content query; using original query.")

    return ParsedMetadataQuery(
        original_query=original,
        content_query=content_query,
        metadata_filters=filters,
        parsed_chips=chips,
        parsed=bool(filters or content_query != original),
        warnings=warnings,
    )


def _extract_dates(body: str, filters: dict[str, str], warnings: list[str]) -> tuple[str, list[str]]:
    chips: list[str] = []
    patterns = [
        (rf"\bcreated\s+before\s+{DATE_RE}", "created_at_to", "Created before"),
        (rf"\bcreated\s+after\s+{DATE_RE}", "created_at_from", "Created after"),
        (rf"\bmodified\s+before\s+{DATE_RE}", "modified_at_to", "Modified before"),
        (rf"\bmodified\s+after\s+{DATE_RE}", "modified_at_from", "Modified after"),
        (rf"\bchỉnh\s+sửa\s+trước\s+{DATE_RE}", "modified_at_to", "Modified before"),
        (rf"\bchỉnh\s+sửa\s+sau\s+{DATE_RE}", "modified_at_from", "Modified after"),
        (rf"\bbefore\s+{DATE_RE}", "created_at_to", "Created before"),
        (rf"\bafter\s+{DATE_RE}", "created_at_from", "Created after"),
        (rf"\btrước\s+{DATE_RE}", "created_at_to", "Created before"),
        (rf"\bsau\s+{DATE_RE}", "created_at_from", "Created after"),
    ]
    for pattern, field, label in patterns:
        match = re.search(pattern, body, flags=re.IGNORECASE)
        if not match:
            continue
        try:
            value = _normalize_date(match.group(1))
        except ValueError as exc:
            warnings.append(str(exc))
            continue
        filters[field] = value
        chips.append(f"{label}: {value}")
        body = f"{body[:match.start()]} {body[match.end():]}"
    return body, chips


def _extract_author(body: str) -> tuple[str, str | None, bool]:
    cue_match = AUTHOR_CUE_RE.search(body)
    if not cue_match:
        return body, None, False

    candidate_region = body[cue_match.start() :]
    for author in sorted(DISPLAY_AUTHORS, key=len, reverse=True):
        match = re.search(rf"\b{re.escape(author)}\b", candidate_region, flags=re.IGNORECASE)
        if match:
            absolute_end = cue_match.start() + match.end()
            return f"{body[: cue_match.start()]} {body[absolute_end:]}", author, True
    return body, None, True


def _remove_unknown_author_phrase(body: str) -> str:
    match = AUTHOR_CUE_RE.search(body)
    if not match:
        return body
    return body[: match.start()]


def _normalize_date(value: str) -> str:
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"Unsupported date format: {value}")


def _clean_content_query(value: str) -> str:
    return " ".join(value.replace("?", " ").split()).strip(" ,.;:")
