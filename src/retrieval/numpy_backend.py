from __future__ import annotations

from pathlib import Path

import numpy as np

from src.retrieval.base import RetrievalBackend


class NumpyBackend(RetrievalBackend):
    name = "numpy"

    def __init__(self, index_dir: Path) -> None:
        super().__init__(index_dir)
        self.vectors: np.ndarray | None = None

    def build(self, vectors: np.ndarray) -> dict[str, int | str | float]:
        np.save(self.index_dir / "embeddings.npy", vectors.astype("float32"))
        self.vectors = vectors.astype("float32")
        return {"backend": self.name, "vectors": int(vectors.shape[0]), "dim": int(vectors.shape[1])}

    def load(self) -> None:
        self.vectors = np.load(self.index_dir / "embeddings.npy")

    def search(self, query_vector: np.ndarray, top_k: int) -> tuple[np.ndarray, np.ndarray]:
        if self.vectors is None:
            self.load()
        scores = self.vectors @ query_vector[0]
        indices = np.argsort(-scores)[:top_k]
        return scores[indices], indices
