# Kịch Bản Slide Và Báo Cáo VDT 2026

Ngày cập nhật: 2026-06-30

Thông điệp xuyên suốt:

```text
Hệ thống này là full-corpus evidence retrieval workspace cho multi-hop QA và
semantic metadata search. Trọng tâm không phải sinh câu trả lời cuối cùng,
mà là tìm đủ bằng chứng, chạy được trên corpus lớn, đo bằng metric đúng,
và giải thích được vì sao kết quả được trả về.
```

Không kể theo sprint. Kể theo câu chuyện: bài toán -> survey -> thiết kế ->
kỹ thuật -> benchmark -> demo -> đóng góp -> giới hạn.

## 0. Timebox Tổng Thể

| Phần | Thời lượng | Nội dung |
| --- | ---: | --- |
| Bài toán + input/output + ví dụ | 1 phút 30 giây | Giải thích vì sao multi-hop retrieval khác search thường. |
| Survey giải pháp hiện nay | 1 phút 30 giây | Open-source research vs closed-source tools, rút insight. |
| Pipeline ingest và search | 3 phút | 2 slide riêng: offline ingest và online search. |
| Engineering, DB, datasets | 2 phút | Hệ thống thật, index, cache, history, API/UI. |
| Benchmark va ablation | 4 phut | Accuracy, latency, resource, TurboVec, bridge-aware. |
| Video demo | 2 phut | Happy cases, paraphrase, metadata, zero result. |
| Đóng góp, giới hạn, next steps | 1 phút 30 giây | Claim an toàn, không overclaim. |

## 1. Slide: Title

**Tiêu đề**

```text
Không gian truy xuất bằng chứng cho QA đa bước
và tìm kiếm metadata ngữ nghĩa
```

**Subtitle**

```text
Full-corpus HotpotQA/VimQA retrieval with Elasticsearch, TurboVec,
hybrid fusion, bridge-aware retrieval, and semantic metadata search
```

**Speaker note**

Mở đầu bằng câu: "Em tập trung vào tầng retrieval: trước khi sinh câu trả lời,
hệ thống cần tìm đúng và đủ các tài liệu làm bằng chứng."

## 2. Slide: Bài Toán, Input/Output, Ví Dụ 1p30s

**Lên slide**

```text
Input:
  Một câu hỏi / truy vấn tự nhiên

Output:
  Top-k documents làm evidence
  + thông tin support document nào đã tìm thấy / còn thiếu

Khác search thông thường:
  Search thường: tìm một tài liệu liên quan
  Multi-hop QA: cần tìm đủ bộ supporting documents
```

**Ví dụ nên nói**

```text
Question: What company produced the show on which Cliff Clavin was a character?

Cần 2 bước evidence:
  1. Cliff Clavin là character trong show nào?
  2. Show đó do company nào sản xuất?

Nếu top-10 chỉ có evidence 1 mà thiếu evidence 2,
downstream reader/LLM vẫn có thể trả lời sai.
```

**Speaker note**

Noi ro metric chinh:

```text
Vì vậy em dùng full_support@10: một query chỉ thành công khi top-10 chứa
đủ tất cả gold supporting documents.
```

## 3. Slide: Survey - Open-Source Research

**Len slide**

| Huong | Dai dien | Uu diem | Han che |
| --- | --- | --- | --- |
| Sparse retrieval | BM25, SPLADE | Nhanh, de debug, manh voi entity/keyword | Yeu khi paraphrase manh, lexical mismatch |
| Dense retrieval | Contriever, BGE, DPR/MDR | Bat ngu nghia tot hon, robust voi paraphrase | Can embedding/index, kho filter metadata hon |
| Hybrid retrieval | BM25 + dense + RRF | Can bang lexical va semantic | Them latency, can tune candidate budget |
| Multi-hop retrieval | MDR, IRCoT, Beam Retrieval | Mo hinh hoa chuoi evidence | Thuong phuc tap, can train/LLM/candidate setting rieng |

