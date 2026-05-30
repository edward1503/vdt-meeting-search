"""End-to-end local preprocessing pipeline for QMSum + AMI."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.core.config import settings
from src.preprocessing.chunking import chunk_meetings
from src.preprocessing.jsonl import write_jsonl
from src.preprocessing.parse_ami import parse_ami
from src.preprocessing.parse_qmsum import parse_qmsum
from src.preprocessing.validate_processed import validate_processed


DEFAULT_QMSUM_DIR = Path("data/raw/QMSum-main/QMSum-main/data")
DEFAULT_AMI_DIR = Path("data/raw/ami_public_manual_1.6.2")
DEFAULT_OUT_DIR = Path("data/processed")


def run_pipeline(
    qmsum_dir: Path = DEFAULT_QMSUM_DIR,
    ami_dir: Path = DEFAULT_AMI_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
    max_qmsum_meetings: int | None = None,
    max_ami_meetings: int | None = None,
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Parsing QMSum from {qmsum_dir}")
    qmsum_meetings, qmsum_queries, qrels = parse_qmsum(qmsum_dir)
    if max_qmsum_meetings:
        keep_ids = {m["meeting_id"] for m in qmsum_meetings[:max_qmsum_meetings]}
        qmsum_meetings = qmsum_meetings[:max_qmsum_meetings]
        qmsum_queries = [q for q in qmsum_queries if q["meeting_id"] in keep_ids]
        qrels = [qrel for qrel in qrels if qrel["meeting_id"] in keep_ids]

    print(f"Parsing AMI from {ami_dir}")
    ami_meetings = parse_ami(ami_dir)
    if max_ami_meetings:
        ami_meetings = ami_meetings[:max_ami_meetings]

    meetings = qmsum_meetings + ami_meetings
    chunks = chunk_meetings(
        meetings,
        target_tokens=max(128, settings.chunk_size - settings.chunk_overlap),
        max_tokens=settings.chunk_size,
        overlap_tokens=settings.chunk_overlap,
    )

    counts = {
        "meetings_qmsum": write_jsonl(out_dir / "meetings_qmsum.jsonl", qmsum_meetings),
        "meetings_ami": write_jsonl(out_dir / "meetings_ami.jsonl", ami_meetings),
        "meetings": write_jsonl(out_dir / "meetings.jsonl", meetings),
        "chunks": write_jsonl(out_dir / "chunks.jsonl", chunks),
        "qmsum_queries": write_jsonl(out_dir / "qmsum_queries.jsonl", qmsum_queries),
        "qrels": write_jsonl(out_dir / "qrels.jsonl", qrels),
    }
    counts["validation"] = validate_processed(out_dir)
    return counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--qmsum-dir", type=Path, default=DEFAULT_QMSUM_DIR)
    parser.add_argument("--ami-dir", type=Path, default=DEFAULT_AMI_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--max-qmsum-meetings", type=int, default=None)
    parser.add_argument("--max-ami-meetings", type=int, default=None)
    args = parser.parse_args()

    counts = run_pipeline(
        qmsum_dir=args.qmsum_dir,
        ami_dir=args.ami_dir,
        out_dir=args.out_dir,
        max_qmsum_meetings=args.max_qmsum_meetings,
        max_ami_meetings=args.max_ami_meetings,
    )
    for key, value in counts.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()

