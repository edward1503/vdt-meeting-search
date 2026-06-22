from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path
from typing import Any

from src.core.config import settings
from src.evaluation.metrics import evaluate_rankings
from src.retrieval.base import SearchHit
from src.retrieval.elasticsearch_retriever import ElasticsearchRetriever

METHOD_MAP = {
    "es_bm25": "bm25",
    "es_dense": "dense",
    "es_hybrid": "hybrid",
    "es_iterative_hybrid": "iterative_hybrid",
    "es_iterative_title": "iterative_title",
    "es_iterative_sentence": "iterative_sentence",
    "es_iterative_fast": "iterative_fast",
}
TURBOVEC_METHODS = {"tv_dense", "tv_hybrid", "tv_filtered_hybrid", "tv_two_hop_bridge_rrf"}
ITERATIVE_MODES = {
    "iterative_hybrid": "context",
    "iterative_title": "title",
    "iterative_sentence": "sentence",
    "iterative_fast": "title",
}


def trec_line(query_id: str, doc_id: str, rank: int, score: float, method: str) -> str:
    return f"{query_id} Q0 {doc_id} {rank} {score:.6f} {method}"


def classify_method(method: str) -> str:
    if method in METHOD_MAP:
        return "es"
    if method in TURBOVEC_METHODS:
        return "turbovec"
    raise ValueError(f"Unsupported retrieval method: {method}")


def map_es_method(method: str) -> str:
    try:
        return METHOD_MAP[method]
    except KeyError as exc:
        raise ValueError(f"Unsupported Elasticsearch method: {method}") from exc


def build_retriever(kind: str, *, url: str, index: str, model_name: str, num_candidates: int) -> Any:
    es = _client(url)
    es_retriever = ElasticsearchRetriever(
        es=es,
        index=index,
        model_name=model_name,
        num_candidates=num_candidates,
        embedding_service_url=settings.embedding_service_url,
        embedding_timeout_seconds=settings.embedding_timeout_seconds,
    )
    if kind == "es":
        return es_retriever
    if kind == "turbovec":
        from src.retrieval.turbovec_retriever import TurboVecHybridRetriever

        return TurboVecHybridRetriever.from_paths(
            bm25_retriever=es_retriever,
            es=es,
            index=index,
            tv_index_path=str(settings.turbovec_index_path),
            model_name=model_name,
        )
    raise ValueError(f"Unsupported retriever kind: {kind}")


def run_benchmark(
    dataset_id: str,
    index: str,
    methods: list[str],
    top_k: int,
    max_queries: int | None,
    url: str,
    model_name: str,
    num_candidates: int,
    candidate_k: int,
    rrf_k: int,
    first_hop_k: int,
    second_hop_k: int,
    context_chars: int,
    run_dir: Path,
    beam_size: int = 3,
    max_bridge_terms: int = 8,
    query_file: Path | None = None,
    qrels_file: Path | None = None,
) -> dict[str, Any]:
    dataset = None if query_file is not None and qrels_file is not None else _load_ir_dataset(dataset_id)
    if query_file is None:
        queries = _load_queries(dataset, max_queries=max_queries)
        qrels = _load_qrels_file(qrels_file, set(queries)) if qrels_file else _load_qrels(dataset, set(queries))
    else:
        queries, source_query_ids = _load_query_file(query_file, max_queries=max_queries)
        if qrels_file:
            qrels = _load_qrels_file(qrels_file, set(queries))
        else:
            source_qrels = _load_qrels(dataset, set(source_query_ids.values()))
            qrels = {
                variant_id: source_qrels[source_id]
                for variant_id, source_id in source_query_ids.items()
                if source_id in source_qrels
            }
    run_dir.mkdir(parents=True, exist_ok=True)

    retrievers: dict[str, Any] = {}
    results = []
    for method in methods:
        kind = classify_method(method)
        retriever = retrievers.setdefault(
            kind,
            build_retriever(kind, url=url, index=index, model_name=model_name, num_candidates=num_candidates),
        )
        runs: dict[str, list[SearchHit]] = {}
        latencies: dict[str, float] = {}
        run_lines: list[str] = []
        for query_id, query_text in queries.items():
            start = time.perf_counter()
            raw_hits = _search_method(
                retriever,
                method,
                query_text,
                top_k,
                candidate_k=candidate_k,
                rrf_k=rrf_k,
                first_hop_k=first_hop_k,
                second_hop_k=second_hop_k,
                context_chars=context_chars,
                num_candidates=num_candidates,
                beam_size=beam_size,
                max_bridge_terms=max_bridge_terms,
            )
            latencies[query_id] = (time.perf_counter() - start) * 1000
            hits = [
                SearchHit(
                    doc_id=str(hit["doc_id"]),
                    score=float(hit.get("score", 0.0)),
                    rank=rank,
                    method=method,
                    hop=int(hit.get("hop", 1) or 1),
                    chain_rank=int(hit["chain_rank"]) if hit.get("chain_rank") is not None else None,
                    chain_doc_ids=tuple(str(doc_id) for doc_id in hit.get("chain_doc_ids", []) if str(doc_id)),
                )
                for rank, hit in enumerate(raw_hits[:top_k], start=1)
            ]
            runs[query_id] = hits
            run_lines.extend(trec_line(query_id, hit.doc_id, hit.rank, hit.score, method) for hit in hits)

        metrics = evaluate_rankings(qrels, runs, latencies, top_k)
        metrics.pop("per_query", None)
        run_path = run_dir / f"{method}_{_dataset_slug(dataset_id)}_top{top_k}.trec"
        run_path.write_text("\n".join(run_lines) + ("\n" if run_lines else ""), encoding="utf-8")
        results.append({"method": method, "metrics": metrics, "run_file": str(run_path)})

    return {
        "config": {
            "dataset_id": dataset_id,
            "index": index,
            "methods": methods,
            "top_k": top_k,
            "max_queries": max_queries,
            "model_name": model_name,
            "num_candidates": num_candidates,
            "candidate_k": candidate_k,
            "queries": len(queries),
            "rrf_k": rrf_k,
            "first_hop_k": first_hop_k,
            "second_hop_k": second_hop_k,
            "hop1_top_k": first_hop_k,
            "hop2_top_k": second_hop_k,
            "context_chars": context_chars,
            "beam_size": beam_size,
            "max_bridge_terms": max_bridge_terms,
            "query_file": str(query_file) if query_file else None,
            "qrels_file": str(qrels_file) if qrels_file else None,
        },
        "results": results,
    }


