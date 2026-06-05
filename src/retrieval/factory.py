from __future__ import annotations

from pathlib import Path

from src.retrieval.base import RetrievalBackend
from src.retrieval.elasticsearch_backend import ElasticsearchBackend
from src.retrieval.faiss_backend import FaissBackend
from src.retrieval.numpy_backend import NumpyBackend
from src.retrieval.turbovec_backend import TurboVecBackend


def create_backend(name: str, index_dir: Path) -> RetrievalBackend:
    normalized = name.strip().lower()
    if normalized == "faiss":
        return FaissBackend(index_dir)
    if normalized in {"elastic", "elasticsearch", "es"}:
        return ElasticsearchBackend(index_dir)
    if normalized in {"turbovec", "turbo_vec", "tv"}:
        return TurboVecBackend(index_dir)
    if normalized == "numpy":
        return NumpyBackend(index_dir)
    raise ValueError(f"Unknown retrieval backend: {name}")


def backend_names() -> list[str]:
    return ["faiss", "elasticsearch", "turbovec"]
