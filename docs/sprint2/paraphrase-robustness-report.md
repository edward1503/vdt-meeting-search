# Paraphrase Robustness Benchmark Report

Ngay chay: 2026-06-11

## Muc tieu

Thi nghiem nay do do ben cua cac retriever khi query bi thay doi ve lexical form nhung van giu y nghia hoi dap goc. Day la mot stress test nho cho HotpotQA retrieval: neu truy van duoc paraphrase bang synonym, retriever co con tim duoc support documents tuong ung voi qrels goc hay khong.

Cac retriever duoc benchmark:

- `es_bm25`
- `es_dense`
- `es_hybrid`
- `es_iterative_hybrid`

## Thiet ke thi nghiem

Input gom 50 HotpotQA queries tu `nano-beir/hotpotqa`. File `evaluation/results/nano_test_queries.tsv` hien co 20 query, nen generator tu dong fill them query tu `ir_datasets` de dat du 50 query.

Moi query goc duoc tao 3 bien the paraphrase:

| Dieu kien | Ty le thay token du dieu kien | So query |
| --- | ---: | ---: |
| `syn020` | 20% | 50 |
| `syn040` | 40% | 50 |
| `syn060` | 60% | 50 |

Paraphrase duoc tao deterministic bang synonym substitution co seed co dinh. Generator khong thay named entities, so, ngay thang, hoac token viet hoa giua cau. Moi variant giu `source_query_id` cua query goc va co `variant_query_id` dang `{source_query_id}::syn{ratio}::v1`.

Qrels khong duoc tao moi. Benchmark map qrels cua `source_query_id` sang `variant_query_id`, vi muc tieu la do retriever robustness truoc lexical variation chu khong phai tao task hoi dap moi.

## Cau hinh chay

Elasticsearch index duoc dung trong run nay:

- Index: `hotpotqa_nano_v1`
- Dataset: `nano-beir/hotpotqa`
- Top-k: `10`
- Candidate-k: `100`
- Num candidates: `100`
- RRF k: `30`
- First hop k: `5`
- Second hop k: `10`
- Context chars: `256`
- Dense model: `BAAI/bge-small-en-v1.5`

Generate paraphrases:

```bash
python scripts/paraphrase_queries.py --input evaluation/results/nano_test_queries.tsv --limit 50 --ratios 0.2,0.4,0.6 --variants-per-ratio 1 --seed 13 --output-tsv evaluation/results/query_paraphrases_50.tsv --output-jsonl evaluation/results/query_paraphrases_50.jsonl
```

Run original baseline:

```bash
python -m src.evaluation.benchmark_es --dataset nano-beir/hotpotqa --index hotpotqa_nano_v1 --methods es_bm25,es_dense,es_hybrid,es_iterative_hybrid --top-k 10 --max-queries 50 --candidate-k 100 --num-candidates 100 --rrf-k 30 --first-hop-k 5 --second-hop-k 10 --context-chars 256 --output evaluation/results/es_nano_original_50.json --run-dir evaluation/runs/paraphrase/original
```

Run paraphrase conditions bang `--query-file`:

```bash
python -m src.evaluation.benchmark_es --dataset nano-beir/hotpotqa --index hotpotqa_nano_v1 --methods es_bm25,es_dense,es_hybrid,es_iterative_hybrid --top-k 10 --query-file evaluation/results/query_paraphrases_50_syn020.tsv --candidate-k 100 --num-candidates 100 --rrf-k 30 --first-hop-k 5 --second-hop-k 10 --context-chars 256 --output evaluation/results/es_nano_paraphrase_syn020.json --run-dir evaluation/runs/paraphrase/syn020
python -m src.evaluation.benchmark_es --dataset nano-beir/hotpotqa --index hotpotqa_nano_v1 --methods es_bm25,es_dense,es_hybrid,es_iterative_hybrid --top-k 10 --query-file evaluation/results/query_paraphrases_50_syn040.tsv --candidate-k 100 --num-candidates 100 --rrf-k 30 --first-hop-k 5 --second-hop-k 10 --context-chars 256 --output evaluation/results/es_nano_paraphrase_syn040.json --run-dir evaluation/runs/paraphrase/syn040
python -m src.evaluation.benchmark_es --dataset nano-beir/hotpotqa --index hotpotqa_nano_v1 --methods es_bm25,es_dense,es_hybrid,es_iterative_hybrid --top-k 10 --query-file evaluation/results/query_paraphrases_50_syn060.tsv --candidate-k 100 --num-candidates 100 --rrf-k 30 --first-hop-k 5 --second-hop-k 10 --context-chars 256 --output evaluation/results/es_nano_paraphrase_syn060.json --run-dir evaluation/runs/paraphrase/syn060
```

