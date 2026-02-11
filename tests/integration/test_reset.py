"""Integration tests for `relay reset`."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from relay.cli import app

runner = CliRunner()


def test_reset_clears_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """After init + reset, state.yml should be back to the initial_stage."""
    monkeypatch.chdir(tmp_path)

    init_result = runner.invoke(app, ["init"])
    assert init_result.exit_code == 0, init_result.output

    # Mutate the state to simulate progress
    state_path = tmp_path / ".relay" / "workflows" / "default" / "state.yml"
    state = yaml.safe_load(state_path.read_text())
    state["stage"] = "done"
    state["iteration_counts"] = {"working": 3, "done": 1}
    state_path.write_text(yaml.dump(state, default_flow_style=False, sort_keys=False))

    # Reset
    reset_result = runner.invoke(app, ["reset"])
    assert reset_result.exit_code == 0, reset_result.output

    # Verify state is back to initial
    state_after = yaml.safe_load(state_path.read_text())
    assert state_after["stage"] == "working", (
        f"Expected stage 'working' after reset, got {state_after['stage']}"
    )


def test_reset_clean_wipes_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """relay reset --clean should delete artifacts but preserve context.md."""
    monkeypatch.chdir(tmp_path)

    init_result = runner.invoke(app, ["init"])
    assert init_result.exit_code == 0, init_result.output

    artifact_dir = tmp_path / ".relay" / "workflows" / "default" / "artifacts"

    # Create a test artifact
    test_artifact = artifact_dir / "output.md"
    test_artifact.write_text("some output content")
    assert test_artifact.exists()

    # Ensure context.md exists (created by init)
    context_md = artifact_dir / "context.md"
    assert context_md.exists(), "context.md should exist after init"

    # Reset with --clean
    reset_result = runner.invoke(app, ["reset", "--clean"])
    assert reset_result.exit_code == 0, reset_result.output

    # Artifact should be deleted
    assert not test_artifact.exists(), "output.md should be deleted after reset --clean"

    # context.md should be preserved
    assert context_md.exists(), "context.md should be preserved after reset --clean"
