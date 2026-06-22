from __future__ import annotations

import csv
import json
from pathlib import Path

from src.evaluation.openai_paraphrase_validation import validate_and_select


FIELDNAMES = [
    "variant_query_id",
    "source_query_id",
    "paraphrase_profile",
    "candidate_index",
    "original_query",
    "paraphrased_query",
    "support_doc_ids",
    "qrels",
    "model_id",
    "prompt_version",
    "generation_notes",
]


def _write_candidates(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def _row(
    source_query_id: str,
    profile: str,
    paraphrased_query: str,
    *,
    original_query: str = "What year did Apollo 11 reach the Moon?",
    variant_query_id: str | None = None,
    qrels: str = '["doc1", "doc2"]',
    support_doc_ids: str = "doc1,doc2",
) -> dict[str, str]:
    return {
        "variant_query_id": variant_query_id or f"{source_query_id}__{profile}__1",
        "source_query_id": source_query_id,
        "paraphrase_profile": profile,
        "candidate_index": "1",
        "original_query": original_query,
        "paraphrased_query": paraphrased_query,
        "support_doc_ids": support_doc_ids,
        "qrels": qrels,
        "model_id": "combo",
        "prompt_version": "test",
        "generation_notes": "test",
    }


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def test_validate_and_select_writes_accepted_rejected_summary_and_benchmark_inputs(tmp_path: Path):
    candidates = tmp_path / "candidates.tsv"
    _write_candidates(
        candidates,
        [
            _row("q1", "natural_mild", "In what year did Apollo 11 reach the Moon?"),
            _row("q1", "natural_strong", "Apollo 11 reached the Moon in what year?"),
        ],
    )

    summary = validate_and_select(candidates, tmp_path / "validated", expected_per_profile=1)

    assert summary["total"] == 2
    assert summary["accepted"] == 2
    assert summary["rejected"] == 0
    assert summary["selected_by_profile"] == {"natural_mild": 1, "natural_strong": 1}
    assert summary["missing_selection_by_profile"] == {"lexical_strong": ["q1"]}

    accepted = _read_tsv(tmp_path / "validated" / "accepted.tsv")
    assert [row["paraphrase_profile"] for row in accepted] == ["natural_mild", "natural_strong"]

    mild = _read_tsv(tmp_path / "validated" / "mild_200.tsv")
    assert mild == [
        {
            "variant_query_id": "q1__natural_mild__1",
            "source_query_id": "q1",
            "query": "In what year did Apollo 11 reach the Moon?",
        }
    ]
    regeneration_needed = _read_tsv(tmp_path / "validated" / "regeneration_needed.tsv")
    assert [(row["source_query_id"], row["paraphrase_profile"]) for row in regeneration_needed] == [
        ("q1", "lexical_strong")
    ]

    summary_file = json.loads((tmp_path / "validated" / "summary.json").read_text(encoding="utf-8"))
    assert summary_file == summary


def test_validate_and_select_rejects_invalid_rows_with_reasons(tmp_path: Path):
    candidates = tmp_path / "candidates.tsv"
    _write_candidates(
        candidates,
        [
            _row("q1", "natural_mild", ""),
            _row("q2", "natural_mild", "What year did Apollo 11 reach the Moon?"),
            _row(
                "q3",
                "natural_mild",
                "In what year did mission 12 reach orbit?",
                original_query="What year did mission 11 reach orbit?",
            ),
            _row(
                "q4",
                "natural_mild",
                "In what year did the spacecraft reach the Moon?",
                original_query="What year did Apollo reach the Moon?",
            ),
            _row("q5", "natural_mild", "In what year did Apollo 11 reach the Moon?", qrels="[]"),
            _row("q6", "natural_mild", "In what year did Apollo 11 reach the Moon?", variant_query_id="dup"),
            _row("q7", "natural_mild", "In what year did Apollo 11 reach the Moon?", variant_query_id="dup"),
            _row("q8", "natural_mild", "In what year did Apollo 11 reach the Moon?", variant_query_id="q8a"),
            _row("q8", "natural_mild", "In what year did Apollo 11 reach the Moon?", variant_query_id="q8b"),
        ],
    )

    summary = validate_and_select(candidates, tmp_path / "validated", expected_per_profile=1)

    rejected = _read_tsv(tmp_path / "validated" / "rejected.tsv")
    reasons_by_variant = {row["variant_query_id"]: row["rejection_reasons"] for row in rejected}
    assert "empty_paraphrase" in reasons_by_variant["q1__natural_mild__1"]
    assert "same_as_original" in reasons_by_variant["q2__natural_mild__1"]
    assert "number_drift" in reasons_by_variant["q3__natural_mild__1"]
    assert "entity_drift" in reasons_by_variant["q4__natural_mild__1"]
    assert "missing_qrels" in reasons_by_variant["q5__natural_mild__1"]
    assert "duplicate_variant_query_id" in reasons_by_variant["dup"]
    assert "duplicate_text_within_source_profile" in reasons_by_variant["q8b"]
    assert summary["rejected_by_reason"]["empty_paraphrase"] == 1
    assert summary["rejected_by_reason"]["same_as_original"] == 1
    assert summary["rejected_by_reason"]["number_drift"] == 1
    assert summary["rejected_by_reason"]["entity_drift"] == 1
    assert summary["rejected_by_reason"]["missing_qrels"] == 1
    assert summary["rejected_by_reason"]["duplicate_variant_query_id"] == 2
    assert summary["rejected_by_reason"]["duplicate_text_within_source_profile"] == 1
    regeneration_needed = _read_tsv(tmp_path / "validated" / "regeneration_needed.tsv")
    assert {
        (row["source_query_id"], row["paraphrase_profile"])
        for row in regeneration_needed
    } == {("q1", "natural_mild"), ("q1", "natural_strong"), ("q1", "lexical_strong")}

def test_validate_and_select_enforces_lexical_strong_content_change(tmp_path: Path):
    candidates = tmp_path / "candidates.tsv"
    original = "What company produced the show on which Cliff Clavin was a character?"
    _write_candidates(
        candidates,
        [
            _row(
                "q1",
                "lexical_strong",
                "Cliff Clavin was a character on the show that was produced by what company?",
                original_query=original,
            ),
            _row(
                "q1",
                "lexical_strong",
                "Which business created the television series featuring Cliff Clavin?",
                original_query=original,
                variant_query_id="q1__lexical_strong__2",
            ),
        ],
    )

    summary = validate_and_select(candidates, tmp_path / "validated", expected_per_profile=1)

    rejected = _read_tsv(tmp_path / "validated" / "rejected.tsv")
    rejected_reasons = {row["variant_query_id"]: row["rejection_reasons"] for row in rejected}
    assert "insufficient_lexical_change" in rejected_reasons["q1__lexical_strong__1"]

    selected = _read_tsv(tmp_path / "validated" / "lexical_strong_200.tsv")
    assert selected == [
        {
            "variant_query_id": "q1__lexical_strong__2",
            "source_query_id": "q1",
            "query": "Which business created the television series featuring Cliff Clavin?",
        }
    ]
    assert summary["selected_by_profile"] == {"lexical_strong": 1}
    assert summary["lexical_quality_by_profile"]["lexical_strong"]["median_content_change_ratio"] >= 0.15
    assert summary["lexical_quality_by_profile"]["lexical_strong"]["low_content_change_lte_0_10"] == 0

    audit = json.loads((tmp_path / "validated" / "lexical_diversity_summary.json").read_text(encoding="utf-8"))
    assert audit["lexical_strong"]["count"] == 1
    examples = _read_tsv(tmp_path / "validated" / "lexical_diversity_examples.tsv")
    assert examples[0]["profile"] == "lexical_strong"

def test_validate_and_select_allows_lexical_strong_for_entity_heavy_short_queries(tmp_path: Path):
    candidates = tmp_path / "candidates.tsv"
    _write_candidates(
        candidates,
        [
            _row(
                "q1",
                "lexical_strong",
                "What category of mixed alcoholic drinks do Tequila Sunrise and Grog belong to?",
                original_query="Tequila Sunrise and Grog, are what?",
            ),
        ],
    )

    summary = validate_and_select(candidates, tmp_path / "validated", expected_per_profile=1, profiles=("lexical_strong",))

    assert summary["selected_by_profile"] == {"lexical_strong": 1}
    assert summary["rejected"] == 0
