from __future__ import annotations

import argparse
import collections
import html
import json
import math
import re
import statistics
import time
from pathlib import Path
from typing import Any, Iterable, Sequence

TOKEN_RE = re.compile(r"[A-Za-z0-9]+")

PAPER_REFERENCES = [
    {
        "name": "HotpotQA original paper",
        "url": "https://aclanthology.org/D18-1259/",
        "note": "Defines bridge/comparison multi-hop QA, supporting facts, and explainable QA setting.",
    },
    {
        "name": "HotpotQA official dataset/wiki preprocessing",
        "url": "https://hotpotqa.github.io/wiki-readme.html",
        "note": "Describes processed Wikipedia pages with title, url, sentence text, hyperlinks, and char offsets.",
    },
    {
        "name": "BEIR benchmark paper",
        "url": "https://arxiv.org/abs/2104.08663",
        "note": "Standardizes heterogeneous retrieval datasets including HotpotQA into corpus/query/qrels evaluation.",
    },
    {
        "name": "BEIR repository data format",
        "url": "https://github.com/beir-cellar/beir",
        "note": "Uses corpus.jsonl, queries.jsonl, and qrels TSV conventions for retrieval benchmarks.",
    },
    {
        "name": "Multi-hop Dense Retrieval",
        "url": "https://arxiv.org/abs/2009.12756",
        "note": "Retrieves evidence chains with hop-conditioned dense retrieval for open-domain multi-hop QA.",
    },
    {
        "name": "DrKIT",
        "url": "https://arxiv.org/abs/2002.10640",
        "note": "Shows an entity-centric differentiable retrieval/reasoning direction relevant to bridge questions.",
    },
]

PIPELINE_RESEARCH = [
    {
        "name": "HotpotQA",
        "url": "https://aclanthology.org/D18-1259/",
        "pipeline": "Dataset được thiết kế cho bridge/comparison multi-hop QA và có supporting facts ở mức sentence.",
        "takeaway": "Đừng chỉ show top-1 doc; phải inspect đủ evidence chain và đo đủ supporting documents.",
    },
    {
        "name": "BEIR format",
        "url": "https://github.com/beir-cellar/beir",
        "pipeline": "Chuẩn hóa retrieval thành corpus, queries, qrels để benchmark nDCG/Recall/MRR/Precision.",
        "takeaway": "Giữ pipeline tách loader/index/retriever/evaluator; qrels là contract đánh giá.",
    },
    {
        "name": "GoldEn Retriever",
        "url": "https://arxiv.org/abs/1910.07000",
        "pipeline": "Lặp giữa đọc context đã retrieve và sinh query mới để tìm missing entity/document.",
        "takeaway": "Iterative query expansion nên dựa trên evidence hop 1, không nối bừa toàn bộ top-k.",
    },
    {
        "name": "Multi-hop Dense Retrieval",
        "url": "https://arxiv.org/abs/2009.12756",
        "pipeline": "Retrieve hop 1 rồi condition hop 2 bằng evidence đã tìm được để học evidence chain.",
        "takeaway": "Dense baseline nâng cấp nên đánh giá theo chain/full_support_recall@k, không chỉ doc recall rời rạc.",
    },
    {
        "name": "Baleen",
        "url": "https://arxiv.org/abs/2101.00436",
        "pipeline": "Condensed retrieval: sau mỗi hop tóm gọn passages đã retrieve thành context nhỏ để truy hồi tiếp.",
        "takeaway": "Khi lên full corpus, phải giới hạn state giữa các hop để search space không phình theo cấp số nhân.",
    },
    {
        "name": "IRCoT",
        "url": "https://arxiv.org/abs/2212.10509",
        "pipeline": "Interleave retrieval với từng reasoning step; step mới lại dẫn retrieval mới.",
        "takeaway": "Sau baseline, có thể dùng reasoning-step/query-step làm debug view cho câu hỏi bridge khó.",
    },
    {
        "name": "DrKIT",
        "url": "https://arxiv.org/abs/2002.10640",
        "pipeline": "Entity-centric retrieval/reasoning bằng virtual KB từ entity mentions và linking.",
        "takeaway": "Bridge questions nên có entity-aware expansion hoặc entity logging để biết hop nào bị đứt.",
    },
]


def percentile(values: list[int | float], p: int) -> int | float | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, math.ceil(p / 100 * len(ordered)) - 1))
    return ordered[idx]


def length_summary(values: list[int | float]) -> dict[str, int | float | None]:
    if not values:
        return {"min": None, "p50": None, "p90": None, "p95": None, "p99": None, "max": None, "avg": None}
    return {
        "min": min(values),
        "p50": percentile(values, 50),
        "p90": percentile(values, 90),
        "p95": percentile(values, 95),
        "p99": percentile(values, 99),
        "max": max(values),
        "avg": round(statistics.mean(values), 3),
    }


def tokens(text: str | None) -> list[str]:
    return TOKEN_RE.findall(str(text or "").lower())


def token_overlap_ratio(query: str, document: str) -> float:
    query_tokens = set(tokens(query))
    if not query_tokens:
        return 0.0
    doc_tokens = set(tokens(document))
    return round(len(query_tokens & doc_tokens) / len(query_tokens), 3)


def safe_count(dataset: Any, method_name: str) -> int | str | None:
    try:
        return getattr(dataset, method_name)()
    except AttributeError:
        return None
    except Exception as exc:  # pragma: no cover - depends on local cache/download state.
        return f"ERROR: {type(exc).__name__}: {str(exc)[:200]}"


def iter_limited(items: Iterable[Any], limit: int | None):
    for idx, item in enumerate(items):
        if limit is not None and idx >= limit:
            break
        yield item


def preview(value: Any, max_chars: int = 360) -> str:
    text = str(value if value is not None else "")
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def record_fields(record: Any) -> list[str]:
    if hasattr(record, "_fields"):
        return [str(field) for field in record._fields]
    if hasattr(record, "_asdict"):
        return [str(field) for field in record._asdict().keys()]
    if hasattr(record, "__dataclass_fields__"):
        return [str(field) for field in record.__dataclass_fields__.keys()]
    if hasattr(record, "__dict__"):
        return [str(field) for field in vars(record).keys() if not field.startswith("_")]
    return []


