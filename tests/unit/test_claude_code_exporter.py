"""Claude Code exporter — produces .claude/agents + .claude/commands."""

from __future__ import annotations

from pathlib import Path

import yaml

from relay.exporters.claude_code import export_to_claude_code

_TEMPLATE_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "relay"
    / "templates"
    / "plan_review_impl_audit"
)


def test_exporter_creates_agent_per_role(tmp_path: Path) -> None:
    output_dir = tmp_path / "project"
    output_dir.mkdir()

    created = export_to_claude_code(_TEMPLATE_DIR, output_dir)
    agents_dir = output_dir / ".claude" / "agents"

    role_names = {"planner", "reviewer", "implementer", "auditor"}
    for role in role_names:
        agent_file = agents_dir / f"{role}.md"
        assert agent_file.exists(), f"Expected {agent_file} to exist"
        body = agent_file.read_text()
        assert body.startswith("---\n"), f"{agent_file} should start with frontmatter"
        # Frontmatter parses as YAML with name + description.
        _, fm, _ = body.split("---\n", 2)
        meta = yaml.safe_load(fm)
        assert meta["name"] == role
        assert meta["description"]

    assert any(p.name == "README.md" for p in created)


def test_exporter_creates_slash_commands(tmp_path: Path) -> None:
    output_dir = tmp_path / "project"
    output_dir.mkdir()

    export_to_claude_code(_TEMPLATE_DIR, output_dir)
    commands_dir = output_dir / ".claude" / "commands"

    for cmd in ["relay-status", "relay-next", "relay-advance", "relay-distill"]:
        cmd_file = commands_dir / f"{cmd}.md"
        assert cmd_file.exists(), f"Expected slash command {cmd_file}"
        body = cmd_file.read_text()
        assert body.startswith("---\n"), f"{cmd_file} should have frontmatter"
        assert "description" in body


def test_exporter_includes_verdict_section_for_branching_roles(tmp_path: Path) -> None:
    output_dir = tmp_path / "project"
    output_dir.mkdir()

    export_to_claude_code(_TEMPLATE_DIR, output_dir)
    reviewer = (output_dir / ".claude" / "agents" / "reviewer.md").read_text()
    assert "## Verdict" in reviewer
    assert "APPROVE" in reviewer
    assert "REQUEST_CHANGES" in reviewer
