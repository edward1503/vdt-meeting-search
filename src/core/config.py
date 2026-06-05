from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    raw_dir: Path = ROOT_DIR / "data" / "raw"
    processed_dir: Path = ROOT_DIR / "data" / "processed"
    index_dir: Path = ROOT_DIR / "data" / "index"
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    chunk_size_words: int = int(os.getenv("CHUNK_SIZE_WORDS", "260"))
    chunk_overlap_words: int = int(os.getenv("CHUNK_OVERLAP_WORDS", "60"))


settings = Settings()

