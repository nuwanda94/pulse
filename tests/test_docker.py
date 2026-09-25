from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_dockerfile_is_multistage_and_non_root() -> None:
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "FROM python:3.12-slim-bookworm AS builder" in text
    assert "FROM python:3.12-slim-bookworm AS runtime" in text
    assert "USER pulse" in text
    assert "HEALTHCHECK" in text
    assert "uvicorn" in text
    assert "useradd" in text


def test_compose_includes_app_postgres_and_redis() -> None:
    text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "postgres:" in text
    assert "redis:" in text
    assert "app:" in text
    assert "condition: service_healthy" in text
    assert "8000:8000" in text
    assert "postgresql+asyncpg://pulse:pulse@postgres:5432/pulse" in text
    assert "redis://redis:6379/0" in text


def test_entrypoint_runs_migrations_by_default() -> None:
    text = (ROOT / "docker/entrypoint.sh").read_text(encoding="utf-8")
    assert "alembic upgrade head" in text
    assert "SKIP_MIGRATIONS" in text


def test_makefile_has_stack_targets() -> None:
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "docker compose up --build -d" in text
    assert "docker compose down" in text