def _search_method(
    retriever: Any,
    method: str,
    query_text: str,
    top_k: int,
    *,
    candidate_k: int,
    rrf_k: int,
    first_hop_k: int,
    second_hop_k: int,
    context_chars: int,
    num_candidates: int,
    beam_size: int,
    max_bridge_terms: int,
) -> list[dict[str, Any]]:
    if classify_method(method) == "turbovec":
        if method == "tv_two_hop_bridge_rrf":
            return retriever.search_two_hop_bridge_rrf(
                query_text,
                top_k,
                hop1_top_k=first_hop_k,
                hop2_top_k=second_hop_k,
                beam_size=beam_size,
                max_bridge_terms=max_bridge_terms,
                candidate_k=candidate_k,
                rrf_k=rrf_k,
            )
        return retriever.search(query_text, method, top_k, candidate_k=candidate_k, rrf_k=rrf_k)
    es_method = map_es_method(method)
    if es_method == "iterative_hybrid":
        return retriever.search_iterative_hybrid(
            query_text,
            top_k,
            candidate_k=candidate_k,
            rrf_k=rrf_k,
            first_hop_k=first_hop_k,
            second_hop_k=second_hop_k,
            context_chars=context_chars,
        )
    if es_method in ITERATIVE_MODES:
        original_num_candidates = getattr(retriever, "num_candidates", num_candidates)
        effective_candidate_k = min(candidate_k, 30) if es_method == "iterative_fast" else candidate_k
        effective_num_candidates = min(num_candidates, 300) if es_method == "iterative_fast" else num_candidates
        retriever.num_candidates = effective_num_candidates
        try:
            return retriever.search_iterative_hybrid(
                query_text,
                top_k,
                candidate_k=effective_candidate_k,
                rrf_k=rrf_k,
                first_hop_k=min(first_hop_k, 3) if es_method == "iterative_fast" else first_hop_k,
                second_hop_k=min(second_hop_k, 5) if es_method == "iterative_fast" else second_hop_k,
                context_chars=context_chars,
                expansion_mode=ITERATIVE_MODES[es_method],
                dedupe_hop2=True,
            )
        finally:
            retriever.num_candidates = original_num_candidates
    return retriever.search(query_text, es_method, top_k, candidate_k=candidate_k, rrf_k=rrf_k)


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark HotpotQA retrieval")
    parser.add_argument("--dataset", default=settings.dataset_id)
    parser.add_argument("--index", default=settings.elasticsearch_index)
    parser.add_argument("--methods", default="es_bm25,tv_hybrid")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--max-queries", type=int, default=None)
    parser.add_argument("--url", default=settings.elasticsearch_url)
    parser.add_argument("--model", default=settings.embedding_model)
    parser.add_argument("--num-candidates", type=int, default=settings.elasticsearch_num_candidates)
    parser.add_argument("--candidate-k", type=int, default=100)
    parser.add_argument("--output", type=Path, default=Path("evaluation/results/retrieval_benchmark.json"))
    parser.add_argument("--run-dir", type=Path, default=Path("evaluation/runs"))
    parser.add_argument("--query-file", type=Path, default=None)
    parser.add_argument("--qrels-file", type=Path, default=None)
    parser.add_argument("--rrf-k", type=int, default=60)
    parser.add_argument("--first-hop-k", type=int, default=settings.multihop_first_hop)
    parser.add_argument("--second-hop-k", type=int, default=settings.multihop_second_hop)
    parser.add_argument("--context-chars", type=int, default=settings.multihop_context_chars)
    parser.add_argument("--beam-size", type=int, default=3)
    parser.add_argument("--max-bridge-terms", type=int, default=8)
    args = parser.parse_args()

    methods = [method.strip() for method in args.methods.split(",") if method.strip()]
    result = run_benchmark(
        dataset_id=args.dataset,
        index=args.index,
        methods=methods,
        top_k=args.top_k,
        max_queries=args.max_queries,
        url=args.url,
        model_name=args.model,
        num_candidates=args.num_candidates,
        candidate_k=args.candidate_k,
        rrf_k=args.rrf_k,
        first_hop_k=args.first_hop_k,
        second_hop_k=args.second_hop_k,
        context_chars=args.context_chars,
        run_dir=args.run_dir,
        beam_size=args.beam_size,
        max_bridge_terms=args.max_bridge_terms,
        query_file=args.query_file,
        qrels_file=args.qrels_file,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


def _load_ir_dataset(dataset_id: str):
    import ir_datasets

    dataset = ir_datasets.load(dataset_id)
    if not dataset.has_queries() or not dataset.has_qrels():
        raise ValueError(f"Dataset must provide queries and qrels: {dataset_id}")
    return dataset


def _load_queries(dataset: Any, max_queries: int | None) -> dict[str, str]:
    queries: dict[str, str] = {}
    for idx, query in enumerate(dataset.queries_iter()):
        if max_queries is not None and idx >= max_queries:
            break
        queries[str(query.query_id)] = str(getattr(query, "text", "") or "")
    return queries


def _load_query_file(path: Path, max_queries: int | None) -> tuple[dict[str, str], dict[str, str]]:
    queries: dict[str, str] = {}
    source_query_ids: dict[str, str] = {}
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for idx, row in enumerate(reader):
            if max_queries is not None and idx >= max_queries:
                break
            query_id = str(row.get("variant_query_id") or row.get("query_id") or "").strip()
            if not query_id:
                raise ValueError(f"Query file row is missing query id: {path}")
            queries[query_id] = str(row["query"])
            source_query_ids[query_id] = str(row.get("source_query_id") or query_id)
    return queries, source_query_ids


def _load_qrels(dataset: Any, query_ids: set[str]) -> dict[str, dict[str, float]]:
    qrels: dict[str, dict[str, float]] = {query_id: {} for query_id in query_ids}
    for qrel in dataset.qrels_iter():
        query_id = str(qrel.query_id)
        if query_id not in qrels:
            continue
        relevance = float(getattr(qrel, "relevance", 1.0))
        if relevance > 0:
            qrels[query_id][str(qrel.doc_id)] = relevance
    return {query_id: scores for query_id, scores in qrels.items() if scores}


def _load_qrels_file(path: Path, query_ids: set[str]) -> dict[str, dict[str, float]]:
    qrels: dict[str, dict[str, float]] = {query_id: {} for query_id in query_ids}
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            query_id = str(row["query_id"])
            if query_id not in qrels:
                continue
            relevance = float(row.get("relevance", 1.0))
            if relevance > 0:
                qrels[query_id][str(row["doc_id"])] = relevance
    return {query_id: scores for query_id, scores in qrels.items() if scores}


def _client(url: str) -> Any:
    from elasticsearch import Elasticsearch

    return Elasticsearch(url, request_timeout=120)


def _dataset_slug(dataset_id: str) -> str:
    return dataset_id.replace("/", "_")


if __name__ == "__main__":
    main()
