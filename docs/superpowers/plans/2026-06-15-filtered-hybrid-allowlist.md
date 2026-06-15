# Filtered Hybrid Allowlist Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `tv_filtered_hybrid` a real BM25-candidate-filtered TurboVec hybrid mode instead of an alias of broad `tv_hybrid`.

**Architecture:** Preserve the current `TurboVecHybridRetriever` boundary. BM25 first produces lexical candidates with `numeric_id`; those ids become a TurboVec `allowlist`; dense search runs inside that candidate set; final ranking still uses existing RRF fusion between BM25 hits and filtered dense hits. If BM25 hits do not contain usable `numeric_id` values, the mode falls back to broad dense search while reusing the already computed BM25 hits.

**Tech Stack:** Python 3.12, pytest, NumPy, Elasticsearch retriever helpers, TurboVec `IdMapIndex.search(..., allowlist=...)`, existing Sprint 3 benchmark/API code.

---

## Scope

In scope:

- Preserve `numeric_id` in Elasticsearch BM25 hits so filtered hybrid can build an allowlist in real runtime.
- Implement `tv_filtered_hybrid` as BM25 allowlist + TurboVec filtered dense search + RRF.
- Keep `tv_hybrid` behavior unchanged.
- Keep `tv_dense` behavior unchanged.
- Add focused unit tests for allowlist behavior, missing-id filtering, and fallback behavior.
- Update Sprint 3 docs that currently describe `tv_filtered_hybrid` as only a follow-up.

Out of scope:

- Running a full 200-query filtered benchmark.
- Changing the default method from `tv_hybrid` to `tv_filtered_hybrid`.
- Docker dependency work for TurboVec runtime.
- Reader/reranker or learned multi-hop retrieval.

## File Structure

- Modify `src/retrieval/elasticsearch_retriever.py`:
  - Preserve `_source.numeric_id` in returned hit dictionaries when present.
- Modify `src/retrieval/turbovec_retriever.py`:
  - Add allowlist construction helper.
  - Add `_search_filtered_hybrid()`.
  - Route `method == "tv_filtered_hybrid"` to the new implementation.
- Modify `tests/test_elasticsearch_retriever.py`:
  - Add a regression test that BM25 search returns `numeric_id`.
- Modify `tests/test_turbovec_retriever.py`:
  - Add tests for true allowlist use and fallback behavior.
- Modify `docs/sprint3/sprint3-report.md`:
  - Replace stale limitation text that says filtered hybrid is functionally equivalent to broad hybrid.
- Modify `docs/sprint3/turbovec-explained-vi.md`:
  - Update the Vietnamese explanation of `tv_filtered_hybrid` to describe implemented behavior.

Note: existing untracked docs `docs/sprint3/retrieval-metrics-vi.md` and `docs/sprint3/turbovec-explained-vi.md` should not be deleted or reverted.

---

### Task 1: Preserve `numeric_id` In Elasticsearch Hits

**Files:**

- Modify: `tests/test_elasticsearch_retriever.py`
- Modify: `src/retrieval/elasticsearch_retriever.py`

- [ ] **Step 1: Add the failing regression test**

Append this test to `tests/test_elasticsearch_retriever.py`:

```python
def test_bm25_search_preserves_numeric_id_from_source():
    class FakeES:
        def search(self, index, body):
            assert index == "idx"
            return {
                "hits": {
                    "hits": [
                        {
                            "_id": "d7",
                            "_score": 2.5,
                            "_source": {
                                "numeric_id": 7,
                                "doc_id": "d7",
                                "title": "Title",
                                "text": "Body",
                                "url": "",
                            },
                        }
                    ]
                }
            }

    retriever = ElasticsearchRetriever(es=FakeES(), index="idx", model_name="model")

    hits = retriever.search("query", "bm25", top_k=1)

    assert hits == [
        {
            "numeric_id": 7,
            "doc_id": "d7",
            "title": "Title",
            "text": "Body",
            "url": "",
            "score": 2.5,
            "source": "bm25",
        }
    ]
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```powershell
python -m pytest tests/test_elasticsearch_retriever.py::test_bm25_search_preserves_numeric_id_from_source -q
```

Expected result before implementation:

```text
FAILED ... assert hits == ...
```

The failure should show the actual hit is missing `numeric_id`.

- [ ] **Step 3: Implement numeric id preservation**

In `src/retrieval/elasticsearch_retriever.py`, replace the body of the loop inside `_search_body()` with this structure:

```python
        for hit in response.get("hits", {}).get("hits", []):
            src = hit.get("_source", {})
            result = {
                "doc_id": src.get("doc_id", hit.get("_id", "")),
                "title": src.get("title", ""),
                "text": src.get("text", ""),
                "url": src.get("url", ""),
                "score": float(hit.get("_score", 0.0)),
                "source": source,
            }
            if "numeric_id" in src and src["numeric_id"] is not None:
                result["numeric_id"] = int(src["numeric_id"])
            hits.append(result)
