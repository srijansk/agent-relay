"""Lessons injection in compose_prompt — opt-in per role, filtered by relevance."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from relay.lessons import Lesson, compile_lessons_json
from relay.prompt import compose_prompt
from relay.protocol.roles import RoleSpec
from relay.protocol.state import StateDocument
from relay.protocol.workflow import WorkflowDefinition

OBSERVED = datetime(2026, 4, 28, 9, 30, tzinfo=timezone.utc)


def _make_workflow() -> WorkflowDefinition:
    return WorkflowDefinition.model_validate(
        {
            "name": "default",
            "version": 1,
            "roles": {
                "planner": {
                    "description": "Plans the work",
                    "writes": ["plan.md"],
                    "reads": ["context.md", "src/relay/state.py"],
                    "rules": "roles/planner.yml",
                }
            },
            "stages": {
                "plan_draft": {"agent": "planner", "next": "done"},
                "done": {"terminal": True},
            },
            "initial_stage": "plan_draft",
            "limits": {},
        }
    )


def _write_lessons(lessons_path: Path, lessons: list[Lesson]) -> None:
    lessons_path.write_text(compile_lessons_json(lessons))


def test_inject_lessons_off_by_default(tmp_path: Path) -> None:
    workflow = _make_workflow()
    state = StateDocument(stage="plan_draft")
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    role = RoleSpec(name="planner", system_prompt="You are the planner.")
    # inject_lessons defaults to False; even with a lessons file, nothing.
    lessons_path = tmp_path / "lessons.json"
    _write_lessons(
        lessons_path,
        [
            Lesson(
                id="aaa",
                role="planner",
                claim="Watch state.py iteration counts",
                severity="warn",
                evidence_run_id="r1",
                evidence_excerpt="x",
                observed_at=OBSERVED,
                tags=["state.py"],
            )
        ],
    )

    prompt = compose_prompt(
        workflow, state, role, artifact_dir, lessons_path=lessons_path
    )
    assert "Lessons from past runs" not in prompt


def test_inject_lessons_on_includes_section(tmp_path: Path) -> None:
    workflow = _make_workflow()
    state = StateDocument(stage="plan_draft")
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    role = RoleSpec(
        name="planner", system_prompt="You are the planner.", inject_lessons=True
    )
    lessons_path = tmp_path / "lessons.json"
    _write_lessons(
        lessons_path,
        [
            Lesson(
                id="aaa",
                role="planner",
                claim="Watch state.py iteration counts",
                severity="warn",
                evidence_run_id="r1",
                evidence_excerpt="x",
                observed_at=OBSERVED,
                tags=["state.py"],
            ),
            Lesson(
                id="bbb",
                role="reviewer",
                claim="Reviewer-only lesson",
                severity="warn",
                evidence_run_id="r2",
                evidence_excerpt="y",
                observed_at=OBSERVED,
                tags=["state.py"],
            ),
        ],
    )

    prompt = compose_prompt(
        workflow, state, role, artifact_dir, lessons_path=lessons_path
    )
    assert "Lessons from past runs" in prompt
    assert "Watch state.py iteration counts" in prompt
    # Reviewer lesson must NOT leak into the planner's prompt.
    assert "Reviewer-only lesson" not in prompt


def test_inject_lessons_marks_highly_relevant_when_tags_overlap_reads(tmp_path: Path) -> None:
    workflow = _make_workflow()
    state = StateDocument(stage="plan_draft")
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    role = RoleSpec(
        name="planner", system_prompt="You are the planner.", inject_lessons=True
    )
    lessons_path = tmp_path / "lessons.json"
    _write_lessons(
        lessons_path,
        [
            Lesson(
                id="aaa",
                role="planner",
                claim="Watch state.py iteration counts",
                severity="warn",
                evidence_run_id="r1",
                evidence_excerpt="x",
                observed_at=OBSERVED,
                tags=["state.py"],
            ),
            Lesson(
                id="bbb",
                role="planner",
                claim="Generic naming concern",
                severity="info",
                evidence_run_id="r2",
                evidence_excerpt="y",
                observed_at=OBSERVED,
                tags=["unrelated.py"],
            ),
        ],
    )

    prompt = compose_prompt(
        workflow, state, role, artifact_dir, lessons_path=lessons_path
    )
    assert "Highly relevant" in prompt
    # The state.py lesson must appear under "Highly relevant".
    relevant_section = prompt.split("Highly relevant")[1]
    assert "Watch state.py iteration counts" in relevant_section


def test_inject_lessons_handles_missing_file(tmp_path: Path) -> None:
    workflow = _make_workflow()
    state = StateDocument(stage="plan_draft")
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    role = RoleSpec(
        name="planner", system_prompt="You are the planner.", inject_lessons=True
    )

    # Path that doesn't exist — should not crash and should not inject.
    prompt = compose_prompt(
        workflow,
        state,
        role,
        artifact_dir,
        lessons_path=tmp_path / "missing.json",
    )
    assert "Lessons from past runs" not in prompt
