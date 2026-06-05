.PHONY: install index api eval benchmark benchmark-smoke test

install:
	pip install -r requirements.txt

index:
	python -m src.indexing.build_faiss

index-smoke:
	python -m src.indexing.build_faiss --model hashing

api:
	uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

eval:
	python -m evaluation.run_eval

benchmark:
	python -m evaluation.benchmark_retrieval --qrels data/eval/ami_qrels.json --top-k 5

benchmark-smoke:
	python -m evaluation.benchmark_retrieval --model hashing --rebuild-shared --qrels data/eval/sample_qrels.json --top-k 5

test:
	pytest -q
