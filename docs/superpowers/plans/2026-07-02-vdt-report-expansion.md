# VDT Report Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the VDT submission report so the DOCX clearly presents the full-corpus retrieval pipeline, the two headline methods, the TurboVec/Elasticsearch architecture tradeoff, 200-query ablations, full-test benchmark results, paper comparisons, and concrete references.

**Architecture:** Keep `submission/bao-cao-vdt-2026.md` as the single source of truth and regenerate both DOCX outputs through `submission/generate_vdt_report.py`. Add focused report readback tests so regenerated DOCX content can be checked without opening Microsoft Word. Use only existing benchmark/report artifacts; do not rerun expensive retrieval benchmarks.

**Tech Stack:** Markdown, `python-docx`, `pytest`, Harness CLI, existing HotpotQA/VimQA benchmark artifacts.

---

## File Structure

- Modify `submission/bao-cao-vdt-2026.md`: rewrite and expand the report content while preserving the six VDT sections.
- Modify `tests/test_generate_vdt_report.py`: add a readback test for the generated DOCX or Markdown source proving key expanded content exists.
- Regenerate `submission/bao-cao-vdt-2026.docx` and `submission/bao-cao-vdt-2026-theo-mau.docx` with `submission/generate_vdt_report.py`.
- Read supporting files only as evidence sources:
  - `docs/sprint5/hotpotqa-test-benchmark-paper-comparison.md`
  - `docs/sprint5/hotpotqa-retrieval-results-summary.md`
  - `docs/sprint5/bridge-aware-second-support-report.md`
  - `docs/sprint5/bridge-aware-tuning-report.md`
  - `docs/sprint5/reranker-rrf-ablation-report.md`
  - `docs/sprint5/title-aware-bm25-ablation-report.md`
  - `docs/sprint3/full-corpus-retrieval-pipeline-vi.md`
  - `docs/decisions/0006-sprint3-dense-backend.md`

## Task 1: Add Report Content Readback Test

**Files:**
- Modify: `tests/test_generate_vdt_report.py`
- Read: `submission/bao-cao-vdt-2026.md`

- [ ] **Step 1: Add a failing source-content test**

Add this test to `tests/test_generate_vdt_report.py` after the existing table test:

```python
def test_submission_markdown_contains_expanded_vdt_sections() -> None:
    source = (ROOT / "submission" / "bao-cao-vdt-2026.md").read_text(encoding="utf-8")

    required_phrases = [
        "TurboVec không thay Elasticsearch",
        "tv_hybrid",
        "tv_bridge_title_entities_rrf",
        "Ablation 200 truy vấn",
        "full test 7,405 truy vấn",
        "Pyserini",
        "MDR",
        "Beam Retrieval",
        "IRCoT",
    ]

    for phrase in required_phrases:
        assert phrase in source
```

- [ ] **Step 2: Run the focused test and confirm it fails before the report rewrite**

Run:

```powershell
python -m pytest tests/test_generate_vdt_report.py -q
```

Expected: the new test fails because the current report source does not yet contain at least one required phrase, especially `Ablation 200 truy vấn` or `TurboVec không thay Elasticsearch`.

- [ ] **Step 3: Commit only the failing test if using strict TDD checkpoints**

Run:

```powershell
git add tests/test_generate_vdt_report.py
git commit -m "test: require expanded VDT report content"
```

Skip this commit if the user prefers a single final report commit; keep the test staged only with the implementation.

## Task 2: Rewrite The Markdown Report Source

**Files:**
- Modify: `submission/bao-cao-vdt-2026.md`
- Read: supporting report files listed in File Structure

- [ ] **Step 1: Replace the current Markdown body with the expanded six-section report**

Use these content rules while editing `submission/bao-cao-vdt-2026.md`:

```text
Section 1 must introduce the project as a full-corpus evidence retrieval workspace for HotpotQA and a dataset-first demo for HotpotQA/VimQA.
Section 2 must describe offline ingest, online retrieval, architecture components, and the TurboVec-versus-Elasticsearch tradeoff.
Section 2 must make tv_hybrid and tv_bridge_title_entities_rrf the two headline methods.
Section 3 must include full-test 7,405-query results with absolute and relative percentage deltas.
Section 3 must include a subsection titled "Ablation 200 truy vấn" with grouped benchmark tables.
Section 4 must evaluate quality, latency, explainability, and paper/benchmark comparison.
Section 5 must state conclusions, limitations, and next steps.
Section 6 must replace placeholder references with concrete references.
```

Keep these exact benchmark values in the expanded report:

