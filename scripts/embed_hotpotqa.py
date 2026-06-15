from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.staging import iter_staging_files


def write_embedding_shard(staging_file: Path, embedding_dir: Path, model: Any, batch_size: int, model_name: str) -> dict[str, Any]:
    embedding_dir.mkdir(parents=True, exist_ok=True)
    texts: list[str] = []
    ids: list[int] = []
    with staging_file.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            texts.append(str(row["embedding_text"]))
            ids.append(int(row["numeric_id"]))

    vectors = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True, batch_size=batch_size)
    vectors = np.asarray(vectors, dtype=np.float32)
    ids_array = np.asarray(ids, dtype=np.uint64)
    stem = staging_file.stem
    np.save(embedding_dir / f"{stem}.float16.npy", vectors.astype(np.float16))
    np.save(embedding_dir / f"{stem}.ids.npy", ids_array)
    meta = {"source_file": staging_file.name, "docs": int(len(ids)), "dims": int(vectors.shape[1]), "model": model_name}
    (embedding_dir / f"{stem}.meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def done_marker_path(progress_dir: Path, staging_file: Path) -> Path:
    return progress_dir / f"{staging_file.stem}.done"


def main() -> None:
    parser = argparse.ArgumentParser(description="Encode HotpotQA staging shards to embedding shards")
    parser.add_argument("--staging-dir", type=Path, required=True)
    parser.add_argument("--embedding-dir", type=Path, required=True)
    parser.add_argument("--progress-dir", type=Path, required=True)
    parser.add_argument("--model", default="BAAI/bge-small-en-v1.5")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--max-files", type=int, default=None)
    args = parser.parse_args()

    from sentence_transformers import SentenceTransformer

    args.progress_dir.mkdir(parents=True, exist_ok=True)
    model = SentenceTransformer(args.model)
    files = [path for path in iter_staging_files(args.staging_dir) if not done_marker_path(args.progress_dir, path).exists()]
    if args.max_files is not None:
        files = files[: args.max_files]
    encoded = []
    for path in files:
        meta = write_embedding_shard(path, args.embedding_dir, model, args.batch_size, args.model)
        done_marker_path(args.progress_dir, path).write_text(json.dumps(meta, indent=2), encoding="utf-8")
        encoded.append(meta)
    print(json.dumps({"encoded": encoded}, indent=2))


if __name__ == "__main__":
    main()
