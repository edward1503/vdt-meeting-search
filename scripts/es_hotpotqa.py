from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.staging import iter_staging_files
from src.retrieval.elasticsearch_retriever import (
    ElasticsearchRetriever,
    bm25_bulk_action,
    build_bm25_index_body,
    build_index_body,
    bulk_action,
)


def done_marker_path(progress_dir: Path, staging_file: Path) -> Path:
    return progress_dir / f"{staging_file.stem}.done"


def select_pending_files(staging_dir: Path, progress_dir: Path, max_files: int | None = None) -> list[Path]:
    pending = [path for path in iter_staging_files(staging_dir) if not done_marker_path(progress_dir, path).exists()]
    if max_files is not None:
        return pending[:max_files]
    return pending


def main() -> None:
    parser = argparse.ArgumentParser(description="HotpotQA Elasticsearch baseline utilities")
    parser.add_argument("--url", default="http://localhost:9200")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create-index")
    create_parser.add_argument("--index", default="hotpotqa_docs_v1")
    create_parser.add_argument("--alias", default="hotpotqa_docs_current")
    create_parser.add_argument("--dims", type=int, default=384)
    create_parser.add_argument("--shards", type=int, default=1)
    create_parser.add_argument("--reset", action="store_true")

    create_bm25_parser = subparsers.add_parser("create-bm25-index")
    create_bm25_parser.add_argument("--index", default="hotpotqa_full_bm25_v1")
    create_bm25_parser.add_argument("--alias", default="hotpotqa_full_bm25_current")
    create_bm25_parser.add_argument("--shards", type=int, default=1)
    create_bm25_parser.add_argument("--reset", action="store_true")

    ingest_parser = subparsers.add_parser("ingest")
    ingest_parser.add_argument("--index", default="hotpotqa_docs_v1")
    ingest_parser.add_argument("--staging-dir", type=Path, default=Path("artifacts/hotpotqa_full/staging"))
    ingest_parser.add_argument("--progress-dir", type=Path, default=Path("artifacts/hotpotqa_full/progress"))
    ingest_parser.add_argument("--model", default="BAAI/bge-small-en-v1.5")
    ingest_parser.add_argument("--batch-size", type=int, default=128)
    ingest_parser.add_argument("--max-files", type=int, default=None)

    ingest_bm25_parser = subparsers.add_parser("ingest-bm25")
    ingest_bm25_parser.add_argument("--index", default="hotpotqa_full_bm25_v1")
    ingest_bm25_parser.add_argument("--staging-dir", type=Path, default=Path("artifacts/hotpotqa_full/staging"))
    ingest_bm25_parser.add_argument("--progress-dir", type=Path, default=Path("artifacts/hotpotqa_full/progress/bm25"))
    ingest_bm25_parser.add_argument("--batch-size", type=int, default=1000)
    ingest_bm25_parser.add_argument("--max-files", type=int, default=None)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--index", default="hotpotqa_docs_current")
    validate_parser.add_argument("--expected-count", type=int, default=None)

    search_parser = subparsers.add_parser("search")
    search_parser.add_argument("--index", default="hotpotqa_docs_current")
    search_parser.add_argument(
        "--method",
        choices=["bm25", "dense", "hybrid", "iterative_hybrid", "iterative_title", "iterative_sentence", "iterative_fast"],
        default="bm25",
    )
    search_parser.add_argument("--query", required=True)
    search_parser.add_argument("--top-k", type=int, default=5)
    search_parser.add_argument("--candidate-k", type=int, default=100)
    search_parser.add_argument("--num-candidates", type=int, default=1000)
    search_parser.add_argument("--model", default="BAAI/bge-small-en-v1.5")

    args = parser.parse_args()
    if args.command == "create-index":
        create_index(args)
    elif args.command == "create-bm25-index":
        create_bm25_index(args)
    elif args.command == "ingest":
        ingest(args)
    elif args.command == "ingest-bm25":
        ingest_bm25(args)
    elif args.command == "validate":
        validate_index(args)
    elif args.command == "search":
        search_index(args)


