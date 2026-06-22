from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.vimqa import build_vimqa_dataset


def stage_vimqa(*, train_path: Path, test_path: Path, staging_dir: Path, results_dir: Path, docs_per_file: int) -> dict[str, int]:
    dataset = build_vimqa_dataset(train_path=train_path, test_path=test_path)
    staging_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    files = []
    for shard_start in range(0, len(dataset.documents), docs_per_file):
        shard_docs = dataset.documents[shard_start : shard_start + docs_per_file]
        path = staging_dir / f"docs-{len(files):05d}.jsonl"
        with path.open("w", encoding="utf-8") as handle:
            for doc in shard_docs:
                handle.write(
                    json.dumps(
                        {
                            "numeric_id": doc.numeric_id,
                            "doc_id": doc.doc_id,
                            "title": doc.title,
                            "text": doc.text,
                            "url": "",
                            "content": doc.content,
                            "embedding_text": doc.embedding_text,
                            "source_split": ",".join(doc.source_splits),
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
        files.append({"file": path.name, "docs": len(shard_docs)})

    (results_dir / "vimqa_queries.tsv").write_text(
        "query_id\tsource_query_id\tquery\tsplit\tanswer\n"
        + "".join(f"{query.query_id}\t{query.query_id}\t{query.query}\t{query.split}\t{query.answer}\n" for query in dataset.queries),
        encoding="utf-8",
    )
    (results_dir / "vimqa_qrels.tsv").write_text(
        "query_id\tdoc_id\trelevance\n" + "".join(f"{query_id}\t{doc_id}\t1\n" for query_id, doc_id in dataset.qrels.items()),
        encoding="utf-8",
    )
    manifest = {
        "dataset": "vimqa",
        "documents": len(dataset.documents),
        "queries": len(dataset.queries),
        "qrels": len(dataset.qrels),
        "files": files,
    }
    (staging_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"documents": len(dataset.documents), "queries": len(dataset.queries), "qrels": len(dataset.qrels), "files": len(files)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage local VimQA JSON files for Elasticsearch retrieval")
    parser.add_argument("--train", type=Path, default=Path("docs/data/vimqa/train_vimqa.json"))
    parser.add_argument("--test", type=Path, default=Path("docs/data/vimqa/test_vimqa.json"))
    parser.add_argument("--staging-dir", type=Path, default=Path("artifacts/vimqa/all/staging"))
    parser.add_argument("--results-dir", type=Path, default=Path("evaluation/results/vimqa"))
    parser.add_argument("--docs-per-file", type=int, default=5000)
    args = parser.parse_args()
    print(
        json.dumps(
            stage_vimqa(
                train_path=args.train,
                test_path=args.test,
                staging_dir=args.staging_dir,
                results_dir=args.results_dir,
                docs_per_file=args.docs_per_file,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
