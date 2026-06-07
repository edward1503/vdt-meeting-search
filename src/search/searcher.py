from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import numpy as np

from src.core.config import settings
from src.embedding.model import EmbeddingModel
from src.search.llm_query import LLMQueryExpander
from src.search.prompt_methods import METHODS, LexicalIndex, build_query_plan, reciprocal_rank_fusion

class MeetingSearcher:
    def __init__(self, index_dir: Path = settings.index_dir) -> None:
        self.index_dir = index_dir
        manifest_path = index_dir / "manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"Index manifest not found: {manifest_path}. Run python -m src.indexing.build_faiss")
        self.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.chunks = _read_jsonl(index_dir / "chunks.jsonl")
        meetings = json.loads((index_dir / "meetings.json").read_text(encoding="utf-8"))
        self.meetings = {str(item["meeting_id"]): item for item in meetings}
        self.model = EmbeddingModel(self.manifest["model_name"])
        self.vectors = np.load(index_dir / "embeddings.npy")
        self.faiss_index = self._load_faiss_index()
        self.lexical_index = LexicalIndex(self.chunks)
        self.llm_expander = LLMQueryExpander(index_dir / "llm_query_cache.json")

    def search(self, query: str, top_k: int = 10, speaker: str | None = None, method: str = "embedding") -> dict[str, Any]:
        start = time.perf_counter()
        normalized_method = method.strip().lower()
        if normalized_method not in METHODS:
            raise ValueError(f"Unknown prompt search method: {method}")

        candidate_limit = min(max(top_k * 10, 40), len(self.chunks))
        scores, indices = self._search_by_method(query, candidate_limit, normalized_method)
        results = self._meeting_results(scores, indices, top_k, speaker)
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return {
            "query": query,
            "top_k": top_k,
            "method": normalized_method,
            "results": results,
            "latency_ms": latency_ms,
        }

    def get_meeting(self, meeting_id: str) -> dict[str, Any] | None:
        return self.meetings.get(meeting_id)

    def _search_by_method(self, query: str, top_k: int, method: str) -> tuple[np.ndarray, np.ndarray]:
        plan = build_query_plan(query, method)
        if method == "embedding":
            return self._search_text(query, top_k)
        if method == "rule_expansion":
            return self._search_text(plan.expanded, top_k)
        if method == "hyde_template":
            return self._search_text(plan.hyde_document, top_k)
        if method == "multi_query_rrf":
            rankings = [self._search_text(variant, top_k)[1] for variant in plan.variants]
            return _fused_to_arrays(reciprocal_rank_fusion(rankings), top_k)
        if method == "hybrid_rrf":
            vector_scores, vector_indices = self._search_text(plan.expanded, top_k)
            lexical_scores, lexical_indices = self.lexical_index.search(plan.expanded, top_k)
            if len(lexical_indices) == 0:
                return vector_scores, vector_indices
            fused = reciprocal_rank_fusion([vector_indices, lexical_indices])
            return _fused_to_arrays(fused, top_k)
        if method == "llm_query_expansion":
            expansion = self.llm_expander.expand(query)
            return self._search_text(expansion["expanded_query"], top_k)
        if method == "llm_hyde":
            expansion = self.llm_expander.expand(query)
            return self._search_text(expansion["hyde_document"], top_k)
        if method == "llm_multi_query_rrf":
            expansion = self.llm_expander.expand(query)
            variants = [query, expansion["expanded_query"], expansion["hyde_document"], *expansion["query_variants"]]
            rankings = [self._search_text(variant, top_k)[1] for variant in _unique_nonempty(variants)]
            return _fused_to_arrays(reciprocal_rank_fusion(rankings), top_k)
        raise ValueError(f"Unknown prompt search method: {method}")

    def _search_text(self, text: str, top_k: int) -> tuple[np.ndarray, np.ndarray]:
        query_vector = self.model.encode([text])
        return self._search_vectors(query_vector, top_k)

    def _meeting_results(
        self,
        scores: np.ndarray,
        indices: np.ndarray,
        top_k: int,
        speaker: str | None,
    ) -> list[dict[str, Any]]:
        meeting_hits: dict[str, dict[str, Any]] = {}
        for score, idx in zip(scores, indices):
            if idx < 0 or idx >= len(self.chunks):
                continue
            chunk = self.chunks[int(idx)]
            if speaker and not _speaker_matches(chunk, speaker):
                continue
            meeting_id = str(chunk["meeting_id"])
            hit = meeting_hits.setdefault(
                meeting_id,
                {
                    "meeting_id": meeting_id,
                    "title": chunk.get("title"),
                    "date": chunk.get("date"),
                    "participants": chunk.get("participants", []),
                    "score": float(score),
                    "snippets": [],
                },
            )
            hit["score"] = max(hit["score"], float(score))
            if len(hit["snippets"]) < 3:
                hit["snippets"].append(
                    {
                        "chunk_id": chunk["chunk_id"],
                        "score": float(score),
                        "speakers": chunk.get("speakers", []),
                        "time_start": chunk.get("time_start"),
                        "time_end": chunk.get("time_end"),
                        "text": chunk["text"],
                    }
                )

        return sorted(meeting_hits.values(), key=lambda item: item["score"], reverse=True)[:top_k]

    def _load_faiss_index(self):
        path = self.index_dir / "chunks.faiss"
        if not path.exists():
            return None
        try:
            import faiss

            return faiss.read_index(str(path))
        except Exception:
            return None

    def _search_vectors(self, query_vector: np.ndarray, top_k: int) -> tuple[np.ndarray, np.ndarray]:
        if self.faiss_index is not None:
            scores, indices = self.faiss_index.search(query_vector.astype("float32"), top_k)
            return scores[0], indices[0]
        scores = self.vectors @ query_vector[0]
        indices = np.argsort(-scores)[:top_k]
        return scores[indices], indices


def _fused_to_arrays(fused: dict[int, float], top_k: int) -> tuple[np.ndarray, np.ndarray]:
    ordered = sorted(fused.items(), key=lambda item: item[1], reverse=True)[:top_k]
    indices = np.array([idx for idx, _ in ordered], dtype="int64")
    scores = np.array([score for _, score in ordered], dtype="float32")
    return scores, indices


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _speaker_matches(chunk: dict[str, Any], speaker: str) -> bool:
    needle = speaker.lower()
    return any(needle in str(value).lower() for value in chunk.get("speakers", []))


def _unique_nonempty(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        cleaned = value.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return result