def schema_for_record(record: Any) -> dict[str, Any]:
    fields = record_fields(record)
    return {
        "type": type(record).__name__,
        "fields": fields,
        "values": {field: preview(getattr(record, field, "")) for field in fields},
        "repr": preview(repr(record), 700),
    }


def field_coverage(records: Sequence[Any], fields: Sequence[str]) -> dict[str, dict[str, int | float]]:
    total = len(records)
    coverage: dict[str, dict[str, int | float]] = {}
    for field in fields:
        present = 0
        non_empty = 0
        for record in records:
            if hasattr(record, field):
                present += 1
                value = getattr(record, field)
                if value not in (None, "", [], {}):
                    non_empty += 1
        coverage[field] = {
            "present": present,
            "non_empty": non_empty,
            "missing": total - present,
            "empty": present - non_empty,
            "non_empty_ratio": round(non_empty / total, 3) if total else 0.0,
        }
    return coverage


def classify_question(text: str) -> list[str]:
    lowered = text.lower()
    labels: list[str] = []
    if " both " in f" {lowered} " or lowered.startswith("both "):
        labels.append("comparison/both")
    if lowered.startswith("which") or "which" in lowered:
        labels.append("which/bridge")
    for word in ["what", "who", "where", "when", "why", "how"]:
        if lowered.startswith(word) or f" {word} " in lowered:
            labels.append(word)
            break
    if any(clue in lowered for clue in ["written by", "located", "founded", "depicts", "translated", "honoree", "same", "occupation"]):
        labels.append("explicit relation clue")
    return labels or ["other"]


def build_support_examples(
    queries: Sequence[Any],
    qrels: Sequence[Any],
    docs_by_id: dict[str, Any],
    max_examples: int = 10,
) -> list[dict[str, Any]]:
    qrels_by_query: dict[str, list[str]] = collections.defaultdict(list)
    for qrel in qrels:
        relevance = float(getattr(qrel, "relevance", 1.0))
        if relevance > 0:
            qrels_by_query[str(getattr(qrel, "query_id"))].append(str(getattr(qrel, "doc_id")))

    examples: list[dict[str, Any]] = []
    for query in queries:
        query_id = str(getattr(query, "query_id"))
        support_ids = qrels_by_query.get(query_id, [])
        if not support_ids:
            continue
        query_text = str(getattr(query, "text", "") or "")
        support_docs = []
        for doc_id in support_ids:
            doc = docs_by_id.get(doc_id)
            if doc is None:
                support_docs.append({"doc_id": doc_id, "missing_from_sample": True})
                continue
            title = str(getattr(doc, "title", "") or "")
            text = str(getattr(doc, "text", "") or "")
            support_docs.append(
                {
                    "doc_id": doc_id,
                    "title": title,
                    "text_preview": preview(text, 500),
                    "text_tokens": len(tokens(text)),
                    "query_token_overlap": token_overlap_ratio(query_text, f"{title} {text}"),
                }
            )
        examples.append(
            {
                "query_id": query_id,
                "query": query_text,
                "support_doc_count": len(support_ids),
                "support_docs": support_docs,
            }
        )
        if len(examples) >= max_examples:
            break
    return examples


def analyze_dataset(
    dataset_id: str,
    sample_docs: int | None,
    sample_queries: int | None,
    skip_docs: bool,
    metadata_only: bool,
    support_examples: int,
) -> dict[str, Any]:
    import ir_datasets

    started = time.perf_counter()
    dataset = ir_datasets.load(dataset_id)
    report: dict[str, Any] = {
        "dataset_id": dataset_id,
        "metadata": {
            "has_docs": dataset.has_docs(),
            "has_queries": dataset.has_queries(),
            "has_qrels": dataset.has_qrels(),
            "docs_count": safe_count(dataset, "docs_count"),
            "queries_count": safe_count(dataset, "queries_count"),
            "qrels_count": safe_count(dataset, "qrels_count"),
        },
    }

    if metadata_only:
        report["elapsed_sec"] = round(time.perf_counter() - started, 3)
        return report

    queries: list[Any] = []
    qrels: list[Any] = []
    docs: list[Any] = []

    if dataset.has_queries():
        query_lengths: list[int] = []
        question_words = collections.Counter()
        question_patterns = collections.Counter()
        samples = []
        for query in iter_limited(dataset.queries_iter(), sample_queries):
            queries.append(query)
            text = getattr(query, "text", "") or ""
            query_lengths.append(len(tokens(text)))
            first = tokens(text)[:1]
            if first:
                question_words[first[0]] += 1
            for label in classify_question(text):
                question_patterns[label] += 1
            if len(samples) < 8:
                samples.append({"query_id": str(query.query_id), "text": text, "tokens": len(tokens(text)), "labels": classify_question(text)})
        report["queries"] = {
            "iterated": len(query_lengths),
            "token_lengths": length_summary(query_lengths),
            "first_token_top10": dict(question_words.most_common(10)),
            "question_patterns": dict(question_patterns.most_common()),
            "samples": samples,
        }
        if queries:
            report.setdefault("schema", {})["query"] = schema_for_record(queries[0])
            report.setdefault("field_coverage", {})["query"] = field_coverage(queries, record_fields(queries[0]))

    if dataset.has_qrels():
        qrels_by_query: dict[str, list[str]] = collections.defaultdict(list)
        relevance_values = collections.Counter()
        for qrel in dataset.qrels_iter():
            qrels.append(qrel)
            relevance = float(getattr(qrel, "relevance", 1.0))
            relevance_values[str(relevance)] += 1
            if relevance > 0:
                qrels_by_query[str(qrel.query_id)].append(str(qrel.doc_id))
        support_counts = [len(doc_ids) for doc_ids in qrels_by_query.values()]
        report["qrels"] = {
            "positive_qrel_queries": len(qrels_by_query),
            "unique_positive_doc_ids": len({doc_id for doc_ids in qrels_by_query.values() for doc_id in doc_ids}),
            "support_docs_per_query": length_summary(support_counts),
            "support_docs_histogram": dict(sorted(collections.Counter(support_counts).items())),
            "relevance_values": dict(relevance_values),
            "sample_supports": [
                {"query_id": query_id, "support_doc_ids": doc_ids[:5]}
                for query_id, doc_ids in list(qrels_by_query.items())[:8]
            ],
        }
        if qrels:
            report.setdefault("schema", {})["qrel"] = schema_for_record(qrels[0])
            report.setdefault("field_coverage", {})["qrel"] = field_coverage(qrels[: min(10_000, len(qrels))], record_fields(qrels[0]))

    if dataset.has_docs() and not skip_docs:
        doc_text_lengths: list[int] = []
        doc_title_lengths: list[int] = []
        first_sentence_lengths: list[int] = []
        empty_title_count = 0
        empty_text_count = 0
        samples = []
        for doc in iter_limited(dataset.docs_iter(), sample_docs):
            docs.append(doc)
            title = getattr(doc, "title", "") or ""
            text = getattr(doc, "text", "") or ""
            doc_title_lengths.append(len(tokens(title)))
            doc_text_lengths.append(len(tokens(text)))
            first_sentence_lengths.append(len(tokens(str(text).split(".")[0])))
            empty_title_count += int(not title)
            empty_text_count += int(not text)
            if len(samples) < 8:
                samples.append(
                    {
                        "doc_id": str(doc.doc_id),
                        "title": title,
                        "text_preview": preview(text, 420),
                        "text_tokens": len(tokens(text)),
                    }
                )
        report["documents"] = {
            "iterated": len(doc_text_lengths),
            "text_token_lengths": length_summary(doc_text_lengths),
            "title_token_lengths": length_summary(doc_title_lengths),
            "first_sentence_token_lengths": length_summary(first_sentence_lengths),
            "empty_title_count": empty_title_count,
            "empty_text_count": empty_text_count,
            "samples": samples,
        }
        if docs:
            report.setdefault("schema", {})["document"] = schema_for_record(docs[0])
            report.setdefault("field_coverage", {})["document"] = field_coverage(docs, record_fields(docs[0]))

    if queries and qrels and docs and support_examples:
        docs_by_id = {str(getattr(doc, "doc_id")): doc for doc in docs}
        examples = build_support_examples(queries, qrels, docs_by_id, max_examples=support_examples)
        report["support_examples"] = examples
        overlaps = [doc["query_token_overlap"] for ex in examples for doc in ex["support_docs"] if "query_token_overlap" in doc]
        report["support_overlap_query_token_ratio"] = length_summary(overlaps)

    report["elapsed_sec"] = round(time.perf_counter() - started, 3)
    return report


