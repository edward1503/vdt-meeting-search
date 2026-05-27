"""Download AMI, ICSI, and QMSum meeting datasets from HuggingFace (raw only)."""

from pathlib import Path
from datasets import load_dataset

DATA_DIR = Path("data/raw")


def download_ami():
    """Download AMI corpus (edinburghcstr/ami, config=ihm)."""
    print("=" * 60)
    print("Downloading AMI transcripts...")
    ds = load_dataset("edinburghcstr/ami", "ihm", trust_remote_code=True)
    ds.save_to_disk(DATA_DIR / "ami")
    print(f"  -> Saved to {DATA_DIR / 'ami'}")


def download_icsi():
    """Download ICSI Meeting Corpus (StDestiny/icsi_cleaned)."""
    print("=" * 60)
    print("Downloading ICSI corpus...")
    ds = load_dataset("StDestiny/icsi_cleaned")
    ds.save_to_disk(DATA_DIR / "icsi")
    print(f"  -> Saved to {DATA_DIR / 'icsi'}")


def download_qmsum():
    """Download QMSum dataset (pszemraj/qmsum-cleaned)."""
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
