from __future__ import annotations

import json
from pathlib import Path

from src.data.vimqa import build_vimqa_dataset


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")


def test_build_vimqa_dataset_deduplicates_contexts_and_preserves_qrels(tmp_path):
    train_path = tmp_path / "train_vimqa.json"
    test_path = tmp_path / "test_vimqa.json"
    shared_context = "Hà Nội là thủ đô của Việt Nam. Thành phố nằm ở miền Bắc."
    write_rows(
        train_path,
        [
            {"question": "Hà Nội là thủ đô của nước nào?", "context": shared_context, "answer": "Việt Nam"},
            {"question": "Hà Nội nằm ở miền nào?", "context": shared_context, "answer": "miền Bắc"},
        ],
    )
    write_rows(
        test_path,
        [{"question": "Thủ đô Việt Nam là gì?", "context": shared_context, "answer": "Hà Nội"}],
    )

    dataset = build_vimqa_dataset(train_path=train_path, test_path=test_path)

    assert len(dataset.documents) == 1
    assert dataset.documents[0].doc_id.startswith("vimqa_ctx_")
    assert dataset.documents[0].content == shared_context
    assert dataset.documents[0].numeric_id == 0
    assert [query.query_id for query in dataset.queries] == [
        "vimqa_train_000000",
        "vimqa_train_000001",
        "vimqa_test_000000",
    ]
    assert set(dataset.qrels) == {"vimqa_train_000000", "vimqa_train_000001", "vimqa_test_000000"}
    assert dataset.qrels["vimqa_test_000000"] == dataset.documents[0].doc_id


def test_build_vimqa_dataset_keeps_split_and_answer_metadata(tmp_path):
    train_path = tmp_path / "train_vimqa.json"
    test_path = tmp_path / "test_vimqa.json"
    write_rows(train_path, [{"question": "Ai?", "context": "Nguyễn Du viết Truyện Kiều.", "answer": "Nguyễn Du"}])
    write_rows(test_path, [])

    dataset = build_vimqa_dataset(train_path=train_path, test_path=test_path)

    assert dataset.documents[0].source_splits == ["train"]
    assert dataset.queries[0].answer == "Nguyễn Du"
    assert dataset.queries[0].split == "train"