**Insight rut ra**

```text
Research methods cho thay retrieval chat luong can ca lexical, semantic,
va multi-hop signal. Nhung de demo/run local tren full corpus, can mot
engineering stack gon, co index, cache, UI, va benchmark artifact.
```

**Speaker note**

Khong noi "em beat paper". Noi: "Em hoc insight tu cac nhanh nay va xay mot
workspace engineering co the chay/benchmark tren full corpus."

## 4. Slide: Survey - Closed-Source / Commercial Search Tools

**Len slide**

| Nhom tool | Vi du | Uu diem | Han che voi de tai |
| --- | --- | --- | --- |
| Enterprise search | Elastic Enterprise Search, Algolia, Azure AI Search | San sang production, filter, dashboard, scaling | It minh bach ve metric multi-hop, chi phi, kho tuy bien evidence metric |
| Vector DB / RAG tools | Pinecone, Weaviate, Qdrant Cloud, Vertex AI Search | Quan ly vector, hybrid search, API tot | Thuong toi uu retrieval chung, khong co full-support metric mac dinh |
| Meeting/document search SaaS | Glean, Notion AI/Q&A, Microsoft Copilot ecosystem | UX tot, ket noi du lieu that | Dong, kho benchmark, khong kiem soat pipeline/ablation |

**Insight rut ra**

```text
Closed-source tools manh ve san pham va tich hop, nhung kho chung minh
retrieval evidence coverage bang benchmark tuy bien.

De tai nay chon huong mo: kiem soat du lieu, index, method, metric,
latency va ablation.
```

## 5. Slide: Pipeline Offline Ingest Data

**Len slide: ve pipeline rieng cho ingest**

```text
Raw dataset
  -> normalize docs / queries / qrels
  -> assign stable doc_id + numeric_id
  -> write staging JSONL shards
  -> generate synthetic metadata
  -> build Elasticsearch BM25 index
  -> generate BGE/BKAI embeddings
  -> build TurboVec / dense index
  -> validate counts + artifacts
```

**Icon/config nen them tren hinh**

| Component | Icon goi y | Config nen ghi |
| --- | --- | --- |
| Dataset | database/table | HotpotQA 5,233,329 docs; VimQA 3,623 docs |
| Elasticsearch | search icon | BM25, filters, hydration |
| Embedding model | model/brain icon | BGE-small 384-dim; BKAI Vietnamese bi-encoder 768-dim |
| TurboVec | compressed/vector icon | HotpotQA 4-bit `.tvim` artifact |
| Metadata | tag/calendar/user icon | author, created_at, modified_at |

**Speaker note**

Noi: "Day la phan bien raw dataset thanh artifact on dinh. Khong co phan nay
thi moi benchmark deu khong lap lai duoc."

## 6. Slide: Pipeline Online Search

**Len slide: ve pipeline rieng cho search**

```text
User query
  -> optional semantic metadata parser
  -> effective_query + metadata_filters
  -> BM25 retrieval in Elasticsearch
  -> dense retrieval in TurboVec / ES dense
  -> hydrate dense hits by numeric_id
  -> RRF / filtered hybrid / bridge-aware fusion
  -> result cards + support overlay + highlights
```

**Nhan 3 diem**

```text
1. Elasticsearch: lexical search, filter, document store.
2. TurboVec: compressed dense search tren full corpus.
3. Application layer: fusion, bridge logic, support overlay, history.
```

**Speaker note**

Noi ro `numeric_id` la cau noi giua vector hit va document source:

```text
TurboVec tra ve numeric_id, Elasticsearch hydrate lai title/content/metadata.
```

## 7. Slide: Ky Thuat, Engineering, DB

**Len slide**

