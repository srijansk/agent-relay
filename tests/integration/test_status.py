"""Integration tests for `relay status`."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from relay.cli import app

runner = CliRunner()


def test_status_shows_stage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """After init, relay status should mention the current stage 'working'."""
    monkeypatch.chdir(tmp_path)

    init_result = runner.invoke(app, ["init"])
    assert init_result.exit_code == 0, init_result.output

    status_result = runner.invoke(app, ["status"])
    assert status_result.exit_code == 0, status_result.output
    assert "working" in status_result.output, (
        f"Expected 'working' in status output, got:\n{status_result.output}"
    )


def test_status_no_workflow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """relay status without init should fail with exit code 1 and show an error."""
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["status"])
    assert result.exit_code == 1, (
        f"Expected exit code 1 when no workflow exists, got {result.exit_code}\n{result.output}"
    )
    # Should mention that no workflow was found or suggest running init
    output_lower = result.output.lower()
    assert "no workflow" in output_lower or "init" in output_lower, (
        f"Expected error message about missing workflow, got:\n{result.output}"
    )