```

- [ ] **Step 4: Verify the focused test passes**

Run:

```powershell
python -m pytest tests/test_elasticsearch_retriever.py::test_bm25_search_preserves_numeric_id_from_source -q
```

Expected result:

```text
1 passed
```

- [ ] **Step 5: Commit this slice**

Run:

```powershell
git add tests/test_elasticsearch_retriever.py src/retrieval/elasticsearch_retriever.py
git commit -m "fix: preserve numeric ids in elasticsearch hits"
```

If the user has not approved commits in this session, skip the commit command and report the exact files changed.

---

### Task 2: Add Filtered Hybrid Allowlist Tests

**Files:**

- Modify: `tests/test_turbovec_retriever.py`

- [ ] **Step 1: Add an allowlist behavior test**

Append this test to `tests/test_turbovec_retriever.py`:

```python
def test_tv_filtered_hybrid_uses_bm25_numeric_ids_as_turbovec_allowlist():
    calls = []

    class FakeESRetriever:
        def search(self, query, method, top_k, candidate_k=100, rrf_k=60):
            assert query == "query"
            assert method == "bm25"
            assert top_k == 4
            return [
                {"doc_id": "d1", "numeric_id": 1, "title": "A", "source": "bm25"},
                {"doc_id": "d2", "numeric_id": 2, "title": "B", "source": "bm25"},
                {"doc_id": "missing-id", "title": "Missing", "source": "bm25"},
                {"doc_id": "d2-duplicate", "numeric_id": 2, "title": "Dup", "source": "bm25"},
            ]

    class FakeTVIndex:
        def search(self, queries, k, allowlist=None):
            calls.append({"k": k, "allowlist": allowlist})
            assert queries.shape == (1, 2)
            return np.array([[0.9, 0.8]], dtype=np.float32), np.array([[2, 1]], dtype=np.uint64)

    class FakeEmbedder:
        def encode(self, texts, normalize_embeddings, convert_to_numpy):
            assert texts == ["query"]
            assert normalize_embeddings is True
            assert convert_to_numpy is True
            return np.array([[1.0, 0.0]], dtype=np.float32)

    class FakeDocStore:
        def hydrate_by_numeric_ids(self, numeric_ids):
            docs = {
                1: {"doc_id": "d1", "numeric_id": 1, "title": "A"},
                2: {"doc_id": "d2", "numeric_id": 2, "title": "B"},
            }
            return [docs[int(numeric_id)] for numeric_id in numeric_ids]

    retriever = TurboVecHybridRetriever(
        bm25_retriever=FakeESRetriever(),
        tv_index=FakeTVIndex(),
        embedder=FakeEmbedder(),
        docstore=FakeDocStore(),
    )

    hits = retriever.search("query", method="tv_filtered_hybrid", top_k=2, bm25_k=4, dense_k=10, rrf_k=30)

    assert calls[0]["k"] == 2
    assert calls[0]["allowlist"].dtype == np.uint64
    assert calls[0]["allowlist"].tolist() == [1, 2]
    assert [hit["doc_id"] for hit in hits] == ["d2", "d1"]
    assert hits[0]["source"] == "bm25+dense"
    assert "allowlist" in retriever.last_timing_ms