| Lop | Thanh phan | Vai tro |
| --- | --- | --- |
| API | FastAPI | Dataset-scoped search, stats, queries, benchmarks |
| UI | React/Vite dashboard | Search, query browser, benchmark page, metadata mode |
| Search engine | Elasticsearch | BM25, metadata filters, document hydration |
| Dense runtime | TurboVec + embedding service | Compressed dense retrieval for HotpotQA |
| Cache | Redis | Cache repeated search responses |
| Local DB | SQLite | Search history / Harness operational records |
| Artifacts | JSONL, TSV, JSON, TREC | Reproducible staging and benchmark outputs |

**Endpoint shape**

```text
GET  /datasets
GET  /datasets/{dataset_id}/queries
GET  /datasets/{dataset_id}/benchmarks
POST /datasets/{dataset_id}/search
```

**Speaker note**

Goi day la "dataset-first runtime": mot API/UI, nhieu dataset profile.

## 8. Slide: Dataset Table

**Len slide**

| Dataset | Ngon ngu | Documents | Queries | Qrels | Muc tieu chinh | Metric chinh |
| --- | --- | ---: | ---: | ---: | --- | --- |
| HotpotQA full corpus | English | 5,233,329 | 7,405 test / 5,447 dev | Multi-support | Multi-hop evidence retrieval | `full_support@10`, nDCG, recall, latency |
| VimQA retrieval proxy | Vietnamese | 3,623 | 9,044 | 9,044 | Cross-dataset Vietnamese retrieval | recall@10, MRR, nDCG, latency |

**Caveat nen dat nho duoi bang**

```text
VimQA duoc dung nhu retrieval proxy tu QA dataset, khong phai BEIR-native benchmark.
```

## 9. Slide: Phuong Phap Cua Minh

**Len slide**

| Method | Nhom | Cach chay | Vai tro |
| --- | --- | --- | --- |
| `es_bm25` | Lexical | Elasticsearch BM25 | Fast baseline, manh voi keyword/entity |
| `tv_dense` | Dense | BGE query embedding -> TurboVec | Semantic retrieval tren full HotpotQA |
| `tv_hybrid` | Hybrid | BM25 + dense candidates -> RRF | Baseline chat luong/practical default |
| `tv_filtered_hybrid` | Filtered hybrid | BM25/filter allowlist + dense rerank | Phu hop metadata constraint |
| `tv_hybrid_rerank` | Reranker ablation | Cross-encoder rerank top-100 | Kiem tra ranking co phai bottleneck |
| `tv_bridge_title_entities_rrf` | Multi-hop | First-hop title/entity -> second-hop query | Quality-first evidence coverage |

**Speaker note**

Nham vao logic: "Em khong chi them method, ma them method de tra loi cau hoi
cu the: lexical co du khong, dense co giup paraphrase khong, reranker co dang
lam khong, va multi-hop failure nam o dau."

## 10. Slide: Benchmark Accuracy - HotpotQA Full Test

**Len slide**

| Method | Full-support@10 | Recall@10 | MRR@10 | nDCG@10 |
| --- | ---: | ---: | ---: | ---: |
| `tv_hybrid` | 0.5175 | 0.7305 | **0.8413** | 0.7001 |
| `tv_bridge_title_entities_rrf` | **0.6008** | **0.7585** | 0.8251 | **0.7120** |
| Delta | **+0.0833** | +0.0280 | -0.0162 | +0.0119 |

**Highlight kieu paper**

```text
Bridge-aware retrieval improves complete evidence coverage:
51.75% -> 60.08% full-support@10
= +8.33 percentage points
= +16.1% relative improvement
```

**Speaker note**

Noi ro trade-off: MRR giam nhe vi method uu tien "du cap support" hon "support
dau tien o rank rat cao".

## 11. Slide: Benchmark Latency - HotpotQA Full Test

**Len slide**

| Method | p50 ms | p95 ms | p99 ms | QPS |
| --- | ---: | ---: | ---: | ---: |
| `tv_hybrid` | **403.46** | **760.92** | **1188.67** | **1.9147** |
| `tv_bridge_title_entities_rrf` | 881.91 | 1598.34 | 2446.69 | 0.7321 |
| Ratio / delta | 2.19x | **2.10x** | 2.06x | -1.1826 |

