"""Rule-based prompt understanding: tách prompt tự nhiên thành semantic query + filters.

Đa điều kiện theo README: chủ đề (topic, giữ trong semantic_query) + người tham gia
(speaker) + thời gian (date_range). Lọc MỀM: chỉ áp filter khi tín hiệu high-precision;
nếu không chắc, giữ nguyên prompt cho BM25 + dense và không áp hard filter.
"""

from __future__ import annotations

import re

SOURCES = ("qmsum", "ami")
# Mã speaker AMI: 3 chữ in hoa + 3 số, vd MEO069, FEO065.
_AMI_SPEAKER_RE = re.compile(r"\b([A-Z]{2,3}\d{3})\b")
# Năm 4 chữ số trong khoảng hợp lý.
_YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")
# "by <Name>" / "with <Name>" / "from <Name>" — bắt cụm tên viết hoa ngay sau giới từ.
_BY_NAME_RE = re.compile(r"\b(?:by|with|from|led by)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,2})")


def parse_prompt(prompt: str, known_speakers: set[str] | None = None) -> dict:
    """Trả về {semantic_query, filters, parsed} cho prompt tự nhiên.

    - filters chỉ chứa điều kiện high-confidence (lọc mềm).
    - semantic_query giữ phần còn lại (gồm topic) cho BM25 + dense.
    """
    text = prompt.strip()
    filters: dict = {}
    parsed: list[str] = []

    source = _match_source(text)
    if source:
        filters["source"] = source
        parsed.append(f"source={source}")

    speaker = _match_speaker(text, known_speakers)
    if speaker:
        filters["speaker"] = speaker
        parsed.append(f"speaker={speaker}")

    date_range = _match_date_range(text)
    if date_range:
        filters["date_range"] = date_range
        parsed.append(f"date={date_range[0]}..{date_range[1]}")

    return {"semantic_query": text, "filters": filters, "parsed": parsed}


def _match_source(text: str) -> str | None:
    lowered = text.lower()
    for source in SOURCES:
        if re.search(rf"\b{source}\b", lowered):
            return source
    return None


def _match_speaker(text: str, known_speakers: set[str] | None) -> str | None:
    ami = _AMI_SPEAKER_RE.search(text)
    if ami:
        return ami.group(1)
    if known_speakers:
        # Khớp tên speaker đã biết (dài nhất trước để ưu tiên tên đầy đủ).
        for name in sorted(known_speakers, key=len, reverse=True):
            if re.search(rf"\b{re.escape(name)}\b", text):
                return name
    match = _BY_NAME_RE.search(text)
    if match:
        return match.group(1)
    return None


def _match_date_range(text: str) -> list[str] | None:
    years = _YEAR_RE.findall(text)
    if not years:
        return None
    years = sorted(years)
    return [f"{years[0]}-01-01", f"{years[-1]}-12-31"]
