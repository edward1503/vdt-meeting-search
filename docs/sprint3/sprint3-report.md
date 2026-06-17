# Báo Cáo Sprint 3: HotpotQA 5M TurboVec Hybrid Retrieval

## 1. Mục tiêu và phạm vi

Sprint 3 đưa hệ thống retrieval HotpotQA từ các thí nghiệm nano lên full corpus `5,233,329` documents. Kiến trúc cuối cùng dùng Elasticsearch cho BM25 và lưu/hydrate document, TurboVec cho dense retrieval dạng nén, và Reciprocal Rank Fusion ở tầng application để tạo hybrid ranking.

Trạng thái: đã implement. Các phần đã hoàn thành gồm staging full corpus, ingest BM25, tạo embedding shards bằng BGE-small, build TurboVec index, benchmark 200 queries, tuning, expose method qua API, cập nhật frontend và validation tập trung.

Những phần vẫn nằm ngoài phạm vi Sprint 3: tích hợp VimQA, answer generation, LLM reasoning, fine-tune embedding, huấn luyện reranker, redesign frontend lớn, và chuyển iterative multi-hop retrieval thành default.

## 2. Môi trường đo đạc

Môi trường local dùng để build/benchmark:

- OS: Microsoft Windows 11 Home Single Language
- CPU: Intel(R) Core(TM) i5-10300H CPU @ 2.50GHz
- RAM: 15.8 GB
- Python: 3.12.4
- Elasticsearch: Docker Compose service `elasticsearch`, image `docker.elastic.co/elasticsearch/elasticsearch:8.15.1`
- Dense model: `BAAI/bge-small-en-v1.5`

Các số latency trong báo cáo này là số đo local trên laptop trên, chưa phải số production hay số đo trên target server.

## 3. Dataset và kích thước corpus

Nguồn corpus: HotpotQA full corpus theo format BEIR/Hugging Face-compatible.

Artifact staging đã hoàn thành:

- `artifacts/hotpotqa_full/staging/manifest.json`
- `docs_written=5,233,329`
- `files_written=105`
- `docs_per_file=50000`
- `numeric_id_start=0`
- `numeric_id_end=5,233,328`

Split dùng trong benchmark hiện tại:

- Dataset split: `beir/hotpotqa/dev`
- Pilot benchmark: `max_queries=200`
- Evaluation cutoff: `top_k=10`

Lưu ý: command kế hoạch ban đầu ghi `beir/hotpotqa`, nhưng benchmark runner cần split có queries và qrels. Vì vậy các benchmark đã đo dùng `beir/hotpotqa/dev`.

## 4. Kiến trúc hệ thống

Decision đã chấp nhận: `docs/decisions/0006-sprint3-dense-backend.md`.

Các thành phần chính:

- Elasticsearch: BM25 lexical index và document hydration store.
- TurboVec: compressed dense vector index dùng `IdMapIndex`, 4-bit quantization, và `uint64` numeric ids.
- Application layer: fuse BM25 ranking và dense ranking bằng RRF cho `tv_hybrid`.
- Legacy Elasticsearch dense/hybrid path vẫn có thể tồn tại cho nano/vector-enabled index cũ, nhưng không phải runtime full-corpus chính.

### 4.1 Pipeline end-to-end hiện tại

Runtime Sprint 3 hiện là pipeline retrieval hai backend:

```text
HotpotQA full corpus
  -> staging JSONL shards với numeric_id ổn định
  -> Elasticsearch BM25 index để lexical retrieval và lưu document
  -> BGE-small embedding shards từ title + text
  -> TurboVec 4-bit IdMapIndex để dense retrieval
  -> FastAPI search methods và support overlay
  -> Redis search-response cache và SQLite history
  -> React/Vite dashboard
```

Khi có query, hệ thống có ba đường chính:

```text
BM25 path:
query text
  -> Elasticsearch multi_match trên title^2 và content
  -> hydrated document hits

TurboVec dense path:
query text
  -> BGE-small query embedding
  -> TurboVec search trên mounted .tvim index
  -> numeric_id hits
  -> Elasticsearch terms lookup bằng numeric_id
  -> hydrated document hits

Hybrid path:
BM25 hits + TurboVec dense hits
  -> Reciprocal Rank Fusion
  -> top-k results
  -> support-doc matched/missing overlay từ HotpotQA qrels
```