**Cau nen noi**

```text
Bridge-aware retrieval la quality-first path: +8.33 pts full-support,
nhung p95 latency tang 2.1x. Vi vay tv_hybrid van phu hop hon cho interactive
default, con bridge la benchmark/quality mode.
```

## 12. Slide: Latency Scaling Chart 100/500/1000/5000

**Len slide: dung bieu do line/bar p95 latency**

Measured artifact: `evaluation/results/hotpotqa_full/dev_speed/summary.csv`.

| Queries | `es_bm25` p95 | `tv_filtered_hybrid` p95 | `tv_hybrid` p95 |
| ---: | ---: | ---: | ---: |
| 100 | 218.96 ms | 445.19 ms | 569.03 ms |
| 500 | 166.40 ms | 391.02 ms | 529.47 ms |
| 1000 | 157.29 ms | 341.20 ms | 494.26 ms |
| 5000 | 174.02 ms | 300.16 ms | not measured |

**Cach ve**

```text
X-axis: query count
Y-axis: p95 latency ms
Series: es_bm25, tv_filtered_hybrid, tv_hybrid
```

**Ghi chu ve moc 10000**

```text
Mentor suggest 100/500/1000/10000. Hien artifact da do den 5000.
Chi them 10000 vao slide neu chay benchmark that; khong extrapolate.
```

## 13. Slide: Resource / TurboVec Focus

**Len slide**

| Item | Gia tri |
| --- | ---: |
| HotpotQA documents | 5,233,329 |
| Embedding model | `BAAI/bge-small-en-v1.5` |
| Embedding dimension | 384 |
| TurboVec compression | 4-bit |
| TurboVec artifact | `hotpotqa_bge_small_4bit.tvim` |
| Artifact size | 1,067,602,206 bytes, about 1.0 GB |
| Build elapsed | about 2.72 minutes |

**Insight**

```text
TurboVec giup giu dense retrieval local-friendly: semantic search tren 5.23M
docs khong can dua toan bo vector float32 vao mot vector DB nang.
```

**Speaker note**

Neu hoi "tai nguyen ton bao nhieu", dua slide nay: 5.23M docs, 384-dim,
4-bit, artifact about 1GB.

## 14. Slide: So Sanh Voi Phuong Phap Khac

**Len slide**

| System / method | Dataset / setting | Metric | Result | Ghi chu |
| --- | --- | --- | ---: | --- |
| Pyserini BM25 multifield | BEIR HotpotQA | nDCG@10 | 0.603 | External reproduced baseline |
| Pyserini SPLADE++ | BEIR HotpotQA | nDCG@10 | 0.687 | Sparse neural |
| Pyserini Contriever | BEIR HotpotQA | nDCG@10 | 0.638 | Dense retriever |
| Pyserini BGE-base | BEIR HotpotQA | nDCG@10 | 0.726 | Larger dense baseline |
| Ours `tv_hybrid` | BEIR HotpotQA test | nDCG@10 | 0.7001 | Hybrid BM25 + TurboVec |
| Ours `tv_bridge_title_entities_rrf` | BEIR HotpotQA test | nDCG@10 | 0.7120 | Bridge-aware quality path |

**Canh bao tren slide**

```text
Use as contextual retrieval comparison, not leaderboard claim.
Index fields, model size, compression, and runtime differ.
```

## 15. Slide: VimQA Results

**Len slide**

| Method | Recall@10 | MRR@10 | nDCG@10 | p95 latency | Ket luan |
| --- | ---: | ---: | ---: | ---: | --- |
| `es_bm25` | 0.9627 | **0.8606** | **0.8859** | **84.42 ms** | Best default |
| `es_dense` BKAI | 0.8716 | 0.7272 | 0.7625 | 115.04 ms | Dense khong thang BM25 |
| `es_hybrid` | **0.9644** | 0.8277 | 0.8609 | 206.30 ms | Recall nhe hon, rank/latency kem |

**Insight**

