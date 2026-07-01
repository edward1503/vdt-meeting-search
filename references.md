# References

This file lists the main research papers, datasets, models, technical stack, and
external tools referenced or used by the current `vdt-meeting-search` codebase.

## 1. Research Papers And Methods

### Directly Used Or Directly Reflected In The System

| Topic | Reference | How it appears in this project |
| --- | --- | --- |
| Multi-hop QA dataset | HotpotQA: A Dataset for Diverse, Explainable Multi-hop Question Answering. https://arxiv.org/abs/1809.09600 | Main English retrieval benchmark/domain. The project evaluates whether top-k retrieval gets all support documents. |
| Retrieval benchmark protocol | BEIR: A Heterogeneous Benchmark for Zero-shot Evaluation of Information Retrieval Models. https://arxiv.org/abs/2104.08663 | HotpotQA is loaded through `ir_datasets` / BEIR-style ids, queries, and qrels. |
| Lexical retrieval | Robertson and Zaragoza, The Probabilistic Relevance Framework: BM25 and Beyond. https://doi.org/10.1561/1500000019 | Elasticsearch BM25 is the lexical baseline and document-store path. |
| Dense passage retrieval | Dense Passage Retrieval for Open-Domain Question Answering. https://arxiv.org/abs/2004.04906 | Motivates dual-encoder dense retrieval as a semantic alternative to BM25. |
| Sentence embeddings | Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks. https://arxiv.org/abs/1908.10084 | Project uses SentenceTransformers-style embedding models for dense retrieval and reranking. |
| BGE embeddings | C-Pack: Packed Resources For General Chinese Embeddings. https://arxiv.org/abs/2309.07597 | BAAI BGE family is used for HotpotQA dense embeddings (`BAAI/bge-small-en-v1.5`). |
| Reciprocal Rank Fusion | Cormack, Clarke, Buettcher, Reciprocal Rank Fusion outperforms Condorcet and individual rank learning methods. https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf | `tv_hybrid`, filtered hybrid, Bridge-RRF, and reranker ablation use RRF-style fusion. |
| Cross-encoder reranking model family | MiniLM: Deep Self-Attention Distillation for Task-Agnostic Compression of Pre-Trained Transformers. https://arxiv.org/abs/2002.10957 | Reranker ablation uses `cross-encoder/ms-marco-MiniLM-L-6-v2`. |

### Referenced For Survey, Comparison, Or Future Work

| Topic | Reference | Why it is included |
| --- | --- | --- |
| Late-interaction retrieval | ColBERT: Efficient and Effective Passage Search via Contextualized Late Interaction over BERT. https://arxiv.org/abs/2004.12832 | Survey comparison for stronger retrieval/reranking designs. Not implemented in runtime. |
| Retrieval-augmented generation | Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. https://arxiv.org/abs/2005.11401 | Background for retrieval-grounded downstream QA/RAG. The current project focuses on retrieval, not answer generation. |
| Vector similarity search | FAISS: https://github.com/facebookresearch/faiss | Survey/comparison point for vector search backends. Not the active backend. |
| Managed/self-hosted vector DB | Milvus hybrid search: https://milvus.io/docs/hybrid_search_with_milvus.md | Survey/comparison point. Not the active backend. |
| Managed/self-hosted vector DB | Qdrant hybrid queries: https://qdrant.tech/documentation/search/hybrid-queries/ | Survey/comparison point. Not the active backend. |
| Hybrid serving platform | Vespa hybrid search tutorial: https://docs.vespa.ai/en/learn/tutorials/hybrid-search.html | Survey/comparison point. Not the active backend. |

## 2. Datasets And Evaluation Sources

| Dataset / source | Local role | Local evidence |
| --- | --- | --- |
| HotpotQA / BEIR HotpotQA | Full-corpus English multi-hop retrieval dataset. | `beir/hotpotqa`, `evaluation/results/hotpotqa_full_dev_queries.tsv`, `artifacts/hotpotqa_full/...` |
| VimQA | Vietnamese retrieval proxy built from QA data: question as query, context as document, mapping as qrel. | `artifacts/vimqa/...`, `evaluation/results/vimqa/vimqa_queries.tsv`, `evaluation/results/vimqa/vimqa_qrels.tsv` |
| Synthetic HotpotQA metadata | Demo metadata filters: `author`, `created_at`, `modified_at`. | `artifacts/hotpotqa_full/metadata/...`, `scripts/generate_synthetic_metadata.py` |
| Synthetic VimQA metadata | Metadata artifact for VimQA profile and semantic metadata search. | `artifacts/vimqa/all/metadata/...`, `tests/test_vimqa_synthetic_metadata.py` |
| Paraphrase query sets | Robustness evaluation against mild, strong, and lexical-strong paraphrases. | `evaluation/results/hotpotqa_full/paraphrase_final/...` |

