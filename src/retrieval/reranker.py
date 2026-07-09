from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any, Protocol


Hit = dict[str, Any]


class RerankerScorer(Protocol):
    def predict(self, pairs: Sequence[tuple[str, str]]) -> Sequence[float]:
        ...


class CrossEncoderReranker:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model: RerankerScorer | None = None

    def predict(self, pairs: Sequence[tuple[str, str]]) -> Sequence[float]:
        return self._get_model().predict(pairs)

    def _get_model(self) -> RerankerScorer:
        if self._model is None:
            cross_encoder_class = _load_cross_encoder_class()
            self._model = cross_encoder_class(self.model_name)
        return self._model


def dedupe_hits(hits: Iterable[Hit]) -> list[Hit]:
    deduped: dict[str, Hit] = {}
    sources_by_doc_id: dict[str, set[str]] = {}

    for hit in hits:
        doc_id = str(hit.get("doc_id") or "").strip()
        if not doc_id:
            continue

        sources_by_doc_id.setdefault(doc_id, set()).update(_source_parts(hit.get("source")))
        if doc_id not in deduped:
            deduped[doc_id] = dict(hit)

    for doc_id, hit in deduped.items():
        hit["source"] = "+".join(sorted(sources_by_doc_id[doc_id]))

    return list(deduped.values())


def rerank_hits(query: str, hits: Iterable[Hit], scorer: RerankerScorer, top_k: int) -> list[Hit]:
    candidates = dedupe_hits(hits)
    if top_k <= 0 or not candidates:
        return []

    pairs = [(query, _document_text(hit)) for hit in candidates]
    scores = list(scorer.predict(pairs))
    if len(scores) != len(candidates):
        raise ValueError("reranker scorer returned a different number of scores than input pairs")

    reranked: list[Hit] = []
    for hit, score in zip(candidates, scores, strict=True):
        model_score = float(score)
        reranked_hit = dict(hit)
        reranked_hit["pre_rerank_score"] = hit.get("score")
        reranked_hit["score"] = model_score
        reranked_hit["reranker_score"] = model_score
        reranked_hit["source"] = _append_source(hit.get("source"), "rerank")
        reranked.append(reranked_hit)

    return sorted(reranked, key=lambda hit: hit["reranker_score"], reverse=True)[:top_k]


def _document_text(hit: Hit) -> str:
    title = str(hit.get("title") or "").strip()
    text = str(hit.get("text") or "").strip()
    return " ".join(part for part in (title, text) if part)


def _source_parts(source: Any) -> set[str]:
    if source is None:
        return set()
    return {part.strip() for part in str(source).split("+") if part.strip()}


def _append_source(source: Any, suffix: str) -> str:
    parts = _ordered_source_parts(source)
    if suffix not in parts:
        parts.append(suffix)
    return "+".join(parts)


def _ordered_source_parts(source: Any) -> list[str]:
    if source is None:
        return []
    return [part.strip() for part in str(source).split("+") if part.strip()]


def _load_cross_encoder_class():
    try:
        from sentence_transformers import CrossEncoder
    except ImportError as exc:
        raise RuntimeError(
            "tv_hybrid_rerank requires sentence-transformers CrossEncoder support. "
            "Install sentence-transformers to use reranking."
        ) from exc
    return CrossEncoder
