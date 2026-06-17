# Full-Corpus HotpotQA Retrieval Pipeline: BM25, Elasticsearch, TurboVec và các câu hỏi phản biện

## 1. Mục tiêu tài liệu

Tài liệu này giải thích lại toàn bộ pipeline retrieval hiện tại của Sprint 3 theo hướng có thể dùng để demo, bảo vệ thiết kế, hoặc tự kiểm tra hệ thống. Nó trả lời các câu hỏi chính:

- BM25 hoạt động như thế nào và vì sao vẫn cần trong hệ dense retrieval?
- Elasticsearch đang xử lý dữ liệu HotpotQA như thế nào?
- HotpotQA có điểm gì đặc biệt so với một bộ search thông thường?
- Query, qrels, docs nối với nhau ra sao, preview nên đọc như thế nào?
- Chiến lược xử lý của hệ thống là gì?
- Metadata và document có được embed chung không?
- Hệ thống hiện tại mạnh ở đâu, yếu ở đâu, cần tự chất vấn gì trước khi claim kết quả?

Kết luận ngắn: hệ thống hiện tại là một full-corpus HotpotQA retrieval demo. Elasticsearch giữ BM25 và document store. TurboVec giữ dense vector index. API fuse kết quả bằng Reciprocal Rank Fusion. Frontend hiển thị search, query preview, benchmark, status và history trên profile full corpus.

## 2. Mental model tổng thể

Pipeline hiện tại có thể hiểu như sau:

```text
HotpotQA full corpus
  -> staging JSONL shards
  -> Elasticsearch BM25 index
  -> embedding shards
  -> TurboVec dense index
  -> FastAPI retrieval methods
  -> Redis cache + SQLite history
  -> React dashboard
```

Có hai đường retrieval chính:

```text
BM25 path:
query text
  -> Elasticsearch multi_match(title^2, content)
  -> full document hits

TurboVec dense path:
query text
  -> BGE-small embedding
  -> TurboVec vector search
  -> numeric_id hits
  -> Elasticsearch hydrate by numeric_id
  -> full document hits

Hybrid path:
BM25 hits + TurboVec hits
  -> RRF fusion
  -> top-k results
  -> support overlay for HotpotQA qrels
```

Nói rất thẳng: TurboVec không thay Elasticsearch. TurboVec thay phần dense vector search full corpus mà Elasticsearch dense_vector không phù hợp với máy local 16GB. Elasticsearch vẫn là text search engine và document store.

## 3. HotpotQA đặc biệt ở đâu?

HotpotQA không chỉ là bài toán tìm một passage giống query nhất. Nó là multi-hop QA. Một query thường cần đủ hai supporting documents để suy luận ra câu trả lời.

Ví dụ từ EDA nano:

```text
Query:
Which of the campaign that brought out the term Vichy Republican on social media was formally launched on June 16, 2015, at Trump Tower in New York City?

Support docs:
49892372 -> nói về thuật ngữ Vichy Republican và liên hệ đến campaign của Donald Trump.
46979246 -> nói campaign Donald Trump 2016 được launched ở Trump Tower ngày 2015-06-16.
```

Nếu hệ thống chỉ retrieve đúng một trong hai docs, user có thể thấy kết quả có vẻ liên quan nhưng vẫn thiếu evidence chain. Vì vậy metric quan trọng không chỉ là `precision@10`, mà là:

- `recall@10`: có lấy được support docs không?
- `mrr@10`: support đầu tiên xuất hiện sớm không?
- `ndcg@10`: ranking support docs tốt không?
- `full_support_recall@10`: có lấy đủ toàn bộ support docs trong top 10 không?

Điểm rất quan trọng: với HotpotQA, `precision@10` nhìn có thể thấp vì mỗi query thường chỉ có 2 relevant docs trong top 10. Nếu hệ thống lấy được trung bình 1.5 support docs trong top 10 thì `precision@10` khoảng `0.15`, không phải là thảm họa như một bài classification thông thường.