TurboVec không thay thế Elasticsearch. Elasticsearch vẫn là lexical retriever và document store. TurboVec thay phần full-corpus dense vector search, vì đưa dense vector 5.23M docs vào Elasticsearch có rủi ro RAM/HNSW quá lớn trên laptop 16 GB.

### 4.2 Cách xử lý dữ liệu HotpotQA

HotpotQA được xử lý như một BEIR-style retrieval dataset: corpus documents, queries và qrels tách rời nhau. Demo hiện tại dùng full `beir/hotpotqa` corpus và split `beir/hotpotqa/dev` để lấy query preview + support labels.

Mỗi corpus document được normalize thành staging row:

```json
{
  "numeric_id": 123,
  "doc_id": "46979246",
  "title": "...",
  "text": "...",
  "url": "...",
  "content": "title + text",
  "embedding_text": "title + text"
}
```

Chính sách field:

| Field | Dùng cho | Có embed không? | Ghi chú |
| --- | --- | --- | --- |
| `title` | BM25, dense embedding, display | Có | Semantic metadata quan trọng nhất với Wikipedia-style docs. |
| `text` | BM25, dense embedding, display | Có | Nội dung chính của document. |
| `content` | Elasticsearch BM25 field | Gián tiếp | Được build từ `title + text`, dùng cho BM25 search. |
| `embedding_text` | Input offline embedding | Có | Được build từ `title + text`, không lưu như source field của BM25-only index. |
| `url` | Display/debug metadata | Không | Giữ để inspect, không dùng làm semantic input. |
| `doc_id` | BEIR/qrels identity và ES `_id` | Không | Operational identifier, không phải natural language evidence. |
| `numeric_id` | Join key giữa TurboVec và Elasticsearch | Không | Stable `uint64` bridge để hydrate dense hits từ ES. |

Điểm cần nhấn mạnh: hệ thống không bỏ qua semantic metadata. `title` đã được embed chung với `text`. Các metadata vận hành như `doc_id`, `numeric_id` và raw `url` cố ý không embed vì chúng ít semantic signal, dễ gây nhiễu dense vector, và làm benchmark khó giải thích hơn.

HotpotQA cũng cần validation theo multi-hop. BEIR qrels đánh dấu support ở mức document, và phần lớn query examples có hai support documents. Vì vậy UI và benchmark tập trung vào support coverage, đặc biệt `full_support_recall@10`, thay vì chỉ nhìn relevant document đầu tiên.

## 5. Index và build artifacts

Elasticsearch BM25 index:

- Index: `hotpotqa_full_bm25_v1`
- Alias demo/full profile: `hotpotqa_full_bm25_current`
- Validated count: `5,233,329`
- BM25-only mapping loại dense vectors và giữ `numeric_id` dưới dạng `long`.

Embedding artifacts:

- Directory: `artifacts/hotpotqa_full/embeddings/`
- Shards: 105 `.float16.npy`, 105 `.ids.npy`, và 105 `.meta.json` files
- Model: `BAAI/bge-small-en-v1.5`
- Dimension: 384
- Vector dtype: `float16`
- ID dtype: `uint64`

TurboVec artifacts:

- Index: `artifacts/hotpotqa_full/turbovec/hotpotqa_bge_small_4bit.tvim`
- Config: `artifacts/hotpotqa_full/turbovec/config.json`
- Config values: `docs=5,233,329`, `shards=105`, `dim=384`, `bit_width=4`
- Index size: 1,067,602,206 bytes

## 6. Cấu hình benchmark

Primary benchmark command:

```powershell
python -m src.evaluation.benchmark_es --dataset beir/hotpotqa/dev --index hotpotqa_full_bm25_v1 --methods es_bm25,tv_dense,tv_hybrid --top-k 10 --max-queries 200 --candidate-k 100 --num-candidates 100 --rrf-k 30 --output evaluation/results/hotpotqa_full/tv_full_200.json --run-dir evaluation/runs/hotpotqa_full
```

Tuning commands:

