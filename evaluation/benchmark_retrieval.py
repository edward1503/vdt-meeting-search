from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
from typing import Any

import numpy as np

from src.core.config import ROOT_DIR, settings
from src.embedding.model import EmbeddingModel
from src.indexing.build_faiss import build_index
from src.retrieval.base import BackendUnavailable
from src.retrieval.factory import backend_names, create_backend


def run_benchmark(
    qrels_path: Path,
    raw_dir: Path,
    index_dir: Path,
    model_name: str,
    top_k: int,
    backends: list[str],
    rebuild_shared: bool,
    rebuild_backends: bool,
) -> dict[str, Any]:
    if rebuild_shared or not (index_dir / "manifest.json").exists():
        shared_stats = build_index(raw_dir, index_dir, model_name)
    else:
        manifest = json.loads((index_dir / "manifest.json").read_text(encoding="utf-8"))
        shared_stats = {"backend": "existing", "model_name": manifest.get("model_name"), "dim": manifest.get("dim")}

    manifest = json.loads((index_dir / "manifest.json").read_text(encoding="utf-8"))
    chunks = _read_jsonl(index_dir / "chunks.jsonl")
    vectors = np.load(index_dir / "embeddings.npy")
    qrels = json.loads(qrels_path.read_text(encoding="utf-8"))
    model = EmbeddingModel(manifest["model_name"])
    query_vectors = model.encode([item["query"] for item in qrels])

    results = []
    for backend_name in backends:
        result = _benchmark_backend(
            backend_name=backend_name,
            index_dir=index_dir,
            vectors=vectors,
            chunks=chunks,
            qrels=qrels,
            query_vectors=query_vectors,
            top_k=top_k,
            rebuild=rebuild_backends,
        )
        results.append(result)

    return {
        "config": {
            "qrels": str(qrels_path),
            "raw_dir": str(raw_dir),
            "index_dir": str(index_dir),
            "model_name": manifest["model_name"],
            "dim": int(vectors.shape[1]),
            "chunks": int(vectors.shape[0]),
            "top_k": top_k,
            "chunk_size_words": settings.chunk_size_words,
            "chunk_overlap_words": settings.chunk_overlap_words,
        },
        "shared_stats": shared_stats,
        "results": results,
    }


def _benchmark_backend(
    backend_name: str,
    index_dir: Path,
    vectors: np.ndarray,
    chunks: list[dict[str, Any]],
    qrels: list[dict[str, Any]],
    query_vectors: np.ndarray,
    top_k: int,
    rebuild: bool,
) -> dict[str, Any]:
    backend = create_backend(backend_name, index_dir)
    build_time_sec = 0.0
    try:
        if rebuild:
            start = time.perf_counter()
            build_stats = backend.build(vectors)
            build_time_sec = time.perf_counter() - start
        else:
            build_stats = {"backend": backend.name, "mode": "loaded"}
            backend.load()
    except (BackendUnavailable, FileNotFoundError, ConnectionError, TimeoutError) as exc:
        return {"backend": backend_name, "status": "skipped", "reason": str(exc)}
    except Exception as exc:
        return {"backend": backend_name, "status": "failed", "reason": f"{type(exc).__name__}: {exc}"}

    latencies = []
    precision_total = 0.0
    recall_total = 0.0
    reciprocal_total = 0.0
    sample_results = []

    for item, query_vector in zip(qrels, query_vectors):
        relevant = set(item["relevant_meeting_ids"])
        candidate_limit = min(max(top_k * 8, 25), len(chunks))
        query_matrix = np.expand_dims(query_vector.astype("float32"), axis=0)
        start = time.perf_counter()
        scores, indices = backend.search(query_matrix, candidate_limit)
        latencies.append((time.perf_counter() - start) * 1000)
        returned = _meeting_results(chunks, scores, indices, top_k)
        returned_ids = [result["meeting_id"] for result in returned]
        hits = [meeting_id for meeting_id in returned_ids if meeting_id in relevant]
        precision_total += len(hits) / max(1, top_k)
        recall_total += len(hits) / max(1, len(relevant))
        reciprocal_total += next(
            (1 / rank for rank, meeting_id in enumerate(returned_ids, start=1) if meeting_id in relevant),
            0.0,
        )
        if len(sample_results) < 3:
            sample_results.append({"query": item["query"], "returned": returned_ids, "relevant": sorted(relevant)})

    count = max(1, len(qrels))
    return {
        "backend": backend.name,
        "status": "ok",
        "build_stats": build_stats,
        "build_time_sec": round(build_time_sec, 4),
        "precision@k": round(precision_total / count, 4),
        "recall@k": round(recall_total / count, 4),
        "mrr@k": round(reciprocal_total / count, 4),
        "latency_avg_ms": round(statistics.fmean(latencies), 4),
        "latency_p50_ms": round(_percentile(latencies, 50), 4),
        "latency_p95_ms": round(_percentile(latencies, 95), 4),
        "storage_mb": round(_backend_storage_mb(index_dir, backend.name), 4),
        "queries": len(qrels),
        "sample_results": sample_results,
    }


def _meeting_results(
    chunks: list[dict[str, Any]],
    scores: np.ndarray,
    indices: np.ndarray,
    top_k: int,
) -> list[dict[str, Any]]:
    meeting_hits: dict[str, dict[str, Any]] = {}
    for score, idx in zip(scores, indices):
        if idx < 0 or idx >= len(chunks):
            continue
        chunk = chunks[int(idx)]
        meeting_id = str(chunk["meeting_id"])
        hit = meeting_hits.setdefault(meeting_id, {"meeting_id": meeting_id, "score": float(score)})
        hit["score"] = max(hit["score"], float(score))
    return sorted(meeting_hits.values(), key=lambda item: item["score"], reverse=True)[:top_k]


def _percentile(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, round((percentile / 100) * (len(ordered) - 1))))
    return ordered[idx]


def _backend_storage_mb(index_dir: Path, backend_name: str) -> float:
    backend_dir = index_dir / backend_name
    paths = []
    if backend_dir.exists():
        paths.extend(path for path in backend_dir.rglob("*") if path.is_file())
    elif backend_name == "faiss" and (index_dir / "chunks.faiss").exists():
        paths.append(index_dir / "chunks.faiss")
    total = sum(path.stat().st_size for path in paths)
    return total / (1024 * 1024)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark retrieval backends over the shared Sprint 1 pipeline")
    parser.add_argument("--qrels", type=Path, default=ROOT_DIR / "data" / "eval" / "sample_qrels.json")
    parser.add_argument("--raw-dir", type=Path, default=settings.raw_dir)
    parser.add_argument("--index-dir", type=Path, default=settings.index_dir)
    parser.add_argument("--model", default=settings.embedding_model)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--backends", default=",".join(backend_names()))
    parser.add_argument("--rebuild-shared", action="store_true")
    parser.add_argument("--no-rebuild-backends", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT_DIR / "evaluation" / "results" / "retrieval_benchmark.json")
    args = parser.parse_args()

    result = run_benchmark(
        qrels_path=args.qrels,
        raw_dir=args.raw_dir,
        index_dir=args.index_dir,
        model_name=args.model,
        top_k=args.top_k,
        backends=[backend.strip() for backend in args.backends.split(",") if backend.strip()],
        rebuild_shared=args.rebuild_shared,
        rebuild_backends=not args.no_rebuild_backends,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