```text
Method tot nhat phu thuoc dataset shape. VimQA co lexical overlap cao,
nen BM25 vua nhanh vua co MRR/nDCG tot hon dense/hybrid.
```

## 16. Slide: Paraphrase Robustness Ablation

**Len slide**

| Method | Original full_support@10 | Lexical-strong full_support@10 | Delta |
| --- | ---: | ---: | ---: |
| `es_bm25` | 0.365 | 0.340 | -0.025 |
| `tv_dense` | 0.515 | 0.495 | **-0.020** |
| `tv_hybrid` | **0.535** | 0.480 | -0.055 |
| `tv_filtered_hybrid` | 0.430 | 0.395 | -0.035 |

**Speaker note**

Noi: "Dense retrieval giam it nhat khi keyword bi thay manh. Hybrid tot tren
query goc, nhung co robustness gap tren lexical-strong paraphrase."

**Bieu do nen dung**

- `docs/sprint4/assets/paraphrase_full_support_decay.png`
- `docs/sprint4/assets/paraphrase_relative_decay.png`

## 17. Slide: Multi-Hop / Bridge Ablation

**Len slide**

| Method | Full-support@10 | Recall@10 | nDCG@10 | p95 latency |
| --- | ---: | ---: | ---: | ---: |
| `tv_hybrid` | 0.5450 | 0.7500 | 0.7291 | 1146.58 ms |
| `tv_two_hop_bridge_rrf` | 0.5600 | 0.7450 | 0.6999 | 2773.59 ms |
| `tv_bridge_title_entities_rrf` | **0.6200** | **0.7850** | **0.7398** | 2670.36 ms |
| tuned `beam1_terms6` | **0.6200** | 0.7775 | 0.7382 | **1224.99 ms** |

**Insight**

```text
Gain that den tu bridge query bang title/entity cua first-hop document.
Tuning cho thay khong can beam rong: beam1_terms6 giu full-support 0.6200
nhung giam p95 gan ve hybrid baseline.
```

## 18. Slide: Reranker Ablation

**Len slide**

| Method | Full-support@10 | Recall@10 | MRR@10 | nDCG@10 | p95 latency |
| --- | ---: | ---: | ---: | ---: | ---: |
| `tv_hybrid` | 0.5450 | 0.7500 | 0.8691 | 0.7291 | 2061.44 ms |
| `tv_hybrid_rerank` | 0.5450 | 0.7550 | 0.9268 | 0.7464 | 1304.28 ms |

**Paired full-support movement**

```text
RRF-only successes: 14
Reranker-only successes: 14
Net reranker wins: 0
```

**Insight**

```text
Reranker cai thien ranking metrics, nhung khong tang full-support trong pilot.
Neu missing/partial support con nhieu, candidate generation quan trong hon
chi rerank top candidates.
```

## 19. Slide: Semantic Metadata Search

**Len slide**

```text
Input:
  "tai lieu ve lich su Viet Nam cua Nguyen An truoc 31/01/2024"

Parsed:
  effective_query = "lich su Viet Nam"
  author = "Nguyen An"
  created_at_to = "2024-01-31"

Execution:
  content relevance -> BM25 / dense / hybrid
  metadata constraints -> Elasticsearch filters
  explanation -> parsed chips in UI
```

**Design decisions**

| Decision | Ly do |
| --- | --- |
| `semantic_metadata=true` opt-in | Khong lam nhieu query QA goc |
| Rule-based parser | De kiem soat va test |
| Manual filters override parsed filters | User control ro rang |
| Khong append metadata vao embedding text | Giu vector noi dung sach |

## 20. Slide: Metadata Filtering Impact

**Len slide**

| Scenario | Filters | Matching docs | Narrowing |
| --- | --- | ---: | ---: |
| Content only | none | 5,233,329 | 0.0000% |
| Author | `author=Nguyen An` | 40,886 | 99.2187% |
| Created January 2024 | `created_at=2024-01-01..2024-01-31` | 222,239 | 95.7534% |
| Author + created January | `author=Nguyen An`, January 2024 | 1,793 | **99.9657%** |

