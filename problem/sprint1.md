# Sprint 1 Problem Notes: Scale-up to 5M Documents

## Context

Baseline hien tai dung Elasticsearch cho BM25, dense kNN, hybrid RRF va `es_iterative_hybrid`. Rieng iterative search la retrieval 2-hop: chay hybrid o hop 1, lay top `first_hop_k`, roi voi tung document hop 1 tao expanded query de search tiep hop 2.

Default hien tai:

```text
first_hop_k = 5
second_hop_k = 10
context_chars = 256
candidate_k = 100
rrf_k = 60
num_candidates = 1000
```

Khi scale len khoang 5M documents, rui ro chinh la iterative retrieval nhan so luong search, embedding, va tai nguyen Elasticsearch tren moi user query.

## P0: Iterative Query Fan-out

Mot request `es_iterative_hybrid` hien chay:

```text
1 hybrid search cho hop 1
+ first_hop_k hybrid searches cho hop 2
```

Voi `first_hop_k=5`, mot request thanh 6 hybrid searches. Moi hybrid lai gom BM25 + dense kNN, nen tong gan dung la:

```text
6 BM25 searches
6 dense kNN searches
6 query embeddings
```

Impact:

- p95/p99 latency co the tang manh tren index 5M docs.
- Mot so it concurrent users cung co the tao workload lon cho Elasticsearch.
- Dense kNN nhieu kha nang la phan dat nhat, nhat la khi `num_candidates=1000`.

Can do:

- Latency tung method: `es_bm25`, `es_dense`, `es_hybrid`, `es_iterative_hybrid`.
- So ES calls va embedding calls tren moi API request.
- p50, p95, p99 duoi concurrent load.

Sprint 1 action:

- Giu `es_hybrid` lam default production method.
- De `es_iterative_hybrid` o debug/advanced mode cho toi khi benchmark chung minh dang dung.
- Benchmark `first_hop_k` voi `2`, `3`, `5`.

## P0: Dense Vector Index Size and Memory Pressure

Moi document luu vector 384 chieu. Raw vector storage xap xi:

```text
5,000,000 docs * 384 dims * 4 bytes = ~7.7 GB
```

Dung luong thuc te se cao hon do HNSW/vector graph overhead, inverted index, `_source`, segment metadata, filesystem cache, va merge overhead.

Impact:

- Single-node Docker dev co the gap heap pressure, slow merge, disk watermark, GC spike hoac latency khong on dinh.
- kNN latency va recall phu thuoc manh vao shard/index settings.
- Rebuild index se ton thoi gian va de rui ro van hanh.

Can do:

- Disk size sau ingest.
- ES heap, CPU, GC, merge time, disk I/O.
- kNN latency theo `num_candidates`.
- Segment count va refresh/merge behavior.

Sprint 1 action:

- Scale test theo moc 100k, 500k, 1M truoc khi len 5M.
- Ghi lai disk/memory/latency o tung moc.
- Khong assume cau hinh 1 shard hien tai con phu hop cho 5M.

## P0: Query Embedding Bottleneck

Hop 2 tao expanded query khac nhau cho tung hop-1 document. Dense branch phai embed tung expanded query do.

Impact:

- Embedding service co the nghen truoc ca Elasticsearch.
- API latency tang neu embedding chay tuan tu.
- Query lap lai se ton compute neu khong cache.

Can do:

- Embedding latency/request.
- So embedding calls/request.
- Cache hit rate.
- CPU/GPU utilization cua embedding service.

Sprint 1 action:

- Them timing breakdown: embedding vs ES search vs fusion.
- Cache search response theo query, method, top-k, index, va iterative parameters.
- Can nhac cache embedding cho expanded queries giong nhau.

## P1: Sharding and kNN Fan-out

Baseline hien dung 1 shard. Voi 5M docs, 1 shard co the qua lon, nhung nhieu shard cung lam query fan-out nang hon.

Impact:

- Nhieu shard tang parallelism nhung cung tang coordination cost.
- kNN candidate gathering phu thuoc shard count.
- Iterative da fan-out nhieu search, nen shard fan-out cang dat.

Can do:

- Latency/recall theo shard count.
- Search queue, thread pool saturation, rejection count.
- Per-shard document count va disk size.

Sprint 1 action:

- Benchmark vai shard configs tren data representative.
- Luon so sanh ca quality metric va latency metric.

## P1: Query Drift in Hop 2

Expanded query hien la:

```text
original query + hop1 title + first context_chars of hop1 text
```

Neu hop 1 lay nham document, hop 2 se bi keo sang topic sai. Tren 5M docs, false positive hop ly se nhieu hon.

Impact:

