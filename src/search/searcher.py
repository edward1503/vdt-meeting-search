from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import numpy as np

from src.core.config import settings
from src.embedding.model import EmbeddingModel
from src.retrieval.base import BackendUnavailable
from src.retrieval.factory import create_backend


class MeetingSearcher:
    def __init__(self, index_dir: Path = settings.index_dir, backend_name: str = settings.retrieval_backend) -> None:
        self.index_dir = index_dir
        self.backend_name = backend_name
        manifest_path = index_dir / "manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"Index manifest not found: {manifest_path}. Run python -m src.indexing.build_faiss")
        self.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.chunks = _read_jsonl(index_dir / "chunks.jsonl")
        meetings = json.loads((index_dir / "meetings.json").read_text(encoding="utf-8"))
        self.meetings = {str(item["meeting_id"]): item for item in meetings}
        self.model = EmbeddingModel(self.manifest["model_name"])
        self.vectors = np.load(index_dir / "embeddings.npy")
        self.backend = create_backend(backend_name, index_dir)
        try:
            self.backend.load()
        except FileNotFoundError:
            if backend_name == "faiss":
                self.backend.build(self.vectors)
            else:
                raise
        except BackendUnavailable:
            raise

    def search(self, query: str, top_k: int = 10, speaker: str | None = None) -> dict[str, Any]:
        start = time.perf_counter()
        query_vector = self.model.encode([query])
        candidate_limit = min(max(top_k * 8, 25), len(self.chunks))
        scores, indices = self.backend.search(query_vector, candidate_limit)

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

        results = sorted(meeting_hits.values(), key=lambda item: item["score"], reverse=True)[:top_k]
        return {
            "query": query,
            "top_k": top_k,
            "backend": self.backend.name,
            "results": results,
            "latency_ms": round((time.perf_counter() - start) * 1000, 2),
        }

    def get_meeting(self, meeting_id: str) -> dict[str, Any] | None:
        return self.meetings.get(meeting_id)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _speaker_matches(chunk: dict[str, Any], speaker: str) -> bool:
    needle = speaker.lower()
    return any(needle in str(value).lower() for value in chunk.get("speakers", []))