## 4. Dữ liệu HotpotQA trong hệ thống hiện tại

Full corpus đang dùng:

| Thành phần | Giá trị hiện tại |
| --- | ---: |
| Corpus docs | 5,233,329 |
| Staging files | 105 |
| Docs per staging file | 50,000 |
| Active query split | `beir/hotpotqa/dev` |
| Dev queries | 5,447 |
| Pilot benchmark queries | 200 |
| Test queries để so sánh paper | 7,405 |

Mỗi document full BEIR HotpotQA có các field quan trọng:

| Field | Vai trò |
| --- | --- |
| `doc_id` | ID gốc của document, dạng string. Dùng làm Elasticsearch `_id`. |
| `title` | Title/page/entity signal. Được search và được đưa vào embedding text. |
| `text` | Nội dung document. Được search và được đưa vào embedding text. |
| `url` | Metadata hiển thị/debug. Không được embed trong pipeline hiện tại. |
| `content` | Chuỗi `title + text`, dùng cho BM25 field trong Elasticsearch. |
| `embedding_text` | Chuỗi `title + text`, dùng khi encode embedding shards. Không lưu vào Elasticsearch BM25 source. |
| `numeric_id` | ID số tuần tự từ 0 đến 5,233,328. Là cầu nối TurboVec với Elasticsearch. |

Staging row có dạng:

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

`numeric_id` tồn tại vì TurboVec `IdMapIndex` làm việc bằng ID số `uint64`, còn HotpotQA `doc_id` là string. Không có `numeric_id` thì dense result từ TurboVec sẽ khó hydrate ngược về document gốc.

## 5. Metadata có được nhúng chung với docs không?

Câu trả lời chính xác: không phải toàn bộ metadata đều được embed chung.

Hiện tại:

- `title` được đưa vào `content` và `embedding_text`, nên title có tham gia cả BM25 lẫn dense embedding.
- `text` được đưa vào `content` và `embedding_text`, nên body document có tham gia cả BM25 lẫn dense embedding.
- `url` không được đưa vào `embedding_text`; nó chỉ là metadata lưu trong Elasticsearch để hiển thị/debug.
- `doc_id` không được embed; nó là định danh.
- `numeric_id` không được embed; nó chỉ là khóa nối TurboVec với Elasticsearch.
- `embedding_text` không được lưu vào BM25-only Elasticsearch source; nó là field staging dùng lúc encode.

Vì vậy câu nói đúng là:

```text
Dense embedding hiện tại được sinh từ title + text.
Metadata định danh như doc_id, numeric_id, url không được nhúng vào vector.
Elasticsearch lưu metadata để hydrate, inspect, support overlay và UI.
```

Có nên embed URL hoặc doc_id không? Thường là không. `doc_id` và `numeric_id` không mang nghĩa ngôn ngữ. `url` có thể chứa token hữu ích trong một số corpus, nhưng cũng dễ gây noise. Với HotpotQA, title là metadata giàu nghĩa nhất, nên đưa title vào text là hợp lý.

## 6. BM25 hoạt động như thế nào?

BM25 là lexical retrieval. Nó tìm document dựa trên từ khóa trong query và document. Trực giác của BM25:

- Nếu document chứa nhiều query terms, điểm tăng.
- Nếu term hiếm trong toàn corpus xuất hiện, điểm tăng mạnh hơn term phổ biến.
- Nếu document quá dài, điểm được normalize để document dài không thắng chỉ vì chứa nhiều từ.
- Nếu một term lặp quá nhiều lần trong cùng document, điểm tăng chậm dần thay vì tăng tuyến tính.

Trong Elasticsearch, query hiện tại là `multi_match`:

```json
{
  "query": {
    "multi_match": {
      "query": "user query",
      "fields": ["title^2", "content"]
    }
  }
}
```

Ý nghĩa:

