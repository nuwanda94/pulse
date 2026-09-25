"""Locust load-test harness for Pulse ingest and query paths.

Usage (against a running stack)::

    locust -f locustfile.py --host http://localhost:8000 --headless -u 10 -r 2 -t 30s

Environment:
    PULSE_API_KEY   API key sent as X-API-Key (default: bench-key)
    PULSE_METRIC    Event / metric name used by tasks (default: bench.latency)
"""

from __future__ import annotations

import os
import random
from typing import Any

from locust import HttpUser, between, task

API_KEY = os.environ.get("PULSE_API_KEY", "bench-key")
METRIC_NAME = os.environ.get("PULSE_METRIC", "bench.latency")
API_KEY_HEADER = os.environ.get("PULSE_API_KEY_HEADER", "X-API-Key")


def _event_payload(name: str = METRIC_NAME) -> dict[str, Any]:
    return {
        "name": name,
        "value": random.random() * 100.0,
        "tags": {"source": "locust", "env": "bench"},
    }


class PulseUser(HttpUser):
    """Mix of single ingest, batch ingest, and query traffic."""

    wait_time = between(0.01, 0.1)

    def on_start(self) -> None:
        self.client.headers[API_KEY_HEADER] = API_KEY

    @task(5)
    def ingest_single(self) -> None:
        self.client.post("/v1/events", json=_event_payload(), name="POST /v1/events")

    @task(3)
    def ingest_batch(self) -> None:
        batch = {"events": [_event_payload() for _ in range(10)]}
        self.client.post("/v1/events/batch", json=batch, name="POST /v1/events/batch")

    @task(2)
    def query_aggregate(self) -> None:
        self.client.post(
            "/v1/queries",
            json={"name": METRIC_NAME, "op": "avg"},
            name="POST /v1/queries",
        )

    @task(1)
    def get_metric(self) -> None:
        self.client.get(f"/v1/metrics/{METRIC_NAME}", name="GET /v1/metrics/{name}")
