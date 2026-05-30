.PHONY: help install lint test build up down clean preprocess index evaluate

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies
	pip install -r requirements.txt

lint: ## Run linter
	ruff check src/ tests/

test: ## Run tests
	pytest tests/ -v

build: ## Build Docker images
	docker compose -f docker/docker-compose.yml build

up: ## Start all services
	docker compose -f docker/docker-compose.yml up -d

down: ## Stop all services
	docker compose -f docker/docker-compose.yml down

clean: ## Clean generated files
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

preprocess: ## Run data preprocessing
	python -m src.preprocessing.pipeline

index: ## Index data to Elasticsearch
	python -m src.indexing.bulk_index

evaluate: ## Run evaluation
	python -m evaluation.run_eval