- Search cả `title` và `content`.
- `title^2` nghĩa là match ở title được boost gấp 2 so với content.
- `content` là `title + text`, nên vẫn giữ toàn bộ signal lexical của document.

Vì sao title boost quan trọng? HotpotQA là entity-heavy. Nhiều support documents là Wikipedia pages. Nếu query nhắc đến một entity, title match thường là tín hiệu rất mạnh.

Ví dụ:

```text
Query: What occupations do both Ian Hunter and Rob Thomas have?
```

BM25 sẽ rất thích docs có title/text chứa `Ian Hunter`, `Rob Thomas`, `occupations`, `singer`, `songwriter`. Với comparison questions, lexical overlap giúp tìm các page entity khá tốt.

## 7. Elasticsearch xử lý data như thế nào?

Elasticsearch hiện có hai vai trò:

1. BM25 lexical index.
2. Document store để hydrate kết quả TurboVec.

BM25-only mapping hiện tại gồm:

| Field | ES type | Vai trò |
| --- | --- | --- |
| `numeric_id` | `long` | Join key với TurboVec. |
| `doc_id` | `keyword` | Stable ID, exact lookup, ES `_id`. |
| `title` | `text` | Search/display title. |
| `text` | `text` | Search/display body. |
| `url` | `keyword` | Metadata, exact value. |
| `content` | `text` | Search field chính cho BM25. |

Quy trình ingest:

```text
scripts/stage_hotpotqa.py
  -> load ir_datasets beir/hotpotqa docs
  -> normalize whitespace
  -> build content = title + text
  -> assign numeric_id
  -> write docs-xxxxx.jsonl + manifest.json

scripts/es_hotpotqa.py create-bm25-index
  -> create ES index with BM25-only mapping
  -> attach alias hotpotqa_full_bm25_current

scripts/es_hotpotqa.py ingest-bm25
  -> read staging files
  -> helpers.bulk() into ES
  -> write progress marker docs-xxxxx.done
  -> refresh after ingest

scripts/es_hotpotqa.py validate
  -> count index
  -> expected 5,233,329
```

Điểm thiết kế quan trọng:

- BM25-only index không lưu dense vector trong Elasticsearch.
- `numeric_id` được lưu trong ES để filtered hybrid và hydration dùng được.
- `_source` khi search chỉ lấy `numeric_id`, `doc_id`, `title`, `text`, `url`, tránh kéo field thừa.
- Progress markers giúp ingest resume nếu dừng giữa chừng.

## 8. TurboVec xử lý dense retrieval như thế nào?

Dense pipeline:

```text
staging JSONL
  -> scripts/embed_hotpotqa.py
  -> encode row["embedding_text"] bằng BAAI/bge-small-en-v1.5
  -> save vectors .float16.npy
  -> save numeric ids .ids.npy
  -> scripts/build_turbovec.py
  -> IdMapIndex(dim=384, bit_width=4)
  -> hotpotqa_bge_small_4bit.tvim
```

Artifacts chính:

| Artifact | Ý nghĩa |
| --- | --- |
| `artifacts/hotpotqa_full/embeddings/*.float16.npy` | Vector embedding theo shard. |
| `artifacts/hotpotqa_full/embeddings/*.ids.npy` | `numeric_id` tương ứng mỗi vector. |
| `artifacts/hotpotqa_full/embeddings/*.meta.json` | Metadata shard: model, dims, docs. |
| `artifacts/hotpotqa_full/turbovec/hotpotqa_bge_small_4bit.tvim` | TurboVec compressed dense index. |
| `artifacts/hotpotqa_full/turbovec/config.json` | `docs`, `dim`, `bit_width`, `shards`. |

Khi search:

```text
query
  -> embedding service encode query thành vector 384 chiều
  -> TurboVec search vector trên .tvim
  -> trả về numeric_id và similarity score
  -> Elasticsearch terms query by numeric_id
  -> hydrate thành doc_id/title/text/url
```

