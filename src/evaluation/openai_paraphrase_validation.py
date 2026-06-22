from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REQUIRED_COLUMNS = {
    "variant_query_id",
    "source_query_id",
    "paraphrased_query",
    "paraphrase_profile",
    "original_query",
    "qrels",
}

PROFILES = ("natural_mild", "natural_strong", "lexical_strong")
PROFILE_OUTPUTS = {
    "natural_mild": "mild_200.tsv",
    "natural_strong": "strong_200.tsv",
    "lexical_strong": "lexical_strong_200.tsv",
}

LEXICAL_STRONG_MIN_CHANGE_RATIO = 0.15
LEXICAL_STRONG_MIN_NEW_CONTENT_TERMS = 2
LEXICAL_STRONG_MAX_CONTENT_JACCARD = 0.80

QUESTION_WORDS = {
    "what",
    "which",
    "who",
    "whom",
    "whose",
    "where",
    "when",
    "why",
    "how",
    "did",
    "does",
    "do",
    "is",
    "are",
    "was",
    "were",
}

CONTENT_STOPWORDS = QUESTION_WORDS | {
    "a",
    "an",
    "and",
    "as",
    "at",
    "be",
    "been",
    "being",
    "by",
    "for",
    "from",
    "had",
    "has",
    "have",
    "he",
    "her",
    "him",
    "his",
    "in",
    "into",
    "it",
    "its",
    "of",
    "on",
    "or",
    "she",
    "that",
    "the",
    "their",
    "them",
    "they",
    "this",
    "to",
    "was",
    "were",
    "while",
    "with",
}

LEADING_NON_ENTITY_WORDS = QUESTION_WORDS | {
    "among",
    "although",
    "both",
}

GENERIC_TITLE_TOKENS = {
    "American",
    "World",
    "No",
    "Open",
    "Singles",
}

ENTITY_FILLER_TOKENS = {"a", "an", "the", "s"}

TOKEN_RE = re.compile(r"[^\W_]+(?:[-'][^\W_]+)*|\d+", re.UNICODE)
NUMBER_RE = re.compile(r"\b\d+(?:[.,]\d+)?\b")


