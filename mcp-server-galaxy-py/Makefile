.PHONY: help install install-dev lint format test test-cov test-watch clean build upload run dev check

# Default target
help:
	@echo "Galaxy MCP Development Commands"
	@echo "================================"
	@echo "  make install        Install dependencies"
	@echo "  make install-dev    Install development dependencies"
	@echo "  make lint          Run linting checks"
	@echo "  make format        Auto-format code"
	@echo "  make test          Run tests"
	@echo "  make test-cov      Run tests with coverage"
	@echo "  make test-watch    Run tests in watch mode"
	@echo "  make clean         Clean build artifacts"
	@echo "  make build         Build package"
	@echo "  make check         Run all checks (lint, test)"
	@echo "  make run           Run the MCP server"
	@echo "  make dev           Run MCP dev server"

# Install dependencies
install:
	uv pip install -r requirements.txt

# Install development dependencies
install-dev: install
	uv pip install -r requirements-test.txt
	uv pip install -e .

# Linting
lint:
	uv run ruff check .
	uv run ruff format --check .
	npx prettier --check "**/*.md"

# Auto-format code
format:
	uv run ruff format .
	uv run ruff check --fix .
	npx prettier --write "**/*.md"

# Run tests
test:
	uv run pytest

# Run tests with coverage
test-cov:
	uv run pytest --cov=galaxy_mcp --cov-report=html --cov-report=term-missing

# Run tests in watch mode (requires pytest-watch)
test-watch:
	uv run pytest-watch

# Clean build artifacts
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf src/*.egg-info
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	find . -type f -name '*.pyc' -delete
	find . -type d -name '__pycache__' -delete

# Build package
build: clean
	uv run python -m build

# Run all checks (lint + test)
check: lint test

# Run the MCP server
run:
	uv run galaxy-mcp

# Run MCP dev server
dev:
	uv run --from . mcp dev galaxy_mcp.server