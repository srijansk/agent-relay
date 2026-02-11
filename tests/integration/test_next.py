"""Integration tests for `relay next`."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from relay.cli import app

runner = CliRunner()


def test_next_shows_prompt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """After init, relay next should display a prompt containing role/task information."""
    monkeypatch.chdir(tmp_path)

    init_result = runner.invoke(app, ["init"])
    assert init_result.exit_code == 0, init_result.output

    next_result = runner.invoke(app, ["next"])
    assert next_result.exit_code == 0, next_result.output
    # The prompt should include the role name "worker" from the minimal workflow
    assert "worker" in next_result.output.lower(), (
        f"Expected 'worker' in next output, got:\n{next_result.output}"
    )


def test_next_terminal_exits_clean(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When the workflow is in a terminal stage, relay next should exit cleanly."""
    monkeypatch.chdir(tmp_path)

    init_result = runner.invoke(app, ["init"])
    assert init_result.exit_code == 0, init_result.output

    # Manually set the state to the terminal stage ("done")
    state_path = tmp_path / ".relay" / "workflows" / "default" / "state.yml"
    state = yaml.safe_load(state_path.read_text())
    state["stage"] = "done"
    state_path.write_text(yaml.dump(state, default_flow_style=False, sort_keys=False))

    next_result = runner.invoke(app, ["next"])
    assert next_result.exit_code == 0, (
        f"Expected clean exit (code 0) at terminal stage, got {next_result.exit_code}\n"
        f"{next_result.output}"
    )
    assert "complete" in next_result.output.lower(), (
        f"Expected completion message, got:\n{next_result.output}"
    )
