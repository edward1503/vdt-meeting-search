from __future__ import annotations

import random
import re
import json
from dataclasses import dataclass, field
from pathlib import Path

TOKEN_RE = re.compile('[A-Za-z-]+|\\d+|[^A-Za-z\\d\\s]+')

SYNONYMS: dict[str, list[str]] = {
    'occupations': ['professions', 'jobs', 'vocations'],
    'city': ['municipality', 'urban area'],
    'famous': ['well-known', 'notable', 'renowned'],
    'scientist': ['researcher', 'scholar'],
    'visit': ['travel to', 'go to'],
    'after': ['following', 'subsequent to'],
    'important': ['major', 'significant', 'notable'],
    'conference': ['symposium', 'meeting', 'event'],
    'campaign': ['initiative', 'drive'],
    'term': ['phrase', 'expression'],
    'media': ['press', 'outlets'],
    'formally': ['officially'],
    'launched': ['started', 'introduced'],
    'depicts': ['portrays', 'shows'],
    'death': ['passing', 'demise'],
    'bay': ['inlet', 'cove'],
    'coast': ['shoreline', 'seaboard'],
    'title': ['name', 'heading'],
    'memoir': ['autobiography', 'personal account'],
    'written': ['authored', 'composed'],
    'honoree': ['recipient', 'awardee'],
    'wrote': ['authored', 'composed'],
    'starred': ['appeared', 'featured'],
    'located': ['situated', 'based'],
    'founded': ['established', 'created'],
    'released': ['published', 'issued'],
    'hosted': ['held', 'organized'],
    'defeated': ['beat', 'overcame'],
    'university': ['college', 'institution'],
    'annual': ['yearly', 'once-a-year'],
    'actor': ['performer', 'cast member'],
    'actress': ['performer', 'female actor'],
}

STOPWORDS = {
    'a', 'an', 'the', 'of', 'in', 'on', 'at', 'to', 'for', 'from',
    'with', 'and', 'or', 'what', 'which', 'who', 'where', 'when',
    'why', 'how', 'do', 'does', 'did', 'is', 'are', 'was', 'were',
}


@dataclass(frozen=True)
class ParaphraseConfig:
    ratios: list[float] = field(default_factory=lambda: [0.2, 0.4, 0.6])
    variants_per_ratio: int = 1
    seed: int = 13


@dataclass(frozen=True)
class QueryVariant:
    variant_query_id: str
    source_query_id: str
    query: str
    ratio: float
    variant_index: int
    changed_terms: list[tuple[str, str]]
    actual_change_ratio: float


def make_query_variants(query_id: str, query: str, config: ParaphraseConfig) -> list[QueryVariant]:
    variants: list[QueryVariant] = []
    for ratio in config.ratios:
        for variant_index in range(1, config.variants_per_ratio + 1):
            rng = random.Random(f'{config.seed}:{query_id}:{ratio}:{variant_index}')
            variant_query, changed_terms, actual_ratio = _paraphrase_once(query, ratio, rng)
            variants.append(QueryVariant(
                variant_query_id=f'{query_id}::syn{int(ratio * 100):03d}::v{variant_index}',
                source_query_id=query_id,
                query=variant_query,
                ratio=ratio,
                variant_index=variant_index,
                changed_terms=changed_terms,
                actual_change_ratio=actual_ratio,
            ))
    return variants


def _paraphrase_once(query: str, ratio: float, rng: random.Random) -> tuple[str, list[tuple[str, str]], float]:
    tokens = TOKEN_RE.findall(query)
    eligible = [idx for idx, token in enumerate(tokens) if _is_eligible(tokens, idx)]
    if not eligible:
        return query, [], 0.0

    target = max(1, round(len(eligible) * ratio))
    chosen = set(rng.sample(eligible, min(target, len(eligible))))
    changed: list[tuple[str, str]] = []
    output = tokens[:]

    for idx in sorted(chosen):
        original = tokens[idx]
        options = SYNONYMS.get(original.lower())
        if not options:
            continue
        replacement = rng.choice(options)
        output[idx] = _match_case(original, replacement)
        changed.append((original, output[idx]))

    return _join_tokens(output), changed, len(changed) / max(1, len(eligible))


def _is_eligible(tokens: list[str], idx: int) -> bool:
    token = tokens[idx]
    lower = token.lower()
    if lower in STOPWORDS or lower not in SYNONYMS:
        return False
    if token.isdigit():
        return False
    if token[:1].isupper() and idx > 0:
        return False
    return True


def _match_case(original: str, replacement: str) -> str:
    if original[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def _join_tokens(tokens: list[str]) -> str:
    text = ''
    for token in tokens:
        if not text:
            text = token
        elif re.fullmatch(r'[^A-Za-z\d\s]+', token):
            text += token
        else:
            text += ' ' + token
    return text


def write_variants_tsv(variants: list[QueryVariant], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ['variant_query_id\tsource_query_id\tratio\tvariant_index\tquery\tchanged_terms\tactual_change_ratio']
    for item in variants:
        changed = ';'.join(f'{src}->{dst}' for src, dst in item.changed_terms)
        lines.append('\t'.join([
            item.variant_query_id,
            item.source_query_id,
            f'{item.ratio:.2f}',
            str(item.variant_index),
            item.query.replace('\t', ' '),
            changed.replace('\t', ' '),
            f'{item.actual_change_ratio:.4f}',
        ]))
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def write_variants_jsonl(variants: list[QueryVariant], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(item.__dict__, ensure_ascii=False) for item in variants]
    suffix = '\n' if lines else ''
    path.write_text('\n'.join(lines) + suffix, encoding='utf-8')
