from __future__ import annotations

from src.retrieval.metadata_query_parser import parse_metadata_query


def test_parse_author_and_created_before_query() -> None:
    parsed = parse_metadata_query("find documents about anarchism by Nguyen An before 01/31/2024")

    assert parsed.parsed is True
    assert parsed.original_query == "find documents about anarchism by Nguyen An before 01/31/2024"
    assert parsed.content_query == "anarchism"
    assert parsed.metadata_filters == {"author": "Nguyen An", "created_at_to": "2024-01-31"}
    assert "Content: anarchism" in parsed.parsed_chips
    assert "Author: Nguyen An" in parsed.parsed_chips
    assert "Created before: 2024-01-31" in parsed.parsed_chips


def test_parse_modified_after_query() -> None:
    parsed = parse_metadata_query("documents about ozone modified after 2024-02-03")

    assert parsed.parsed is True
    assert parsed.content_query == "ozone"
    assert parsed.metadata_filters == {"modified_at_from": "2024-02-03"}
    assert "Modified after: 2024-02-03" in parsed.parsed_chips


def test_does_not_parse_original_hotpotqa_question_with_written_by() -> None:
    query = "Scarface Nation was a book written by an arts critic of what nationality?"
    parsed = parse_metadata_query(query)

    assert parsed.parsed is False
    assert parsed.content_query == query
    assert parsed.metadata_filters == {}
    assert parsed.warnings


def test_manual_author_must_match_known_synthetic_author() -> None:
    parsed = parse_metadata_query("find documents about anarchism by Not A Real Author before 01/31/2024")

    assert parsed.parsed is True
    assert parsed.content_query == "anarchism"
    assert parsed.metadata_filters == {"created_at_to": "2024-01-31"}
    assert any("author" in warning.lower() for warning in parsed.warnings)

def test_parse_vietnamese_author_and_created_before_query() -> None:
    parsed = parse_metadata_query("tài liệu về lịch sử Việt Nam của Nguyen An trước 31/01/2024")

    assert parsed.parsed is True
    assert parsed.content_query == "lịch sử Việt Nam"
    assert parsed.metadata_filters == {"author": "Nguyen An", "created_at_to": "2024-01-31"}
    assert "Content: lịch sử Việt Nam" in parsed.parsed_chips
    assert "Author: Nguyen An" in parsed.parsed_chips
    assert "Created before: 2024-01-31" in parsed.parsed_chips

def test_parse_vietnamese_modified_after_query() -> None:
    parsed = parse_metadata_query("văn bản về giáo dục bởi Tran Minh chỉnh sửa sau 2024-02-03")

    assert parsed.parsed is True
    assert parsed.content_query == "giáo dục"
    assert parsed.metadata_filters == {"author": "Tran Minh", "modified_at_from": "2024-02-03"}
    assert "Author: Tran Minh" in parsed.parsed_chips
    assert "Modified after: 2024-02-03" in parsed.parsed_chips
