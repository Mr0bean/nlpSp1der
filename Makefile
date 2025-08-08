# Makefile for Newsletter System

.PHONY: help install install-dev test lint format clean build run-crawler run-basic docs protect

# Default target
help:
	@echo "Available targets:"
	@echo "  install     - Install package in development mode"
	@echo "  install-dev - Install with development dependencies"
	@echo "  test        - Run tests"
	@echo "  lint        - Run linting checks"
	@echo "  format      - Format code with black"
	@echo "  clean       - Clean build artifacts"
	@echo "  build       - Build package"
	@echo "  run-crawler - Run optimized crawler"
	@echo "  run-basic   - Run basic crawler"
	@echo "  docs        - View documentation structure"
	@echo "  protect     - Run protected flow check"

# Installation targets
install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"

# Development targets
test:
	python -m pytest src/tests/ -v

lint:
	flake8 src/
	mypy src/newsletter_system/

format:
	black src/

# Build targets
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

build: clean
	python -m build

# Run targets
run-crawler:
	python3 src/scripts/run_optimized.py

run-basic:
	python3 src/scripts/run.py

# Documentation
docs:
	@echo "📚 Documentation Structure:"
	@find docs -name "*.md" | head -10
	@echo ""
	@echo "📁 Source Structure:"
	@find src -name "*.py" -not -path "*/test*" | head -10

# Protected flows check
protect:
	python3 scripts/protect_flows_check.py --staged || true

# Setup development environment
setup-dev: install-dev
	playwright install chromium
	@echo "✅ Development environment ready!"
	@echo "💡 Run 'make run-crawler' to start crawling"

# Check project health
check: lint test
	@echo "✅ All checks passed!"