from __future__ import annotations

import math
import re
from collections.abc import Iterable

TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def reciprocal_rank_fusion(rankings: Iterable[list[str]], k: int = 60) -> dict[str, float]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return scores


def dcg(relevances: list[float]) -> float:
    return sum((2**rel - 1) / math.log2(rank + 1) for rank, rel in enumerate(relevances, start=1))
