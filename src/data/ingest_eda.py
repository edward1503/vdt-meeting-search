from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
from typing import Any

TOKEN_RE = re.compile(r"[A-Za-z0-9]+")
GIB = 1024**3


def make_ingest_content(title: str | None, text: str | None) -> str:
    clean_title = _collapse_whitespace(title)
    clean_text = _collapse_whitespace(text)
    if clean_title and clean_text:
        return f"{clean_title}\n{clean_text}"
    return clean_title or clean_text


def estimate_ingest_plan(
    total_docs: int,
    avg_source_bytes: float,
    embedding_dims: int,
    shard_target_gb: float = 30,
    staging_docs_per_file: int = 50_000,
    bulk_target_mb: float = 10,
) -> dict[str, Any]:
    source_gb = total_docs * avg_source_bytes / GIB
    embedding_float32_gb = total_docs * embedding_dims * 4 / GIB
    embedding_float16_gb = total_docs * embedding_dims * 2 / GIB

    # Bulk payload is JSON, so vector values cost much more than their binary size.
    estimated_bulk_doc_bytes = avg_source_bytes + embedding_dims * 10 + 256
    recommended_bulk_docs = max(1, int((bulk_target_mb * 1024 * 1024) // max(1, estimated_bulk_doc_bytes)))

    estimated_index_gb = source_gb + embedding_float32_gb * 1.5
    recommended_primary_shards = max(1, math.ceil(estimated_index_gb / max(1e-9, shard_target_gb)))

    return {
        "total_docs": total_docs,
        "avg_source_bytes": round(avg_source_bytes, 3),
        "estimated_source_gb": _round_gb(source_gb),
        "embedding_float32_gb": _round_gb(embedding_float32_gb),
        "embedding_float16_gb": _round_gb(embedding_float16_gb),
        "estimated_index_gb": _round_gb(estimated_index_gb),
        "staging_docs_per_file": staging_docs_per_file,
        "staging_file_count": math.ceil(total_docs / max(1, staging_docs_per_file)),
        "bulk_target_mb": bulk_target_mb,
        "estimated_bulk_doc_bytes": round(estimated_bulk_doc_bytes, 3),
        "recommended_bulk_docs": recommended_bulk_docs,
        "shard_target_gb": shard_target_gb,
        "recommended_primary_shards": recommended_primary_shards,
    }


class IngestEdaAccumulator:
    def __init__(self, sample_limit: int = 8, longest_limit: int = 8) -> None:
        self.sample_limit = sample_limit
        self.longest_limit = longest_limit
        self.iterated = 0
        self.missing = {"title": 0, "text": 0, "url": 0, "content": 0}
        self.title_token_lengths: list[int] = []
        self.text_token_lengths: list[int] = []
        self.content_token_lengths: list[int] = []
        self.content_char_lengths: list[int] = []
        self.source_bytes: list[int] = []
        self.samples: list[dict[str, Any]] = []
        self.longest_docs: list[dict[str, Any]] = []
        self._seen_doc_ids: set[str] = set()
        self._duplicate_doc_ids: set[str] = set()
        self._seen_content_hashes: set[str] = set()
        self._duplicate_content_hashes: set[str] = set()

    def add(self, raw_doc: Any) -> None:
        doc_id = str(getattr(raw_doc, "doc_id"))
        title = str(getattr(raw_doc, "title", "") or "")
        text = str(getattr(raw_doc, "text", "") or "")
        url = str(getattr(raw_doc, "url", "") or "")
        content = make_ingest_content(title, text)

        self.iterated += 1
        self.missing["title"] += int(not title)
        self.missing["text"] += int(not text)
        self.missing["url"] += int(not url)
        self.missing["content"] += int(not content)

        title_tokens = _token_count(title)
        text_tokens = _token_count(text)
        content_tokens = _token_count(content)
        content_chars = len(content)
        source_bytes = len(
            json.dumps(
                {"doc_id": doc_id, "title": title, "text": text, "url": url, "content": content},
                ensure_ascii=False,
            ).encode("utf-8")
        )

        self.title_token_lengths.append(title_tokens)
        self.text_token_lengths.append(text_tokens)
        self.content_token_lengths.append(content_tokens)
        self.content_char_lengths.append(content_chars)
        self.source_bytes.append(source_bytes)

        if doc_id in self._seen_doc_ids:
            self._duplicate_doc_ids.add(doc_id)
        self._seen_doc_ids.add(doc_id)

        content_hash = hashlib.blake2b(content.encode("utf-8"), digest_size=16).hexdigest()
        if content_hash in self._seen_content_hashes:
            self._duplicate_content_hashes.add(content_hash)
        self._seen_content_hashes.add(content_hash)

        sample = {
            "doc_id": doc_id,
            "title": title,
            "url": url,
            "content_tokens": content_tokens,
            "content_chars": content_chars,
            "source_bytes": source_bytes,
            "content_preview": _preview(content),
        }
        if len(self.samples) < self.sample_limit:
            self.samples.append(sample)
        self._add_longest(sample)

    def summary(
        self,
        total_docs: int | None = None,
        embedding_dims: int = 384,
        shard_target_gb: float = 30,
        staging_docs_per_file: int = 50_000,
        bulk_target_mb: float = 10,
    ) -> dict[str, Any]:
        docs_for_estimate = int(total_docs or self.iterated)
        avg_source_bytes = statistics.mean(self.source_bytes) if self.source_bytes else 0.0
        return {
            "iterated": self.iterated,
            "total_docs": total_docs,
            "missing": dict(self.missing),
            "duplicates": {
                "doc_id_duplicate_count": len(self._duplicate_doc_ids),
                "content_hash_duplicate_count": len(self._duplicate_content_hashes),
            },
            "title_token_lengths": length_summary(self.title_token_lengths),
            "text_token_lengths": length_summary(self.text_token_lengths),
            "content_token_lengths": length_summary(self.content_token_lengths),
            "content_char_lengths": length_summary(self.content_char_lengths),
            "source_bytes": length_summary(self.source_bytes),
            "samples": list(self.samples),
            "longest_docs": sorted(self.longest_docs, key=lambda item: item["content_tokens"], reverse=True),
            "ingest_plan": estimate_ingest_plan(
                total_docs=docs_for_estimate,
                avg_source_bytes=avg_source_bytes,
                embedding_dims=embedding_dims,
                shard_target_gb=shard_target_gb,
                staging_docs_per_file=staging_docs_per_file,
                bulk_target_mb=bulk_target_mb,
            ),
        }

    def _add_longest(self, sample: dict[str, Any]) -> None:
        self.longest_docs.append(sample)
        self.longest_docs.sort(key=lambda item: item["content_tokens"], reverse=True)
        del self.longest_docs[self.longest_limit :]


def render_ingest_markdown(report: dict[str, Any]) -> str:
    metadata = report.get("metadata", {})
    documents = report.get("documents", {})
    ingest_plan = documents.get("ingest_plan", {})
    splits = report.get("splits", [])
    lines = [
        "# HotpotQA Full Ingest EDA",
        "",
        "## Dataset",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Dataset | {report.get('dataset_id', '')} |",
        f"| Docs count | {_fmt(metadata.get('docs_count'))} |",
        f"| Queries count | {_fmt(metadata.get('queries_count'))} |",
        f"| Qrels count | {_fmt(metadata.get('qrels_count'))} |",
        f"| Docs iterated for EDA | {_fmt(documents.get('iterated'))} |",
        "",
        "## Document Profile",
        "",
    ]
    if documents.get("skipped"):
        lines.extend(["Docs scan skipped: " + str(documents.get("skip_reason", "not provided")), ""])
    lines.extend(["| Metric | Value |", "|---|---|"])
    for key, value in documents.get("missing", {}).items():
        lines.append(f"| missing.{key} | {_fmt(value)} |")
    for key, value in documents.get("duplicates", {}).items():
        lines.append(f"| duplicates.{key} | {_fmt(value)} |")
    for key in ["p50", "p95", "p99", "max", "avg"]:
        lines.append(f"| content_tokens.{key} | {_fmt(documents.get('content_token_lengths', {}).get(key))} |")
    lines.append(f"| source_bytes.avg | {_fmt(documents.get('source_bytes', {}).get('avg'))} |")

    lines.extend(
        [
            "",
            "## Ingest Plan Estimate",
            "",
            "| Field | Value |",
            "|---|---|",
        ]
    )
    for key in [
        "recommended_primary_shards",
        "recommended_bulk_docs",
        "staging_file_count",
        "embedding_float32_gb",
        "embedding_float16_gb",
        "estimated_source_gb",
        "estimated_index_gb",
    ]:
        if key in ingest_plan:
            lines.append(f"| {key} | {_fmt(ingest_plan.get(key))} |")

    if splits:
        lines.extend(["", "## Query/Qrel Splits", "", "| Dataset | Queries | Qrels |", "|---|---|---|"])
        for split in splits:
            lines.append(
                f"| {split.get('dataset_id', '')} | {_fmt(split.get('queries_count'))} | {_fmt(split.get('qrels_count'))} |"
            )

    lines.extend(
        [
            "",
            "## Ingest Implications",
            "",
            "- Use one Elasticsearch index with text fields and one dense_vector field.",
            "- Build staging JSONL shards before embedding so workers can resume by shard.",
            "- Use doc_id as Elasticsearch _id to make reruns idempotent.",
            "- Disable refresh and replicas during initial bulk ingest, then restore after final count validation.",
        ]
    )
    return "\n".join(lines) + "\n"


def length_summary(values: list[int | float]) -> dict[str, int | float | None]:
    if not values:
        return {"min": None, "p50": None, "p90": None, "p95": None, "p99": None, "max": None, "avg": None}
    ordered = sorted(values)
    return {
        "min": min(values),
        "p50": _percentile(ordered, 50),
        "p90": _percentile(ordered, 90),
        "p95": _percentile(ordered, 95),
        "p99": _percentile(ordered, 99),
        "max": max(values),
        "avg": round(statistics.mean(values), 3),
    }


def _collapse_whitespace(value: str | None) -> str:
    return " ".join(str(value or "").split())


def _token_count(value: str | None) -> int:
    return len(TOKEN_RE.findall(str(value or "")))


def _percentile(ordered: list[int | float], p: int) -> int | float:
    idx = min(len(ordered) - 1, max(0, math.ceil(p / 100 * len(ordered)) - 1))
    return ordered[idx]


def _preview(value: str, max_chars: int = 360) -> str:
    text = _collapse_whitespace(value)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def _round_gb(value: float) -> float:
    if value == 0:
        return 0.0
    if abs(value) < 0.001:
        return round(value, 6)
    return round(value, 3)


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{value:,.3f}".rstrip("0").rstrip(".")
    return str(value)
