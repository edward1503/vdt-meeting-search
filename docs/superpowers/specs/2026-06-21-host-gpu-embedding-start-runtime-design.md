# Host GPU Embedding Start Runtime Design

## Goal

Provide one local startup command for the retrieval demo while keeping the embedding model on the host GPU. The runtime should avoid downloading PyTorch and SentenceTransformers into Docker images, but it should stop treating the embedding server as an invisible side process that can be missing, stale, or accidentally running on CPU.

The desired developer command is:

```bash
./start.sh
```

That command starts or reuses the host embedding service, proves it can embed on GPU, then starts Docker Compose for Elasticsearch, Redis, FastAPI, and the React frontend.

## Current State

- `docker-compose.yml` runs `elasticsearch`, `redis`, `api`, and `frontend`.
- The API container calls `EMBEDDING_SERVICE_URL`, currently `http://host.docker.internal:8010/embed`, for TurboVec query embeddings.
- `scripts/embedding_server.py` runs a host FastAPI embedding service with `SentenceTransformer`.
- `scripts/docker-dev.sh` and `scripts/docker-dev.ps1` can start the host embedding process, but they do not make device selection, PID ownership, log location, or `/embed` readiness explicit.
- The local machine has an NVIDIA GPU visible to both host `nvidia-smi` and Docker GPU passthrough, but the fastest implementation path is to keep model dependencies on the host.

## Decision

Use a host GPU embedding service managed by `start.sh`, not a Docker embedding service.

This keeps Docker image builds lean and avoids re-downloading or reinstalling GPU model dependencies inside containers. Docker Compose remains responsible for infrastructure and app services; `start.sh` owns the host embedding process lifecycle and readiness checks.

## Runtime Flow

1. `start.sh` checks required commands: `docker`, `python`, and `nvidia-smi`.
2. `start.sh` verifies host Python can import `torch` and `sentence_transformers`, then prints Torch, SentenceTransformers, CUDA availability, and GPU name.
3. `start.sh` checks `http://127.0.0.1:8010/health`.
4. If an embedding service is already healthy, the script reuses it and still verifies `/embed`.
5. If no healthy service exists, `start.sh` starts:

   ```bash
   CUDA_VISIBLE_DEVICES=0 python scripts/embedding_server.py --host 0.0.0.0 --port 8010 --device cuda
   ```

6. `start.sh` writes logs to `logs/embedding_server.stdout.log` and `logs/embedding_server.stderr.log`, and writes the process id to `.runtime/embedding_server.pid`.
7. `start.sh` polls `/health`, then calls `/embed` with a short text and requires a 384-dimensional vector before starting Compose.
8. `start.sh` runs:

   ```bash
   docker compose up -d --build elasticsearch redis api frontend
   ```

9. `start.sh` runs a small API smoke against `/datasets`, `/datasets/hotpotqa/stats`, and a HotpotQA `tv_hybrid` search.
10. The script prints final URLs for the frontend, API docs, and embedding health endpoint.

## Embedding Server Behavior

`scripts/embedding_server.py` should gain an explicit device option:

```bash
--device auto|cpu|cuda
```

For this runtime, `start.sh` uses `--device cuda`. If CUDA model loading or embedding fails, the startup should fail hard instead of silently falling back to CPU. This makes GPU usage honest and keeps later dense/hybrid failures from surfacing as API 500s during UI use.

`/health` should remain cheap and available, but it should expose runtime details when known:

- `status`
- `model`
- `device`
- `torch_cuda_available`
- `embedding_dim`, after warmup or first successful embed

The readiness gate for `start.sh` is `/embed`, not `/health`, because `/health` alone does not prove the model can load and produce vectors.

## Docker Compose Contract

Compose should continue running app infrastructure:

- Elasticsearch
- Redis
- API
- Frontend

The API container should keep using:

```text
EMBEDDING_SERVICE_URL=http://host.docker.internal:8010/embed
```

No PyTorch or SentenceTransformers dependency should be added to `requirements-api.txt` for this change.

## Error Handling

`start.sh` should stop with a clear error when:

- Docker is not reachable.
- `nvidia-smi` is unavailable.
- Host Python cannot import required embedding dependencies.
- CUDA is unavailable to Torch when `--device cuda` is requested.
- Port `8010` is occupied by a non-healthy service.
- `/embed` fails or returns the wrong vector dimension.
- Docker Compose does not bring up the app services.

If an existing embedding service is healthy but not running on CUDA, `start.sh` should report the mismatch and stop instead of reusing it.

## Validation

Expected proof for implementation:

- Host smoke: `nvidia-smi` sees the GPU.
- Host Python smoke: Torch reports CUDA available.
- Embedding smoke: `POST http://127.0.0.1:8010/embed` returns a 384-dimensional vector.
- Docker connectivity smoke: API container can reach `http://host.docker.internal:8010/health`.
- Compose smoke: `docker compose ps` shows API, frontend, Elasticsearch, and Redis up; Elasticsearch and Redis healthy.
- Retrieval smoke: HotpotQA `tv_hybrid` search through `http://127.0.0.1:8001/datasets/hotpotqa/search` returns HTTP 200 and non-empty results.

## Non-Goals

- Do not create a Docker GPU embedding service in this change.
- Do not install PyTorch or SentenceTransformers into the API Docker image.
- Do not change retrieval ranking logic, TurboVec index format, Elasticsearch indexes, or frontend query behavior.
- Do not add automatic CPU fallback for the GPU startup path.

## Open Implementation Notes

- `start.sh` is the primary requested entrypoint. Existing `scripts/docker-dev.ps1` can either remain as a legacy helper or be updated later to call the same workflow from PowerShell.
- On Windows, users may run `start.sh` through Git Bash, WSL, or another shell that supports POSIX shell scripts. The script should avoid Bash-only features where practical unless the shebang explicitly requires Bash.
- The previous CPU debug process on port `8010` should be stopped or rejected during implementation if it does not report `device=cuda`.
