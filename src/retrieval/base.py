from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np


class RetrievalBackend(ABC):
    name: str

    def __init__(self, index_dir: Path) -> None:
        self.index_dir = index_dir

    @abstractmethod
    def build(self, vectors: np.ndarray) -> dict[str, int | str | float]:
        raise NotImplementedError

    @abstractmethod
    def load(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def search(self, query_vector: np.ndarray, top_k: int) -> tuple[np.ndarray, np.ndarray]:
        raise NotImplementedError


class BackendUnavailable(RuntimeError):
    pass