Trong Docker, API container không chạy PyTorch/SentenceTransformers trực tiếp. Nó gọi embedding service ở host qua `http://host.docker.internal:8010/embed`. Đây là cách migration nhẹ: container API không phình vì model runtime.

## 9. Các method retrieval hiện tại

| Method | Cách chạy | Điểm mạnh | Điểm yếu |
| --- | --- | --- | --- |
| `es_bm25` | Elasticsearch BM25 trên `title^2 + content`. | Nhanh, ổn định, tốt với entity/date/exact terms. | Miss semantic bridge nếu lexical overlap thấp. |
| `tv_dense` | Embed query, search TurboVec full dense index, hydrate ES. | Bắt semantic/paraphrase tốt hơn BM25. | Chậm hơn BM25, yếu với exact rare tokens. |
| `tv_hybrid` | Chạy BM25 + TurboVec dense rộng, fuse bằng RRF. | Best quality trong pilot hiện tại. | Latency cao nhất. |
| `tv_filtered_hybrid` | BM25 tạo allowlist numeric_id, TurboVec search trong allowlist, fuse RRF. | Giảm search space, nhanh hơn broad hybrid. | Nếu BM25 không đưa support doc vào allowlist thì dense không cứu được. |

Benchmark pilot 200 dev queries:

| Method | Precision@10 | Recall@10 | MRR@10 | nDCG@10 | Full support@10 | p95 ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `es_bm25` | 0.1205 | 0.6025 | 0.7108 | 0.5727 | 0.365 | 360 |
| `tv_dense` | 0.1445 | 0.7225 | 0.8472 | 0.7082 | 0.515 | 868 |
| `tv_hybrid` | 0.1500 | 0.7500 | 0.8681 | 0.7286 | 0.545 | 3089 |
| `tv_filtered_hybrid` | 0.1360 | 0.6800 | 0.8225 | 0.6735 | 0.455 | 1954 |

Kết luận từ số liệu hiện tại:

- `tv_hybrid` tốt nhất về quality.
- `es_bm25` nhanh nhất và vẫn là fallback cần giữ.
- `tv_dense` chứng minh dense path có ích trên full corpus.
- `tv_filtered_hybrid` nhanh hơn broad hybrid nhưng mất support recall quá nhiều để làm default.

## 10. RRF fusion là gì và vì sao dùng?

RRF là Reciprocal Rank Fusion. Nó cộng điểm dựa trên thứ hạng, không cộng raw score.

Công thức:

```text
RRF_score(doc) = sum(1 / (rrf_k + rank_i(doc)))
```

Nếu một document đứng cao trong cả BM25 và dense, nó được đẩy lên cao. Nếu một document chỉ có ở dense nhưng rank rất cao, nó vẫn có cơ hội vào top-k.

Vì sao không cộng score trực tiếp?

- BM25 score và dense similarity không cùng thang đo.
- BM25 score phụ thuộc corpus/analyzer/term statistics.
- Dense score phụ thuộc vector similarity và normalization.
- RRF tránh phải calibrate score giữa hai hệ.

Điều này hợp với Sprint 3 vì mục tiêu là baseline engineering sạch, dễ debug, không cần train reranker trước.

## 11. Preview data nên đọc như thế nào?

Một preview tốt cần cho thấy 4 thứ:

1. Query text.
2. Support doc IDs từ qrels.
3. Top results từ method đang chạy.
4. Result nào trùng support, result nào còn thiếu.

Ví dụ cách đọc một query:

```text
query_id = 5a811667554299260e20a23d
query = What occupations do both Ian Hunter and Rob Thomas have?
support_doc_ids = [6668827, 580274]
```

Nếu search top 10 trả:

```text
rank 1: 6668827, is_support=true
rank 2: ...
rank 5: 580274, is_support=true
```

Thì query này đạt full support trong top 10. Nếu chỉ có `6668827` mà thiếu `580274`, hệ thống có partial recall nhưng fail `full_support_recall@10`.

