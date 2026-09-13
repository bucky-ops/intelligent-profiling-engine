.PHONY: help install dev lint type test test-cov security docker docker-run clean docs

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:  ## Install runtime deps
	pip install -r requirements.txt
	python -m spacy download en_core_web_sm

dev:  ## Install dev + test deps and pre-commit hooks
	pip install -r requirements-dev.txt
	python -m spacy download en_core_web_sm
	pre-commit install

lint:  ## Run ruff
	ruff check src tests

type:  ## Run mypy
	mypy src

test:  ## Run pytest
	pytest tests

test-cov:  ## Run pytest with coverage
	pytest tests --cov=src/profile_system --cov-report=term-missing --cov-report=html

security:  ## Run pip-audit + bandit
	pip-audit -r requirements.txt --strict
	bandit -r src -q

docker:  ## Build the Docker image
	docker build -t intelligent-profiling-engine:latest .

docker-run:  ## Run the Streamlit app in Docker
	docker compose up -d web
	@echo "Open http://localhost:8501"

docs:  ## Serve mkdocs locally
	mkdocs serve

clean:  ## Remove build artefacts
	rm -rf build dist *.egg-info .pytest_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
