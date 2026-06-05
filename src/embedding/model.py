from __future__ import annotations

import hashlib

import numpy as np


class EmbeddingModel:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model = None
        if model_name != "hashing":
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(model_name)

    def encode(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        if self._model is None:
            return _hashing_encode(texts)
        vectors = self._model.encode(
            texts,
            batch_size=batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=len(texts) > batch_size,
        )
        return vectors.astype("float32")


def _hashing_encode(texts: list[str], dim: int = 384) -> np.ndarray:
    vectors = np.zeros((len(texts), dim), dtype="float32")
    for row, text in enumerate(texts):
        for token in text.lower().split():
            digest = hashlib.md5(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "little") % dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vectors[row, idx] += sign
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms

