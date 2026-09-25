"""Tests for the load-test harness and benchmark reporter."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LOCUSTFILE = ROOT / "locustfile.py"
BENCHMARK_SCRIPT = ROOT / "scripts" / "benchmark.py"


def _load_benchmark_module():
    spec = importlib.util.spec_from_file_location("pulse_benchmark", BENCHMARK_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_locustfile_exists_and_defines_expected_tasks() -> None:
    assert LOCUSTFILE.exists()
    source = LOCUSTFILE.read_text(encoding="utf-8")
    for path in ("/v1/events", "/v1/events/batch", "/v1/queries", "/v1/metrics/"):
        assert path in source
    locust = pytest.importorskip("locust")
    spec = importlib.util.spec_from_file_location("pulse_locustfile", LOCUSTFILE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    user = module.PulseUser
    task_names = {fn.__name__ for fn in user.tasks}
    assert {"ingest_single", "ingest_batch", "query_aggregate", "get_metric"} <= task_names
    assert locust is not None


def test_percentile_and_stats_from_latencies() -> None:
    bench = _load_benchmark_module()
    samples = [10.0, 20.0, 30.0, 40.0, 50.0]
    stats = bench.stats_from_latencies("POST /v1/events", samples, duration_s=2.0)
    assert stats.requests == 5
    assert stats.rps == pytest.approx(2.5)
    assert stats.p50_ms == pytest.approx(30.0)
    assert stats.p95_ms == pytest.approx(48.0)
    assert stats.p99_ms == pytest.approx(49.6)


def test_render_markdown_dry_run_has_no_invented_numbers() -> None:
    bench = _load_benchmark_module()
    report = bench.BenchmarkReport(
        generated_at="2026-01-01T00:00:00+00:00",
        mode="dry-run",
        host="http://127.0.0.1:8000",
        users=5,
        spawn_rate=2.0,
        duration="10s",
        endpoints=[],
        notes=["Dry-run only"],
    )
    markdown = bench.render_markdown(report)
    assert "No live load test was executed" in markdown
    assert "| `" not in markdown


def test_render_markdown_includes_measured_rows() -> None:
    bench = _load_benchmark_module()
    stats = bench.stats_from_latencies("POST /v1/events/batch", [5.0, 7.0, 9.0], duration_s=1.0)
    report = bench.BenchmarkReport(
        generated_at="2026-01-01T00:00:00+00:00",
        mode="live",
        host="http://example",
        users=2,
        spawn_rate=1.0,
        duration="1s",
        endpoints=[stats],
        notes=["measured"],
    )
    markdown = bench.render_markdown(report)
    assert "`POST /v1/events/batch`" in markdown
    assert str(stats.rps) in markdown
    assert str(stats.p50_ms) in markdown


def test_benchmark_cli_dry_run_writes_file(tmp_path: Path) -> None:
    output = tmp_path / "BENCHMARKS.md"
    completed = subprocess.run(
        [
            sys.executable,
            str(BENCHMARK_SCRIPT),
            "--dry-run",
            "--output",
            str(output),
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert output.exists()
    body = output.read_text(encoding="utf-8")
    assert "Pulse benchmarks" in body
    assert "No live load test was executed" in body
    payload = json.loads(completed.stdout)
    assert payload["mode"] == "dry-run"
    assert payload["endpoints"] == []