Frontend nên giúp người xem trả lời nhanh:

- Query này có bao nhiêu support docs?
- Top-k đã match được mấy support docs?
- Missing support doc IDs là gì?
- Những result không phải support có vẻ là false positive hay là evidence gần đúng?
- BM25 và TurboVec cùng tìm một doc hay mỗi bên tìm một hop khác nhau?

## 12. Chiến lược xử lý hiện tại

Chiến lược Sprint 3 là tối ưu theo thứ tự:

1. Đưa full corpus vào persistent storage trước.
2. Giữ BM25 làm baseline và document store.
3. Tách dense vector search ra TurboVec để tránh Elasticsearch dense overhead.
4. Dùng `numeric_id` làm join key ổn định giữa ES và TurboVec.
5. Dùng RRF để fuse lexical và semantic signal.
6. Dùng benchmark pilot để chọn default demo.
7. Giữ legacy nano ở lịch sử, không để nó lẫn với runtime full.

Đây là lựa chọn thực dụng vì máy local có giới hạn RAM. Nó không phải thuật toán retrieval mới, nhưng là một kiến trúc đủ sạch để:

- scale từ 5k docs lên 5.23M docs;
- benchmark được 4 method hiện tại;
- inspect được support docs trên UI;
- vận hành được trong Docker mà không mount toàn bộ dependency model vào API image.

## 13. Tự phản biện hệ thống

### 13.1. Câu hỏi về dữ liệu

**Q1. Full corpus đã thật sự là 5,233,329 docs chưa?**

Có bằng staging manifest và ES validation trong Sprint 3 report. Tuy vậy, khi demo trên máy khác vẫn phải chạy lại validate count cho alias đang dùng, vì alias sai là lỗi rất dễ xảy ra.

**Q2. Query browser đang dùng toàn bộ dev queries hay chỉ sample?**

API `/queries` dùng `beir/hotpotqa/dev` khi `ir_datasets` có sẵn, fallback sang TSV checked-in trong Docker. Frontend phân trang. Cần kiểm tra `total` từ endpoint để chắc UI không chỉ đang show vài chục query cũ.

**Q3. Qrels của HotpotQA trong BEIR có đủ sentence-level supporting facts không?**

Không. BEIR qrels ở mức document. Nếu sau này làm answer generation hoặc explainable QA sentence-level, cần map lại HotpotQA gốc hoặc Wikipedia preprocessing có sentence offsets.

**Q4. Có giữ title/url đầy đủ không?**

Full BEIR có `title` và `url`; staging giữ cả hai. Nano legacy thiếu title/url nên không nên dùng nano để suy ra behavior full.

**Q5. Có normalize làm mất thông tin không?**

Staging collapse whitespace nhưng không sửa typo hoặc artifact Wikipedia. Đây là đúng cho benchmark công bằng, nhưng UI preview có thể nhìn hơi xấu với các artifact như nối chữ hoặc ký tự lạ.

### 13.2. Câu hỏi về indexing

**Q6. BM25 index có chứa dense vector không?**

Không trong full current path. BM25-only mapping loại dense vector để giảm overhead. Dense vector nằm trong TurboVec `.tvim`.

**Q7. Metadata nào tham gia search?**

`title` và `content` tham gia BM25. `title` và `text` tham gia dense embedding thông qua `embedding_text`. `url`, `doc_id`, `numeric_id` không tham gia embedding.

**Q8. Nếu TurboVec và Elasticsearch build từ hai staging khác nhau thì sao?**

Hệ thống có thể hydrate sai hoặc mất kết quả. Đây là rủi ro lớn. Cần so sánh manifest/config: `docs`, `numeric_id_start/end`, model, dim, bit_width, index alias.

**Q9. `numeric_id` có bền không?**

Bền nếu staging order không đổi. Nếu rebuild corpus theo thứ tự khác, cùng `doc_id` có thể nhận `numeric_id` khác. Do đó ES index và TurboVec artifact phải được coi như một cặp build artifact.

