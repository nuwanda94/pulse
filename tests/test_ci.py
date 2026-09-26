"""Sanity checks for the GitHub Actions CI workflow."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def test_ci_workflow_exists() -> None:
    assert WORKFLOW.is_file()
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "name: CI" in text
    for job in ("lint:", "typecheck:", "test:", "load-test:", "live-benchmark:"):
        assert job in text
    assert "ruff check" in text
    assert "mypy app" in text
    assert "pytest" in text
    assert "postgres:16" in text
    assert "redis:7" in text
    assert "cache: pip" in text
    assert "scripts/benchmark.py" in text
    assert "--dry-run" in text
    # Live measured run is manual-only; never automatic on push/PR.
    assert "workflow_dispatch" in text
    assert "github.event_name == 'workflow_dispatch'" in text
    assert "--live" in text
    assert "actions/upload-artifact" in text
