from __future__ import annotations

import subprocess
from pathlib import Path


def test_highlight_terms_ignore_stopwords_and_split_matching_text(tmp_path: Path) -> None:
    script = tmp_path / "check-highlight.ts"
    helper_url = (Path.cwd() / "frontend/src/lib/highlight.ts").as_uri()
    script.write_text(
        f"""
import assert from 'node:assert/strict';
import {{ buildHighlightTerms, splitHighlightedText }} from '{helper_url}';

const terms = buildHighlightTerms('Scarface Nation was a book written by an arts critic of what nationality?');
assert.deepEqual(terms, ['scarface', 'nation', 'book', 'written', 'arts', 'critic', 'nationality']);

const segments = splitHighlightedText('The Scarface Nation book discusses an arts critic and national identity.', terms);
assert(segments.some((segment) => segment.highlighted && segment.text === 'Scarface'));
assert(segments.some((segment) => segment.highlighted && segment.text === 'Nation'));
assert(segments.some((segment) => segment.highlighted && segment.text === 'book'));
assert(!segments.some((segment) => segment.highlighted && segment.text.toLowerCase() === 'the'));
""".strip(),
        encoding="utf-8",
    )

    tsx = Path("frontend/node_modules/.bin/tsx.cmd")
    if not tsx.exists():
        tsx = Path("frontend/node_modules/.bin/tsx")

    result = subprocess.run(
        [str(tsx), str(script)],
        cwd=Path.cwd(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout


def test_search_view_renders_highlighted_result_text() -> None:
    source = Path("frontend/src/components/SearchView.tsx").read_text(encoding="utf-8")

    assert "buildHighlightTerms" in source
    assert "HighlightText" in source
    assert "highlightTerms={highlightTerms}" in source