**Q10. Có cần index `url` dạng text để search không?**

Hiện không. `url` là keyword metadata. Nếu sau này query có URL/path signal thì có thể cân nhắc, nhưng với HotpotQA title/text quan trọng hơn.

### 13.3. Câu hỏi về retrieval quality

**Q11. Vì sao `tv_filtered_hybrid` nhanh hơn nhưng recall thấp hơn?**

Vì dense search bị giới hạn trong BM25 allowlist. Nếu BM25 không đưa support doc thứ hai vào candidate set, TurboVec không có cơ hội tìm nó. Với multi-hop bridge questions, đây là lỗi rất tự nhiên.

**Q12. Vì sao `tv_hybrid` vẫn chỉ full_support@10 = 0.545?**

Vì hệ thống vẫn là single-turn retrieval fusion, chưa học evidence chain. HotpotQA cần hop reasoning. Broad hybrid giúp nhưng chưa thay thế MDR-style hoặc reranker pairwise.

**Q13. Có nên dùng `tv_dense` thay `tv_hybrid` không?**

Không làm default hiện tại. `tv_dense` tốt hơn BM25 nhưng thấp hơn `tv_hybrid` về full support. Tuy nhiên nó là diagnostic rất tốt để biết dense index có ích thật hay không.

**Q14. Có nên chỉ dùng BM25 vì nhanh hơn không?**

Nếu demo nhấn latency, có. Nếu demo nhấn retrieval quality/full support, không. BM25 p95 nhanh nhưng full_support@10 thấp hơn `tv_hybrid` 0.180 absolute trong pilot.

**Q15. Có cần reranker không?**

Có thể cần ở Sprint sau. RRF chỉ fuse rank đơn giản. Reranker cross-encoder hoặc pairwise evidence reranker có thể giúp reorder top candidates, nhưng sẽ tăng latency và complexity.

### 13.4. Câu hỏi về benchmark

**Q16. 200 queries có đủ so sánh với papers không?**

Không. 200 queries là project-progress pilot. Muốn paper-comparable cần chạy full `beir/hotpotqa/test` 7,405 queries, cố định top-k/config/hardware, và ghi protocol rõ.

**Q17. Benchmark latency có đại diện production không?**

Không hoàn toàn. Nó đo trên Windows laptop i5-10300H, RAM 15.8GB. Target hardware khác có thể thay đổi p95 rất nhiều.

**Q18. Có leak hay mismatch giữa dev/test không?**

Hiện demo dùng dev queries/qrels. Nếu báo cáo nghiên cứu, cần tách rõ dev để tuning, test để final. Không dùng test để chọn hyperparameter.

**Q19. Metric `full_support_recall@10` đã đủ chưa?**

Nó rất hữu ích nhưng chưa đủ cho answer QA. Nó chỉ biết đủ docs trong top-k, chưa biết câu trả lời có suy luận đúng không, chưa biết sentence evidence đúng không.

**Q20. Có cần benchmark nhiều top_k hơn không?**

Có. Top 10 tốt cho UI demo, nhưng research nên xem recall@20/50/100 để biết retriever có chứa evidence trong candidate pool cho reranker/reader không.

### 13.5. Câu hỏi về vận hành

**Q21. Docker hiện là full local hay hybrid local + container?**

Hiện là nhẹ theo hướng hybrid: ES/Redis/API/frontend trong Docker, TurboVec artifact mount từ local, embedding service chạy trên host. Cách này tránh build PyTorch/SentenceTransformers vào API image.

**Q22. Redis cache có làm sai benchmark/demo không?**

Cache tốt cho repeated UI search, nhưng benchmark offline không nên bị cache API response chi phối. Khi đo latency retrieval thật, cần ghi rõ có cache hay không.

**Q23. API startup có load TurboVec ngay không?**

