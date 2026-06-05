from __future__ import annotations

from pathlib import Path

import numpy as np

from src.retrieval.base import BackendUnavailable, RetrievalBackend


class FaissBackend(RetrievalBackend):
    name = "faiss"

    def __init__(self, index_dir: Path) -> None:
        super().__init__(index_dir)
        self.backend_dir = index_dir / self.name
        self.path = self.backend_dir / "chunks.faiss"
        self.index = None

    def build(self, vectors: np.ndarray) -> dict[str, int | str | float]:
        try:
            import faiss
        except Exception as exc:  # pragma: no cover
            raise BackendUnavailable(f"FAISS is not installed: {exc}") from exc

        self.backend_dir.mkdir(parents=True, exist_ok=True)
        index = faiss.IndexFlatIP(vectors.shape[1])
        index.add(vectors.astype("float32"))
        faiss.write_index(index, str(self.path))
        self.index = index
        return {"backend": self.name, "vectors": int(vectors.shape[0]), "dim": int(vectors.shape[1])}

    def load(self) -> None:
        try:
            import faiss
        except Exception as exc:  # pragma: no cover
            raise BackendUnavailable(f"FAISS is not installed: {exc}") from exc

        path = self.path if self.path.exists() else self.index_dir / "chunks.faiss"
        if not path.exists():
            raise FileNotFoundError(f"FAISS index not found: {path}")
        self.index = faiss.read_index(str(path))

    def search(self, query_vector: np.ndarray, top_k: int) -> tuple[np.ndarray, np.ndarray]:
        if self.index is None:
            self.load()
        scores, indices = self.index.search(query_vector.astype("float32"), top_k)
        return scores[0], indices[0]
