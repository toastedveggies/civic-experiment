.PHONY: install lint test run fmt clean

install:
	pip install -e ".[dev]"

lint:
	ruff check src/ tests/
	mypy src/

test:
	pytest tests/ -v

run:
	la_agendas crawl --dry-run

fmt:
	black src/ tests/
	ruff check --fix src/ tests/

clean:
	find . -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -r {} + 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .ruff_cache

