"""Unit tests cho rule-based prompt understanding (không cần ES/model)."""

from src.search.query_understanding import parse_prompt


def test_extracts_source_and_ami_speaker():
    out = parse_prompt("Find AMI meetings with MEO069 about interface design")
    assert out["filters"]["source"] == "ami"
    assert out["filters"]["speaker"] == "MEO069"


def test_extracts_year_date_range():
    out = parse_prompt("qmsum meetings about budget in 2005")
    assert out["filters"]["source"] == "qmsum"
    assert out["filters"]["date_range"] == ["2005-01-01", "2005-12-31"]


def test_extracts_name_after_led_by():
    out = parse_prompt("meetings led by Darren Millar about health")
    assert out["filters"]["speaker"] == "Darren Millar"


def test_soft_filter_no_match_keeps_full_query():
    out = parse_prompt("what did the team decide about the remote control?")
    assert out["filters"] == {}
    assert out["semantic_query"].startswith("what did the team")
    assert out["parsed"] == []