```

- [ ] **Step 2: Add a fallback behavior test**

Append this test to `tests/test_turbovec_retriever.py`:

```python
def test_tv_filtered_hybrid_falls_back_to_broad_dense_when_allowlist_is_empty():
    calls = []

    class FakeESRetriever:
        def search(self, query, method, top_k, candidate_k=100, rrf_k=60):
            return [
                {"doc_id": "d1", "title": "A", "source": "bm25"},
                {"doc_id": "d2", "numeric_id": None, "title": "B", "source": "bm25"},
            ]

    class FakeTVIndex:
        def search(self, queries, k, allowlist=None):
            calls.append({"k": k, "allowlist": allowlist})
            return np.array([[0.7]], dtype=np.float32), np.array([[3]], dtype=np.uint64)

    class FakeEmbedder:
        def encode(self, texts, normalize_embeddings, convert_to_numpy):
            return np.array([[1.0, 0.0]], dtype=np.float32)

    class FakeDocStore:
        def hydrate_by_numeric_ids(self, numeric_ids):
            return [{"doc_id": "d3", "numeric_id": 3, "title": "C"}]

    retriever = TurboVecHybridRetriever(
        bm25_retriever=FakeESRetriever(),
        tv_index=FakeTVIndex(),
        embedder=FakeEmbedder(),
        docstore=FakeDocStore(),
    )

    hits = retriever.search("query", method="tv_filtered_hybrid", top_k=2, bm25_k=2, dense_k=5, rrf_k=30)

    assert calls == [{"k": 5, "allowlist": None}]
    assert [hit["doc_id"] for hit in hits] == ["d1", "d3"]
```

- [ ] **Step 3: Run the new tests and verify they fail**

Run:

```powershell
python -m pytest tests/test_turbovec_retriever.py::test_tv_filtered_hybrid_uses_bm25_numeric_ids_as_turbovec_allowlist tests/test_turbovec_retriever.py::test_tv_filtered_hybrid_falls_back_to_broad_dense_when_allowlist_is_empty -q
```

Expected result before implementation:

```text
FAILED ... allowlist ...
```

The current code routes `tv_filtered_hybrid` to broad `_search_hybrid()`, so the first test should show `allowlist` is `None` instead of `np.uint64([1, 2])`.

---

### Task 3: Implement Real `tv_filtered_hybrid`

**Files:**

- Modify: `src/retrieval/turbovec_retriever.py`

- [ ] **Step 1: Add allowlist construction helper**

In `src/retrieval/turbovec_retriever.py`, add this method inside `TurboVecHybridRetriever` below `_embed_query()`:

```python
    def _build_allowlist(self, hits: list[dict[str, Any]]) -> np.ndarray | None:
        ids: list[int] = []
        seen: set[int] = set()
        for hit in hits:
            raw_numeric_id = hit.get("numeric_id")
            if raw_numeric_id is None:
                continue
            try:
                numeric_id = int(raw_numeric_id)
            except (TypeError, ValueError):
                continue
            if numeric_id in seen:
                continue
            seen.add(numeric_id)
            ids.append(numeric_id)
        if not ids:
            return None
        return np.asarray(ids, dtype=np.uint64)
```

- [ ] **Step 2: Add filtered hybrid implementation**

In `src/retrieval/turbovec_retriever.py`, add this method below `_search_hybrid()`:

```python
    def _search_filtered_hybrid(self, query: str, top_k: int, bm25_k: int, dense_k: int, rrf_k: int) -> list[dict[str, Any]]:
        start = time.perf_counter()
        bm25_hits = self.bm25_retriever.search(query, "bm25", bm25_k)
        bm25_ms = (time.perf_counter() - start) * 1000

        start = time.perf_counter()
        allowlist = self._build_allowlist(bm25_hits)
        allowlist_ms = (time.perf_counter() - start) * 1000

        dense_search_k = min(dense_k, len(allowlist)) if allowlist is not None else dense_k
        dense_hits = self._search_dense(query, dense_search_k, allowlist=allowlist)
        timing = {**self.last_timing_ms, "bm25": bm25_ms, "allowlist": allowlist_ms}

        start = time.perf_counter()
        fused = fuse_rrf([bm25_hits, dense_hits], top_k=top_k, rrf_k=rrf_k)
        timing["fusion"] = (time.perf_counter() - start) * 1000
        self.last_timing_ms = timing
        return fused