```powershell
python -m src.evaluation.benchmark_es --dataset beir/hotpotqa/dev --index hotpotqa_full_bm25_v1 --methods tv_hybrid --top-k 10 --max-queries 200 --candidate-k 50 --num-candidates 50 --rrf-k 30 --output evaluation/results/hotpotqa_full/tune_k50_rrf30.json --run-dir evaluation/runs/hotpotqa_full/tune_k50_rrf30
python -m src.evaluation.benchmark_es --dataset beir/hotpotqa/dev --index hotpotqa_full_bm25_v1 --methods tv_hybrid --top-k 10 --max-queries 200 --candidate-k 200 --num-candidates 200 --rrf-k 30 --output evaluation/results/hotpotqa_full/tune_k200_rrf30.json --run-dir evaluation/runs/hotpotqa_full/tune_k200_rrf30
python -m src.evaluation.benchmark_es --dataset beir/hotpotqa/dev --index hotpotqa_full_bm25_v1 --methods tv_hybrid --top-k 10 --max-queries 200 --candidate-k 100 --num-candidates 100 --rrf-k 60 --output evaluation/results/hotpotqa_full/tune_k100_rrf60.json --run-dir evaluation/runs/hotpotqa_full/tune_k100_rrf60
```

Filtered hybrid comparison command:

```powershell
python -m src.evaluation.benchmark_es --dataset beir/hotpotqa/dev --index hotpotqa_full_bm25_v1 --methods tv_filtered_hybrid --top-k 10 --max-queries 200 --candidate-k 100 --num-candidates 100 --rrf-k 30 --output evaluation/results/hotpotqa_full/tv_filtered_full_200.json --run-dir evaluation/runs/hotpotqa_full/tv_filtered_hybrid
```

Các số benchmark hiện tại là project-progress pilot trên 200 dev queries. Chưa dùng để claim paper-comparable với BEIR/HotpotQA test split.

## 7. Accuracy metrics

Primary 200-query benchmark (`evaluation/results/hotpotqa_full/tv_full_200.json`) cộng với filtered hybrid comparison:

| Method | precision@10 | recall@10 | mrr@10 | ndcg@10 | full_support_recall@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `es_bm25` | 0.1205 | 0.6025 | 0.7108 | 0.5727 | 0.365 |
| `tv_dense` | 0.1445 | 0.7225 | 0.8472 | 0.7082 | 0.515 |
| `tv_hybrid` | 0.1500 | 0.7500 | 0.8681 | 0.7286 | 0.545 |
| `tv_filtered_hybrid` | 0.1360 | 0.6800 | 0.8225 | 0.6735 | 0.455 |

Diễn giải:

- `tv_hybrid` tăng `full_support_recall@10` thêm `+0.180` absolute so với BM25 trong 200-query pilot.
- `tv_dense` cũng vượt BM25, chứng minh dense path bằng TurboVec có ích trên full corpus.
- `tv_filtered_hybrid` nhanh hơn broad hybrid nhưng mất `0.090` absolute full-support recall so với `tv_hybrid`.

## 8. Latency và QPS

Primary 200-query benchmark:

| Method | p50 ms | p95 ms | p99 ms | QPS |
| --- | ---: | ---: | ---: | ---: |
| `es_bm25` | 126.3355 | 359.6319 | 731.5949 | 5.9315 |
| `tv_dense` | 572.2161 | 868.0033 | 1214.8422 | 1.2499 |
| `tv_hybrid` | 1004.3562 | 3089.2229 | 4072.7476 | 0.7935 |
| `tv_filtered_hybrid` | 277.7706 | 1953.6118 | 2662.0642 | 1.7396 |

BM25 vẫn là path nhanh nhất. TurboVec dense và hybrid cải thiện retrieval quality nhưng tốn thêm thời gian embedding, vector search, fusion và hydration. Filtered hybrid nhanh hơn broad hybrid vì dense search bị giới hạn trong BM25 numeric-id allowlist, nhưng chính giới hạn này có thể làm mất support document ở hop thứ hai.

## 9. Kết quả tuning

Tất cả tuning và filtered comparison runs dùng 200 queries và `top_k=10`.

| Config | precision@10 | recall@10 | ndcg@10 | full_support_recall@10 | p50 ms | p95 ms | QPS | Artifact |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `k=50, rrf=30` | 0.1480 | 0.7400 | 0.7214 | 0.535 | 694.3532 | 2053.6018 | 0.8918 | `evaluation/results/hotpotqa_full/tune_k50_rrf30.json` |
| `k=100, rrf=30` | 0.1500 | 0.7500 | 0.7286 | 0.545 | 1004.3562 | 3089.2229 | 0.7935 | `evaluation/results/hotpotqa_full/tv_full_200.json` |
| `k=200, rrf=30` | 0.1495 | 0.7475 | 0.7282 | 0.540 | 811.1356 | 2528.6700 | 0.8488 | `evaluation/results/hotpotqa_full/tune_k200_rrf30.json` |
| `k=100, rrf=60` | 0.1490 | 0.7450 | 0.7246 | 0.535 | 919.7449 | 2111.4717 | 0.7895 | `evaluation/results/hotpotqa_full/tune_k100_rrf60.json` |
| `filtered k=100, rrf=30` | 0.1360 | 0.6800 | 0.6735 | 0.455 | 277.7706 | 1953.6118 | 1.7396 | `evaluation/results/hotpotqa_full/tv_filtered_full_200.json` |