def create_index(args: argparse.Namespace) -> None:
    es = _client(args.url)
    if args.reset and es.indices.exists(index=args.index):
        es.indices.delete(index=args.index)
    if not es.indices.exists(index=args.index):
        es.indices.create(index=args.index, body=build_index_body(dims=args.dims, shards=args.shards))
    es.indices.put_alias(index=args.index, name=args.alias)
    print(json.dumps({"index": args.index, "alias": args.alias, "created": True}, indent=2))


def create_bm25_index(args: argparse.Namespace) -> None:
    es = _client(args.url)
    if args.reset and es.indices.exists(index=args.index):
        es.indices.delete(index=args.index)
    if not es.indices.exists(index=args.index):
        es.indices.create(index=args.index, body=build_bm25_index_body(shards=args.shards))
    es.indices.put_alias(index=args.index, name=args.alias)
    print(json.dumps({"index": args.index, "alias": args.alias, "created": True, "mode": "bm25"}, indent=2))


def ingest(args: argparse.Namespace) -> None:
    args.progress_dir.mkdir(parents=True, exist_ok=True)
    files = select_pending_files(args.staging_dir, args.progress_dir, max_files=args.max_files)
    es = _client(args.url)
    model = _embedding_model(args.model)
    ingested_files = []
    for path in files:
        docs = ingest_file(es, model, args.index, path, args.batch_size)
        done_marker_path(args.progress_dir, path).write_text(
            json.dumps({"file": path.name, "docs": docs}, indent=2), encoding="utf-8"
        )
        ingested_files.append({"file": path.name, "docs": docs})
    if ingested_files:
        es.indices.refresh(index=args.index)
    print(json.dumps({"index": args.index, "files": ingested_files}, indent=2))


def ingest_bm25(args: argparse.Namespace) -> None:
    args.progress_dir.mkdir(parents=True, exist_ok=True)
    files = select_pending_files(args.staging_dir, args.progress_dir, max_files=args.max_files)
    es = _client(args.url)
    ingested_files = []
    for path in files:
        docs = ingest_bm25_file(es, args.index, path, args.batch_size)
        done_marker_path(args.progress_dir, path).write_text(
            json.dumps({"file": path.name, "docs": docs}, indent=2), encoding="utf-8"
        )
        ingested_files.append({"file": path.name, "docs": docs})
    if ingested_files:
        es.indices.refresh(index=args.index)
    print(json.dumps({"index": args.index, "files": ingested_files, "mode": "bm25"}, indent=2))


def ingest_file(es: Any, model: Any, index: str, path: Path, batch_size: int) -> int:
    batch: list[dict[str, Any]] = []
    docs = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            batch.append(json.loads(line))
            if len(batch) >= batch_size:
                _flush_batch(es, model, index, batch)
                docs += len(batch)
                batch.clear()
    if batch:
        _flush_batch(es, model, index, batch)
        docs += len(batch)
    return docs


def ingest_bm25_file(es: Any, index: str, path: Path, batch_size: int) -> int:
    from elasticsearch import helpers

    batch: list[dict[str, Any]] = []
    docs = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            batch.append(json.loads(line))
            if len(batch) >= batch_size:
                helpers.bulk(es, [bm25_bulk_action(index, row) for row in batch], chunk_size=len(batch), request_timeout=120)
                docs += len(batch)
                batch.clear()
    if batch:
        helpers.bulk(es, [bm25_bulk_action(index, row) for row in batch], chunk_size=len(batch), request_timeout=120)
        docs += len(batch)
    return docs


def validate_index(args: argparse.Namespace) -> None:
    es = _client(args.url)
    count = int(es.count(index=args.index)["count"])
    result = {"index": args.index, "count": count, "expected_count": args.expected_count}
    if args.expected_count is not None:
        result["count_matches"] = count == args.expected_count
    print(json.dumps(result, indent=2))
    if args.expected_count is not None and count != args.expected_count:
        raise SystemExit(1)