## 3. Models

| Model | Role | Where it appears |
| --- | --- | --- |
| `BAAI/bge-small-en-v1.5` | HotpotQA document/query embedding model, 384 dimensions. | `src/api/dataset_profiles.py`, `src/core/config.py`, `scripts/embed_hotpotqa.py`, `scripts/embedding_server.py` |
| `bkai-foundation-models/vietnamese-bi-encoder` | VimQA dense embedding model, 768 dimensions. | `src/api/dataset_profiles.py`, `scripts/embedding_server.py` |
| `cross-encoder/ms-marco-MiniLM-L-6-v2` | Reranker model used in the RRF-vs-reranker pilot ablation. | `src/retrieval/reranker.py`, `docs/sprint5/reranker-rrf-ablation-report.md` |
| `BAAI/bge-m3` | Considered in analysis/planning as a stronger multilingual embedding option. | `docs/data/vimqa/`, `docs/sprint4/plan.md` |

## 4. Backend And Retrieval Stack

| Technology | Version / source | Role |
| --- | --- | --- |
| Python | `python:3.12-slim` Docker base image | API, retrieval, ingest, evaluation, scripts. |
| FastAPI | `0.136.3` in `requirements-api.txt`; `>=0.115.0` in `requirements.txt` | HTTP API and embedding service. |
| Uvicorn | `0.49.0` in `requirements-api.txt`; `>=0.30.6` in `requirements.txt` | ASGI server for FastAPI. |
| Pydantic | `2.13.4` in `requirements-api.txt`; `>=2.9.2` in `requirements.txt` | API validation/modeling. |
| Elasticsearch Python client | `8.19.3` in `requirements-api.txt`; `>=8.15,<9` in `requirements.txt` | Index lifecycle, BM25 search, hydration, metadata filters. |
| Elasticsearch server | Docker image `docker.elastic.co/elasticsearch/elasticsearch:8.15.1` | BM25 index, document store, VimQA dense-vector index. |
| Redis Python client | `5.3.1` in `requirements-api.txt`; `>=5,<6` in `requirements.txt` | API-side search cache client. |
| Redis server | Docker image `redis:7.4-alpine` | Runtime response cache. |
| NumPy | `2.3.5` in `requirements-api.txt`; `>=1.26.4` in `requirements.txt` | Embedding shards, vector loading, TurboVec build/search helpers. |
| TurboVec | `0.8.0` | HotpotQA compressed dense index, `.tvim` artifact, `IdMapIndex`. |
| SentenceTransformers | `>=3.0.1` | Host embedding service and cross-encoder reranking. Not installed in the slim API image by default. |
| ir_datasets | `>=0.5.8` | HotpotQA corpus/query/qrels loading for staging and benchmarks. |
| SQLite | Python standard library `sqlite3` | Search history database. |
| Docker Compose | `docker-compose.yml` | Local runtime orchestration for Elasticsearch, Redis, API, and frontend. |

## 5. Frontend Stack

| Technology | Version / source | Role |
| --- | --- | --- |
| Node.js | `node:22-alpine` Docker base image | Frontend development/build runtime. |
| React | `^19.0.1` | Dashboard UI. |
| React DOM | `^19.0.1` | Browser rendering. |
| Vite | `^6.2.3` | Frontend dev server/build tool. |
| @vitejs/plugin-react | `^5.0.4` | React integration for Vite. |
| TypeScript | `~5.8.2` | Frontend type-checking. |
| Tailwind CSS | `^4.1.14` plus `@tailwindcss/vite` | UI styling. |
| Autoprefixer | `^10.4.21` | CSS post-processing dependency. |
| Recharts | `^3.8.1` | Benchmark/metric charts. |
| lucide-react | `^0.546.0` | UI icons. |
| motion | `^12.23.24` | UI animation dependency. |
| clsx | `^2.1.1` | Conditional class composition. |
| tailwind-merge | `^3.6.0` | Tailwind class merge helper. |
| Express | `^4.21.2` | Frontend/server support dependency. |
| dotenv | `^17.2.3` | Environment loading support. |
| esbuild | `^0.25.0` | Frontend build tooling dependency. |
| tsx | `^4.21.0` | TypeScript execution tooling dependency. |
| @google/genai | `^2.4.0` | Declared frontend dependency; not part of the active retrieval runtime path. |
| Nginx | `nginx:1.27-alpine` production image | Static frontend serving in production Docker stage. |
| Google Fonts | Hanken Grotesk, Inter, Geist, JetBrains Mono | Frontend typography via `frontend/src/index.css`. |

