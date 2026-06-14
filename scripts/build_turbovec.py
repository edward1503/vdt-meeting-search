from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def iter_embedding_shards(embedding_dir: Path) -> Iterator[Path]:
    yield from sorted(embedding_dir.glob("*.float16.npy"))


def load_embedding_shard(vector_path: Path) -> tuple[np.ndarray, np.ndarray]:
    ids_path = vector_path.with_name(vector_path.name.replace(".float16.npy", ".ids.npy"))
    vectors = np.load(vector_path).astype(np.float32)
    ids = np.load(ids_path).astype(np.uint64)
    return vectors, ids


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a TurboVec IdMapIndex from embedding shards")
    parser.add_argument("--embedding-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config-output", type=Path, required=True)
    parser.add_argument("--dim", type=int, default=384)
    parser.add_argument("--bit-width", type=int, default=4)
    parser.add_argument("--max-shards", type=int, default=None)
    args = parser.parse_args()

    from turbovec import IdMapIndex

    shards = list(iter_embedding_shards(args.embedding_dir))
    if args.max_shards is not None:
        shards = shards[: args.max_shards]
    index = IdMapIndex(dim=args.dim, bit_width=args.bit_width)
    docs = 0
    for shard in shards:
        vectors, ids = load_embedding_shard(shard)
        index.add_with_ids(vectors, ids)
        docs += int(ids.shape[0])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    index.write(str(args.output))
    config = {
        "dim": args.dim,
        "bit_width": args.bit_width,
        "shards": len(shards),
        "docs": docs,
        "built_at": datetime.now(timezone.utc).isoformat(),
    }
    args.config_output.parent.mkdir(parents=True, exist_ok=True)
    args.config_output.write_text(json.dumps(config, indent=2), encoding="utf-8")
    print(json.dumps(config, indent=2))


if __name__ == "__main__":
    main()
