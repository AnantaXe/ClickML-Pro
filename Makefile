.PHONY: help install install-dev install-all lint test serve docker-build docker-up clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install core package
	pip install -e .

install-dev: ## Install with dev dependencies
	pip install -e ".[dev]"

install-all: ## Install all optional dependencies
	pip install -e ".[all,dev]"

install-training: ## Install with training dependencies
	pip install -e ".[training]"

install-data: ## Install with data engineering dependencies
	pip install -e ".[data]"

lint: ## Run linter
	ruff check clickml_pro/ tests/
	mypy clickml_pro/

format: ## Auto-format code
	ruff format clickml_pro/ tests/

test: ## Run tests
	pytest tests/ -v --tb=short

test-cov: ## Run tests with coverage
	pytest tests/ -v --cov=clickml_pro --cov-report=html --cov-report=term

serve: ## Start the API server
	clickml serve

serve-dev: ## Start the API server in dev mode
	clickml serve --reload

docker-build: ## Build Docker images
	docker compose build

docker-up: ## Start all services
	docker compose up -d

docker-down: ## Stop all services
	docker compose down

docker-logs: ## Follow Docker logs
	docker compose logs -f

clean: ## Remove build artifacts
	rm -rf build/ dist/ *.egg-info .pytest_cache htmlcov .mypy_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
