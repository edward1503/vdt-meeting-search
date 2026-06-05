from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from src.core.config import settings
from src.embedding.model import EmbeddingModel
from src.preprocessing.chunking import chunk_meetings
from src.preprocessing.parse_ami import load_meetings


def build_index(raw_dir: Path, output_dir: Path, model_name: str) -> dict[str, int | str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    meetings = load_meetings(raw_dir)
    chunks = chunk_meetings(meetings, settings.chunk_size_words, settings.chunk_overlap_words)
    if not chunks:
        raise ValueError("No chunks produced from raw data")

    model = EmbeddingModel(model_name)
    vectors = model.encode([chunk["text"] for chunk in chunks])

    np.save(output_dir / "embeddings.npy", vectors)
    _write_jsonl(output_dir / "chunks.jsonl", chunks)
    _write_json(output_dir / "meetings.json", meetings)
    _write_json(output_dir / "manifest.json", {"model_name": model_name, "dim": int(vectors.shape[1])})

    backend = "numpy"
    try:
        import faiss

        index = faiss.IndexFlatIP(vectors.shape[1])
        index.add(vectors)
        faiss.write_index(index, str(output_dir / "chunks.faiss"))
        backend = "faiss"
    except Exception as exc:  # pragma: no cover
        _write_json(output_dir / "faiss_error.json", {"error": str(exc)})

    return {"meetings": len(meetings), "chunks": len(chunks), "dim": int(vectors.shape[1]), "backend": backend}


def _write_jsonl(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build FAISS index for meeting chunks")
    parser.add_argument("--raw-dir", type=Path, default=settings.raw_dir)
    parser.add_argument("--output-dir", type=Path, default=settings.index_dir)
    parser.add_argument("--model", default=settings.embedding_model)
    args = parser.parse_args()
    stats = build_index(args.raw_dir, args.output_dir, args.model)
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()

