# Makefile for tradestation-cli-mcp
# See docs/01-project-structure.md §"Workspace tooling"

.PHONY: install test lint typecheck codegen vendor clean

install:
	pip install -e ".[dev]"

test:
	pytest -m "not live" -v

lint:
	ruff format --check src tests scripts
	ruff check src tests scripts

typecheck:
	mypy src/tradestation

codegen:
	python scripts/codegen.py

vendor:
	python scripts/verify_pin.py
	python scripts/fetch_v3_spec.py

clean:
	rm -rf build dist .eggs *.egg-info
	rm -rf .mypy_cache .ruff_cache .pytest_cache
	rm -rf coverage.xml .coverage htmlcov
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