Compare results:

```bash
python scripts/compare_paraphrase_results.py --baseline evaluation/results/es_nano_original_50.json --variant syn020=evaluation/results/es_nano_paraphrase_syn020.json --variant syn040=evaluation/results/es_nano_paraphrase_syn040.json --variant syn060=evaluation/results/es_nano_paraphrase_syn060.json --output evaluation/results/paraphrase_summary.csv
```

## Artifacts

| Artifact | Mo ta |
| --- | --- |
| `evaluation/results/query_paraphrases_50.tsv` | 150 query variants, gom ca 3 ty le |
| `evaluation/results/query_paraphrases_50.jsonl` | Ban JSONL cua variants, co metadata changed terms |
| `evaluation/results/query_paraphrases_50_syn020.tsv` | 50 variants muc 20% |
| `evaluation/results/query_paraphrases_50_syn040.tsv` | 50 variants muc 40% |
| `evaluation/results/query_paraphrases_50_syn060.tsv` | 50 variants muc 60% |
| `evaluation/results/es_nano_original_50.json` | Benchmark original 50 queries |
| `evaluation/results/es_nano_paraphrase_syn020.json` | Benchmark syn020 |
| `evaluation/results/es_nano_paraphrase_syn040.json` | Benchmark syn040 |
| `evaluation/results/es_nano_paraphrase_syn060.json` | Benchmark syn060 |
| `evaluation/results/paraphrase_summary.csv` | Delta metrics so voi original |
| `evaluation/runs/paraphrase/*/*.trec` | TREC run files theo condition va method |

## Ket qua tong quan

Bang duoi day ghi cac metric chinh tren original va 3 muc paraphrase. Moi run deu co 50 queries.

| Condition | Method | Recall@10 | Full support recall@10 | NDCG@10 | MRR@10 | P95 latency ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| original | es_bm25 | 0.88 | 0.76 | 0.8188 | 0.9072 | 113.5265 |
| original | es_dense | 0.86 | 0.74 | 0.8191 | 0.8872 | 135.5532 |
| original | es_hybrid | 0.91 | 0.82 | 0.8631 | 0.9253 | 241.5370 |
| original | es_iterative_hybrid | 0.90 | 0.82 | 0.8341 | 0.9033 | 1508.9099 |
| syn020 | es_bm25 | 0.86 | 0.74 | 0.8107 | 0.9062 | 71.3584 |
| syn020 | es_dense | 0.86 | 0.74 | 0.8058 | 0.8717 | 90.5184 |
| syn020 | es_hybrid | 0.90 | 0.80 | 0.8543 | 0.9253 | 169.6718 |
| syn020 | es_iterative_hybrid | 0.88 | 0.78 | 0.8247 | 0.9133 | 1205.6986 |
| syn040 | es_bm25 | 0.87 | 0.74 | 0.8171 | 0.9162 | 76.5208 |
| syn040 | es_dense | 0.86 | 0.74 | 0.8134 | 0.8872 | 112.2846 |
| syn040 | es_hybrid | 0.90 | 0.80 | 0.8536 | 0.9253 | 180.4794 |
| syn040 | es_iterative_hybrid | 0.88 | 0.78 | 0.8171 | 0.9000 | 1144.3947 |
| syn060 | es_bm25 | 0.86 | 0.74 | 0.8113 | 0.9072 | 68.6134 |
| syn060 | es_dense | 0.86 | 0.74 | 0.8113 | 0.8801 | 108.0180 |
| syn060 | es_hybrid | 0.90 | 0.80 | 0.8545 | 0.9253 | 261.3507 |
| syn060 | es_iterative_hybrid | 0.88 | 0.78 | 0.8201 | 0.8933 | 1519.2750 |