def search_index(args: argparse.Namespace) -> None:
    retriever = ElasticsearchRetriever(
        es=_client(args.url),
        index=args.index,
        model_name=args.model,
        num_candidates=args.num_candidates,
    )
    if args.method in {"iterative_title", "iterative_sentence", "iterative_fast"}:
        mode = {"iterative_title": "title", "iterative_sentence": "sentence", "iterative_fast": "title"}[args.method]
        hits = retriever.search_iterative_hybrid(
            args.query,
            args.top_k,
            candidate_k=min(args.candidate_k, 30) if args.method == "iterative_fast" else args.candidate_k,
            first_hop_k=3 if args.method == "iterative_fast" else 5,
            second_hop_k=5 if args.method == "iterative_fast" else 10,
            expansion_mode=mode,
            dedupe_hop2=True,
        )
    else:
        hits = retriever.search(args.query, args.method, args.top_k, candidate_k=args.candidate_k)
    print(json.dumps({"query": args.query, "method": args.method, "results": hits}, ensure_ascii=False, indent=2))


def _flush_batch(es: Any, model: Any, index: str, rows: list[dict[str, Any]]) -> None:
    from elasticsearch import helpers

    embeddings = model.encode([row["embedding_text"] for row in rows], normalize_embeddings=True, convert_to_numpy=True)
    actions = [bulk_action(index, row, _vector_to_list(embeddings[idx])) for idx, row in enumerate(rows)]
    helpers.bulk(es, actions, chunk_size=len(actions), request_timeout=120)


def _client(url: str) -> Any:
    from elasticsearch import Elasticsearch

    return Elasticsearch(url, request_timeout=120)


def _embedding_model(model_name: str) -> Any:
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


def metadata_filters_from_args(args: argparse.Namespace) -> dict[str, str]:
    filters = {}
    for field in ('author', 'created_at_from', 'created_at_to', 'modified_at_from', 'modified_at_to'):
        value = getattr(args, field, None)
        if value:
            filters[field] = value
    return filters


def create_bm25_index(args: argparse.Namespace) -> None:
    es = _client(args.url)
    if args.reset and es.indices.exists(index=args.index):
        es.indices.delete(index=args.index)
    if not es.indices.exists(index=args.index):
        es.indices.create(
            index=args.index,
            body=build_bm25_index_body(shards=args.shards, include_metadata=getattr(args, 'metadata', False)),
        )
    es.indices.put_alias(index=args.index, name=args.alias)
    print(json.dumps({'index': args.index, 'alias': args.alias, 'created': True, 'mode': 'bm25'}, indent=2))


