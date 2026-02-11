"""Integration tests for `relay validate`."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from relay.cli import app

runner = CliRunner()


def test_validate_valid_workflow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A freshly initialised workflow should pass validation."""
    monkeypatch.chdir(tmp_path)

    init_result = runner.invoke(app, ["init"])
    assert init_result.exit_code == 0, init_result.output

    validate_result = runner.invoke(app, ["validate"])
    assert validate_result.exit_code == 0, (
        f"Expected valid workflow (exit 0), got {validate_result.exit_code}\n"
        f"{validate_result.output}"
    )
    assert "valid" in validate_result.output.lower(), (
        f"Expected 'valid' in output, got:\n{validate_result.output}"
    )


def test_validate_missing_role_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Deleting the role file should cause validate to report an error."""
    monkeypatch.chdir(tmp_path)

    init_result = runner.invoke(app, ["init"])
    assert init_result.exit_code == 0, init_result.output

    # Delete the role file that the minimal workflow references
    role_file = tmp_path / ".relay" / "workflows" / "default" / "roles" / "worker.yml"
    assert role_file.exists(), "Role file should exist after init"
    role_file.unlink()

    validate_result = runner.invoke(app, ["validate"])
    assert validate_result.exit_code == 1, (
        f"Expected exit code 1 for missing role file, got {validate_result.exit_code}\n"
        f"{validate_result.output}"
    )
    # Should mention the missing role file
    output_lower = validate_result.output.lower()
    assert "error" in output_lower or "not found" in output_lower, (
        f"Expected error about missing role file, got:\n{validate_result.output}"
    )
