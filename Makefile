.PHONY: install index api eval test

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

test:
	pytest -q