Khuyến nghị method default: `tv_hybrid`.

Operating point nên dùng cho laptop demo: `candidate_k=50`, `num_candidates=50`, `rrf_k=30`. Config này giữ `full_support_recall@10` chỉ thấp hơn 0.010 absolute so với best measured config, trong khi giảm p95 khoảng 1 giây so với `k=100, rrf=30`.

Operating point quality-first: `candidate_k=100`, `num_candidates=100`, `rrf_k=30`.

## 10. API và demo notes

API hiện accept và route các method full-corpus chính:

- `es_bm25`
- `tv_dense`
- `tv_hybrid`
- `tv_filtered_hybrid`

Các Elasticsearch dense/hybrid legacy method không còn là full-corpus demo default. `DEFAULT_SEARCH_METHOD` hiện default sang `tv_hybrid`. TurboVec methods route qua `TurboVecHybridRetriever` và trả `latency_breakdown_ms` trong uncached response khi có timing data. Endpoint `/stats` báo cả Elasticsearch config và TurboVec config.

Cấu hình API/demo search hiện tại:

| Setting | Current value | Ý nghĩa |
| --- | --- | --- |
| `DATASET_ID` | `beir/hotpotqa/dev` | Query examples và qrels cho support overlay. |
| `ELASTICSEARCH_INDEX` | `hotpotqa_full_bm25_current` trong Docker full profile | Alias BM25 index và document hydration. |
| `DEFAULT_SEARCH_METHOD` | `tv_hybrid` | Method default của frontend/API. |
| Exposed methods | `es_bm25`, `tv_dense`, `tv_hybrid`, `tv_filtered_hybrid` | Các method demo full-corpus hiện tại. |
| Search `top_k` default | `10` | Số kết quả default trả về từ `/search`. |
| `HYBRID_BM25_K` | `100` | Số BM25 candidates API dùng cho TurboVec hybrid nếu không override. |
| `HYBRID_DENSE_K` | `100` | Số dense candidates API dùng cho TurboVec hybrid nếu không override. |
| `RRF_K` | `60` | RRF constant của API runtime từ `src/core/config.py`. Các benchmark comparison trong report này dùng `rrf_k=30` trừ khi ghi khác. |
| `TURBOVEC_DIM` | `384` | Khớp dimension của BGE-small embedding. |
| `TURBOVEC_BIT_WIDTH` | `4` | Cấu hình quantization của TurboVec. |
| `TURBOVEC_INDEX_PATH` | `artifacts/hotpotqa_full/turbovec/hotpotqa_bge_small_4bit.tvim` | Mounted dense index artifact. |
| `EMBEDDING_SERVICE_URL` | `http://host.docker.internal:8010/embed` trong Docker full profile | Host embedding service mà API container gọi. |
| `SEARCH_CACHE_TTL_SECONDS` | `300` | Redis TTL cho repeated `/search` responses. |

Khi trình bày/demo, cần phân biệt rõ hai loại cấu hình:

- API runtime defaults phục vụ Docker demo hiện tại và có thể đổi bằng environment variables.
- Benchmark protocol được cố định theo từng run và lưu trong result JSON. Primary quality comparison trong report này dùng 200 dev queries, `top_k=10`, `candidate_k=100`, `num_candidates=100`, và `rrf_k=30` cho broad `tv_hybrid`.

Focused API validation:

```text
python -m pytest tests/test_api_es_config.py tests/test_api_cache.py tests/test_search_history.py -q
9 passed, 3 warnings
```

## 11. Hạn chế hiện tại

