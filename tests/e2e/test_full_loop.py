"""End-to-end test: full manual workflow round-trip.

init → next → manually write output with verdict → advance → status → ... → done
"""

import yaml
from typer.testing import CliRunner

from relay.cli import app

runner = CliRunner()


def test_full_manual_loop(tmp_path, monkeypatch):
    """Test a complete 2-stage workflow: worker produces output → done."""
    monkeypatch.chdir(tmp_path)

    # 1. Init
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0, result.output
    assert "initialized" in result.output.lower()

    # 2. Status — should show "working" stage
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0, result.output
    assert "working" in result.output.lower()

    # 3. Next — should print a prompt
    result = runner.invoke(app, ["next"])
    assert result.exit_code == 0, result.output
    assert "worker" in result.output.lower()

    # 4. Simulate agent output — write to the artifact file
    artifact_dir = tmp_path / ".relay" / "workflows" / "default" / "artifacts"
    output_file = artifact_dir / "output.md"
    output_file.write_text("# Output\n\nThe task is complete.\n")

    # 5. Advance — linear transition, should move to "done"
    result = runner.invoke(app, ["advance"])
    assert result.exit_code == 0, result.output
    assert "done" in result.output.lower()

    # 6. Status — should show "done" / terminal
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0, result.output
    assert "done" in result.output.lower()

    # 7. Next — should say workflow is complete
    result = runner.invoke(app, ["next"])
    assert result.exit_code == 0, result.output
    assert "complete" in result.output.lower()


def test_branching_workflow_loop(tmp_path, monkeypatch):
    """Test a branching workflow: reviewer approves or rejects."""
    monkeypatch.chdir(tmp_path)

    # Init with template
    result = runner.invoke(app, ["init", "--template", "plan-review-implement-audit"])
    assert result.exit_code == 0, result.output

    # Status — should show plan_draft
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0, result.output
    assert "plan_draft" in result.output

    # Simulate planner output
    artifact_dir = tmp_path / ".relay" / "workflows" / "default" / "artifacts"
    (artifact_dir / "plan.md").write_text("# Plan\n\n## Step 1\nDo the thing.\n")

    # Advance (plan_draft is linear → plan_review)
    result = runner.invoke(app, ["advance"])
    assert result.exit_code == 0, result.output
    assert "plan_review" in result.output

    # Simulate reviewer output with APPROVE verdict
    (artifact_dir / "plan_review.md").write_text(
        "# Plan Review\n\n## Verdict: APPROVE\n\n## Summary\nLooks good.\n"
    )

    # Advance — should extract verdict and go to plan_approved
    result = runner.invoke(app, ["advance"])
    assert result.exit_code == 0, result.output
    assert "plan_approved" in result.output

    # Verify state
    state_path = tmp_path / ".relay" / "workflows" / "default" / "state.yml"
    state = yaml.safe_load(state_path.read_text())
    assert state["stage"] == "plan_approved"


def test_branching_workflow_reject(tmp_path, monkeypatch):
    """Test that a REQUEST_CHANGES verdict loops back to the planner."""
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["init", "--template", "plan-review-implement-audit"])
    assert result.exit_code == 0

    artifact_dir = tmp_path / ".relay" / "workflows" / "default" / "artifacts"

    # Plan draft → plan review (linear)
    (artifact_dir / "plan.md").write_text("# Plan\n")
    result = runner.invoke(app, ["advance"])
    assert "plan_review" in result.output

    # Reviewer rejects
    (artifact_dir / "plan_review.md").write_text(
        "# Plan Review\n\n## Verdict: REQUEST_CHANGES\n\n## Required Changes\n1. Fix step 2.\n"
    )
    result = runner.invoke(app, ["advance"])
    assert result.exit_code == 0
    assert "plan_changes" in result.output

    # Should be back at planner
    result = runner.invoke(app, ["status"])
    assert "plan_changes" in result.output
    assert "planner" in result.output.lower()


def test_export_to_cursor(tmp_path, monkeypatch):
    """Test exporting a workflow to Cursor format."""
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["init", "--template", "plan-review-implement-audit"])
    assert result.exit_code == 0

    result = runner.invoke(app, ["export", "cursor", "--output", str(tmp_path / "exported")])
    assert result.exit_code == 0, result.output
    assert "exported" in result.output.lower()

    # Verify files were created
    exported = tmp_path / "exported" / ".cursor"
    assert (exported / "rules" / "planner.mdc").exists()
    assert (exported / "rules" / "reviewer.mdc").exists()
    assert (exported / "rules" / "implementer.mdc").exists()
    assert (exported / "rules" / "auditor.mdc").exists()
    assert (exported / "prompts" / "planner.txt").exists()
    assert (exported / "workflow" / "state.yml").exists()
