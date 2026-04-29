"""End-to-end: a lesson from run 1 must surface in run 2's planner prompt.

This is the headline value proposition for v0.2 — agents that get measurably
better on a task class because past plans / reviews / audits are compiled
into typed lessons that the next planner reads. The test simulates two
sequential runs and asserts the compounding effect actually happens.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from typer.testing import CliRunner

from relay.cli import app
from relay.prompt import compose_prompt
from relay.protocol.roles import RoleSpec
from relay.protocol.state import StateDocument
from relay.protocol.workflow import WorkflowDefinition

runner = CliRunner()


def _write_artifact(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def test_lesson_from_first_run_surfaces_in_second_run_prompt(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)

    # --- Run 1: bug-rca-fix template, simulate a complete workflow ---
    init = runner.invoke(app, ["init", "--template", "bug-rca-fix"])
    assert init.exit_code == 0, init.output

    wf_dir = tmp_path / ".relay" / "workflows" / "default"
    artifacts = wf_dir / "artifacts"

    # Drop in a realistic plan_review.md whose Required Changes section
    # contains a tag-bearing claim: "state.py" should turn up as a tag.
    _write_artifact(
        artifacts / "context.md",
        "# Context\n\nFix iteration counts mutation in src/relay/state.py.\n",
    )
    _write_artifact(
        artifacts / "plan_review.md",
        "## Verdict: REQUEST_CHANGES\n\n"
        "## Required Changes\n"
        "- Plan ignores the iteration_counts mutation in src/relay/state.py "
        "when state advances. The fix must guard against negative values.\n",
    )
    _write_artifact(
        artifacts / "audit.md",
        "## Verdict: REQUEST_CHANGES\n\n"
        "## Catches\n"
        "- Implementer disabled tests/unit/test_state_document.py to make "
        "the suite pass. Do not weaken existing tests.\n",
    )

    # Force run 1 to a terminal state, snapshot via the CLI advance path.
    # The bug-rca-fix workflow's terminal stage is `done`. We jump straight
    # there by overwriting state.yml — simpler than driving a full loop.
    state_path = wf_dir / "state.yml"
    state = StateDocument.load(state_path)
    state.metadata = {"run_slug": "run1"}
    state.stage = "verify"  # last non-terminal in bug-rca-fix
    state.save(state_path)

    # The auditor verdict in audit.md is REQUEST_CHANGES — but for this
    # test we want to land on `done`. Override via --verdict approve.
    advance = runner.invoke(app, ["advance", "--verdict", "approve"])
    assert advance.exit_code == 0, advance.output
    assert "Workflow complete" in advance.output

    # Snapshot should now exist.
    history = list((tmp_path / ".relay" / "history").iterdir())
    assert len(history) == 1, f"Expected one history dir, found {[p.name for p in history]}"
    run_dir = history[0]
    assert (run_dir / "artifacts" / "plan_review.md").exists()
    assert (run_dir / "artifacts" / "audit.md").exists()

    # --- Distill lessons ---
    distill = runner.invoke(app, ["distill"])
    assert distill.exit_code == 0, distill.output
    lessons_json = tmp_path / ".relay" / "lessons.json"
    lessons_md = tmp_path / ".relay" / "LESSONS.md"
    assert lessons_json.exists()
    assert lessons_md.exists()

    # --- Run 2: compose the planner prompt and assert lessons appear ---
    # Reset the workflow to its initial stage so we're at a clean run 2.
    runner.invoke(app, ["reset", "--clean"])
    _write_artifact(
        artifacts / "context.md",
        "# Context\n\nNew bug in src/relay/state.py affects iteration_counts.\n",
    )

    # Load the planner role from the template (bug-rca-fix planner has
    # inject_lessons: true).
    planner_yml = wf_dir / "roles" / "planner.yml"
    planner_role = RoleSpec.model_validate(yaml.safe_load(planner_yml.read_text()))
    assert planner_role.inject_lessons is True

    workflow = WorkflowDefinition.model_validate(
        yaml.safe_load((wf_dir / "workflow.yml").read_text())
    )
    state = StateDocument.load(state_path)
    # Drive to the fix_plan stage so the planner is the active role.
    state.stage = "fix_plan"

    prompt = compose_prompt(
        workflow,
        state,
        planner_role,
        artifact_dir=artifacts,
        lessons_path=tmp_path / ".relay" / "lessons.json",
    )

    # The reviewer's claim from run 1 must surface in run 2's planner prompt.
    assert "Lessons from past runs" in prompt
    assert "state.py" in prompt or "iteration_counts" in prompt
    # The auditor's lesson is for the auditor role, NOT the planner — must
    # not leak across roles.
    assert "disabled tests/unit/test_state_document.py" not in prompt