- Benchmark chạy trên một Windows laptop khoảng 16 GB RAM; latency cần đo lại trên target deployment hardware trước khi claim production.
- `tv_filtered_hybrid` dùng BM25 `numeric_id` candidates làm TurboVec allowlist trước RRF fusion. 200-query benchmark nhanh hơn broad `tv_hybrid`, nhưng quality thấp hơn đủ rõ để chưa nên thay broad `tv_hybrid` làm default.
- Query embedding trong benchmark/API path vẫn local và synchronous, đóng góp đáng kể vào latency của dense/hybrid methods.
- BM25 vẫn là fallback low-latency tốt nhất khi yêu cầu quality thấp hơn hoặc khi dense path gặp vấn đề.
- Harness story verification commands vẫn cần cleanup để `story verify-all` chạy được như release check nhanh, không bị stale/heavyweight commands.
- Benchmark hiện tại chỉ là project-progress pilot 200 dev queries, chưa phải BEIR/paper-comparable result.

## 12. Bước tiếp theo

1. Investigate filtered hybrid recall loss bằng cách inspect các query mà broad `tv_hybrid` tìm đủ support documents nhưng `tv_filtered_hybrid` miss một document.
2. Cache query embeddings cho repeated benchmark/API queries.
3. Cân nhắc hạ API `HYBRID_BM25_K` và `HYBRID_DENSE_K` xuống 50 cho laptop demo, trong khi giữ 100 cho quality-first evaluation.
4. Re-run benchmark trên target deployment hardware và ghi một bảng latency theo platform.
5. Khi cần claim research/paper-comparable, chạy full `beir/hotpotqa/test` 7,405 queries với protocol cố định.

## Acceptance Evidence

```text
python scripts/es_hotpotqa.py validate --index hotpotqa_full_bm25_v1 --expected-count 5233329
count_matches=true

python -m pytest tests/test_benchmark_es.py tests/test_turbovec_retriever.py -q
10 passed

python -m pytest tests/test_api_es_config.py tests/test_api_cache.py tests/test_search_history.py -q
9 passed, 3 warnings

python scripts/verify_sprint3_benchmark.py
status=ok, queries=200, tv_hybrid_full_support_recall@10=0.545

python -m src.evaluation.benchmark_es --dataset beir/hotpotqa/dev --index hotpotqa_full_bm25_v1 --methods tv_filtered_hybrid --top-k 10 --max-queries 200 --candidate-k 100 --num-candidates 100 --rrf-k 30 --output evaluation/results/hotpotqa_full/tv_filtered_full_200.json --run-dir evaluation/runs/hotpotqa_full/tv_filtered_hybrid
tv_filtered_hybrid full_support_recall@10=0.455, p95=1953.6118ms, qps=1.7396
```

Primary artifacts:

- `artifacts/hotpotqa_full/staging/manifest.json`
- `artifacts/hotpotqa_full/turbovec/hotpotqa_bge_small_4bit.tvim`
- `artifacts/hotpotqa_full/turbovec/config.json`
- `evaluation/results/hotpotqa_full/tv_full_200.json`
- `evaluation/results/hotpotqa_full/tune_k50_rrf30.json`
- `evaluation/results/hotpotqa_full/tune_k200_rrf30.json`
- `evaluation/results/hotpotqa_full/tune_k100_rrf60.json`
- `evaluation/results/hotpotqa_full/tv_filtered_full_200.json`
- `evaluation/runs/hotpotqa_full/*.trec`
- `evaluation/runs/hotpotqa_full/tv_filtered_hybrid/*.trec`

## 13. Kết luận cho buổi trình bày

Sprint 3 đã hoàn thành mục tiêu engineering chính: hệ thống không còn dừng ở nano/5k docs hoặc Elasticsearch dense-vector nhỏ. Full HotpotQA `5,233,329` docs đã có BM25 index, dense embedding shards, TurboVec 4-bit index và API/frontend demo trên full profile.

Điểm nên nhấn mạnh với mentor:

- Elasticsearch vẫn giữ vai trò BM25 và document store; TurboVec thay dense vector search full corpus.
- Dense embedding hiện tại dùng `title + text`; metadata vận hành như `doc_id`, `numeric_id`, `url` không embed để tránh noise.
- `tv_hybrid` là default vì quality tốt nhất trong pilot: `full_support_recall@10=0.545`.
- `tv_filtered_hybrid` là hướng tối ưu latency nhưng đang mất recall, chưa nên làm default.
- Benchmark hiện tại là progress pilot 200 dev queries; muốn paper-comparable cần chạy full `beir/hotpotqa/test` 7,405 queries.