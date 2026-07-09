# US-S5-013 Word Report Table Rendering

## Status

implemented

## Lane

normal

## Product Contract

The VDT submission Word report renders Markdown tables as real Word tables instead of flattening table rows into compact paragraphs.

## Relevant Product Docs

- `submission/bao-cao-vdt-2026.md`

## Acceptance Criteria

- Markdown tables in the submission source produce `docx` table elements.
- Header cells are visually distinct from data cells.
- Existing report paragraphs and headings continue to render through the same generator.

## Design Notes

- Commands: `python submission/generate_vdt_report.py`
- Tables: render with python-docx `Document.add_table`, `Table Grid`, compact Times New Roman cell text, and header shading.
- Domain rules: the report content remains unchanged; only Word formatting changes.

## Validation

| Layer | Expected proof |
| --- | --- |
| Unit | `pytest tests/test_generate_vdt_report.py -q` |
| Integration | `python submission/generate_vdt_report.py` |
| E2E | Read generated docx and confirm result tables exist. |
| Platform | Not required. |
| Release | Not required. |

## Harness Delta

None.

## Evidence

- RED: `pytest tests/test_generate_vdt_report.py -q` failed because `document.tables` was empty.
- GREEN: `pytest tests/test_generate_vdt_report.py -q` passed.
- Compile: `python -m py_compile submission/generate_vdt_report.py tests/test_generate_vdt_report.py` passed.
- Generated: `submission/bao-cao-vdt-2026.docx` and `submission/bao-cao-vdt-2026-theo-mau.docx`.
- Docx readback: generated report has 2 Word tables; the result table header is `Phương pháp`, `Full-support@10`, `Recall@10`, `nDCG@10`, `Độ trễ p95`.
