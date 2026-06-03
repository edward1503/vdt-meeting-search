# Changelog

> Lịch sử này được tổng hợp từ `git log --oneline --decorate -n 20`, `git show --stat -n 5`, và trạng thái working tree tại lần đồng bộ docs ngày 03/06/2026. Mục tiêu là giúp follow nhanh các mốc thay đổi như khi đọc GitHub commit history.

## 03/06/2026 — Docs sync theo codebase hiện tại

Status: working tree update, chưa commit.

### Changed
- Đồng bộ `docs/plan.md` với implementation hiện có: frontend demo, evaluation script, tests, ingest API, metadata embedding đều đã có code.
- Đồng bộ `docs/sprint_plan.md` từ checklist kế hoạch sang trạng thái thực tế của codebase.
- Đồng bộ `docs/decision_explanation.md` với tiến trình mới: status note, demo UI, evaluation matrix, ingest API, complex-query eval gap, và yêu cầu verify E2E benchmark.
- Thêm historical note vào `docs/brainstorming.md` để phân biệt brainstorm cũ với source of truth hiện tại.
- Ghi rõ phần chưa verify trong lượt này: benchmark E2E với Elasticsearch sống, metric cuối cùng, và complex-query evaluation set.
- Ghi chú trong `docs/processing.md` rằng `metadata_queries.jsonl` vẫn là planned artifact; pipeline hiện tại chưa thấy generator cho file này.

### Current working tree notes
- Có thay đổi chưa commit trong `README.md`, `docs/brainstorming.md`, `docs/decision_explanation.md`, `docs/plan.md`, `docs/research.md`, `docs/sprint_plan.md`, `start.sh`.
- Các file diagram/proposal cũ ở gốc `docs/` đang được di chuyển sang `docs/architecture/` và `docs/mentor-duty/`.
- File changelog này được thêm mới để theo dõi lịch sử và follow-up.

## c1f28f9 — feat: update baseline

### Highlights
- Cập nhật baseline vận hành: `Makefile`, Docker config, `start.sh`, embedding config và README.
- Thêm `docs/sprint_plan.md`.
- Thêm proposal docx ở `docs/Meeting-Semantic-Search-Proposal.docx` trước khi working tree hiện tại di chuyển sang `docs/mentor-duty/`.

### Files touched
- `.dockerignore`, `Makefile`, `README.md`, `docker/Dockerfile`, `docker/docker-compose.yml`, `docs/sprint_plan.md`, `src/core/config.py`, `src/embedding/model.py`, `start.sh`.

## 78d3e95 — docs: update proposal

### Highlights
- Cập nhật README/debai và thêm nhiều tài liệu proposal/brainstorming/diagram.
- Thêm app demo/reference trong `nexus-intelligence/` và archive `nexus-intelligence.zip`.

### Files touched
- `AGENTS.MD`, `README.md`, `debai.md`, `docs/architecture.svg`, `docs/benchmark_flow.svg`, `docs/brainstorming.md`, `docs/pipeline.svg`, `nexus-intelligence/*`.

## 488f8ad — feat: metadata embedding, prompt NLU, ingest API, demo UI, eval matrix, tests + CI

### Highlights
- Thêm metadata embedding song song với content embedding: `content_embedding` và `metadata_embedding`.
- Thêm rule-based prompt understanding cho source/speaker/date và lọc mềm.
- Mở rộng FastAPI: `POST /search`, `POST /meetings`, `PUT /meetings/{id}`, `DELETE /meetings/{id}`, API key cho write endpoints.
- Thêm demo UI static ở `frontend/index.html` và mount qua FastAPI.
- Mở rộng evaluation: metrics IR, latency p50/p95, matrix mode x channel.
- Thêm tests cho API, chunking, RRF fusion, query understanding.
- Cập nhật CI workflow.

### Files touched
- `.github/workflows/ci.yml`, `evaluation/run_eval.py`, `frontend/index.html`, `src/api/main.py`, `src/indexing/bulk_index.py`, `src/search/hybrid.py`, `src/search/query_understanding.py`, `tests/*`.

## f388d95 — docs: ground plan/research/processing to README

### Highlights
- Ground lại plan/research/processing theo yêu cầu README.
- Chốt hướng metadata embedding, prompt NLU theo topic/person/time, evaluation theo source và config.
- Thêm `docs/decision_explanation.md` bằng tiếng Việt để giải thích quyết định thiết kế.

### Files touched
- `docs/decision_explanation.md`, `docs/plan.md`, `docs/processing.md`, `docs/research.md`.

## 158f381 — update phase 1

### Highlights
- Thêm pipeline preprocessing QMSum/AMI, chunking, validation, JSONL helpers.
- Thêm embedding model wrapper, bulk indexing, hybrid search, evaluation baseline.
- Cập nhật docs plan/processing/research cho phase 1.

### Files touched
- `src/preprocessing/*`, `src/embedding/model.py`, `src/indexing/bulk_index.py`, `src/search/hybrid.py`, `evaluation/run_eval.py`, `docs/processing.md`, `docs/research.md`, `docs/plan.md`.

## Earlier history

| Commit | Summary |
|--------|---------|
| `821b889` | Split `plan.md` into `research.md` and `plan.md`. |
| `a968f6a` | Document reranking strategy. |
| `898bf3d` | Document embedding input strategy. |
| `286065f` | Document chunking strategy Method B. |
| `9d687a9` | Fix download script and AMI config. |
| `5908b71` | Add ICSI and QMSum download script support. |
| `d52db6a` | Add AMI corpus download script. |
| `1d6aa39` | Initial project setup with Docker infrastructure and FastAPI. |
| `8bf0e8e` | Add initial implementation plan and CI/CD structure. |

## Follow-up Checklist

- Run `make test` after docs/code changes if code changed again.
- Start Elasticsearch and run `make index` if processed data or index mapping changed.
- Run `python -m evaluation.run_eval --matrix --limit <n>` for a smoke benchmark, then full benchmark before final report.
- Decide whether to implement/generate `data/processed/metadata_queries.jsonl` for complex prompt evaluation.
- Commit diagram/proposal moves together with docs updates so GitHub history stays readable.
