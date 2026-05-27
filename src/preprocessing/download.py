"""Download AMI, ICSI, and QMSum meeting datasets from HuggingFace."""

import json
from pathlib import Path

from datasets import load_dataset
from tqdm import tqdm


DATA_DIR = Path("data/raw")


def download_ami_transcripts():
    """Download AMI corpus transcripts (edinburghcstr/ami)."""
    print("=" * 60)
    print("Downloading AMI transcripts...")
    ds = load_dataset("edinburghcstr/ami", "headset-single", trust_remote_code=True)

    output_dir = DATA_DIR / "ami_transcripts"
    output_dir.mkdir(parents=True, exist_ok=True)

    for split in ["train", "validation", "test"]:
        meetings = {}
        for row in tqdm(ds[split], desc=f"AMI {split}"):
            mid = row["meeting_id"]
            if mid not in meetings:
                meetings[mid] = []
            meetings[mid].append({
                "text": row["text"],
                "speaker_id": row["speaker_id"],
                "begin_time": row["begin_time"],
                "end_time": row["end_time"],
            })

        for mid, utterances in meetings.items():
            utterances.sort(key=lambda x: x["begin_time"])
            filepath = output_dir / f"{mid}.json"
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump({"meeting_id": mid, "split": split, "utterances": utterances}, f, ensure_ascii=False, indent=2)

    print(f"  -> {len(list(output_dir.glob('*.json')))} meeting files saved to {output_dir}")


def download_ami_summaries():
    """Download AMI summaries (knkarthick/AMI)."""
    print("Downloading AMI summaries...")
    ds = load_dataset("knkarthick/AMI")

    output_dir = DATA_DIR / "ami_summaries"
    output_dir.mkdir(parents=True, exist_ok=True)

    summaries = []
    for split in ["train", "validation", "test"]:
        for row in ds[split]:
            summaries.append({
                "id": row["id"],
                "summary": row["summary"],
                "dialogue": row["dialogue"],
            })

    filepath = output_dir / "summaries.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(summaries, f, ensure_ascii=False, indent=2)

    print(f"  -> {len(summaries)} summaries saved to {filepath}")


def download_icsi():
    """Download ICSI Meeting Corpus (StDestiny/icsi_cleaned)."""
    print("=" * 60)
    print("Downloading ICSI corpus...")
    ds = load_dataset("StDestiny/icsi_cleaned")

    output_dir = DATA_DIR / "icsi"
    output_dir.mkdir(parents=True, exist_ok=True)

    meetings = []
    for i, row in enumerate(ds["train"]):
        meetings.append({
            "meeting_id": f"icsi_{i:03d}",
            "dialogue": row["dialogue"],
            "summary": row["summary"],
        })

    filepath = output_dir / "meetings.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(meetings, f, ensure_ascii=False, indent=2)

    print(f"  -> {len(meetings)} meetings saved to {filepath}")


def download_qmsum():
    """Download QMSum dataset (pszemraj/qmsum-cleaned)."""
    print("=" * 60)
    print("Downloading QMSum...")
    ds = load_dataset("pszemraj/qmsum-cleaned")

    output_dir = DATA_DIR / "qmsum"
    output_dir.mkdir(parents=True, exist_ok=True)

    for split in ["train", "validation", "test"]:
        records = []
        for row in tqdm(ds[split], desc=f"QMSum {split}"):
            records.append({
                "id": row["id"],
                "pid": row["pid"],
                "input": row["input"],
                "output": row["output"],
            })

        filepath = output_dir / f"{split}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)

        print(f"  -> {len(records)} records saved to {filepath}")


if __name__ == "__main__":
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    download_ami_transcripts()
    download_ami_summaries()
    download_icsi()
    download_qmsum()
    print("=" * 60)
    print("All datasets downloaded successfully.")