```

- [ ] **Step 3: Route `tv_filtered_hybrid` to the new method**

In `TurboVecHybridRetriever.search()`, replace the current `tv_filtered_hybrid` branch:

```python
        if method == "tv_filtered_hybrid":
            return self._search_hybrid(query, top_k, bm25_k=bm25_k, dense_k=dense_k, rrf_k=rrf_k)
```

with:

```python
        if method == "tv_filtered_hybrid":
            return self._search_filtered_hybrid(query, top_k, bm25_k=bm25_k, dense_k=dense_k, rrf_k=rrf_k)
```

- [ ] **Step 4: Run the filtered hybrid tests**

Run:

```powershell
python -m pytest tests/test_turbovec_retriever.py -q
```

Expected result:

```text
3 passed
```

- [ ] **Step 5: Commit this slice**

Run:

```powershell
git add tests/test_turbovec_retriever.py src/retrieval/turbovec_retriever.py
git commit -m "feat: implement filtered turbovec hybrid search"
```

If the user has not approved commits in this session, skip the commit command and report the exact files changed.

---

### Task 4: Verify Benchmark/API Compatibility

**Files:**

- Verify: `tests/test_benchmark_es.py`
- Verify: `tests/test_api_es_config.py`
- Verify: `tests/test_api_cache.py`
- Verify: `tests/test_search_history.py`

- [ ] **Step 1: Check test capability is present**

Run:

```powershell
.\scripts\bin\harness-cli.exe query tools --capability test --status present
```

Expected result includes:

```text
pytest ... present
```

- [ ] **Step 2: Run retrieval and benchmark tests**

Run:

```powershell
python -m pytest tests/test_elasticsearch_retriever.py tests/test_turbovec_retriever.py tests/test_benchmark_es.py -q
```

Expected result after implementation:

```text
all selected tests passed
```

- [ ] **Step 3: Run API focused tests**

Run:

```powershell
python -m pytest tests/test_api_es_config.py tests/test_api_cache.py tests/test_search_history.py -q
```

Expected result after implementation:

```text
9 passed
```

Warnings are acceptable if they are the existing FastAPI deprecation warnings already present in prior Sprint 3 validation.

- [ ] **Step 4: Run whitespace check**

Run:

```powershell
git diff --check
```

Expected result:

```text
no output and exit code 0
```

---

### Task 5: Update Sprint 3 Documentation

**Files:**

- Modify: `docs/sprint3/sprint3-report.md`
- Modify: `docs/sprint3/turbovec-explained-vi.md`

- [ ] **Step 1: Update Sprint 3 report limitation**

In `docs/sprint3/sprint3-report.md`, replace this limitation:

```markdown
- The measured `tv_filtered_hybrid` path remains functionally equivalent to broad hybrid search; allowlist-optimized dense search is still a follow-up.
```

with:

```markdown
- `tv_filtered_hybrid` now uses BM25 `numeric_id` candidates as a TurboVec allowlist before RRF fusion. It still needs a fresh full benchmark before it can replace broad `tv_hybrid` as the recommended default.
```

- [ ] **Step 2: Update Sprint 3 next step**

In `docs/sprint3/sprint3-report.md`, replace this next step:

```markdown
1. Add an optimized `tv_filtered_hybrid` allowlist path and benchmark it against broad `tv_hybrid`.
```

with:

```markdown
1. Benchmark the implemented `tv_filtered_hybrid` allowlist path against broad `tv_hybrid` on the same 200-query and full-dev settings.
```

- [ ] **Step 3: Update Vietnamese TurboVec explanation**

In `docs/sprint3/turbovec-explained-vi.md`, replace the `tv_filtered_hybrid` section with:

```markdown
### `tv_filtered_hybrid`

`tv_filtered_hybrid` dùng BM25 làm bước lọc candidate trước. Thay vì để TurboVec search toàn bộ 5.23M vector, hệ thống lấy `numeric_id` từ các BM25 hits, truyền danh sách đó vào TurboVec `allowlist`, rồi dense search chỉ trong tập candidate này. Kết quả cuối vẫn được fuse với BM25 bằng RRF.

