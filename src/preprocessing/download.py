"""Download AMI, ICSI, and QMSum meeting datasets from HuggingFace (text only)."""

import json
from pathlib import Path

DATA_DIR = Path("data/raw")


def _optional_hf_imports():
    try:
        from datasets import load_dataset
        from tqdm import tqdm
    except ImportError as exc:
        raise RuntimeError(
            "HuggingFace download support is optional. Install `datasets` and `tqdm` "
            "only if you need to download datasets instead of using local official zip files."
        ) from exc
    return load_dataset, tqdm


def download_ami():
    """Download AMI corpus text-only via streaming (skips 29GB audio download)."""
    load_dataset, tqdm = _optional_hf_imports()
    print("=" * 60)
    print("Downloading AMI transcripts (text only, streaming)...")
    output_dir = DATA_DIR / "ami"
    output_dir.mkdir(parents=True, exist_ok=True)

    for split in ["train", "validation", "test"]:
        ds = load_dataset("edinburghcstr/ami", "ihm", split=split, streaming=True)
        records = []
        for row in tqdm(ds, desc=f"AMI {split}"):
            records.append({
                "meeting_id": row["meeting_id"],
                "audio_id": row["audio_id"],
                "text": row["text"],
                "begin_time": row["begin_time"],
                "end_time": row["end_time"],
                "speaker_id": row["speaker_id"],
            })

        with open(output_dir / f"{split}.json", "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False)

        print(f"  -> {len(records)} utterances saved ({split})")


def download_icsi():
    """Download ICSI Meeting Corpus."""
    load_dataset, _ = _optional_hf_imports()
    print("=" * 60)
    print("Downloading ICSI corpus...")
    ds = load_dataset("StDestiny/icsi_cleaned")
    ds.save_to_disk(DATA_DIR / "icsi")
    print(f"  -> Saved to {DATA_DIR / 'icsi'}")


def download_qmsum():
    """Download QMSum dataset."""
    load_dataset, _ = _optional_hf_imports()
    print("=" * 60)
    print("Downloading QMSum...")
    ds = load_dataset("pszemraj/qmsum-cleaned")
    ds.save_to_disk(DATA_DIR / "qmsum")
    print(f"  -> Saved to {DATA_DIR / 'qmsum'}")


if __name__ == "__main__":
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    download_ami()
    download_icsi()
    download_qmsum()
    print("=" * 60)
    print("All datasets downloaded.")
