from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from src.data.load_hotpotqa import Document


@dataclass(frozen=True)
class SearchHit:
    doc_id: str
    score: float
    rank: int
    method: str
    hop: int = 1


class Retriever(Protocol):
    name: str

    def search(self, query: str, top_k: int) -> list[SearchHit]:
        ...


def build_doc_lookup(documents: list[Document]) -> dict[str, Document]:
    return {doc.doc_id: doc for doc in documents}
