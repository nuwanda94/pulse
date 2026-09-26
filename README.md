# Pulse

High-throughput **event ingestion and real-time aggregation API** built with FastAPI.

Pulse accepts authenticated events (single or batch), enforces per-key rate limits, aggregates metrics on read, and exposes Prometheus metrics with structured request logs. Designed as a small, production-shaped service: auth, quotas, observability, migrations, CI, and a reproducible load harness.

## Highlights

- **Authenticated ingest** — single and batch event APIs with hashed API keys and admin key lifecycle
- **Write rate limiting** — Redis-backed limiter (in-memory fallback) with `GET /v1/usage` for remaining quota
- **On-read aggregation** — named metric summaries, bucketed timeseries, and constrained ad-hoc queries
- **Observability** — Prometheus `/metrics`, request-id middleware, structlog with duration fields
- **Ops-ready** — async Postgres (SQLAlchemy 2 + Alembic), Docker multi-stage image, health/readiness probes
- **Quality bar** — Ruff, strict mypy, pytest, GitHub Actions CI, Locust + benchmark script

## Tech stack

| Layer | Choice |
|-------|--------|
| API | FastAPI, Pydantic v2, Uvicorn, orjson |
| Data | PostgreSQL, SQLAlchemy 2.0 async, Alembic, asyncpg |
| Cache / limits | Redis (token/sliding window style limiter) |
| Observability | prometheus-client, structlog |
| Tooling | Python 3.12, Ruff, mypy (strict), pytest, Locust |
| Delivery | Docker multi-stage, docker compose, GitHub Actions |

## Quickstart

```bash
cp .env.example .env
docker compose up --build
```

App listens on **port 8000**.

| Probe | Purpose |
|-------|---------|
| `GET /health` | Process liveness |
| `GET /ready` | Postgres + Redis reachability |
| `GET /metrics` | Prometheus text exposition |
| `GET /docs` | Interactive OpenAPI UI |

### Example: create a key and ingest an event

```bash
# Create an admin-capable key (secret returned once)
curl -s -X POST http://127.0.0.1:8000/v1/api-keys \
  -H "X-API-Key: $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "demo", "is_admin": false}' 

# Ingest a single event
curl -s -X POST http://127.0.0.1:8000/v1/events \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "page_view", "value": 1, "tags": {"path": "/home"}}'
```

## HTTP API

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

### Authentication

Send the raw secret in the `X-API-Key` header (name configurable via `API_KEY_HEADER`). Secrets are stored hashed; the raw value is returned only once on create. Admin routes require an admin key.

### Errors

Responses use a consistent envelope (plus FastAPI `detail`):

```json
{
  "detail": "Missing API key",
  "error": {"code": "unauthorized", "message": "Missing API key"},
  "request_id": "..."
}
```

`X-Request-ID` is accepted and echoed on responses.

## Architecture

```
Clients ──► FastAPI (auth, rate limit, metrics middleware)
              │
              ├─► PostgreSQL  (events, aggregates, API keys)
              └─► Redis       (rate-limit counters; optional)
```

- **Ingest path**: validate → rate-limit → persist events (bulk-friendly batch path).
- **Read path**: aggregate from stored events (count/sum/avg and timeseries buckets).
- **Ops**: Alembic migrations, non-root Docker image, healthchecks, structured logs with request id and timing.

## Configuration

Copy `.env.example`. Notable settings:

| Variable | Role |
|----------|------|
| `DATABASE_URL` | `postgresql+asyncpg://…` |
| `REDIS_URL` | `redis://…` or `rediss://…` |
| `API_KEY_HEADER` | Header name for API keys |
| `RATE_LIMIT_REQUESTS` / `RATE_LIMIT_WINDOW_SECONDS` | Per-key write quota |
| `LOG_LEVEL` | structlog level |

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
make lint        # ruff
make typecheck   # mypy (strict)
make test        # pytest
make benchmark   # load harness → BENCHMARKS.md
```

CI (GitHub Actions) runs lint → typecheck → tests on push/PR, with Postgres and Redis services. Measured live benchmarks run only on manual `workflow_dispatch` so numbers stay honest and reproducible.

## Benchmarks

Performance figures are **not** invented in this README. Generate them with:

```bash
make benchmark   # dry-run by default; writes BENCHMARKS.md
python scripts/benchmark.py --live --host http://127.0.0.1:8000
```

See `BENCHMARKS.md` for the latest measured RPS and latency percentiles after a live run.