**Speaker note**

Noi ro day la synthetic metadata demo, khong phai metadata meeting that. Gia tri
la chung minh co che thu hep candidate space va explainable filters.

## 21. Slide: Video Demo Plan

**Len slide**

```text
Video demo: khong long tieng, chi quay UI + chu thich ngan tren slide.
He thong can bat real runtime truoc khi quay/test.
```

**Test cases can quay**

| Case | Dataset | Input | Method/mode | Expected show |
| --- | --- | --- | --- | --- |
| Happy QA | HotpotQA | Query preset tu tap dev/test | `tv_hybrid` | Results + Support Hit + Gold Support Found |
| Paraphrase | HotpotQA | Lexical-strong paraphrase | `tv_dense`/`tv_hybrid` | Ket qua van co support hits, highlight thay doi |
| Metadata search | HotpotQA/VimQA | `documents about anarchism by Nguyen An before 01/31/2024` | Semantic metadata on | Parsed chips + filters + narrowed results |
| Vietnamese search | VimQA | Query tu VimQA | `es_bm25` | BM25 results nhanh, benchmark page |
| Zero-result/strict filter | HotpotQA | Metadata filter khong khop | metadata filter | 0 results, UI khong crash, filter state ro rang |

**Checklist truoc khi quay**

```text
1. Bat Elasticsearch + Redis + API + frontend.
2. Neu dung HotpotQA dense/hybrid, bat embedding service va TurboVec artifact.
3. Warm cache cho 2-3 happy cases.
4. Test zero-result case truoc khi quay.
5. Quay khong long tieng; trong luc thuyet trinh noi theo script rieng.
```

## 22. Slide: Dong Gop Chinh

**Len slide**

```text
1. Full-corpus HotpotQA retrieval runtime tren 5.23M documents.
2. Hybrid retrieval workspace: Elasticsearch BM25 + TurboVec dense + RRF.
3. Multi-hop evidence metric va support overlay: do tim du bang chung.
4. Bridge-aware retrieval tang full-support@10 tu 0.5175 len 0.6008 tren full test.
5. Dataset-first API/UI cho HotpotQA va VimQA.
6. Semantic metadata search: natural query -> effective query + filters.
7. Benchmark/ablation artifacts: paraphrase, reranker, bridge, VimQA, latency.
```

**Speaker note**

Goi day la dong gop ca research-style evaluation lan engineering system.

## 23. Slide: Gioi Han Va Claim An Toan

**Len slide**

| Nen claim | Khong nen claim |
| --- | --- |
| Retrieval evidence coverage tren HotpotQA full test | Answer EM/F1 hoac supporting-fact F1 |
| Full-corpus runtime va benchmark artifacts | Production SLA latency |
| Bridge-aware la quality-first benchmark method | Learned multi-hop retriever |
| Metadata search da co opt-in parser/API/UI path | Metadata meeting that / production search quality |
| VimQA la retrieval proxy tieng Viet | Native BEIR leaderboard cho tieng Viet |

**Cau chot**

```text
Em tach ro implemented path va validated claim: cai nao da chay duoc,
cai nao da benchmark du, va cai nao chi la huong tiep theo.
```

## 24. Slide: Next Steps

**Len slide**

```text
1. Optimize bridge latency: cache embeddings, reduce duplicated hydration.
2. Add live semantic metadata benchmark lon hon.
3. Define real meeting metadata schema: speaker, timestamp, participants, agenda, action items.
4. Add reader/answer stage neu muon so sanh answer EM/F1 voi HotpotQA papers.
5. Run 10,000-query latency benchmark neu can bieu do scale theo yeu cau mentor.
```

## 25. Phu Luc: Cong Thuc Metrics

### Precision@k

```text
Precision@k = (# relevant documents in top-k) / k
```

### Recall@k

```text
Recall@k = (# relevant documents in top-k) / (# relevant documents)
```

