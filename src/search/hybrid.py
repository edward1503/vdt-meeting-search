"""Hybrid BM25 + kNN search with app-layer RRF and meeting aggregation."""

from __future__ import annotations

from collections import defaultdict

from elasticsearch import Elasticsearch

from src.core.config import settings
from src.embedding.model import embed_texts
from src.indexing.bulk_index import DEFAULT_INDEX


def search_meetings(
    query: str,
    index_name: str = DEFAULT_INDEX,
    es_host: str = settings.es_host,
    top_k: int = 10,
    mode: str = "hybrid",
    source: str | None = None,
    speaker: str | None = None,
    date_range: list[str] | None = None,
    parse_prompt: bool = False,
    channel: str = "content",
    num_candidates: int | None = None,
) -> dict:
    semantic_query = query
    parsed: list[str] = []
    if parse_prompt:
        from src.search.query_understanding import parse_prompt as _parse
        understood = _parse(query)
        semantic_query = understood["semantic_query"]
        parsed = understood["parsed"]
        # Lọc mềm: chỉ dùng filter tự tách khi caller chưa truyền tường minh.
        source = source or understood["filters"].get("source")
        speaker = speaker or understood["filters"].get("speaker")
        date_range = date_range or understood["filters"].get("date_range")

    es = Elasticsearch(es_host, request_timeout=60)
    try:
        filters = _filters(source=source, speaker=speaker, date_range=date_range)
        bm25_hits = _bm25(es, index_name, semantic_query, filters, size=max(50, top_k * 5), channel=channel) if mode in {"bm25", "hybrid"} else []
        knn_hits = _knn(es, index_name, semantic_query, filters, size=max(50, top_k * 5), channel=channel, num_candidates=num_candidates) if mode in {"semantic", "hybrid"} else []
        if mode == "bm25":
            fused = _rank_only(bm25_hits)
        elif mode == "semantic":
            fused = _rank_only(knn_hits)
        else:
            fused = _rrf([bm25_hits, knn_hits])
        meetings = _aggregate_meetings(fused, top_k=top_k)
        return {
            "query": query,
            "mode": mode,
            "filters": {"source": source, "speaker": speaker, "date_range": date_range},
            "parsed": parsed,
            "results": meetings,
            "debug": {"bm25_hits": len(bm25_hits), "knn_hits": len(knn_hits)},
        }
    finally:
        es.close()


def _filters(source: str | None = None, speaker: str | None = None, date_range: list[str] | None = None) -> list[dict]:
    filters = []
    if source:
        filters.append({"term": {"source": source}})
    if speaker:
        filters.append({"term": {"speakers": speaker}})
    if date_range:
        filters.append({"range": {"date": {"gte": date_range[0], "lte": date_range[1]}}})
    return filters


def _bm25(es: Elasticsearch, index_name: str, query: str, filters: list[dict], size: int, channel: str = "content") -> list[dict]:
    fields = {
        "content": ["content_text^3", "metadata_text", "title"],
        "metadata": ["metadata_text^3", "title"],
    }[channel]
    body = {
        "size": size,
        "query": {
            "bool": {
                "must": [{
                    "multi_match": {
                        "query": query,
                        "fields": fields,
                    }
                }],
                "filter": filters,
            }
        },
        "highlight": {"fields": {"content_text": {"fragment_size": 180, "number_of_fragments": 2}}},
    }
    return _normalize_hits(es.search(index=index_name, body=body)["hits"]["hits"])


def _knn(es: Elasticsearch, index_name: str, query: str, filters: list[dict], size: int, channel: str = "content", num_candidates: int | None = None) -> list[dict]:
    field = "metadata_embedding" if channel == "metadata" else "content_embedding"
    vector = embed_texts([query])[0]
    body = {
        "knn": {
            "field": field,
            "query_vector": vector,
            "k": size,
            "num_candidates": num_candidates or max(size * 4, 100),
            "filter": filters,
        },
        "size": size,
    }
    return _normalize_hits(es.search(index=index_name, body=body)["hits"]["hits"])


def _normalize_hits(hits: list[dict]) -> list[dict]:
    out = []
    for rank, hit in enumerate(hits, start=1):
        source = hit["_source"]
        out.append({
            "rank": rank,
            "score": hit.get("_score") or 0.0,
            "chunk_id": source.get("chunk_id"),
            "meeting_id": source.get("meeting_id"),
            "raw_meeting_id": source.get("raw_meeting_id"),
            "source": source.get("source"),
            "title": source.get("title"),
            "text": source.get("content_text"),
            "speakers": source.get("speakers") or [],
            "date": source.get("date"),
            "start_time": source.get("start_time"),
            "time_start": source.get("time_start"),
            "time_end": source.get("time_end"),
            "highlight": hit.get("highlight", {}).get("content_text", []),
        })
    return out


def _rank_only(hits: list[dict]) -> list[dict]:
    return [{**hit, "rrf_score": 1.0 / hit["rank"]} for hit in hits]


def _rrf(hit_lists: list[list[dict]], rank_constant: int = 60) -> list[dict]:
    best_hit_by_chunk: dict[str, dict] = {}
    scores: defaultdict[str, float] = defaultdict(float)
    for hits in hit_lists:
        for rank, hit in enumerate(hits, start=1):
            chunk_id = hit["chunk_id"]
            scores[chunk_id] += 1.0 / (rank_constant + rank)
            best_hit_by_chunk.setdefault(chunk_id, hit)
    fused = []
    for chunk_id, score in scores.items():
        fused.append({**best_hit_by_chunk[chunk_id], "rrf_score": score})
    return sorted(fused, key=lambda hit: hit["rrf_score"], reverse=True)


def _aggregate_meetings(hits: list[dict], top_k: int) -> list[dict]:
    grouped: dict[str, dict] = {}
    for hit in hits:
        meeting_id = hit["meeting_id"]
        group = grouped.setdefault(meeting_id, {
            "meeting_id": meeting_id,
            "raw_meeting_id": hit.get("raw_meeting_id"),
            "source": hit.get("source"),
            "title": hit.get("title"),
            "date": hit.get("date"),
            "start_time": hit.get("start_time"),
            "participants": [],
            "score": 0.0,
            "evidence": [],
        })
        group["score"] = max(group["score"], hit.get("rrf_score", 0.0))
        for speaker in hit.get("speakers") or []:
            if speaker not in group["participants"]:
                group["participants"].append(speaker)
        if len(group["evidence"]) < 3:
            group["evidence"].append({
                "chunk_id": hit.get("chunk_id"),
                "score": hit.get("rrf_score", hit.get("score", 0.0)),
                "text": hit.get("text"),
                "highlight": hit.get("highlight"),
                "speakers": hit.get("speakers"),
                "time_start": hit.get("time_start"),
                "time_end": hit.get("time_end"),
            })
    for group in grouped.values():
        group["score"] += 0.01 * max(0, len(group["evidence"]) - 1)
    return sorted(grouped.values(), key=lambda group: group["score"], reverse=True)[:top_k]
