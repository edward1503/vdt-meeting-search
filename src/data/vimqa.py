from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VimQADocument:
    numeric_id: int
    doc_id: str
    title: str
    text: str
    content: str
    embedding_text: str
    source_splits: list[str]


@dataclass(frozen=True)
class VimQAQuery:
    query_id: str
    query: str
    doc_id: str
    split: str
    answer: str


@dataclass(frozen=True)
class VimQADataset:
    documents: list[VimQADocument]
    queries: list[VimQAQuery]
    qrels: dict[str, str]


def normalize_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", str(value)).strip().split())


def context_doc_id(context: str) -> str:
    digest = hashlib.sha1(normalize_text(context).lower().encode("utf-8")).hexdigest()[:16]
    return f"vimqa_ctx_{digest}"


def load_rows(path: Path) -> list[dict[str, str]]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError(f"VimQA file must contain a JSON list: {path}")
    return rows


def build_vimqa_dataset(*, train_path: Path, test_path: Path) -> VimQADataset:
    docs_by_id: dict[str, VimQADocument] = {}
    split_sets: dict[str, list[str]] = {}
    queries: list[VimQAQuery] = []

    for split, path in (("train", train_path), ("test", test_path)):
        for index, row in enumerate(load_rows(path)):
            question = normalize_text(row.get("question", ""))
            context = normalize_text(row.get("context", ""))
            answer = normalize_text(row.get("answer", ""))
            if not question or not context:
                raise ValueError(f"VimQA row is missing question/context: {path}:{index}")

            doc_id = context_doc_id(context)
            split_values = split_sets.setdefault(doc_id, [])
            if split not in split_values:
                split_values.append(split)
            if doc_id not in docs_by_id:
                docs_by_id[doc_id] = VimQADocument(
                    numeric_id=len(docs_by_id),
                    doc_id=doc_id,
                    title="VimQA context",
                    text=context,
                    content=context,
                    embedding_text=context,
                    source_splits=[],
                )

            query_id = f"vimqa_{split}_{index:06d}"
            queries.append(VimQAQuery(query_id=query_id, query=question, doc_id=doc_id, split=split, answer=answer))

    documents = [
        VimQADocument(
            numeric_id=doc.numeric_id,
            doc_id=doc.doc_id,
            title=doc.title,
            text=doc.text,
            content=doc.content,
            embedding_text=doc.embedding_text,
            source_splits=split_sets[doc.doc_id],
        )
        for doc in sorted(docs_by_id.values(), key=lambda item: item.numeric_id)
    ]
    return VimQADataset(documents=documents, queries=queries, qrels={query.query_id: query.doc_id for query in queries})