`get_tv_retriever()` lazy-load qua cache khi method TV được gọi. First request có thể chậm hơn warm request do load `.tvim` và embedding warmup.

**Q24. Nếu embedding service chết thì sao?**

BM25 vẫn chạy. TurboVec methods sẽ fail hoặc timeout vì không embed được query. UI cần hiển thị lỗi rõ và cho fallback `es_bm25`.

**Q25. Search cache key đã đủ phân biệt chưa?**

Cache key gồm index, query_id, query, method, top_k. Nếu thay hybrid k/rrf/env mà key không đổi, cache có thể trả response cũ. Đây là điểm cần cải thiện nếu tuning runtime thường xuyên.

### 13.6. Câu hỏi về frontend/demo

**Q26. User nhìn Search làm sao biết đúng support docs?**

Search response có `support` summary và mỗi result có `is_support`. UI cần làm nổi bật matched/missing support docs. Nếu chỉ show title/text thì người xem phải dò tay, rất mệt.

**Q27. Query preview có nên load 100k queries vào browser không?**

Không. Cần phân trang endpoint. Hiện `/queries` có `limit`, `offset`, `search`, frontend mặc định 10/trang. Đây là đúng hướng.

**Q28. Bấm query preview sang Search có hợp lý không?**

Có. Nó biến query browser thành entrypoint demo: chọn query có qrels, handoff sang Search, auto-run method, xem support coverage.

**Q29. Benchmark page có nên giữ legacy nano không?**

Có, nhưng phải đặt dưới current full-corpus và label rõ là legacy/history. Không để người xem nhầm nano là runtime hiện tại.

**Q30. Status page cần show gì để tránh nhầm scope?**

Cần show index alias, corpus doc count, dataset split, default method, TurboVec path, embedding service URL, cache TTL. Đây là các field quyết định demo đang chạy đúng full profile hay không.

## 14. Diễn giải lại toàn bộ hệ thống bằng lời đơn giản

Hệ thống giống như có hai người tìm tài liệu:

- Người thứ nhất là Elasticsearch BM25. Người này rất giỏi tìm chữ khớp: tên người, địa danh, ngày tháng, cụm từ hiếm. Người này nhanh.
- Người thứ hai là TurboVec dense search. Người này không nhìn chữ y hệt, mà nhìn nghĩa của câu hỏi và nghĩa của tài liệu qua vector embedding. Người này chậm hơn nhưng tìm được những tài liệu liên quan theo nghĩa.

HotpotQA khó vì một câu hỏi thường cần hai tài liệu. Một tài liệu có thể nói về entity trung gian, tài liệu còn lại mới chứa đáp án. Nếu chỉ tìm một tài liệu đúng thì chưa đủ.

Vì vậy hệ thống làm như sau:

1. Lấy toàn bộ 5.23M documents HotpotQA.
2. Chuẩn hóa mỗi document thành `title`, `text`, `url`, `content`, `numeric_id`.
3. Đưa `title + text` vào Elasticsearch để BM25 search.
4. Đưa `title + text` qua embedding model để tạo vector.
5. Nén vector vào TurboVec 4-bit để chứa được full corpus trên máy local.
6. Khi user search, chạy BM25, TurboVec hoặc cả hai.
7. Nếu chạy hybrid, fuse hai ranking bằng RRF.
8. Dùng Elasticsearch lấy lại document đầy đủ từ `numeric_id`.
9. So với qrels để đánh dấu result nào là support document.
10. Frontend hiển thị query, results, support matched/missing, benchmark và status.

Điểm mạnh hiện tại: đã chuyển được từ 5k docs legacy lên 5.23M docs full corpus, có dense retrieval thật bằng TurboVec, có hybrid quality tốt hơn BM25, có benchmark và UI bám runtime full.

Điểm yếu hiện tại: benchmark mới là 200-query pilot, latency đo trên laptop, query embedding còn synchronous, filtered hybrid mất recall, và hệ thống chưa có learned multi-hop retriever hoặc reranker.

