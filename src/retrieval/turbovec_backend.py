from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core.config import settings
from src.retrieval.base import BackendUnavailable, RetrievalBackend


class TurboVecBackend(RetrievalBackend):
    name = "turbovec"

    def __init__(self, index_dir: Path, bit_width: int = settings.turbovec_bit_width) -> None:
        super().__init__(index_dir)
        self.bit_width = bit_width
        self.backend_dir = index_dir / self.name
        self.path = self.backend_dir / f"chunks-b{bit_width}.tv"
        self.index = None

    def build(self, vectors: np.ndarray) -> dict[str, int | str | float]:
        try:
            from turbovec import IdMapIndex
        except Exception as exc:  # pragma: no cover
            raise BackendUnavailable(f"TurboVec is not installed: {exc}") from exc
        dim = int(vectors.shape[1])
        if dim % 8 != 0:
            raise BackendUnavailable(f"TurboVec requires vector dim to be a positive multiple of 8, got {dim}")

        self.backend_dir.mkdir(parents=True, exist_ok=True)
        index = IdMapIndex(dim=dim, bit_width=self.bit_width)
        index.prepare()
        ids = np.arange(vectors.shape[0], dtype="uint64")
        index.add_with_ids(vectors.astype("float32"), ids)
        index.write(str(self.path))
        self.index = index
        return {
            "backend": self.name,
            "vectors": int(vectors.shape[0]),
            "dim": dim,
            "bit_width": self.bit_width,
        }

    def load(self) -> None:
        try:
            from turbovec import IdMapIndex
        except Exception as exc:  # pragma: no cover
            raise BackendUnavailable(f"TurboVec is not installed: {exc}") from exc
        if not self.path.exists():
            raise FileNotFoundError(f"TurboVec index not found: {self.path}")
        self.index = IdMapIndex.load(str(self.path))

    def search(self, query_vector: np.ndarray, top_k: int) -> tuple[np.ndarray, np.ndarray]:
        if self.index is None:
            self.load()
        scores, ids = self.index.search(query_vector.astype("float32"), top_k)
        return scores[0], ids[0].astype("int64")