Nên dùng khi:

- Muốn giảm search space của dense retrieval.
- Query có lexical signal đủ tốt để BM25 tạo candidate set đáng tin.
- Muốn thử trade-off latency/quality so với broad `tv_hybrid`.

Trade-off:

- Nếu BM25 không đưa support doc vào candidate set, filtered dense search cũng không thể tìm lại document đó.
- Nếu Elasticsearch hit thiếu `numeric_id` hoặc index không khớp TurboVec artifact, mode này phải fallback sang dense search rộng hoặc trả kết quả kém.
- Cần benchmark riêng trước khi dùng làm default.
```

- [ ] **Step 4: Verify docs wording**

Run:

```powershell
rg -n "functionally equivalent|allowlist-optimized dense search is still a follow-up|vẫn chưa được tối ưu thật sự" docs/sprint3
```

Expected result after doc updates:

```text
no matches
```

- [ ] **Step 5: Commit doc updates**

Run:

```powershell
git add docs/sprint3/sprint3-report.md docs/sprint3/turbovec-explained-vi.md
git commit -m "docs: describe filtered hybrid allowlist behavior"
```

If the user has not approved commits in this session, skip the commit command and report the exact files changed.

---

### Task 6: Harness Records And Final Evidence

**Files:**

- Modify durable local state: `harness.db`

- [ ] **Step 1: Record story evidence for US-S3-008**

Run after tests pass:

```powershell
.\scripts\bin\harness-cli.exe story update --id US-S3-008 --unit 1 --integration 0 --e2e 0 --platform 0 --evidence "python -m pytest tests/test_elasticsearch_retriever.py tests/test_turbovec_retriever.py tests/test_benchmark_es.py -q passed; tv_filtered_hybrid now uses BM25 numeric_id allowlist for TurboVec search with broad dense fallback when no allowlist exists."
```

Expected result:

```text
Story US-S3-008 updated.
```

- [ ] **Step 2: Record trace**

Run:

```powershell
.\scripts\bin\harness-cli.exe trace --summary "Completed optimized tv_filtered_hybrid allowlist retrieval mode" --intake 10 --story US-S3-008 --agent codex --outcome completed --actions "preserved numeric_id in Elasticsearch hits,added filtered hybrid allowlist tests,implemented TurboVec allowlist path,updated Sprint 3 docs,ran focused pytest suites" --read "src/retrieval/elasticsearch_retriever.py,src/retrieval/turbovec_retriever.py,tests/test_elasticsearch_retriever.py,tests/test_turbovec_retriever.py,docs/sprint3/sprint3-report.md,docs/sprint3/turbovec-explained-vi.md" --changed "src/retrieval/elasticsearch_retriever.py,src/retrieval/turbovec_retriever.py,tests/test_elasticsearch_retriever.py,tests/test_turbovec_retriever.py,docs/sprint3/sprint3-report.md,docs/sprint3/turbovec-explained-vi.md,harness.db" --errors "none" --friction "none" --notes "Full 200-query benchmark remains a follow-up; this task proves behavior with focused unit and compatibility tests."
```

Expected result:

```text
Trace recorded and tier meets normal-lane requirement.
```

- [ ] **Step 3: Final status check**

Run:

```powershell
git status --short
```

Expected result:

```text
Only intentional implementation, test, doc, and local harness DB changes are present.
```

If the two Vietnamese docs from the prior task remain untracked, keep them and mention them separately. Do not delete or revert them.

## Self-Review

- Spec coverage: The plan implements BM25 `numeric_id` preservation, true TurboVec allowlist filtering, fallback behavior, RRF fusion preservation, tests, docs, and Harness evidence.
- Open-item scan: The plan contains no unfinished sections or unspecified code paths.
- Type consistency: `numeric_id` is normalized to `int` in hit dictionaries and converted to `np.ndarray` with `dtype=np.uint64` before passing to TurboVec `allowlist`.
- Risk note: This plan does not claim quality or latency improvement until a fresh benchmark is run; it only proves behavior and compatibility.
