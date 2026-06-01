"""Embedding model wrapper with GPU support and e5 prefix handling."""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import torch
from sentence_transformers import SentenceTransformer

from src.core.config import settings

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    return SentenceTransformer(settings.embedding_model, device=DEVICE)


def _add_prefix(texts: list[str], prefix: str) -> list[str]:
    """Add e5-style prefix if using an e5 model."""
    if "e5" in settings.embedding_model.lower():
        return [f"{prefix}: {t}" for t in texts]
    return texts


def embed_texts(texts: list[str], batch_size: int = 64, is_query: bool = False) -> list[list[float]]:
    model = get_embedding_model()
    prefix = "query" if is_query else "passage"
    prefixed = _add_prefix(texts, prefix)
    vectors = model.encode(
        prefixed,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=len(texts) > batch_size,
    )
    if isinstance(vectors, np.ndarray):
        return vectors.astype(float).tolist()
    return [np.asarray(v, dtype=float).tolist() for v in vectors]