def validate_and_select(
    candidates_tsv: Path | str,
    output_dir: Path | str,
    *,
    expected_per_profile: int = 200,
    profiles: tuple[str, ...] = PROFILES,
) -> dict[str, Any]:
    candidates_path = Path(candidates_tsv)
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    rows, fieldnames = _read_rows(candidates_path)
    _validate_schema(fieldnames)

    duplicate_variant_ids = _duplicate_values(row["variant_query_id"] for row in rows)
    seen_text_by_source_profile: dict[tuple[str, str], set[str]] = defaultdict(set)

    accepted: list[dict[str, str]] = []
    rejected: list[dict[str, str]] = []
    rejected_by_reason: Counter[str] = Counter()

    for row in rows:
        reasons = _row_rejection_reasons(row, duplicate_variant_ids, seen_text_by_source_profile)
        if reasons:
            rejected_row = dict(row)
            rejected_row["rejection_reasons"] = ";".join(reasons)
            rejected.append(rejected_row)
            rejected_by_reason.update(reasons)
        else:
            accepted.append(dict(row))

    selected_by_profile_rows = _select_by_profile(accepted, profiles)
    selected_by_profile = {
        profile: len(selected_by_profile_rows.get(profile, []))
        for profile in profiles
        if selected_by_profile_rows.get(profile)
    }
    source_ids = _source_ids_in_input(rows)
    source_rows = _source_rows_by_id(rows)
    missing_selection_by_profile = _missing_selection(
        selected_by_profile_rows,
        source_ids,
        expected_per_profile,
        profiles,
    )
    regeneration_rows = _regeneration_rows(missing_selection_by_profile, source_rows)

    lexical_quality_by_profile = _lexical_quality_by_profile(selected_by_profile_rows)
    lexical_examples = _lexical_example_rows(selected_by_profile_rows)

    _write_tsv(target_dir / "accepted.tsv", accepted, fieldnames)
    _write_tsv(target_dir / "rejected.tsv", rejected, [*fieldnames, "rejection_reasons"])
    _write_tsv(
        target_dir / "lexical_diversity_examples.tsv",
        lexical_examples,
        [
            "source_query_id",
            "profile",
            "content_change_ratio",
            "content_jaccard",
            "new_content_terms",
            "removed_content_terms",
            "original_query",
            "paraphrased_query",
        ],
    )
    _write_tsv(
        target_dir / "regeneration_needed.tsv",
        regeneration_rows,
        ["source_query_id", "original_query", "support_doc_ids", "qrels", "paraphrase_profile", "constraints"],
    )
    for profile in profiles:
        _write_benchmark_input(target_dir / PROFILE_OUTPUTS.get(profile, f"{profile}.tsv"), selected_by_profile_rows.get(profile, []))

    summary: dict[str, Any] = {
        "input": str(candidates_path),
        "total": len(rows),
        "accepted": len(accepted),
        "rejected": len(rejected),
        "accepted_by_profile": dict(sorted(Counter(row["paraphrase_profile"] for row in accepted).items())),
        "selected_by_profile": selected_by_profile,
        "rejected_by_reason": dict(sorted(rejected_by_reason.items())),
        "missing_selection_by_profile": missing_selection_by_profile,
        "outputs": {
            "accepted": str(target_dir / "accepted.tsv"),
            "rejected": str(target_dir / "rejected.tsv"),
            "regeneration_needed": str(target_dir / "regeneration_needed.tsv"),
            "summary": str(target_dir / "summary.json"),
            "natural_mild": str(target_dir / "mild_200.tsv"),
            "natural_strong": str(target_dir / "strong_200.tsv"),
            "lexical_strong": str(target_dir / "lexical_strong_200.tsv"),
        },
        "lexical_quality_by_profile": lexical_quality_by_profile,
    }
    (target_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (target_dir / "lexical_diversity_summary.json").write_text(
        json.dumps(lexical_quality_by_profile, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def _read_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        fieldnames = reader.fieldnames or []
        return [dict(row) for row in reader], fieldnames


def _validate_schema(fieldnames: list[str]) -> None:
    missing = sorted(REQUIRED_COLUMNS.difference(fieldnames))
    if missing:
        raise ValueError(f"Missing required paraphrase columns: {', '.join(missing)}")


def _duplicate_values(values: Any) -> set[str]:
    counts = Counter(str(value) for value in values)
    return {value for value, count in counts.items() if count > 1}


def _row_rejection_reasons(
    row: dict[str, str],
    duplicate_variant_ids: set[str],
    seen_text_by_source_profile: dict[tuple[str, str], set[str]],
) -> list[str]:
    reasons: list[str] = []
    original = row.get("original_query", "")
    paraphrase = row.get("paraphrased_query", "")

    if not paraphrase.strip():
        reasons.append("empty_paraphrase")
    elif _normalize_text(paraphrase) == _normalize_text(original):
        reasons.append("same_as_original")

    if row.get("variant_query_id", "") in duplicate_variant_ids:
        reasons.append("duplicate_variant_query_id")

    source_profile = (row.get("source_query_id", ""), row.get("paraphrase_profile", ""))
    normalized_paraphrase = _normalize_text(paraphrase)
    if normalized_paraphrase and normalized_paraphrase in seen_text_by_source_profile[source_profile]:
        reasons.append("duplicate_text_within_source_profile")
    else:
        seen_text_by_source_profile[source_profile].add(normalized_paraphrase)

    if not _has_qrels(row.get("qrels", "")):
        reasons.append("missing_qrels")

    if paraphrase.strip() and Counter(_numbers(original)) != Counter(_numbers(paraphrase)):
        reasons.append("number_drift")

    if paraphrase.strip() and _has_entity_drift(original, paraphrase):
        reasons.append("entity_drift")

    if paraphrase.strip() and row.get("paraphrase_profile", "") == "lexical_strong":
        lexical_reasons = _lexical_strong_rejection_reasons(original, paraphrase)
        reasons.extend(lexical_reasons)

    return reasons

def _lexical_strong_rejection_reasons(original: str, paraphrase: str) -> list[str]:
    metrics = _content_change_metrics(original, paraphrase)
    reasons: list[str] = []
    if metrics["new_content_term_count"] == 0:
        reasons.append("no_new_content_terms")
    has_too_few_new_terms = metrics["new_content_term_count"] < LEXICAL_STRONG_MIN_NEW_CONTENT_TERMS
    ratio_is_meaningful = metrics["original_content_term_count"] >= LEXICAL_STRONG_MIN_NEW_CONTENT_TERMS
    has_low_change_ratio = ratio_is_meaningful and metrics["content_change_ratio"] < LEXICAL_STRONG_MIN_CHANGE_RATIO
    if has_low_change_ratio or has_too_few_new_terms:
        reasons.append("insufficient_lexical_change")
    if metrics["content_jaccard"] > LEXICAL_STRONG_MAX_CONTENT_JACCARD:
        reasons.append("high_content_overlap")
    return reasons

def _content_change_metrics(original: str, paraphrase: str) -> dict[str, Any]:
    original_terms = set(_content_terms(original, original))
    paraphrase_terms = set(_content_terms(paraphrase, original))
    new_terms = sorted(paraphrase_terms - original_terms)
    removed_terms = sorted(original_terms - paraphrase_terms)
    union = original_terms | paraphrase_terms
    intersection = original_terms & paraphrase_terms
    content_jaccard = len(intersection) / len(union) if union else 1.0
    content_change_ratio = len(new_terms) / len(original_terms) if original_terms else 0.0
    return {
        "content_change_ratio": round(content_change_ratio, 4),
        "content_jaccard": round(content_jaccard, 4),
        "new_content_terms": new_terms,
        "removed_content_terms": removed_terms,
        "new_content_term_count": len(new_terms),
        "original_content_term_count": len(original_terms),
    }

def _content_terms(text: str, original_for_entities: str) -> list[str]:
    entity_tokens = set()
    for entity in _extract_entities(original_for_entities):
        entity_tokens.update(_normalize_text(entity).split())
    terms: list[str] = []
    for token in _normalize_text(text).split():
        if not token or token in CONTENT_STOPWORDS:
            continue
        if token.isdigit() or token in entity_tokens:
            continue
        terms.append(token)
    return terms

def _lexical_quality_by_profile(rows_by_profile: dict[str, list[dict[str, str]]]) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for profile, rows in rows_by_profile.items():
        if not rows:
            continue
        metrics = [_content_change_metrics(row.get("original_query", ""), row.get("paraphrased_query", "")) for row in rows]
        change_ratios = sorted(metric["content_change_ratio"] for metric in metrics)
        jaccards = sorted(metric["content_jaccard"] for metric in metrics)
        low_change = sum(1 for metric in metrics if metric["content_change_ratio"] <= 0.10)
        no_new_terms = sum(1 for metric in metrics if metric["new_content_term_count"] == 0)
        high_jaccard = sum(1 for metric in metrics if metric["content_jaccard"] >= 0.85)
        count = len(metrics)
        summary[profile] = {
            "count": count,
            "mean_content_change_ratio": round(sum(change_ratios) / count, 4),
            "median_content_change_ratio": _median(change_ratios),
            "mean_content_jaccard": round(sum(jaccards) / count, 4),
            "median_content_jaccard": _median(jaccards),
            "low_content_change_lte_0_10": low_change,
            "low_content_change_lte_0_10_pct": round(low_change / count, 4),
            "no_new_content_terms": no_new_terms,
            "no_new_content_terms_pct": round(no_new_terms / count, 4),
            "content_jaccard_gte_0_85": high_jaccard,
            "content_jaccard_gte_0_85_pct": round(high_jaccard / count, 4),
        }
    return summary

def _lexical_example_rows(rows_by_profile: dict[str, list[dict[str, str]]]) -> list[dict[str, str]]:
    examples: list[dict[str, str]] = []
    for profile, rows in rows_by_profile.items():
        ordered = sorted(
            rows,
            key=lambda row: _content_change_metrics(row.get("original_query", ""), row.get("paraphrased_query", ""))["content_change_ratio"],
        )
        for row in ordered[:10]:
            metrics = _content_change_metrics(row.get("original_query", ""), row.get("paraphrased_query", ""))
            examples.append(
                {
                    "source_query_id": row.get("source_query_id", ""),
                    "profile": profile,
                    "content_change_ratio": f'{metrics["content_change_ratio"]:.4f}',
                    "content_jaccard": f'{metrics["content_jaccard"]:.4f}',
                    "new_content_terms": ",".join(metrics["new_content_terms"]),
                    "removed_content_terms": ",".join(metrics["removed_content_terms"]),
                    "original_query": row.get("original_query", ""),
                    "paraphrased_query": row.get("paraphrased_query", ""),
                }
            )
    return examples

def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    midpoint = len(values) // 2
    if len(values) % 2:
        return round(values[midpoint], 4)
    return round((values[midpoint - 1] + values[midpoint]) / 2, 4)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", text.lower(), flags=re.UNICODE)).strip()


def _numbers(text: str) -> list[str]:
    return [match.replace(",", "") for match in NUMBER_RE.findall(text)]


def _has_qrels(value: str) -> bool:
    text = value.strip()
    if not text:
        return False
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return text not in {"[]", "{}"}
    if isinstance(parsed, dict):
        return bool(parsed)
    if isinstance(parsed, list):
        return bool(parsed)
    return bool(parsed)


def _has_entity_drift(original: str, paraphrase: str) -> bool:
    entities = _extract_entities(original)
    if not entities:
        return False

    preserved = sum(1 for entity in entities if _entity_is_preserved(entity, paraphrase))
    required = max(1, int(len(entities) * 0.75 + 0.999))
    return preserved < required


def _extract_entities(text: str) -> list[str]:
    tokens = TOKEN_RE.findall(text)
    entities: list[str] = []
    current: list[str] = []

    for idx, token in enumerate(tokens):
        if _is_entity_token(token, idx):
            current.append(token)
            continue
        if token.isdigit() and current:
            current.append(token)
            continue
        _flush_entity(current, entities)
        current = []
    _flush_entity(current, entities)
    return entities


def _is_entity_token(token: str, idx: int) -> bool:
    if token.isdigit():
        return False
    if idx == 0 and _entity_token_base(token) in LEADING_NON_ENTITY_WORDS:
        return False
    if token in GENERIC_TITLE_TOKENS:
        return False
    return token[:1].isupper() or token.isupper()


def _entity_token_base(token: str) -> str:
    return re.sub(r"'s$", "", token.lower())


def _flush_entity(current: list[str], entities: list[str]) -> None:
    if not current:
        return
    if len(current) >= 2 or len(current[0]) >= 4:
        entity = " ".join(current)
        if entity.lower() not in QUESTION_WORDS:
            entities.append(entity)


def _entity_is_preserved(entity: str, paraphrase: str) -> bool:
    normalized_entity = _normalize_text(entity)
    normalized_paraphrase = _normalize_text(paraphrase)
    if normalized_entity in normalized_paraphrase:
        return True
    entity_tokens = [
        token
        for token in _normalize_text(entity).split()
        if token and token not in ENTITY_FILLER_TOKENS
    ]
    if not entity_tokens:
        return True
    preserved_tokens = sum(1 for token in entity_tokens if re.search(rf"\b{re.escape(token)}\b", normalized_paraphrase))
    return preserved_tokens == len(entity_tokens)


def _select_by_profile(rows: list[dict[str, str]], profiles: tuple[str, ...]) -> dict[str, list[dict[str, str]]]:
    selected: dict[str, list[dict[str, str]]] = {profile: [] for profile in profiles}
    seen_source_profile: set[tuple[str, str]] = set()
    for row in rows:
        profile = row.get("paraphrase_profile", "")
        if profile not in profiles:
            continue
        key = (row.get("source_query_id", ""), profile)
        if key in seen_source_profile:
            continue
        seen_source_profile.add(key)
        selected[profile].append(row)
    return selected


def _source_ids_in_input(rows: list[dict[str, str]]) -> list[str]:
    source_ids: list[str] = []
    seen: set[str] = set()
    for row in rows:
        source_id = row.get("source_query_id", "")
        if source_id and source_id not in seen:
            seen.add(source_id)
            source_ids.append(source_id)
    return source_ids


def _source_rows_by_id(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    source_rows: dict[str, dict[str, str]] = {}
    for row in rows:
        source_id = row.get("source_query_id", "")
        if source_id and source_id not in source_rows:
            source_rows[source_id] = row
    return source_rows


def _missing_selection(
    selected_by_profile_rows: dict[str, list[dict[str, str]]],
    source_ids: list[str],
    expected_per_profile: int,
    profiles: tuple[str, ...],
) -> dict[str, list[str]]:
    missing: dict[str, list[str]] = {}
    expected_source_ids = source_ids[:expected_per_profile]
    for profile in profiles:
        selected_sources = {row.get("source_query_id", "") for row in selected_by_profile_rows.get(profile, [])}
        missing_sources = [source_id for source_id in expected_source_ids if source_id not in selected_sources]
        if missing_sources:
            missing[profile] = missing_sources
    return missing


def _regeneration_rows(
    missing_selection_by_profile: dict[str, list[str]],
    source_rows: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for profile, source_ids in missing_selection_by_profile.items():
        for source_id in source_ids:
            source_row = source_rows.get(source_id, {})
            rows.append(
                {
                    "source_query_id": source_id,
                    "original_query": source_row.get("original_query", ""),
                    "support_doc_ids": source_row.get("support_doc_ids", ""),
                    "qrels": source_row.get("qrels", ""),
                    "paraphrase_profile": profile,
                    "constraints": "preserve named entities, numbers, years, dates, relation, and qrels meaning",
                }
            )
    return rows


def _write_tsv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_benchmark_input(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["variant_query_id", "source_query_id", "query"], delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "variant_query_id": row["variant_query_id"],
                    "source_query_id": row["source_query_id"],
                    "query": row["paraphrased_query"],
                }
            )