- Iterative co the tang recall cho mot so query multi-hop nhung giam precision o query khac.
- Document generic/popular co the xuat hien lap lai va duoc RRF boost.
- Ket qua cuoi co the sai nhung score cao do xuat hien trong nhieu hop-2 rankings.

Can do:

- `full_support_recall@k` so voi latency.
- Precision drop so voi `es_hybrid`.
- Hop distribution trong final top-k.
- Failure cases khi hop-1 evidence sai keo hop 2 sai.

Sprint 1 action:

- Log expanded queries va hop traces cho iterative search.
- Them score threshold/rank limit truoc khi expand hop-1 docs.
- So sanh naive context expansion voi title-only hoac entity-focused expansion.

## P1: RRF Fusion May Reward Repeated Noise

Final ranking fuse hop 1 va toan bo hop 2 rankings bang RRF. Document xuat hien o nhieu hop-2 rankings se duoc cong diem.

Impact:

- Supporting docs dung co the duoc boost, day la diem tot.
- Generic docs cung co the duoc boost neu match nhieu expanded queries.
- RRF hien khong hieu evidence chain hay quan he logic giua hop 1 va hop 2.

Can do:

- Duplicate doc frequency across hop-2 rankings.
- Final top-k docs xuat hien nhieu lan nhung khong relevant.
- Chenh lech giua document recall va full support recall.

Sprint 1 action:

- Luu debug trace: hop 1, expanded queries, hop 2 rankings, final fused ranking.
- Inspect cac case iterative thua hybrid.

## P1: API Concurrency Risk

Mot request iterative tao nhieu ES searches va embedding calls. Concurrent users se nhan workload nay len.

Vi du 10 concurrent requests voi `first_hop_k=5`:

```text
10 requests * 6 hybrid searches = 60 hybrid searches
60 hybrid searches = 60 BM25 + 60 dense kNN searches
10 requests * 6 embeddings = 60 embeddings
```

Impact:

- ES search queue co the tang nhanh.
- Embedding service co the saturate.
- Tail latency khong on dinh du average latency nhin van on.

Can do:

- QPS duoi concurrency.
- Timeout rate.
- ES search queue/rejection count.
- API worker utilization.

Sprint 1 action:

- Them timeout va concurrency limit cho iterative mode.
- Load test concurrent requests, khong chi benchmark tuan tu.
- Can nhac disable iterative khoi public/default API cho toi khi co guard.

## P2: No Chunking May Hurt Quality on Long Documents

Baseline hien map 1 source document thanh 1 ES document va 1 vector. Voi HotpotQA ngan thi on, nhung meeting minutes hoac documents dai co the can passage-level retrieval.

Impact:

- Dense vector bi loang semantic voi document dai.
- BM25 co the match keyword nhung dense retrieval miss local context.
- Chunking cai thien quality nhung lam so vectors vuot 5M.

Can do:

- Average/p95 document length.
- Retrieval quality theo document length bucket.
- Dense failures tren long documents.

Sprint 1 action:

- Do document length distribution truoc khi chot no-chunking.
- Xem chunking la tradeoff quality/scale, khong phai default assumption.

## P2: Ingest and Rebuild Operational Risk

O 5M docs, ingest gom staging, embedding, bulk indexing, vector graph construction, refresh, va segment merges.

Impact:

- Full rebuild co the rat lau.
- Ingest fail giua chung can resume/retry chac chan.
- Can alias strategy de switch index khong downtime.

Can do:

- Docs/sec cho embedding va bulk indexing.
- Failed batch retry count.
- Total rebuild time.
- Refresh/merge time.

Sprint 1 action:

- Verify staging resume va bulk ingest retry behavior.
- Dung index alias cho current/next index truoc khi rebuild production-scale.

## Sprint 1 Measurement Checklist

- Benchmark `es_bm25`, `es_dense`, `es_hybrid`, `es_iterative_hybrid` tai 100k, 500k, 1M docs.
- Measure p50, p95, p99 latency cho tung method.
- Measure `recall@k`, `mrr@k`, `ndcg@k`, dac biet `full_support_recall@k`.
- Record ES disk size, heap, CPU, GC, search queue, merge behavior.
- Record embedding latency va so embedding calls/request.
- Compare iterative settings:

```text
first_hop_k: 2, 3, 5
second_hop_k: 5, 10
candidate_k: 50, 100, 200
num_candidates: 200, 500, 1000
```

## Initial Position

Cho toi khi scale benchmark chung minh nguoc lai, dung `es_hybrid` lam default. Giu `es_iterative_hybrid` cho multi-hop debugging, offline evaluation, hoac selected hard queries. Rui ro can kiem soat dau tien la fan-out: moi lan tang `first_hop_k` se truc tiep nhan tai Elasticsearch va embedding service.