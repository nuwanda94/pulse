# Pulse Implementation Backlog

Ordered list of atomic tasks. The automation always picks the **first** task whose status is `pending`.

Status values: `pending` | `in_progress` | `done`

---

## 1. chore: project foundation

- [x] Status: done
- Create `pyproject.toml` with modern tooling (ruff, mypy, pytest, httpx, fastapi, uvicorn, pydantic-settings, sqlalchemy[asyncio], asyncpg, redis, prometheus-client, orjson, structlog, alembic, locust).
- Add `Makefile` with targets: `lint`, `typecheck`, `test`, `format`, `benchmark`.
- Add `.gitignore`, `.python-version` (3.12), `ruff.toml` / config in pyproject.
- Add empty `app/` package structure and `tests/` skeleton.
- Add `docker-compose.yml` (postgres + redis only for now).
- Commit message style: `chore: ...`

## 2. chore: core config and settings

- [x] Status: done
- Implement `app/core/config.py` using Pydantic Settings (env-based).
- Settings: app name, debug, database URL, redis URL, API key header name, rate-limit defaults, log level.
- Add `.env.example`.
- Basic unit tests for settings loading.

## 3. feat: health and readiness endpoints

- [x] Status: done
- `GET /health` (liveness) and `GET /ready` (checks postgres + redis connectivity).
- Wire into FastAPI app in `app/main.py`.
- Integration tests using TestClient / httpx + docker services (or mocked).

## 4. feat: Prometheus metrics endpoint

- [x] Status: done
- `GET /metrics` using prometheus_client.
- Basic request counters / histograms middleware.
- Tests that `/metrics` returns text/plain and contains expected metric names.

## 5. chore: database models and session

- [x] Status: done
- SQLAlchemy 2.0 async engine + session dependency.
- Models: Event, MetricAggregate, ApiKey (minimal columns).
- Alembic setup + initial migration.
- Tests for session creation and basic model round-trip.

## 6. feat: API-key authentication

- [x] Status: done
- Dependency that extracts `X-API-Key`, looks up in DB (or in-memory for early stage), attaches current key to request state.
- Admin-scoped operations protected.
- Unit + integration tests for missing/invalid/valid keys.

## 7. feat: create / list / revoke API keys

- [x] Status: done
- `POST /v1/api-keys`, `GET /v1/api-keys`, `DELETE /v1/api-keys/{key_id}`.
- Proper Pydantic schemas, hashing of secrets, never return full secret after creation except once.
- Tests covering happy path and authorization failures.

## 8. feat: single event ingest

- [x] Status: done
- `POST /v1/events` – accept event payload (name, value, tags, timestamp).
- Persist to Postgres (or buffer).
- Auth required.
- Validation + tests.

## 9. feat: batch event ingest (high-throughput path)

- [ ] Status: in_progress
- `POST /v1/events/batch` – accept list of events, use efficient bulk insert or Redis buffer.
- Idempotency-Key support.
- Load-oriented tests (correctness under concurrent calls).

## 10. feat: rate limiting per API key

- [ ] Status: pending
- Redis-backed token-bucket or sliding-window limiter.
- Apply as dependency/middleware on write endpoints.
- `GET /v1/usage` showing remaining quota.
- Tests that enforce limits and return 429.

## 11. feat: metric aggregation queries

- [ ] Status: pending
- `GET /v1/metrics/{name}` – current aggregate (count/sum/avg).
- `GET /v1/metrics/{name}/timeseries` – bucketed series.
- Background or on-read aggregation from events.
- Tests with seeded data.

## 12. feat: lightweight ad-hoc query endpoint

- [ ] Status: pending
- `POST /v1/queries` – limited aggregation language or fixed operators.
- Keep scope small; reject complex queries.
- Tests.

## 13. chore: structured logging and request-id middleware

- [ ] Status: pending
- structlog setup, request-id generation/propagation, timing middleware.
- Tests that logs contain expected fields (or that middleware runs).

## 14. chore: Docker production image and compose for full stack

- [ ] Status: pending
- Multi-stage Dockerfile, non-root user, healthchecks.
- Full `docker-compose.yml` including the app service.
- Makefile targets to bring everything up.

## 15. feat: load-test harness and benchmark script

- [ ] Status: pending
- Locustfile (or k6) covering single + batch ingest + query paths.
- `scripts/benchmark.py` that runs under controlled conditions and writes `BENCHMARKS.md` with RPS / latency percentiles.
- CI-friendly; no manual numbers in README.

## 16. chore: GitHub Actions CI

- [ ] Status: pending
- Workflow: lint → typecheck → unit/integration tests → (optional) short load test.
- Cache dependencies, use services for postgres/redis.

## 17. fix / polish: error handling, OpenAPI polish, README finalization

- [ ] Status: pending
- Consistent error responses, better OpenAPI descriptions, final README with generated benchmark placeholder.
- Any remaining small fixes discovered during previous steps.

---

**Automation rules**

1. Always select the first `pending` task.
2. Mark it `in_progress` at start, `done` only after lint + typecheck + tests pass and code is pushed.
3. Commit messages must follow conventional commits matching the task type (`chore:`, `feat:`, `fix:`).
4. Never invent performance numbers; only generate them via the benchmark script.
5. Keep each change focused; do not implement later tasks early.
