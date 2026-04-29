"""Integration test: `relay export claude-code`."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from relay.cli import app

runner = CliRunner()


def test_export_claude_code_creates_subagents_and_commands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init", "--template", "plan-review-implement-audit"])

    result = runner.invoke(app, ["export", "claude-code"])
    assert result.exit_code == 0, result.output

    agents_dir = tmp_path / ".claude" / "agents"
    commands_dir = tmp_path / ".claude" / "commands"
    assert agents_dir.is_dir()
    assert commands_dir.is_dir()

    for role in ("planner", "reviewer", "implementer", "auditor"):
        agent_file = agents_dir / f"{role}.md"
        assert agent_file.exists(), f"Missing subagent file: {agent_file}"
        body = agent_file.read_text()
        # Frontmatter must parse as YAML.
        _, fm, _ = body.split("---\n", 2)
        meta = yaml.safe_load(fm)
        assert meta["name"] == role
        assert meta["description"]

    for cmd in ("relay-status", "relay-next", "relay-advance", "relay-distill"):
        assert (commands_dir / f"{cmd}.md").exists()


def test_export_claude_code_aliases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init", "--template", "plan-review-implement-audit"])

    # Each of these should resolve to the claude-code exporter.
    for fmt in ("claude-code", "claude", "ClaudeCode"):
        proj = tmp_path / fmt.lower()
        proj.mkdir()
        result = runner.invoke(app, ["export", fmt, "-o", str(proj)])
        assert result.exit_code == 0, f"format {fmt} failed: {result.output}"
        assert (proj / ".claude" / "agents" / "planner.md").exists()
