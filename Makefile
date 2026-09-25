.PHONY: lint typecheck test format benchmark install

install:
	pip install -e ".[dev]"

lint:
	ruff check .

format:
	ruff format .
	ruff check --fix .

typecheck:
	mypy app

test:
	pytest

benchmark:
	python scripts/benchmark.py