def search_index(args: argparse.Namespace) -> None:
    retriever = ElasticsearchRetriever(
        es=_client(args.url),
        index=args.index,
        model_name=args.model,
        num_candidates=args.num_candidates,
    )
    metadata_filters = metadata_filters_from_args(args)
    if args.method in {'iterative_title', 'iterative_sentence', 'iterative_fast'}:
        mode = {'iterative_title': 'title', 'iterative_sentence': 'sentence', 'iterative_fast': 'title'}[args.method]
        hits = retriever.search_iterative_hybrid(
            args.query,
            args.top_k,
            candidate_k=min(args.candidate_k, 30) if args.method == 'iterative_fast' else args.candidate_k,
            first_hop_k=3 if args.method == 'iterative_fast' else 5,
            second_hop_k=5 if args.method == 'iterative_fast' else 10,
            expansion_mode=mode,
            dedupe_hop2=True,
        )
    else:
        hits = retriever.search(
            args.query,
            args.method,
            args.top_k,
            candidate_k=args.candidate_k,
            metadata_filters=metadata_filters or None,
        )
    print(json.dumps({'query': args.query, 'method': args.method, 'results': hits}, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description='HotpotQA Elasticsearch baseline utilities')
    parser.add_argument('--url', default='http://localhost:9200')
    subparsers = parser.add_subparsers(dest='command', required=True)

    create_parser = subparsers.add_parser('create-index')
    create_parser.add_argument('--index', default='hotpotqa_docs_v1')
    create_parser.add_argument('--alias', default='hotpotqa_docs_current')
    create_parser.add_argument('--dims', type=int, default=384)
    create_parser.add_argument('--shards', type=int, default=1)
    create_parser.add_argument('--reset', action='store_true')

    create_bm25_parser = subparsers.add_parser('create-bm25-index')
    create_bm25_parser.add_argument('--index', default='hotpotqa_full_bm25_v1')
    create_bm25_parser.add_argument('--alias', default='hotpotqa_full_bm25_current')
    create_bm25_parser.add_argument('--shards', type=int, default=1)
    create_bm25_parser.add_argument('--reset', action='store_true')
    create_bm25_parser.add_argument('--metadata', action='store_true')

    ingest_parser = subparsers.add_parser('ingest')
    ingest_parser.add_argument('--index', default='hotpotqa_docs_v1')
    ingest_parser.add_argument('--staging-dir', type=Path, default=Path('artifacts/hotpotqa_full/staging'))
    ingest_parser.add_argument('--progress-dir', type=Path, default=Path('artifacts/hotpotqa_full/progress'))
    ingest_parser.add_argument('--model', default='BAAI/bge-small-en-v1.5')
    ingest_parser.add_argument('--batch-size', type=int, default=128)
    ingest_parser.add_argument('--max-files', type=int, default=None)

    ingest_bm25_parser = subparsers.add_parser('ingest-bm25')
    ingest_bm25_parser.add_argument('--index', default='hotpotqa_full_bm25_v1')
    ingest_bm25_parser.add_argument('--staging-dir', type=Path, default=Path('artifacts/hotpotqa_full/staging'))
    ingest_bm25_parser.add_argument('--progress-dir', type=Path, default=Path('artifacts/hotpotqa_full/progress/bm25'))
    ingest_bm25_parser.add_argument('--batch-size', type=int, default=1000)
    ingest_bm25_parser.add_argument('--max-files', type=int, default=None)

    validate_parser = subparsers.add_parser('validate')
    validate_parser.add_argument('--index', default='hotpotqa_docs_current')
    validate_parser.add_argument('--expected-count', type=int, default=None)

    search_parser = subparsers.add_parser('search')
    search_parser.add_argument('--index', default='hotpotqa_docs_current')
    search_parser.add_argument(
        '--method',
        choices=['bm25', 'dense', 'hybrid', 'iterative_hybrid', 'iterative_title', 'iterative_sentence', 'iterative_fast'],
        default='bm25',
    )
    search_parser.add_argument('--query', required=True)
    search_parser.add_argument('--top-k', type=int, default=5)
    search_parser.add_argument('--candidate-k', type=int, default=100)
    search_parser.add_argument('--num-candidates', type=int, default=1000)
    search_parser.add_argument('--model', default='BAAI/bge-small-en-v1.5')
    search_parser.add_argument('--author')
    search_parser.add_argument('--created-at-from')
    search_parser.add_argument('--created-at-to')
    search_parser.add_argument('--modified-at-from')
    search_parser.add_argument('--modified-at-to')

    args = parser.parse_args()
    if args.command == 'create-index':
        create_index(args)
    elif args.command == 'create-bm25-index':
        create_bm25_index(args)
    elif args.command == 'ingest':
        ingest(args)
    elif args.command == 'ingest-bm25':
        ingest_bm25(args)
    elif args.command == 'validate':
        validate_index(args)
    elif args.command == 'search':
        search_index(args)


def _vector_to_list(vector: Any) -> list[float]:
    if hasattr(vector, "astype"):
        vector = vector.astype(float)
    if hasattr(vector, "tolist"):
        return [float(value) for value in vector.tolist()]
    return [float(value) for value in vector]


if __name__ == "__main__":
    main()