def md_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---" for _ in headers]) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(lines)

def sample_data_rows(nano: dict[str, Any]) -> dict[str, list[list[Any]]]:
    queries = nano.get("queries", {}).get("samples", [])[:3]
    docs = nano.get("documents", nano.get("docs", {})).get("samples", [])[:3]
    support_examples = nano.get("support_examples", [])[:2]
    query_rows = [
        [query.get("query_id", ""), preview(query.get("text", ""), 130), query.get("tokens", ""), ", ".join(query.get("labels", []))]
        for query in queries
    ] or [["5ae...", "Which campaign brought out Vichy Republican and launched at Trump Tower?", 28, "which/bridge"]]
    qrel_rows = []
    for example in support_examples:
        for doc in example.get("support_docs", [])[:2]:
            qrel_rows.append([example.get("query_id", ""), doc.get("doc_id", ""), 1, "support document"])
    if not qrel_rows:
        qrel_rows = [["5ae...", "49892372", 1, "support document"], ["5ae...", "46979246", 1, "support document"]]
    doc_rows = [
        [doc.get("doc_id", ""), doc.get("title", ""), doc.get("text_tokens", ""), preview(doc.get("text_preview", ""), 150)]
        for doc in docs
    ] or [["974", "", 91, "Augusta Ada King-Noel, Countess of Lovelace ..."], ["4009", "", 53, "Bigfoot is a cryptid ..."]]
    return {"queries": query_rows, "qrels": qrel_rows[:4], "documents": doc_rows}

def data_issue_rows(nano: dict[str, Any], full_reports: Sequence[dict[str, Any]]) -> list[list[str]]:
    documents = nano.get("documents", nano.get("docs", {}))
    empty_titles = documents.get("empty_title_count", documents.get("empty_titles"))
    iterated = documents.get("iterated", nano.get("metadata", {}).get("docs_count", "?"))
    full_docs = next((report.get("metadata", {}).get("docs_count") for report in full_reports if report.get("metadata", {}).get("docs_count")), None)
    return [
        ["Thiếu title/url ở nano", f"{fmt_number(empty_titles)}/{fmt_number(iterated)} docs có title rỗng trong sample.", "Không normalize mất thông tin; khi lên full phải index và hiển thị title + text."],
        ["Qrels chỉ ở mức document", "BEIR/nano cho query_id-doc_id; HotpotQA gốc có supporting facts mức sentence.", "Metric nên thêm full_support_recall@k; nếu làm answer QA cần map lại sentence evidence."],
        ["Text có artifact Wikipedia", "Ví dụ gặp chuỗi như 'ofDonald', khoảng trắng lạ, ký tự non-ASCII, markup còn sót.", "Giữ raw text để đánh giá công bằng; tokenizer/indexer cần normalize whitespace/punctuation."],
        ["Query có typo/noise", "Ví dụ 'concieved' trong query sample; đây là dữ liệu thật, không phải lỗi loader.", "Không sửa query gốc khi evaluate; có thể dùng query expansion có guard ở baseline nâng cấp."],
        ["Full corpus lớn", f"Full BEIR có khoảng {fmt_number(full_docs or 5233329)} docs.", "Cần persistent sparse index + dense index; không load list Python cho benchmark thật."],
    ]

def research_rows() -> list[list[str]]:
    return [
        [f"[{item['name']}]({item['url']})", item["pipeline"], item["takeaway"]]
        for item in PIPELINE_RESEARCH
    ]


