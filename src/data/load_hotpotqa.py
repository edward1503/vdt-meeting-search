from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Document:
    doc_id: str
    title: str
    text: str

    @property
    def content(self) -> str:
        if self.title:
            return f"{self.title}\n{self.text}"
        return self.text


@dataclass(frozen=True)
class Query:
    query_id: str
    text: str


@dataclass(frozen=True)
class HotpotDataset:
    dataset_id: str
    documents: list[Document]
    queries: list[Query]
    qrels: dict[str, dict[str, float]]

    @property
    def doc_by_id(self) -> dict[str, Document]:
        return {doc.doc_id: doc for doc in self.documents}


def load_hotpotqa(dataset_id: str, max_docs: int | None = None, max_queries: int | None = None) -> HotpotDataset:
    try:
        import ir_datasets
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("ir_datasets is required. Install with: pip install -r requirements.txt") from exc

    dataset = ir_datasets.load(dataset_id)
    documents = [_to_document(doc) for doc in _take(dataset.docs_iter(), max_docs)]
    queries = [_to_query(query) for query in _take(dataset.queries_iter(), max_queries)]
    available_query_ids = {query.query_id for query in queries}
    available_doc_ids = {doc.doc_id for doc in documents}
    qrels: dict[str, dict[str, float]] = {}
    for qrel in dataset.qrels_iter():
        query_id = str(getattr(qrel, "query_id"))
        doc_id = str(getattr(qrel, "doc_id"))
        if query_id not in available_query_ids or doc_id not in available_doc_ids:
            continue
        relevance = float(getattr(qrel, "relevance", 1.0))
        if relevance <= 0:
            continue
        qrels.setdefault(query_id, {})[doc_id] = relevance

    queries = [query for query in queries if query.query_id in qrels]
    return HotpotDataset(dataset_id=dataset_id, documents=documents, queries=queries, qrels=qrels)


def _to_document(raw_doc) -> Document:
    doc_id = str(getattr(raw_doc, "doc_id"))
    title = str(getattr(raw_doc, "title", "") or "")
    text = str(getattr(raw_doc, "text", "") or "")
    return Document(doc_id=doc_id, title=title, text=text)


def _to_query(raw_query) -> Query:
    query_id = str(getattr(raw_query, "query_id"))
    text = str(getattr(raw_query, "text", "") or "")
    return Query(query_id=query_id, text=text)


def _take(items: Iterable, limit: int | None):
    if limit is None:
        yield from items
        return
    for idx, item in enumerate(items):
        if idx >= limit:
            break
        yield item
