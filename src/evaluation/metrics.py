from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Any

from src.retrieval.base import SearchHit
from src.retrieval.utils import dcg


@dataclass(frozen=True)
class QueryEval:
    query_id: str
    returned: list[str]
    relevant: list[str]
    precision: float
    recall: float
    mrr: float
    ndcg: float
    full_support: float
    latency_ms: float


def evaluate_rankings(
    qrels: dict[str, dict[str, float]],
    runs: dict[str, list[SearchHit]],
    latencies_ms: dict[str, float],
    k: int,
) -> dict[str, Any]:
    per_query = []
    support_cutoffs = _support_cutoffs(k)
    support_by_cutoff: dict[int, list[float]] = {cutoff: [] for cutoff in support_cutoffs}
    chain_reciprocal_ranks: list[float] = []
    chain_recall_at_1: list[float] = []
    chain_recall_at_5: list[float] = []
    has_chain_output = False
    for query_id, relevant_scores in qrels.items():
        relevant = {doc_id for doc_id, score in relevant_scores.items() if score > 0}
        hits = runs.get(query_id, [])[:k]
        returned = [hit.doc_id for hit in hits]
        hit_flags = [1.0 if doc_id in relevant else 0.0 for doc_id in returned]
        precision = sum(hit_flags) / max(1, k)
        recall = sum(hit_flags) / max(1, len(relevant))
        mrr = next((1.0 / rank for rank, doc_id in enumerate(returned, start=1) if doc_id in relevant), 0.0)
        gains = [relevant_scores.get(doc_id, 0.0) for doc_id in returned]
        ideal_gains = sorted(relevant_scores.values(), reverse=True)[:k]
        ndcg = dcg(gains) / max(1e-9, dcg(ideal_gains))
        full_support = 1.0 if relevant and relevant.issubset(set(returned)) else 0.0
        for cutoff in support_cutoffs:
            support_by_cutoff[cutoff].append(_full_support_at(returned, relevant, cutoff))

        ranked_chains = _extract_ranked_chains(hits)
        if ranked_chains:
            has_chain_output = True
        chain_rank = _first_full_support_chain_rank(ranked_chains, relevant)
        chain_reciprocal_ranks.append(1.0 / chain_rank if chain_rank else 0.0)
        chain_recall_at_1.append(1.0 if chain_rank and chain_rank <= 1 else 0.0)
        chain_recall_at_5.append(1.0 if chain_rank and chain_rank <= 5 else 0.0)

        per_query.append(
            QueryEval(
                query_id=query_id,
                returned=returned,
                relevant=sorted(relevant),
                precision=precision,
                recall=recall,
                mrr=mrr,
                ndcg=ndcg,
                full_support=full_support,
                latency_ms=latencies_ms.get(query_id, 0.0),
            )
        )

    latencies = [item.latency_ms for item in per_query]
    total_latency_sec = sum(latencies) / 1000
    metrics = {
        f"precision@{k}": round(_mean([item.precision for item in per_query]), 4),
        f"recall@{k}": round(_mean([item.recall for item in per_query]), 4),
        f"mrr@{k}": round(_mean([item.mrr for item in per_query]), 4),
        f"ndcg@{k}": round(_mean([item.ndcg for item in per_query]), 4),
        "latency_p50_ms": round(_percentile(latencies, 50), 4),
        "latency_p95_ms": round(_percentile(latencies, 95), 4),
        "latency_p99_ms": round(_percentile(latencies, 99), 4),
        "qps": round(len(per_query) / max(1e-9, total_latency_sec), 4),
        "queries": len(per_query),
        "per_query": [item.__dict__ for item in per_query],
    }
    for cutoff in support_cutoffs:
        metrics[f"full_support_recall@{cutoff}"] = round(_mean(support_by_cutoff[cutoff]), 4)
    if has_chain_output:
        metrics["chain_recall@1"] = round(_mean(chain_recall_at_1), 4)
        metrics["chain_recall@5"] = round(_mean(chain_recall_at_5), 4)
        metrics["chain_mrr"] = round(_mean(chain_reciprocal_ranks), 4)
    return metrics


def _support_cutoffs(k: int) -> list[int]:
    return sorted({cutoff for cutoff in (2, 5, k) if 0 < cutoff <= k})


def _full_support_at(returned: list[str], relevant: set[str], cutoff: int) -> float:
    if not relevant:
        return 0.0
    return 1.0 if relevant.issubset(set(returned[:cutoff])) else 0.0


def _extract_ranked_chains(hits: list[SearchHit]) -> list[tuple[str, ...]]:
    chains: dict[tuple[str, ...], int] = {}
    for hit in hits:
        if not hit.chain_doc_ids:
            continue
        chain = tuple(str(doc_id) for doc_id in hit.chain_doc_ids if str(doc_id))
        if not chain:
            continue
        rank = hit.chain_rank if hit.chain_rank is not None else hit.rank
        chains[chain] = min(chains.get(chain, rank), rank)
    return [chain for chain, _ in sorted(chains.items(), key=lambda item: item[1])]


def _first_full_support_chain_rank(ranked_chains: list[tuple[str, ...]], relevant: set[str]) -> int | None:
    if not relevant:
        return None
    for rank, chain in enumerate(ranked_chains, start=1):
        if relevant.issubset(set(chain)):
            return rank
    return None


def _mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def _percentile(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, math.ceil((percentile / 100) * len(ordered)) - 1))
    return ordered[idx]