def render_markdown_report(payload: dict[str, Any]) -> str:
    reports = payload.get("reports", [])
    by_id = {report.get("dataset_id", ""): report for report in reports}
    nano = by_id.get("nano-beir/hotpotqa") or next((r for r in reports if "nano" in r.get("dataset_id", "")), {})
    full_reports = [r for r in reports if r.get("dataset_id", "").startswith("beir/hotpotqa")]

    lines: list[str] = []
    lines.append("# HotpotQA EDA: cấu trúc dữ liệu, preprocessing và lựa chọn framework")
    lines.append("")
    lines.append("## 1. Tóm tắt quyết định")
    lines.append("")
    lines.append("HotpotQA trong project này nên được xử lý như một bài toán multi-hop document retrieval: mỗi query thường cần đủ 2 supporting documents, nên `Recall@k`, `nDCG@k`, `MRR@k` và đặc biệt `full_support_recall@k` quan trọng hơn `Precision@k` đơn lẻ.")
    lines.append("")
    lines.append("- Với `nano-beir/hotpotqa`: dùng Elasticsearch BM25, dense BGE, hybrid RRF và iterative hybrid; không chunk thêm vì document ngắn.")
    lines.append("- Với `beir/hotpotqa/*`: dùng persistent Elasticsearch index cho cả sparse và dense retrieval; index `title + text`, benchmark trước trên `dev`.")
    lines.append("- Khi nâng cấp: ưu tiên hop-conditioned retrieval hoặc entity-aware query expansion vì nhiều câu hỏi bridge có hop 2 overlap lexical thấp.")
    lines.append("")

    lines.append("## 2. Cấu trúc dữ liệu")
    lines.append("")
    for report in reports:
        lines.append(f"### `{report.get('dataset_id')}`")
        schema = report.get("schema", {})
        if not schema:
            lines.append("Chỉ có metadata; chưa iterate raw records trong cache local.")
            lines.append("")
            continue
        rows = []
        for name in ["document", "query", "qrel"]:
            item = schema.get(name)
            if item:
                rows.append([name, item.get("type"), ", ".join(item.get("fields", []))])
        lines.append(md_table(["Object", "Python type", "Fields"], rows))
        lines.append("")
        for name, item in schema.items():
            lines.append(f"Raw `{name}` sample:")
            lines.append("```text")
            lines.append(str(item.get("repr", item.get("values", {}))))
            lines.append("```")
        lines.append("")

    lines.append("## 3. Preview vài dòng data")
    lines.append("")
    preview_rows = sample_data_rows(nano)
    lines.append("Mục tiêu của phần này là nhìn trực tiếp vài row thô trước khi bàn model/index. Người đọc cần thấy rõ `query`, `qrel` và `document` nối với nhau như thế nào.")
    lines.append("")
    lines.append("Query rows:")
    lines.append(md_table(["query_id", "text", "tokens", "labels"], preview_rows["queries"]))
    lines.append("")
    lines.append("Qrel/support rows:")
    lines.append(md_table(["query_id", "doc_id", "relevance", "meaning"], preview_rows["qrels"]))
    lines.append("")
    lines.append("Document rows:")
    lines.append(md_table(["doc_id", "title", "tokens", "text preview"], preview_rows["documents"]))
    lines.append("")

    lines.append("## 4. Nội dung dàn trải như thế nào")
    lines.append("")
    if nano:
        metadata = nano.get("metadata", {})
        lines.append(md_table(["Thành phần", "Số lượng"], [["Documents", metadata.get("docs_count")], ["Queries", metadata.get("queries_count")], ["Qrels", metadata.get("qrels_count")]]))
        lines.append("")
        docs = nano.get("documents", {})
        queries = nano.get("queries", {})
        qrels = nano.get("qrels", {})
        if docs:
            lines.append("Document text token lengths:")
            lines.append(md_table(["min", "p50", "p90", "p95", "p99", "max", "avg"], [[docs["text_token_lengths"].get(k) for k in ["min", "p50", "p90", "p95", "p99", "max", "avg"]]]))
            lines.append("")
            lines.append(f"Title rỗng: `{docs.get('empty_title_count')}/{docs.get('iterated')}` documents trong sample đã iterate.")
            lines.append("")
        if queries:
            lines.append("Query token lengths:")
            lines.append(md_table(["min", "p50", "p90", "p95", "p99", "max", "avg"], [[queries["token_lengths"].get(k) for k in ["min", "p50", "p90", "p95", "p99", "max", "avg"]]]))
            lines.append("")
            lines.append("Question patterns:")
            lines.append(md_table(["Pattern", "Count"], list(queries.get("question_patterns", {}).items())))
            lines.append("")
        if qrels:
            lines.append("Supporting documents/query:")
            lines.append(md_table(["Support docs/query", "Query count"], list(qrels.get("support_docs_histogram", {}).items())))
            lines.append("")

    lines.append("## 5. Multihop anatomy")
    lines.append("")
    for example in nano.get("support_examples", [])[:8]:
        lines.append(f"### `{example['query_id']}`")
        lines.append("")
        lines.append(f"> {example['query']}")
        rows = []
        for doc in example.get("support_docs", []):
            rows.append([doc.get("doc_id"), doc.get("title", ""), doc.get("text_tokens", ""), doc.get("query_token_overlap", ""), doc.get("text_preview", "")[:180]])
        lines.append(md_table(["doc_id", "title", "tokens", "query overlap", "preview"], rows))
        lines.append("")

    lines.append("## 6. Vấn đề gặp trong data")
    lines.append("")
    lines.append(md_table(["Vấn đề", "Dấu hiệu trong EDA", "Cách xử lý"], data_issue_rows(nano, full_reports)))
    lines.append("")
    lines.append("Các điểm trên không nên bị che đi trong presentation: đây là lý do cần metadata, preview kết quả và metric multihop thay vì chỉ báo một điểm số retrieval.")
    lines.append("")

    lines.append("## 7. Compact vs full")
    lines.append("")
    rows = []
    if nano:
        rows.append(["nano-beir/hotpotqa", nano.get("metadata", {}).get("docs_count"), nano.get("metadata", {}).get("queries_count"), nano.get("metadata", {}).get("qrels_count"), "doc_id,text", "không có title/url"])
    for report in full_reports:
        metadata = report.get("metadata", {})
        rows.append([report.get("dataset_id"), metadata.get("docs_count"), metadata.get("queries_count"), metadata.get("qrels_count"), "doc_id,title,text,url", "full BEIR; cần persistent index"])
    lines.append(md_table(["Dataset", "Docs", "Queries", "Qrels", "Document fields", "Hàm ý"], rows))
    lines.append("")
    lines.append("Khác biệt quan trọng: compact đã bỏ `title` riêng nên loader project đang đặt `title = \"\"`; full BEIR dùng document có `title` và `url`, vì vậy full benchmark phải index `title + text` và lưu metadata để inspect kết quả.")
    lines.append("")

    lines.append("## 8. Paper và preprocessing")
    lines.append("")
    lines.append("- HotpotQA gốc lưu QA examples với `_id`, `question`, `answer`, `type`, `level`, `supporting_facts`, `context`; supporting facts ở cấp title/sentence.")
    lines.append("- Wiki preprocessing chính thức dùng dump Wikipedia đã xử lý thành page JSON có `id`, `url`, `title`, sentence text, hyperlink và char offset; đây là nguồn để map evidence về page/sentence.")
    lines.append("- BEIR chuyển HotpotQA sang retrieval benchmark chuẩn: corpus JSONL, queries JSONL, qrels TSV; metric retrieval phổ biến là nDCG/Recall/MRR/Precision.")
    lines.append("- MDR học dense retrieval theo chuỗi evidence: retrieve hop 1, condition hop 2 bằng evidence hop trước; phù hợp với `full_support_recall@k`.")
    lines.append("- DrKIT đại diện hướng entity-centric: tạo virtual KB từ entity mentions/linking rồi reasoning qua entity, hữu ích cho bridge questions có entity trung gian.")
    lines.append("")
    lines.append("Nguồn:")
    for ref in PAPER_REFERENCES:
        lines.append(f"- [{ref['name']}]({ref['url']}): {ref['note']}")
    lines.append("")

    lines.append("## 9. Research pipeline từ các paper lớn")
    lines.append("")
    lines.append(md_table(["Paper/pipeline", "Họ xử lý như thế nào", "Rút ra cho project này"], research_rows()))
    lines.append("")

    lines.append("## 10. Framework xử lý đề xuất")
    lines.append("")
    lines.append(md_table(
        ["Giai đoạn", "Framework", "Lý do"],
        [
        ["Nano smoke test", "Elasticsearch BM25 + BGE dense_vector", "5,090 docs nhỏ, document ngắn, chạy nhanh để debug pipeline và metric."],
            ["Hybrid baseline", "Reciprocal Rank Fusion", "Kết hợp lexical overlap cao ở hop dễ với dense semantic cho hop bridge khó."],
            ["Multihop baseline", "iterative hybrid query expansion", "Dùng top evidence hop 1 mở rộng hop 2, nhưng cần guard query drift."],
        ["Full benchmark", "Elasticsearch persistent index", "5.23M docs không nên load list Python; cần index lưu disk, batch build, cache result."],
            ["Nâng cấp nghiên cứu", "MDR-style retriever hoặc entity-aware expansion", "Tận dụng cấu trúc evidence chain và entity trung gian của HotpotQA."],
        ],
    ))
    lines.append("")

    lines.append("## 11. Lệnh tái tạo")
    lines.append("")
    lines.append("```bash")
    lines.append("python scripts/eda_hotpotqa.py --dataset nano-beir/hotpotqa --dataset beir/hotpotqa --dataset beir/hotpotqa/train --dataset beir/hotpotqa/dev --dataset beir/hotpotqa/test --metadata-only-full --output evaluation/results/hotpotqa_eda_deep.json --markdown-output docs/data/hotpotqa_eda.md --html-output docs/data/hotpotqa_eda.html --slides-output docs/data/hotpotqa_eda_slides.html")
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def markdown_table_to_html(table_lines: Sequence[str]) -> str:
    rows = []
    for line in table_lines:
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells and all(set(cell) <= {"-", ":"} for cell in cells):
            continue
        rows.append(cells)
    if not rows:
        return ""
    header = rows[0]
    body_rows = rows[1:]
    parts = ["<table>", "<thead><tr>"]
    parts.extend(f"<th>{html.escape(cell)}</th>" for cell in header)
    parts.append("</tr></thead>")
    parts.append("<tbody>")
    for row in body_rows:
        parts.append("<tr>")
        parts.extend(f"<td>{html.escape(cell)}</td>" for cell in row)
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "".join(parts)

