"""Persisted history — snapshot terminal-stage runs into .relay/history/."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import yaml

from relay.history import (
    history_dir,
    is_history_enabled,
    list_runs,
    make_run_id,
    snapshot_run,
)
from relay.protocol.state import StateDocument
from relay.protocol.workflow import WorkflowDefinition


def _make_workflow(name: str = "default") -> WorkflowDefinition:
    return WorkflowDefinition.model_validate(
        {
            "name": name,
            "version": 1,
            "roles": {
                "worker": {
                    "description": "Does the thing",
                    "writes": ["output.md"],
                    "reads": ["context.md"],
                    "rules": "roles/worker.yml",
                }
            },
            "stages": {
                "working": {"agent": "worker", "next": "done"},
                "done": {"terminal": True},
            },
            "initial_stage": "working",
            "limits": {},
        }
    )


def _seed_workflow(workflow_dir: Path, workflow: WorkflowDefinition) -> None:
    workflow_dir.mkdir(parents=True)
    (workflow_dir / "workflow.yml").write_text(
        yaml.dump(workflow.model_dump(mode="json"), sort_keys=False)
    )
    (workflow_dir / "roles").mkdir()
    (workflow_dir / "roles" / "worker.yml").write_text(
        "name: worker\nsystem_prompt: do work\n"
    )
    artifacts = workflow_dir / "artifacts"
    artifacts.mkdir()
    (artifacts / "context.md").write_text("# Context\n\nDo the thing.\n")
    (artifacts / "output.md").write_text("# Output\n\nDone.\n")


def test_make_run_id_format() -> None:
    moment = datetime(2026, 4, 28, 9, 30, tzinfo=timezone.utc)
    rid = make_run_id("default", now=moment)
    assert rid == "20260428-0930-default"
    assert rid.startswith("20260428-0930-")


def test_make_run_id_slugifies_workflow_name() -> None:
    rid = make_run_id("Bug RCA — fix #1!", now=datetime(2026, 4, 28, tzinfo=timezone.utc))
    assert "bug-rca-fix-1" in rid
    assert " " not in rid


def test_is_history_enabled_default_true() -> None:
    assert is_history_enabled(None) is True
    assert is_history_enabled({}) is True
    assert is_history_enabled({"history": {"enabled": True}}) is True


def test_is_history_enabled_can_be_disabled() -> None:
    assert is_history_enabled({"history": {"enabled": False}}) is False


def test_snapshot_copies_artifacts_and_state(tmp_path: Path) -> None:
    relay_dir = tmp_path / ".relay"
    workflow_dir = relay_dir / "workflows" / "default"
    workflow = _make_workflow()
    _seed_workflow(workflow_dir, workflow)

    state = StateDocument(stage="done", iteration_counts={"working": 1})
    snapshot = snapshot_run(
        relay_dir=relay_dir,
        workflow_dir=workflow_dir,
        workflow=workflow,
        state=state,
        run_id="20260428-0930-default",
    )

    assert snapshot.exists()
    assert (snapshot / "workflow.yml").exists()
    assert (snapshot / "roles" / "worker.yml").exists()
    assert (snapshot / "artifacts" / "output.md").exists()
    assert (snapshot / "artifacts" / "context.md").exists()
    assert (snapshot / "state.yml").exists()
    assert (snapshot / "run.yml").exists()

    summary = yaml.safe_load((snapshot / "run.yml").read_text())
    assert summary["run_id"] == "20260428-0930-default"
    assert summary["final_stage"] == "done"
    assert summary["iteration_counts"] == {"working": 1}


def test_snapshot_handles_collision_by_suffixing(tmp_path: Path) -> None:
    relay_dir = tmp_path / ".relay"
    workflow_dir = relay_dir / "workflows" / "default"
    workflow = _make_workflow()
    _seed_workflow(workflow_dir, workflow)
    state = StateDocument(stage="done")

    first = snapshot_run(
        relay_dir=relay_dir,
        workflow_dir=workflow_dir,
        workflow=workflow,
        state=state,
        run_id="20260428-0930-default",
    )
    second = snapshot_run(
        relay_dir=relay_dir,
        workflow_dir=workflow_dir,
        workflow=workflow,
        state=state,
        run_id="20260428-0930-default",
    )
    assert first != second
    assert first.exists() and second.exists()
    assert second.name.endswith("-2") or second.name.endswith("-3")


def test_list_runs_returns_chronological(tmp_path: Path) -> None:
    relay_dir = tmp_path / ".relay"
    history_root = history_dir(relay_dir)
    history_root.mkdir(parents=True)

    # Out-of-order creation, but list_runs sorts lexicographically (which
    # equals chronological for the YYYYMMDD-HHMM prefix).
    (history_root / "20260428-1100-default").mkdir()
    (history_root / "20260428-0930-default").mkdir()
    (history_root / "not-a-run").mkdir()  # ignored
    (history_root / "scratch.txt").write_text("ignore me")

    runs = list_runs(relay_dir)
    assert [p.name for p in runs] == [
        "20260428-0930-default",
        "20260428-1100-default",
    ]