## 15. Chiến lược tiếp theo nên hỏi và làm gì?

Nếu mục tiêu là demo ổn định:

1. Giữ default `tv_hybrid` nhưng cân nhắc k=50 cho laptop demo.
2. Luôn show status full corpus trước khi demo.
3. Chọn vài query có matched support rõ để demo handoff Queries -> Search.
4. Giữ `es_bm25` làm fallback nếu embedding service/TurboVec chậm.

Nếu mục tiêu là báo cáo nghiên cứu:

1. Chạy full `beir/hotpotqa/test` 7,405 queries.
2. Tách dev tuning và test final.
3. Báo cáo thêm recall@20/50/100.
4. Thêm analysis per query type: bridge, comparison, entity-heavy, lexical-low-overlap.
5. Inspect filtered hybrid failure cases.

Nếu mục tiêu là cải thiện chất lượng:

1. Cache query embeddings.
2. Rerank top candidates bằng cross-encoder hoặc lightweight reranker.
3. Thử hop-conditioned retrieval: retrieve hop 1, sinh/condition query hop 2.
4. Log entity/title overlap để hiểu khi nào BM25 thắng dense và ngược lại.
5. Xây debug view so sánh BM25-only, dense-only, hybrid trên cùng query.

## 16. Source of truth trong repo

Các file chính cần đọc khi audit pipeline:

| File | Vai trò |
| --- | --- |
| `src/data/staging.py` | Normalize document, tạo `content`, `embedding_text`, `numeric_id`. |
| `scripts/stage_hotpotqa.py` | Stage corpus từ `ir_datasets`. |
| `scripts/es_hotpotqa.py` | Create/index/ingest/validate/search Elasticsearch. |
| `src/retrieval/elasticsearch_retriever.py` | BM25 query, ES mapping, RRF fusion, ES retriever. |
| `scripts/embed_hotpotqa.py` | Encode staging shards thành embedding shards. |
| `scripts/build_turbovec.py` | Build TurboVec `IdMapIndex`. |
| `src/retrieval/turbovec_retriever.py` | TurboVec dense/hybrid/filtered search và hydrate từ ES. |
| `src/api/main.py` | API methods, cache, support overlay, benchmark payload. |
| `docs/sprint3/sprint3-report.md` | Metrics, artifacts, limitations và recommendation Sprint 3. |
| `docs/data/hotpotqa/hotpotqa_eda.md` | EDA, preview query/qrels/docs, HotpotQA dataset notes. |

## 17. Câu trả lời ngắn cho câu hỏi lớn

**BM25 làm gì?** Tìm theo lexical overlap trên `title^2` và `content`, nhanh và mạnh với entity/date/exact terms.

**Elasticsearch xử lý data ra sao?** Nó lưu `numeric_id`, `doc_id`, `title`, `text`, `url`, `content`; index BM25; hydrate kết quả TurboVec bằng `numeric_id`.

**HotpotQA đặc biệt gì?** Multi-hop, thường cần đủ 2 support docs, qrels ở mức document trong BEIR, nên cần `full_support_recall@k` và UI support overlay.

**Preview nên xem gì?** Query, support doc IDs, top results, `is_support`, matched/missing support docs, source BM25/dense/hybrid.

**Chiến lược xử lý là gì?** ES cho BM25 + document store, TurboVec cho dense full corpus, RRF cho hybrid, Redis cache cho repeated UI search, benchmark pilot để chọn default.

**Metadata có embed chung không?** Chỉ `title + text` được embed. `url`, `doc_id`, `numeric_id` không embed; chúng là metadata/keys để hiển thị, hydrate và nối hệ thống.

**Hệ thống đã đủ để claim paper chưa?** Chưa. Hiện đủ để demo full-corpus Sprint 3 và báo cáo progress. Muốn paper-comparable cần full test benchmark 7,405 queries và protocol chặt hơn.