```text
Full test:
tv_hybrid full_support@10=51.75%, recall@10=73.05%, MRR@10=84.13%, nDCG@10=70.01%, p95=0.76s.
tv_bridge_title_entities_rrf full_support@10=60.08%, recall@10=75.85%, MRR@10=82.51%, nDCG@10=71.20%, p95=1.60s.
Delta full_support@10 +8.33 percentage points, about +16.1% relative.
Delta recall@10 +2.80 percentage points, about +3.8% relative.
Delta nDCG@10 +1.19 percentage points, about +1.7% relative.
Delta p95 latency about +110.1% relative.

200-query ladder:
es_bm25 full_support@10=36.50%, recall@10=60.25%, nDCG@10=57.27%, p95=359.6319 ms.
tv_hybrid full_support@10=54.50%, recall@10=75.00%, nDCG@10=72.91%, p95=1146.5764 ms.

Title-aware BM25:
es_bm25 full_support@10=36.50%, recall@10=60.25%, MRR@10=71.08%, nDCG@10=57.27%.
es_bm25_title full_support@10=36.50%, recall@10=60.50%, MRR@10=71.59%, nDCG@10=57.86%.

Bridge ablation:
tv_hybrid full_support@10=54.50%, recall@10=75.00%, nDCG@10=72.91%, p95=1146.5764 ms.
tv_two_hop_bridge_rrf full_support@10=56.00%, recall@10=74.50%, nDCG@10=69.99%, p95=2773.5883 ms.
tv_bridge_title_entities_rrf full_support@10=62.00%, recall@10=78.50%, nDCG@10=73.98%, p95=2670.3591 ms.

Bridge tuning:
beam1_terms6 full_support@10=62.00%, recall@10=77.75%, nDCG@10=73.82%, p95=1224.9911 ms, qps=1.1034.
beam2_terms4 full_support@10=61.00%, recall@10=78.25%, nDCG@10=74.30%, p95=1758.8852 ms, qps=0.7452.
beam2_terms6 full_support@10=62.00%, recall@10=78.50%, nDCG@10=74.23%, p95=2593.4644 ms, qps=0.6062.
beam2_terms8 full_support@10=62.00%, recall@10=78.50%, nDCG@10=73.99%, p95=1827.7998 ms, qps=0.6896.
beam3_terms8 full_support@10=62.00%, recall@10=78.50%, nDCG@10=73.98%, p95=2670.3591 ms, qps=0.5206.
```

- [ ] **Step 2: Include the TurboVec/Elasticsearch explanation with cautious wording**

The report must include this meaning, not necessarily this exact wording:

```text
TurboVec không thay Elasticsearch. Elasticsearch vẫn là thành phần tốt nhất trong hệ thống cho BM25, filter, lưu document và hydrate kết quả. TurboVec được chọn cho dense retrieval full-corpus cục bộ vì dense_vector/HNSW của Elasticsearch trên 5.23M documents có rủi ro RAM và index overhead cao trong môi trường laptop. Cấu hình TurboVec 4-bit tạo artifact khoảng 1.07 GB và nối ngược về Elasticsearch bằng numeric_id.
```

- [ ] **Step 3: Include the paper-comparison caveat**

The report must include this meaning:

```text
Only BEIR/Pyserini nDCG@10 is a retrieval-style comparison. HotpotQA QA papers, MDR, Beam Retrieval, and IRCoT are used to compare motivation and retrieval design, not to claim direct leaderboard superiority. full_support@10 is evidence coverage before a reader/answer stage, not answer EM/F1.
```

## Task 3: Regenerate DOCX Outputs

**Files:**
- Modify/generated: `submission/bao-cao-vdt-2026.docx`
- Modify/generated: `submission/bao-cao-vdt-2026-theo-mau.docx`
- Read: `submission/generate_vdt_report.py`

- [ ] **Step 1: Check for Word lock file**

Run:

```powershell
Get-ChildItem submission -Force | Where-Object { $_.Name -like '~$*.docx' }
```

Expected: no lock files. If `submission/~$o-cao-vdt-2026.docx` exists, ask the user to close the DOCX in Word before regenerating.

- [ ] **Step 2: Regenerate the DOCX files**

Run:

```powershell
python submission/generate_vdt_report.py
```

Expected output includes:

```text
D:\VSCODE\vdt-meeting-search\submission\bao-cao-vdt-2026.docx
D:\VSCODE\vdt-meeting-search\submission\bao-cao-vdt-2026-theo-mau.docx
```

If generation fails because the DOCX is locked, stop and ask the user to close Word.

## Task 4: Verify Markdown, DOCX, And Tests

**Files:**
- Read: `submission/bao-cao-vdt-2026.md`
- Read: `submission/bao-cao-vdt-2026.docx`
- Run: `tests/test_generate_vdt_report.py`