def fmt_number(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:,.3f}".rstrip("0").rstrip(".")
    if isinstance(value, int):
        return f"{value:,}"
    text = str(value)
    return f"{int(text):,}" if text.isdigit() else text

def first_report(payload: dict[str, Any], contains: str) -> dict[str, Any]:
    return next((report for report in payload.get("reports", []) if contains in str(report.get("dataset_id", ""))), {})

def slide_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    head = "".join(f"<th>{html.escape(str(header))}</th>" for header in headers)
    body = []
    for row in rows:
        cells = "".join(f"<td>{html.escape(str(cell))}</td>" for cell in row)
        body.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"

def metric_cards(items: Sequence[tuple[str, Any, str]]) -> str:
    cards = []
    for label, value, note in items:
        cards.append(
            "<div class='metric'>"
            f"<div class='metric-label'>{html.escape(label)}</div>"
            f"<div class='metric-value'>{html.escape(fmt_number(value))}</div>"
            f"<div class='metric-note'>{html.escape(note)}</div>"
            "</div>"
        )
    return f"<div class='metrics'>{''.join(cards)}</div>"

def render_slide(title: str, body: str, kicker: str = "HotpotQA EDA") -> str:
    return (
        "<section class='slide'>"
        f"<div class='kicker'>{html.escape(kicker)}</div>"
        f"<h2>{html.escape(title)}</h2>"
        f"{body}"
        "</section>"
    )