## Delta so voi original

| Condition | Method | Delta recall@10 | Delta full support recall@10 | Delta NDCG@10 | Delta MRR@10 |
| --- | --- | ---: | ---: | ---: | ---: |
| syn020 | es_bm25 | -0.02 | -0.02 | -0.0081 | -0.0010 |
| syn020 | es_dense | 0.00 | 0.00 | -0.0133 | -0.0155 |
| syn020 | es_hybrid | -0.01 | -0.02 | -0.0088 | 0.0000 |
| syn020 | es_iterative_hybrid | -0.02 | -0.04 | -0.0094 | 0.0100 |
| syn040 | es_bm25 | -0.01 | -0.02 | -0.0017 | 0.0090 |
| syn040 | es_dense | 0.00 | 0.00 | -0.0057 | 0.0000 |
| syn040 | es_hybrid | -0.01 | -0.02 | -0.0095 | 0.0000 |
| syn040 | es_iterative_hybrid | -0.02 | -0.04 | -0.0170 | -0.0033 |
| syn060 | es_bm25 | -0.02 | -0.02 | -0.0075 | 0.0000 |
| syn060 | es_dense | 0.00 | 0.00 | -0.0078 | -0.0071 |
| syn060 | es_hybrid | -0.01 | -0.02 | -0.0086 | 0.0000 |
| syn060 | es_iterative_hybrid | -0.02 | -0.04 | -0.0140 | -0.0100 |

## Nhan xet

`es_hybrid` la retriever on dinh nhat trong thi nghiem nay. No giu `recall@10 = 0.90` o ca ba muc paraphrase, chi giam `-0.01` so voi original. `full_support_recall@10` giam tu `0.82` xuong `0.80`, tuc delta `-0.02` o ca syn020, syn040 va syn060.

`es_dense` rat on dinh ve `recall@10` va `full_support_recall@10`: ca ba muc paraphrase deu giu `recall@10 = 0.86` va `full_support_recall@10 = 0.74`. Tuy nhien `ndcg@10` va `mrr@10` co dao dong nhe, cho thay ranking order van bi anh huong boi paraphrase.

`es_bm25` khong sup do nhu ky vong xau nhat, mot phan vi paraphrase duoc kiem soat va van giu nhieu lexical anchor quan trong. Recall dao dong tu `0.86` den `0.87`, giam toi da `-0.02` so voi original.

`es_iterative_hybrid` co recall van kha tot nhung nhay hon ve full-support retrieval. `full_support_recall@10` giam tu `0.82` xuong `0.78` o ca ba muc paraphrase. Dieu nay goi y iterative expansion co the bi anh huong khi paraphrase lam yeu bridge terms hoac thay doi evidence context trong hop sau.

Latency khong nen duoc doc nhu mot ket luan robustness chinh trong run nay, vi embedding cache, warm-up va tai cuc bo co the lam p95 dao dong. Metric latency van duoc report de trace run, nhung ket luan chinh nen dua tren quality metrics.

## Han che

- Paraphrase hien la synonym substitution deterministic, chua phai paraphrase tu nhien nhu LLM paraphrase.
- Synonym dictionary con nho, nen mot so query co `actual_change_ratio` thap hon muc target neu it token du dieu kien.
- Qrels duoc giu tu query goc, vi vay manual inspection van can thiet neu mo rong dictionary hoac dung LLM paraphrase de tranh doi nghia cau hoi.
- Benchmark chi chay tren 50 queries cua nano HotpotQA, chua du de ket luan tong quat cho full corpus.

## Ket luan

Voi 50-query paraphrase benchmark nay, hybrid retrieval la lua chon can bang nhat: chat luong cao nhat tren original va suy giam nho khi query bi lexical paraphrase. Dense retrieval on dinh ve recall, BM25 giam nhe, con iterative hybrid can them guard cho query expansion hoac bridge-term preservation neu dung trong multi-hop production pipeline.