### MRR@k

```text
MRR@k = mean(1 / rank_of_first_relevant_document)
```

Neu khong co relevant document trong top-k, contribution la 0.

### nDCG@k

```text
DCG@k = sum_i rel_i / log2(i + 1)
nDCG@k = DCG@k / IDCG@k
```

### Full-support@k

```text
full_support@k = (# queries where top-k contains all gold support docs)
                  / (# queries)
```

Day la metric quan trong nhat cho HotpotQA trong deck.

### Latency

```text
p50 = median latency
p95 = latency threshold covering 95% of queries
p99 = latency threshold covering 99% of queries
QPS = processed queries per second
```

## 26. Phu Luc: Ablation Table Tong Hop

| Ablation | Cau hoi | Ket qua ngan | Ket luan |
| --- | --- | --- | --- |
| Paraphrase | Method co robust khi lexical overlap giam? | `tv_dense` giam it nhat tren lexical-strong: -0.020 | Dense path can thiet cho semantic robustness |
| Title-aware BM25 | Boost title co tang full-support? | `full_support@10` giu 0.365 | Khong giai quyet loi missing second support |
| Reranker | Rerank top-100 co tang full-support? | Net reranker wins = 0 | Chua phai bottleneck chinh trong pilot |
| Multi-hop bridge | First-hop title/entity co giup support thu hai? | `0.545 -> 0.620` dev pilot; `0.5175 -> 0.6008` full test | Gain chinh den tu candidate generation |
| TurboVec | Dense retrieval full corpus co local-friendly? | 5.23M docs, 384-dim, 4-bit, about 1GB artifact | Giup dense retrieval kha thi tren local demo |
| VimQA | Hybrid/dense co luon thang BM25? | BM25 co MRR/nDCG va latency tot nhat | Method phu thuoc dataset shape |

## 27. Phu Luc: References

| Reference | Dung de noi gi |
| --- | --- |
| HotpotQA paper / homepage | Multi-hop QA va supporting evidence |
| BEIR paper | Retrieval benchmark framing |
| Pyserini BEIR regressions | Contextual baseline nDCG@10 cho HotpotQA |
| MDR | Multi-hop dense retrieval concept |
| IRCoT | Interleaving reasoning/retrieval concept |
| Beam Retrieval | Evidence chain / beam-style multi-hop retrieval |
| Elasticsearch docs | BM25, filters, indexing |
| TurboVec project | Compressed dense retrieval |
| BGE-small | English embedding model |
| BKAI Vietnamese bi-encoder | Vietnamese dense retrieval model |

## 28. Noi Dung Dua Vao Bao Cao Viet

Bao cao viet nen dai hon slide, nhung cung thu tu:

1. Gioi thieu: evidence retrieval cho QA da buoc va metadata search.
2. Survey: open-source research va closed-source tools, insight.
3. Kien truc offline ingest va online search.
4. Thiet ke engineering: API/UI, Elasticsearch, TurboVec, Redis, SQLite, artifacts.
5. Dataset: HotpotQA va VimQA.
6. Methods: BM25, dense, hybrid, filtered hybrid, reranker, bridge-aware.
7. Evaluation protocol va metrics.
8. Ket qua HotpotQA full test.
9. Latency/resource/TurboVec.
10. VimQA benchmark.
11. Semantic metadata search.
12. Ablation: paraphrase, title-aware, reranker, bridge tuning.
13. Video demo/test cases.
14. Dong gop chinh.
15. Gioi han va huong phat trien.
16. References.

Doan claim chuan cho bao cao:

```text
Tren full BEIR HotpotQA test 7,405 queries, bridge-aware retrieval cai thien
complete evidence coverage tu 51.75% len 60.08% trong top-10. Cai gia la p95
latency tang tu 0.76s len 1.60s. Vi vay bridge-aware retrieval la quality-first
benchmark path, con tv_hybrid van la interactive default hop ly hon neu chua
toi uu second-hop latency.
```