- [ ] **Step 1: Run focused pytest**

Run:

```powershell
python -m pytest tests/test_generate_vdt_report.py -q
```

Expected:

```text
2 passed
```

- [ ] **Step 2: Read back generated DOCX text**

Run:

```powershell
python -c "from docx import Document; d=Document('submission/bao-cao-vdt-2026.docx'); text='\n'.join(p.text for p in d.paragraphs); checks=['TurboVec không thay Elasticsearch','tv_bridge_title_entities_rrf','Ablation 200 truy vấn','Pyserini','IRCoT']; missing=[c for c in checks if c not in text]; print('missing=', missing); print('tables=', len(d.tables))"
```

Expected:

```text
missing= []
tables= <a number greater than or equal to 6>
```

- [ ] **Step 3: Inspect the changed files**

Run:

```powershell
git diff --stat
git diff -- submission/bao-cao-vdt-2026.md tests/test_generate_vdt_report.py
```

Expected: diff only contains the intended report rewrite and focused test additions, plus generated DOCX binary changes.

## Task 5: Record Harness Evidence

**Files:**
- Read: `docs/TRACE_SPEC.md`
- Durable record: Harness intake/trace through `scripts/bin/harness-cli.exe`

- [ ] **Step 1: Record or update Harness intake**

Run:

```powershell
.\scripts\bin\harness-cli.exe intake --type "Change request" --summary "Expanded VDT submission report with pipeline, TurboVec architecture, ablations, benchmarks, paper comparison, and references" --lane tiny --flags "existing behavior,weak proof" --docs "submission/bao-cao-vdt-2026.md,submission/bao-cao-vdt-2026.docx,docs/superpowers/specs/2026-07-02-vdt-report-expansion-design.md"
```

Expected: prints an intake id. Use that id in the trace.

- [ ] **Step 2: Record Harness trace**

Run:

```powershell
.\scripts\bin\harness-cli.exe trace --summary "Expanded and regenerated VDT submission report" --intake <INTAKE_ID> --agent codex --outcome completed --actions "read approved spec,expanded report markdown,regenerated docx outputs,ran report tests,read back docx content" --read "docs/superpowers/specs/2026-07-02-vdt-report-expansion-design.md,submission/generate_vdt_report.py,docs/sprint5/hotpotqa-test-benchmark-paper-comparison.md,docs/sprint5/hotpotqa-retrieval-results-summary.md,docs/sprint5/bridge-aware-second-support-report.md,docs/sprint5/bridge-aware-tuning-report.md,docs/sprint5/reranker-rrf-ablation-report.md,docs/sprint5/title-aware-bm25-ablation-report.md,docs/TRACE_SPEC.md" --changed "submission/bao-cao-vdt-2026.md,submission/bao-cao-vdt-2026.docx,submission/bao-cao-vdt-2026-theo-mau.docx,tests/test_generate_vdt_report.py" --friction "none"
```

Expected: trace meets the required tier for a tiny-lane change.

## Task 6: Final Review And Commit

**Files:**
- Commit: intended report/test/generated DOCX changes only
- Do not stage unrelated pre-existing modified frontend/API/test files

- [ ] **Step 1: Check status**

Run:

```powershell
git status --short
```

Expected: includes only intended new changes from this plan plus any unrelated pre-existing user changes. Do not stage unrelated pre-existing changes.

- [ ] **Step 2: Commit report changes**

Run:

```powershell
git add submission/bao-cao-vdt-2026.md submission/bao-cao-vdt-2026.docx submission/bao-cao-vdt-2026-theo-mau.docx tests/test_generate_vdt_report.py
git commit -m "Expand VDT submission report"
```

Expected: one commit containing the expanded report source, regenerated DOCX files, and report tests.

- [ ] **Step 3: Prepare final response**

Mention:

```text
Updated submission/bao-cao-vdt-2026.md and regenerated both DOCX outputs.
Added expanded pipeline/architecture, TurboVec vs Elasticsearch explanation, two headline methods, 200-query ablations, full-test percentage deltas, paper comparison, and references.
Verification: python -m pytest tests/test_generate_vdt_report.py -q passed; DOCX readback found required sections and tables.
```

## Self-Review

- Spec coverage: The plan maps each approved spec requirement to Tasks 1-4, with Harness trace and commit steps in Tasks 5-6.
- Placeholder scan: The only angle-bracket placeholder is `<INTAKE_ID>` in a command that explicitly depends on the prior Harness output; replace it with the printed id during execution.
- Scope check: This remains a single report-generation change. It does not touch retrieval code, API behavior, frontend behavior, or benchmark execution.
