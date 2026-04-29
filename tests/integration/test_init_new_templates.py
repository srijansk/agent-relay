"""Integration tests for the new v0.2 templates: bug-rca-fix and rfc-then-implement."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from relay.cli import app
from relay.protocol.workflow import WorkflowDefinition

runner = CliRunner()


@pytest.mark.parametrize(
    "template_name, expected_initial_stage, expected_role_count",
    [
        ("bug-rca-fix", "reproduce", 6),
        ("rfc-then-implement", "rfc_draft", 4),
        ("plan-review-implement-audit", "plan_draft", 4),
    ],
)
def test_init_new_templates_produce_valid_workflow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    template_name: str,
    expected_initial_stage: str,
    expected_role_count: int,
) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "--template", template_name])
    assert result.exit_code == 0, result.output

    wf_dir = tmp_path / ".relay" / "workflows" / "default"
    wf_yml = wf_dir / "workflow.yml"
    assert wf_yml.exists()

    workflow = WorkflowDefinition.model_validate(yaml.safe_load(wf_yml.read_text()))
    assert workflow.initial_stage == expected_initial_stage
    assert len(workflow.roles) == expected_role_count

    roles_dir = wf_dir / "roles"
    for role_name in workflow.roles:
        assert (roles_dir / f"{role_name}.yml").exists()


def test_template_validate_command_passes_for_new_templates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each shipped template must pass `relay validate`."""
    for template_name in ("bug-rca-fix", "rfc-then-implement", "plan-review-implement-audit"):
        proj = tmp_path / template_name
        proj.mkdir()
        monkeypatch.chdir(proj)
        init_result = runner.invoke(app, ["init", "--template", template_name])
        assert init_result.exit_code == 0, init_result.output
        validate_result = runner.invoke(app, ["validate"])
        assert validate_result.exit_code == 0, validate_result.output


def test_planner_role_in_plan_review_template_has_inject_lessons_true(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init", "--template", "plan-review-implement-audit"])
    planner_yml = tmp_path / ".relay" / "workflows" / "default" / "roles" / "planner.yml"
    raw = yaml.safe_load(planner_yml.read_text())
    assert raw.get("inject_lessons") is True
