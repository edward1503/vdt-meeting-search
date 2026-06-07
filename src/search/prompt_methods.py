from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable

import numpy as np


STOPWORDS = {
    "a",
    "an",
    "and",
    "about",
    "for",
    "in",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
    "meeting",
    "meetings",
    "discussion",
    "discussing",
    "talking",
}

DOMAIN_EXPANSIONS = {
    "battery": ["power", "energy", "consumption", "life", "charging"],
    "power": ["battery", "energy", "consumption"],
    "remote": ["control", "button", "buttons", "interface", "features", "functions"],
    "button": ["buttons", "controls", "interface", "remote"],
    "interface": ["ui", "user", "buttons", "controls"],
    "market": ["research", "customer", "customers", "needs", "requirements"],
    "customer": ["market", "needs", "requirements", "users"],
    "requirement": ["requirements", "needs", "specification", "project"],
    "requirements": ["needs", "specification", "project", "manager"],
    "prototype": ["design", "evaluation", "test", "testing"],
    "evaluation": ["test", "testing", "prototype", "assessment"],
    "testing": ["test", "evaluation", "prototype"],
    "lcd": ["display", "screen", "interface"],
    "display": ["lcd", "screen", "visual"],
    "screen": ["lcd", "display", "interface"],
    "cost": ["price", "target", "budget", "expense"],
    "price": ["cost", "target", "budget"],
    "industrial": ["designer", "design", "shape", "casing", "appearance"],
    "designer": ["industrial", "design", "shape", "casing"],
    "shape": ["casing", "form", "appearance", "design"],
    "casing": ["shape", "case", "appearance", "design"],
    "presentation": ["final", "project", "plan", "slides"],
    "plan": ["project", "schedule", "presentation", "final"],
}

METHODS = ["embedding", "rule_expansion", "hyde_template", "multi_query_rrf", "hybrid_rrf", "llm_query_expansion", "llm_hyde", "llm_multi_query_rrf"]


@dataclass(frozen=True)
class QueryPlan:
    method: str
    original: str
    normalized: str
    expanded: str
    hyde_document: str
    variants: list[str]


def build_query_plan(query: str, method: str) -> QueryPlan:
    normalized = normalize_query(query)
    expanded = expand_query(normalized)
    hyde_document = build_hyde_document(normalized, expanded)
    variants = _unique_nonempty([query, normalized, expanded, hyde_document])
    return QueryPlan(method=method, original=query, normalized=normalized, expanded=expanded, hyde_document=hyde_document, variants=variants)


def normalize_query(query: str) -> str:
    tokens = tokenize(query)
    kept = [token for token in tokens if token not in STOPWORDS]
    return " ".join(kept) if kept else query.strip().lower()


def expand_query(query: str) -> str:
    tokens = tokenize(query)
    expanded = list(tokens)
    for token in tokens:
        expanded.extend(DOMAIN_EXPANSIONS.get(token, []))
        if token.endswith("s"):
            expanded.extend(DOMAIN_EXPANSIONS.get(token[:-1], []))
    return " ".join(_dedupe(expanded))


def build_hyde_document(normalized_query: str, expanded_query: str) -> str:
    focus = normalized_query or expanded_query
    context = expanded_query or normalized_query
    return (
        "Relevant meeting transcript excerpt. "
        f"The team discusses {focus}. "
        f"Important related concepts include {context}. "
        "Participants compare requirements, design choices, constraints, decisions, and next steps."
    )


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def reciprocal_rank_fusion(rankings: Iterable[Iterable[int]], k: int = 60) -> dict[int, float]:
    fused: dict[int, float] = {}
    for ranking in rankings:
        for rank, idx in enumerate(ranking, start=1):
            fused[int(idx)] = fused.get(int(idx), 0.0) + 1.0 / (k + rank)
    return fused


class LexicalIndex:
    def __init__(self, chunks: list[dict]) -> None:
        self.doc_tokens = [tokenize(chunk.get("text", "")) for chunk in chunks]
        self.doc_lengths = [len(tokens) for tokens in self.doc_tokens]
        self.avg_doc_length = sum(self.doc_lengths) / max(1, len(self.doc_lengths))
        self.term_frequencies = [Counter(tokens) for tokens in self.doc_tokens]
        document_frequency: Counter[str] = Counter()
        for tokens in self.doc_tokens:
            document_frequency.update(set(tokens))
        self.document_frequency = document_frequency
        self.document_count = len(chunks)

    def search(self, query: str, top_k: int) -> tuple[np.ndarray, np.ndarray]:
        query_terms = [term for term in tokenize(query) if term not in STOPWORDS]
        if not query_terms:
            return np.array([], dtype="float32"), np.array([], dtype="int64")
        scores = np.zeros(self.document_count, dtype="float32")
        k1 = 1.5
        b = 0.75
        for term in query_terms:
            df = self.document_frequency.get(term, 0)
            if df == 0:
                continue
            idf = math.log(1 + (self.document_count - df + 0.5) / (df + 0.5))
            for idx, frequencies in enumerate(self.term_frequencies):
                tf = frequencies.get(term, 0)
                if tf == 0:
                    continue
                length_norm = 1 - b + b * self.doc_lengths[idx] / max(1e-9, self.avg_doc_length)
                scores[idx] += idf * (tf * (k1 + 1)) / (tf + k1 * length_norm)
        ranked = np.argsort(-scores)[:top_k]
        ranked = ranked[scores[ranked] > 0]
        return scores[ranked], ranked.astype("int64")


def _dedupe(values: Iterable[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _unique_nonempty(values: Iterable[str]) -> list[str]:
    return [value for value in _dedupe(value.strip() for value in values) if value]