## 6. Development, Testing, And Operational Tooling

| Tool | Role |
| --- | --- |
| pytest | Python unit/integration test runner used throughout `tests/`. |
| TypeScript `tsc --noEmit` | Frontend type-check/lint command via `npm run lint`. |
| Docker / Docker Compose | Local runtime orchestration and containerized API/frontend services. |
| Harness CLI | Project task matrix, intake, trace, tool registry, and validation bookkeeping. |
| PowerShell / Bash helper scripts | Local developer workflows: `start.sh`, `scripts/docker-dev.ps1`, `scripts/docker-dev.sh`. |
| OpenAI API workflow | Used in paraphrase generation/validation workflow documents and notebook protocol. |
| Kaggle notebook workflow | Used for paraphrase roundtrip generation/validation protocol. |

## 7. Evaluation, Metrics, And Report Artifacts

| Area | Local implementation / artifact |
| --- | --- |
| Metrics | `src/evaluation/metrics.py`: precision@k, recall@k, MRR@k, nDCG@k, full-support recall, chain metrics. |
| Benchmark runner | `src/evaluation/benchmark_es.py` |
| TREC output | `evaluation/runs/**/*.trec` |
| HotpotQA full-corpus benchmark | `evaluation/results/hotpotqa_full/tv_full_200.json`, `evaluation/results/hotpotqa_full/tv_filtered_full_200.json` |
| VimQA benchmark | `evaluation/results/vimqa/bm25_vimqa_full.json`, `evaluation/results/vimqa/dense_bkai_vimqa_full.json` |
| Paraphrase robustness | `docs/sprint4/paraphrase-robustness-report.md`, `evaluation/results/hotpotqa_full/paraphrase_final/...` |
| Bridge-RRF multi-hop ablation | `docs/sprint4/retrieval-improvement-report.md`, `evaluation/results/hotpotqa_full/bridge_rrf/...` |
| Ranking diagnostics | `docs/sprint5/ranking-diagnostics-report.md`, `evaluation/results/hotpotqa_full/ranking_diagnostics/...` |
| Reranker RRF ablation | `docs/sprint5/reranker-rrf-ablation-report.md`, `evaluation/results/hotpotqa_full/reranker_ablation/...` |
| Metadata demo | `docs/sprint4/metadata-demo-report.md`, `evaluation/results/hotpotqa_full/metadata/scenario_summary.json` |
| Semantic metadata evaluation | `docs/sprint5/semantic-metadata-search-report.md`, `docs/sprint5/vimqa-semantic-metadata-search-report.md` |

## 8. External And Managed Tools Referenced For Survey

These tools are not active runtime dependencies unless stated elsewhere. They
are included because the report/presentation compares the local design against
common research and commercial retrieval stacks.

| Tool / platform | Reference |
| --- | --- |
| Elastic hybrid search | https://www.elastic.co/what-is/hybrid-search |
| Pinecone hybrid search | https://docs.pinecone.io/guides/search/hybrid-search |
| Azure AI Search hybrid search | https://learn.microsoft.com/en-us/azure/search/hybrid-search-overview |
| Algolia NeuralSearch | https://www.algolia.com/doc/guides/ai-relevance/neuralsearch/get-started |
| FAISS | https://github.com/facebookresearch/faiss |
| Milvus | https://milvus.io/docs/hybrid_search_with_milvus.md |
| Qdrant | https://qdrant.tech/documentation/search/hybrid-queries/ |
| Vespa | https://docs.vespa.ai/en/learn/tutorials/hybrid-search.html |

## 9. Project Documents That Ground These References

| Document | Use |
| --- | --- |
| `README.md` | Runtime overview, Docker setup, benchmark commands, dataset-first behavior. |
| `REPORT.md` | Mentor-facing report and survey/benchmark narrative. |
| `PRESENTATION.md` | Presentation script and mentor Q&A. |
| `docs/architecture/current-architecture.md` | Current architecture and Mermaid diagrams. |
| `docs/sprint3/sprint3-report.md` | Full-corpus TurboVec build and benchmark evidence. |
| `docs/sprint4/sprint4-report.md` | Paraphrase, metadata, VimQA, Bridge-RRF, dataset-first summary. |
| `docs/sprint5/ranking-diagnostics-report.md` | Ranking diagnostics before reranker. |
| `docs/sprint5/reranker-rrf-ablation-report.md` | Reranker-vs-RRF pilot result. |
