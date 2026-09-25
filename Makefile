.PHONY: lint typecheck test format benchmark install up down logs ps migrate

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

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f app

ps:
	docker compose ps

migrate:
	docker compose run --rm app alembic upgrade head
