.PHONY: install benchmark api

install:
	pip install -r requirements.txt

benchmark:
	python -m src.evaluation.benchmark_es --dataset nano-beir/hotpotqa --index hotpotqa_nano_current --methods es_bm25,es_dense,es_hybrid,es_iterative_hybrid --top-k 10 --candidate-k 100 --num-candidates 100 --rrf-k 30 --first-hop-k 5 --second-hop-k 10 --context-chars 256 --output evaluation/results/es_nano_iterative.json --run-dir evaluation/runs/iterative

api:
	uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
