# Pulse

High-throughput event ingestion and real-time aggregation API built with FastAPI.

The service accepts authenticated events (single or batch), rate-limits writes per API key, aggregates metrics on read, and exposes Prometheus plus structured request logs.

## Status

Implementation follows the ordered backlog in `TASKS.md`. All listed application features through CI are in place.

Performance numbers are **not** claimed in this README. Generate them with the benchmark harness:

```bash
make benchmark   # writes BENCHMARKS.md (dry-run by default)
# live numbers (requires a running stack):
python scripts/benchmark.py --live --host http://127.0.0.1:8000
```

See `BENCHMARKS.md` after a run. Until then that file is a placeholder only.

On GitHub Actions, measured (`--live`) benchmarks run **only** when you manually start the **CI** workflow (`workflow_dispatch`). Push and pull-request runs keep the dry-run job only. After a successful manual live run, `BENCHMARKS.md` is committed to the branch and also uploaded as the `benchmarks` artifact.

## Quickstart

```bash
cp .env.example .env
docker compose up --build
```

The app listens on port 8000. Probes:

- `GET /health` — process liveness
- `GET /ready` — Postgres + Redis reachability
- `GET /metrics` — Prometheus text exposition
- `GET /docs` — OpenAPI UI

## Authentication

Send the raw secret in `X-API-Key` (configurable via `API_KEY_HEADER`). Secrets are stored hashed. The raw value is returned only once, on `POST /v1/api-keys`.

Admin operations (`/v1/api-keys`, `/v1/admin/ping`) require an admin key.

## HTTP API (≤15 endpoints)

| Method | Path | Auth | Notes |
|--------|------|------|--------|
| GET | `/health` | no | Liveness |
| GET | `/ready` | no | Readiness |
| GET | `/metrics` | no | Prometheus |
| GET | `/v1/me` | key | Current key metadata |
| GET | `/v1/admin/ping` | admin | Admin probe |
| POST | `/v1/api-keys` | admin | Create key (secret once) |
| GET | `/v1/api-keys` | admin | List keys |
| DELETE | `/v1/api-keys/{key_id}` | admin | Revoke key |
| POST | `/v1/events` | key + write limit | Single ingest |
| POST | `/v1/events/batch` | key + write limit | Batch ingest; `Idempotency-Key` supported |
| GET | `/v1/usage` | key | Remaining write quota |
| GET | `/v1/metrics/{name}` | key | Count / sum / avg |
| GET | `/v1/metrics/{name}/timeseries` | key | Bucketed series |
| POST | `/v1/queries` | key | Fixed-operator ad-hoc query |

Errors use FastAPI's `detail` field and an additional envelope:

```json
{
  "detail": "Missing API key",
  "error": {"code": "unauthorized", "message": "Missing API key"},
  "request_id": "..."
}
```

`X-Request-ID` is accepted and echoed on responses.

## Configuration

Copy `.env.example`. Notable settings:

- `DATABASE_URL` — `postgresql+asyncpg://…`
- `REDIS_URL` — `redis://…` or `rediss://…`
- `API_KEY_HEADER`
- `RATE_LIMIT_REQUESTS` / `RATE_LIMIT_WINDOW_SECONDS`
- `LOG_LEVEL`

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
make lint
make typecheck
make test
make benchmark
```

## Architecture

- FastAPI + Pydantic v2 + Uvicorn
- PostgreSQL via SQLAlchemy 2.0 async + Alembic
- Redis for rate-limit counters (in-memory fallback)
- Prometheus request counters and latency histograms
- structlog with request-id and duration
- Locust file plus `scripts/benchmark.py` for reproducible load numbers
