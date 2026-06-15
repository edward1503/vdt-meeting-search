from __future__ import annotations

import sqlite3
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "harness.db"
CLI_PATH = ROOT / "scripts" / "bin" / "harness-cli.exe"
EXPECTED_COLUMNS = {
    "name",
    "provider",
    "command",
    "description",
    "args",
    "responsibility",
    "since",
    "kind",
    "capability",
    "scan_target",
    "status",
    "checked_at",
}


def main() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(tool)")}
        missing = EXPECTED_COLUMNS - columns
        if missing:
            raise AssertionError(f"tool table missing columns: {sorted(missing)}")

    summary = subprocess.run(
        [str(CLI_PATH), "query", "tools", "--summary"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    if "tool" not in summary.stdout.lower():
        raise AssertionError("tool summary did not include tool rows/header")

    present = subprocess.run(
        [str(CLI_PATH), "query", "tools", "--capability", "benchmark", "--status", "present"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    if "python" not in present.stdout.lower():
        raise AssertionError("benchmark capability query did not include python")

    print("Harness tool registry verification passed")


if __name__ == "__main__":
    main()
