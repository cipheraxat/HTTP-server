.PHONY: help install dev test coverage lint format clean run

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install package
	pip install -e .

dev:  ## Install with development dependencies
	pip install -e ".[dev]"

test:  ## Run tests
	pytest

coverage:  ## Run tests with coverage report
	pytest --cov=src/httpserver --cov-report=html --cov-report=term-missing
	@echo "Coverage report: htmlcov/index.html"

lint:  ## Run linters
	ruff check src tests
	mypy src

format:  ## Format code
	ruff format src tests
	ruff check --fix src tests

clean:  ## Clean build artifacts
	rm -rf build dist *.egg-info
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	rm -rf htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +

run:  ## Run the server
	python -m httpserver

run-dev:  ## Run server in development mode with debug logging
	python -m httpserver --log-level DEBUG --cors

benchmark:  ## Run load test (requires wrk)
	@echo "Starting server in background..."
	python -m httpserver &
	@sleep 2
	@echo "Running benchmark..."
	wrk -t4 -c100 -d10s http://127.0.0.1:8080/health
	@pkill -f "python -m httpserver" || true
