"""Integration tests for `relay init`."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from relay.cli import app

runner = CliRunner()


def test_init_creates_relay_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """relay init should create .relay/workflows/default/workflow.yml."""
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0, result.output

    workflow_yml = tmp_path / ".relay" / "workflows" / "default" / "workflow.yml"
    assert workflow_yml.exists(), f"Expected {workflow_yml} to exist"


def test_init_creates_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """relay init should create state.yml with the initial_stage."""
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0, result.output

    state_yml = tmp_path / ".relay" / "workflows" / "default" / "state.yml"
    assert state_yml.exists(), f"Expected {state_yml} to exist"

    state = yaml.safe_load(state_yml.read_text())
    assert state["stage"] == "working", f"Expected initial stage 'working', got {state['stage']}"


def test_init_named_workflow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """relay init --name foo should create .relay/workflows/foo/."""
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "--name", "foo"])
    assert result.exit_code == 0, result.output

    wf_dir = tmp_path / ".relay" / "workflows" / "foo"
    assert wf_dir.is_dir(), f"Expected {wf_dir} to be a directory"
    assert (wf_dir / "workflow.yml").exists()
    assert (wf_dir / "state.yml").exists()


def test_init_duplicate_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Running relay init twice for the same workflow should fail with exit code 1."""
    monkeypatch.chdir(tmp_path)

    first = runner.invoke(app, ["init"])
    assert first.exit_code == 0, first.output

    second = runner.invoke(app, ["init"])
    assert second.exit_code == 1, (
        f"Expected exit code 1 on duplicate init, got {second.exit_code}\n{second.output}"
    )


# Template directory lives at src/relay/templates/<template_name>
_TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "src" / "relay" / "templates" / "plan_review_implement_audit"


@pytest.mark.skipif(
    not _TEMPLATE_DIR.exists(),
    reason=f"Template directory not found at {_TEMPLATE_DIR}; template not yet created",
)
def test_init_with_template(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """relay init --template plan-review-implement-audit copies template files."""
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "--template", "plan-review-implement-audit"])
    assert result.exit_code == 0, result.output

    wf_dir = tmp_path / ".relay" / "workflows" / "default"
    assert wf_dir.is_dir()
    assert (wf_dir / "workflow.yml").exists()
    # Template should have a roles sub-directory with at least one file
    roles_dir = wf_dir / "roles"
    assert roles_dir.is_dir(), "Template should include a roles/ directory"
    assert any(roles_dir.iterdir()), "roles/ should contain at least one file"