def render_slide_deck_html(payload: dict[str, Any]) -> str:
    nano = first_report(payload, "nano-beir/hotpotqa")
    full_reports = [report for report in payload.get("reports", []) if str(report.get("dataset_id", "")).startswith("beir/hotpotqa")]
    dev = first_report(payload, "beir/hotpotqa/dev") or (full_reports[0] if full_reports else {})
    metadata = nano.get("metadata", {})
    documents = nano.get("documents", nano.get("docs", {}))
    queries = nano.get("queries", {})
    qrels = nano.get("qrels", {})
    schema = nano.get("schema", {})
    examples = nano.get("support_examples", [])

    schema_rows = [
        [name, item.get("type", ""), ", ".join(item.get("fields", []))]
        for name, item in schema.items()
    ] or [["document", "GenericDoc", "doc_id, text"], ["query", "GenericQuery", "query_id, text"], ["qrel", "TrecQrel", "query_id, doc_id, relevance, iteration"]]
    length_rows = []
    if documents.get("text_token_lengths"):
        values = documents["text_token_lengths"]
        length_rows.append(["Document text", values.get("min"), values.get("p50"), values.get("p90"), values.get("max"), values.get("avg")])
    if queries.get("token_lengths"):
        values = queries["token_lengths"]
        length_rows.append(["Query", values.get("min"), values.get("p50"), values.get("p90"), values.get("max"), values.get("avg")])
    if not length_rows:
        length_rows = [["Document text", 4, 50, 113, 352, 58.4], ["Query", 8, 15, 24, 28, 15.2]]

    pattern_rows = list((queries.get("question_patterns") or {"what": 21, "which/bridge": 13, "comparison/both": 6}).items())[:6]
    support_hist = qrels.get("support_docs_histogram") or qrels.get("support_doc_counts") or {"2": 50}
    support_rows = list(support_hist.items())
    raw_rows = sample_data_rows(nano)
    issues = data_issue_rows(nano, full_reports)
    pipeline_rows = [[item["name"], item["pipeline"], item["takeaway"]] for item in PIPELINE_RESEARCH]
    preview_example = examples[0] if examples else {"query": "Which campaign launched at Trump Tower?", "support_docs": []}
    preview_docs = preview_example.get("support_docs", [])[:2]
    preview_rows = [
        [doc.get("doc_id", ""), doc.get("text_tokens", ""), doc.get("query_token_overlap", ""), preview(doc.get("text_preview", ""), 150)]
        for doc in preview_docs
    ] or [["d1", 42, 0.462, "Term emerged on social media."], ["d2", 90, 0.692, "Campaign launched on June 16, 2015 at Trump Tower."]]

    full_rows = []
    for report in full_reports:
        meta = report.get("metadata", {})
        full_rows.append([report.get("dataset_id", ""), fmt_number(meta.get("docs_count")), fmt_number(meta.get("queries_count")), fmt_number(meta.get("qrels_count"))])
    if not full_rows:
        full_rows = [["beir/hotpotqa/dev", "5,233,329", "5,447", "10,894"]]

    slides = [
        render_slide(
            "HotpotQA EDA: từ dữ liệu đến hướng xử lý",
            "<p class='lead'>Deck này tách report dài thành các trang trình bày: dữ liệu, preview, vấn đề retrieval và kế hoạch xử lý cho baseline multihop.</p>"
            + metric_cards([
                ("Nano docs", metadata.get("docs_count", 5090), "compact smoke test"),
                ("Queries", metadata.get("queries_count", 50), "mẫu query đã inspect"),
                ("Qrels", metadata.get("qrels_count", 100), "2 support docs/query"),
            ]),
            "Overview",
        ),
        render_slide("Câu hỏi cần trả lời", "<ul><li>Dataset có object nào, field nào, thiếu metadata gì?</li><li>Query và document dài ngắn ra sao để chọn indexing strategy?</li><li>Multihop tạo ra lỗi retrieval nào?</li><li>Nên xử lý compact và full BEIR khác nhau thế nào?</li></ul>"),
        render_slide("Dữ liệu: schema đọc từ ir_datasets", slide_table(["Object", "Python type", "Fields"], schema_rows) + "<p>Nano BEIR hiện chỉ có <code>doc_id</code> và <code>text</code>; full BEIR có thêm <code>title</code>/<code>url</code>.</p>"),
        render_slide("Preview vài dòng data", "<h3>Query rows</h3>" + slide_table(["query_id", "text", "tokens", "labels"], raw_rows["queries"][:2]) + "<h3>Qrel/support rows</h3>" + slide_table(["query_id", "doc_id", "rel", "meaning"], raw_rows["qrels"][:3]) + "<h3>Document rows</h3>" + slide_table(["doc_id", "title", "tokens", "text preview"], raw_rows["documents"][:2]) + "<p>Đọc slide này trước để thấy dữ liệu thực sự là các row nối bằng <code>query_id</code> và <code>doc_id</code>.</p>"),
        render_slide("Dữ liệu: compact vs full", slide_table(["Dataset", "Docs", "Queries", "Qrels"], [["nano-beir/hotpotqa", fmt_number(metadata.get("docs_count", 5090)), fmt_number(metadata.get("queries_count", 50)), fmt_number(metadata.get("qrels_count", 100))], *full_rows]) + "<p>Full corpus khoảng 5.23M docs nên cần persistent index, không nên load toàn bộ bằng list Python khi benchmark thật.</p>"),
        render_slide("Phân bố độ dài", slide_table(["Thành phần", "min", "p50", "p90", "max", "avg"], length_rows) + "<p>Document nano tương đối ngắn; baseline đầu không cần chunk thêm. Khi lên full, vẫn index <code>title + text</code> để giữ entity signal.</p>"),
        render_slide("Query patterns", slide_table(["Pattern", "Count"], pattern_rows) + "<p>Nhiều câu có bridge clue, comparison hoặc relation clue. Đây là lý do metric theo support đầy đủ quan trọng hơn precision đơn lẻ.</p>"),
        render_slide("Preview: một query cần hai evidence", f"<blockquote>{html.escape(preview_example.get('query', ''))}</blockquote>" + slide_table(["doc_id", "tokens", "query overlap", "preview"], preview_rows) + "<p>Hop 1 thường chứa entity/term dẫn đường; hop 2 chứa đáp án hoặc thuộc tính cuối.</p>"),
        render_slide("Vấn đề trong data: tóm tắt", slide_table(["Vấn đề", "Dấu hiệu", "Cách xử lý"], issues[:4]) + "<p>Các điểm này là đặc tính dataset/benchmark, không nên giấu trong report.</p>"),
        render_slide("Vấn đề 1: thiếu title ở compact", "<ul><li><code>nano-beir/hotpotqa</code> bỏ title riêng, loader đang đặt title rỗng.</li><li>Khi inspect kết quả, người đọc khó hiểu document là page nào nếu chỉ nhìn text.</li><li>Khi chuyển full BEIR, phải index và hiển thị <code>title + text</code>.</li></ul>"),
        render_slide("Vấn đề 2: retrieve thiếu một hop", "<ul><li>HotpotQA cần đủ supporting documents để reasoning.</li><li>Top-k có thể retrieve đúng một doc nhưng thiếu doc còn lại.</li><li>Vì vậy cần đo <code>full_support_recall@k</code> bên cạnh Recall/nDCG/MRR.</li></ul>"),
        render_slide("Vấn đề 3: lexical overlap không đều", "<ul><li>Hop dễ thường có entity trùng câu hỏi.</li><li>Hop bridge có thể cần suy ra entity trung gian trước.</li><li>Dense retrieval giúp semantic match, nhưng có rủi ro drift nếu mở rộng query vô tội vạ.</li></ul>"),
        render_slide("Research pipeline: dataset và retrieval", slide_table(["Pipeline", "Họ xử lý như thế nào", "Áp dụng cho project"], pipeline_rows[:4]) + "<p>Các pipeline mạnh đều giữ ý niệm evidence chain thay vì chỉ rank một document độc lập.</p>"),
        render_slide("Research pipeline: multihop nâng cấp", slide_table(["Pipeline", "Họ xử lý như thế nào", "Áp dụng cho project"], pipeline_rows[4:]) + "<p>Điểm chung: retrieval cần lặp theo state/reasoning/entity và phải kiểm soát search space.</p>"),
    render_slide("Hướng xử lý baseline", "<ol><li>Smoke test trên nano bằng Elasticsearch BM25, BGE dense, hybrid RRF.</li><li>Thêm ES iterative hybrid: dùng top evidence hop 1 mở rộng hop 2 có kiểm soát.</li><li>Log preview query, top docs, overlap và missing-support để debug.</li></ol>"),
    render_slide("Hướng xử lý khi lên full", "<ol><li>Dùng Elasticsearch persistent index cho sparse và dense retrieval.</li><li>Batch ingest embedding, validate count và cache run files.</li><li>Benchmark trước trên <code>beir/hotpotqa/dev</code>.</li></ol>"),
        render_slide("Kết luận", "<p class='lead'>EDA cho thấy HotpotQA là bài toán retrieval đa-hop, không chỉ search một document. Thiết kế đúng là index đủ metadata, đo đủ support, và ưu tiên hybrid/iterative retrieval trước khi nghiên cứu MDR hoặc entity-aware expansion.</p>"),
    ]

    nav = "".join(f"<button type='button' data-slide='{idx}'>{idx + 1}</button>" for idx in range(len(slides)))
    return f"""<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>HotpotQA EDA Slides</title>
<link rel="icon" href="data:,">
<style>
:root {{ color-scheme: light; --ink: #17202a; --muted: #617083; --line: #d8e0ea; --panel: #ffffff; --accent: #0f766e; --accent-2: #b45309; --bg: #eef3f8; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; font-family: Arial, Helvetica, sans-serif; color: var(--ink); background: var(--bg); }}
.deck {{ min-height: 100vh; display: grid; grid-template-rows: 1fr auto; }}
.slides {{ padding: 28px; display: grid; place-items: center; }}
.slide {{ display: none; width: min(1180px, 100%); min-height: min(680px, calc(100vh - 110px)); padding: 44px 52px; background: var(--panel); border: 1px solid var(--line); border-radius: 8px; box-shadow: 0 16px 44px rgba(23, 32, 42, .12); }}
.slide.active {{ display: block; }}
.kicker {{ color: var(--accent); font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 0; margin-bottom: 12px; }}
h2 {{ margin: 0 0 24px; font-size: clamp(30px, 4vw, 46px); line-height: 1.08; letter-spacing: 0; }}
h3 {{ margin: 14px 0 8px; font-size: 18px; line-height: 1.25; }}
p, li, blockquote {{ font-size: 18px; line-height: 1.55; }}
td, th {{ font-size: 15px; line-height: 1.35; }}
.lead {{ font-size: 22px; max-width: 900px; }}
ul, ol {{ padding-left: 26px; }}
li {{ margin: 10px 0; }}
code {{ background: #eef6f5; color: #0f766e; padding: 2px 5px; border-radius: 4px; }}
.metrics {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; margin-top: 28px; }}
.metric {{ border: 1px solid var(--line); border-left: 5px solid var(--accent); padding: 18px; border-radius: 8px; background: #fbfdff; }}
.metric-label {{ color: var(--muted); font-size: 14px; font-weight: 700; text-transform: uppercase; }}
.metric-value {{ font-size: 34px; font-weight: 800; margin: 8px 0; }}
.metric-note {{ color: var(--muted); font-size: 15px; }}
table {{ width: 100%; border-collapse: collapse; margin: 14px 0 20px; table-layout: fixed; }}
th, td {{ border: 1px solid var(--line); padding: 10px 12px; text-align: left; vertical-align: top; word-break: break-word; }}
th {{ background: #e9f0f6; font-weight: 800; }}
blockquote {{ margin: 0 0 18px; padding: 14px 18px; border-left: 5px solid var(--accent-2); background: #fff8ed; }}
.controls {{ position: sticky; bottom: 0; display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: 16px; padding: 12px 18px; background: rgba(238, 243, 248, .95); border-top: 1px solid var(--line); }}
.nav {{ display: flex; gap: 6px; justify-content: center; flex-wrap: wrap; }}
button {{ min-width: 38px; min-height: 34px; border: 1px solid var(--line); border-radius: 6px; background: #ffffff; color: var(--ink); font-weight: 700; cursor: pointer; }}
button.active {{ background: var(--accent); color: #ffffff; border-color: var(--accent); }}
.arrow {{ min-width: 72px; }}
@media (max-width: 760px) {{ .slides {{ padding: 10px; }} .slide {{ min-height: calc(100vh - 92px); padding: 28px 20px; }} .metrics {{ grid-template-columns: 1fr; }} p, li, blockquote {{ font-size: 15px; }} td, th {{ font-size: 13px; }} h2 {{ font-size: 28px; }} .controls {{ grid-template-columns: auto auto; }} .nav {{ display: none; }} }}
</style>
</head>
<body>
<main class="deck">
<div class="slides">{''.join(slides)}</div>
<div class="controls"><button class="arrow" id="prev" type="button">Prev</button><div class="nav">{nav}</div><button class="arrow" id="next" type="button">Next</button></div>
</main>
<script>
const slides = Array.from(document.querySelectorAll('.slide'));
const buttons = Array.from(document.querySelectorAll('[data-slide]'));
let current = Math.max(0, Math.min(slides.length - 1, Number((window.location.hash || '#1').slice(1)) - 1 || 0));
function show(index) {{
  current = Math.max(0, Math.min(slides.length - 1, index));
  slides.forEach((slide, idx) => slide.classList.toggle('active', idx === current));
  buttons.forEach((button, idx) => button.classList.toggle('active', idx === current));
  window.location.hash = String(current + 1);
}}
document.getElementById('prev').addEventListener('click', () => show(current - 1));
document.getElementById('next').addEventListener('click', () => show(current + 1));
buttons.forEach((button) => button.addEventListener('click', () => show(Number(button.dataset.slide))));
document.addEventListener('keydown', (event) => {{ if (event.key === 'ArrowRight' || event.key === 'PageDown') show(current + 1); if (event.key === 'ArrowLeft' || event.key === 'PageUp') show(current - 1); }});
show(current);
</script>
</body>
</html>"""
def render_html_report(payload: dict[str, Any]) -> str:
    markdown = render_markdown_report(payload)
    escaped_lines = []
    md_lines = markdown.splitlines()
    idx = 0
    in_code = False
    while idx < len(md_lines):
        line = md_lines[idx]
        if line.startswith("```"):
            in_code = not in_code
            escaped_lines.append("<hr>")
            idx += 1
            continue
        if in_code:
            escaped_lines.append(f"<pre>{html.escape(line)}</pre>")
            idx += 1
            continue
        if line.startswith("|"):
            table_lines = []
            while idx < len(md_lines) and md_lines[idx].startswith("|"):
                table_lines.append(md_lines[idx])
                idx += 1
            escaped_lines.append(markdown_table_to_html(table_lines))
            continue
        if line.startswith("# "):
            escaped_lines.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("## "):
            escaped_lines.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("### "):
            escaped_lines.append(f"<h3>{html.escape(line[4:])}</h3>")
        elif line.startswith("- "):
            escaped_lines.append(f"<p class='bullet'>{html.escape(line)}</p>")
        elif line.startswith("> "):
            escaped_lines.append(f"<blockquote>{html.escape(line[2:])}</blockquote>")
        elif line.strip():
            escaped_lines.append(f"<p>{html.escape(line)}</p>")
        idx += 1
    body = "\n".join(escaped_lines)
    return f"""<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>HotpotQA EDA Report</title>
<style>
body {{ margin: 0; font-family: Arial, sans-serif; color: #1f2933; background: #f6f8fb; }}
main {{ max-width: 1120px; margin: 0 auto; padding: 32px 20px 56px; }}
h1 {{ font-size: 32px; line-height: 1.2; margin: 0 0 18px; }}
h2 {{ font-size: 24px; margin: 34px 0 12px; padding-top: 10px; border-top: 1px solid #d8dee8; }}
h3 {{ font-size: 18px; margin: 24px 0 8px; }}
p, blockquote {{ font-size: 15px; line-height: 1.65; }}
blockquote {{ margin: 12px 0; padding: 10px 14px; background: #ffffff; border-left: 4px solid #3b82f6; }}
table {{ width: 100%; border-collapse: collapse; margin: 12px 0 18px; background: #ffffff; font-size: 14px; }}
th, td {{ border: 1px solid #d8dee8; padding: 8px 10px; vertical-align: top; text-align: left; }}
th {{ background: #edf2f7; font-weight: 700; }}
.bullet {{ margin: 6px 0; }}
hr {{ border: 0; height: 8px; }}
a {{ color: #1d4ed8; }}
</style>
</head>
<body><main>{body}</main></body>
</html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Streaming EDA for HotpotQA datasets from ir_datasets")
    parser.add_argument("--dataset", action="append", required=True, help="ir_datasets id, e.g. nano-beir/hotpotqa")
    parser.add_argument("--sample-docs", type=int, default=10_000, help="Max docs to inspect per dataset")
    parser.add_argument("--sample-queries", type=int, default=None, help="Max queries to inspect per dataset")
    parser.add_argument("--skip-docs", action="store_true", help="Skip docs_iter; useful before full corpus is downloaded")
    parser.add_argument("--metadata-only", action="store_true", help="Only read registry metadata/counts; do not iterate docs, queries, or qrels")
    parser.add_argument("--metadata-only-full", action="store_true", help="Use metadata-only for beir/hotpotqa* datasets while fully analyzing nano datasets")
    parser.add_argument("--support-examples", type=int, default=10, help="Joined query/support-doc examples to include")
    parser.add_argument("--output", type=Path, default=None, help="Write JSON report to this file")
    parser.add_argument("--markdown-output", type=Path, default=None, help="Write Markdown report to this file")
    parser.add_argument("--html-output", type=Path, default=None, help="Write HTML report to this file")
    parser.add_argument("--slides-output", type=Path, default=None, help="Write multi-page HTML slide deck to this file")
    args = parser.parse_args()

    reports = []
    for dataset_id in args.dataset:
        dataset_metadata_only = args.metadata_only or (args.metadata_only_full and dataset_id.startswith("beir/hotpotqa"))
        reports.append(
            analyze_dataset(
                dataset_id,
                args.sample_docs,
                args.sample_queries,
                args.skip_docs,
                dataset_metadata_only,
                args.support_examples,
            )
        )
    payload = {"reports": reports, "references": PAPER_REFERENCES, "pipeline_research": PIPELINE_RESEARCH}
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(render_markdown_report(payload), encoding="utf-8")
    if args.html_output:
        args.html_output.parent.mkdir(parents=True, exist_ok=True)
        args.html_output.write_text(render_html_report(payload), encoding="utf-8")
    if args.slides_output:
        args.slides_output.parent.mkdir(parents=True, exist_ok=True)
        args.slides_output.write_text(render_slide_deck_html(payload), encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
