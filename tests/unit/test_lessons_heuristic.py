"""Heuristic lesson extraction — deterministic, no LLM."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from relay.lessons import (
    Lesson,
    compile_lessons_json,
    compile_lessons_md,
    extract_lessons_from_history,
    filter_lessons_for_role,
    parse_artifact_for_lessons,
    render_lessons_section,
)

OBSERVED = datetime(2026, 4, 28, 9, 30, tzinfo=timezone.utc)


def test_required_changes_yield_warn_lessons_for_planner() -> None:
    """Reviewer's Required Changes are lessons FOR the planner (audience)."""
    review = """
## Verdict: REQUEST_CHANGES

## Required Changes

- **Correctness** Step 3 doesn't specify which table to write to in src/db.py
  - Why it matters: ambiguous about state.py schema mutation
  - Suggested fix: name the table

- Step 5 forgets the rollback for migrations.py.
"""
    lessons = parse_artifact_for_lessons(
        review,
        artifact_filename="plan_review.md",
        fallback_role="planner",
        run_id="20260428-0930-default",
        observed_at=OBSERVED,
    )
    assert len(lessons) == 2
    severities = {lesson.severity for lesson in lessons}
    assert severities == {"warn"}
    roles = {lesson.role for lesson in lessons}
    # Audience-not-writer: the planner is the role learning from the reviewer's
    # rejections, so the lesson role is "planner".
    assert roles == {"planner"}
    tags = {tag for lesson in lessons for tag in lesson.tags}
    assert "src/db.py" in tags
    assert any(tag.endswith(".py") for tag in tags)


def test_catches_under_audit_yield_error_lessons_for_implementer() -> None:
    """Auditor's Catches are lessons FOR the implementer (audience)."""
    audit = """
## Verdict: REQUEST_CHANGES

## Catches

- Implementer skipped the rollback test entirely.
- The new index in state.py is missing a guard against negative iteration_counts.
"""
    lessons = parse_artifact_for_lessons(
        audit,
        artifact_filename="audit.md",
        fallback_role="implementer",
        run_id="20260428-0945-default",
        observed_at=OBSERVED,
    )
    assert len(lessons) == 2
    assert all(lesson.severity == "error" for lesson in lessons)
    # Auditor catches → audience: implementer
    assert all(lesson.role == "implementer" for lesson in lessons)


def test_must_fix_under_audit_yield_error_lessons_for_implementer() -> None:
    """Auditor's MUST_FIX section (pria template format) is implementer-audience errors."""
    audit = """
## Verdict: REQUEST_CHANGES

## MUST_FIX (blocking)
- The build log does not cover step 4. The implementer skipped scheduler setup.
- Test suite was not run after the schema change in src/db.py.

## SHOULD_FIX (non-blocking)
- Inline comments could be clearer in worker.py.
"""
    lessons = parse_artifact_for_lessons(
        audit,
        artifact_filename="build_review.md",
        fallback_role="implementer",
        run_id="20260429-0525-pria",
        observed_at=OBSERVED,
    )
    severities = [lesson.severity for lesson in lessons]
    # MUST_FIX → error (2 bullets); SHOULD_FIX → info (1 bullet)
    assert severities.count("error") == 2
    assert severities.count("info") == 1
    assert all(lesson.role == "implementer" for lesson in lessons)


def test_suggestions_yield_info_lessons_for_planner() -> None:
    review = """
## Suggestions

- Consider adding a CHANGELOG entry.
- The naming convention could be tightened.
"""
    lessons = parse_artifact_for_lessons(
        review,
        artifact_filename="plan_review.md",
        fallback_role="planner",
        run_id="20260428-1000-default",
        observed_at=OBSERVED,
    )
    assert len(lessons) == 2
    assert all(lesson.severity == "info" for lesson in lessons)
    assert all(lesson.role == "planner" for lesson in lessons)


def test_extraction_is_deterministic_and_idempotent() -> None:
    """Same input must produce same lesson IDs across runs (stable hash)."""
    review = """
## Required Changes
- Step 3 doesn't specify the migration order.
"""
    a = parse_artifact_for_lessons(
        review,
        artifact_filename="plan_review.md",
        fallback_role="reviewer",
        run_id="20260428-0930-default",
        observed_at=OBSERVED,
    )
    b = parse_artifact_for_lessons(
        review,
        artifact_filename="plan_review.md",
        fallback_role="reviewer",
        run_id="20260428-0930-default",
        observed_at=OBSERVED,
    )
    assert [lesson.id for lesson in a] == [lesson.id for lesson in b]


def test_empty_input_yields_empty_lessons() -> None:
    assert parse_artifact_for_lessons(
        "",
        artifact_filename="plan_review.md",
        fallback_role="reviewer",
        run_id="r",
        observed_at=OBSERVED,
    ) == []
    assert parse_artifact_for_lessons(
        "## Verdict: APPROVE\n\nLooks good.\n",
        artifact_filename="plan_review.md",
        fallback_role="reviewer",
        run_id="r",
        observed_at=OBSERVED,
    ) == []


def test_extract_lessons_from_history_walks_runs(tmp_path: Path) -> None:
    history = tmp_path / "history"
    run1 = history / "20260428-0930-default" / "artifacts"
    run2 = history / "20260428-1100-default" / "artifacts"
    run1.mkdir(parents=True)
    run2.mkdir(parents=True)

    (run1 / "plan_review.md").write_text(
        "## Required Changes\n- Step 3 misses migrations.py.\n"
    )
    (run2 / "audit.md").write_text(
        "## Catches\n- Skipped the rollback test in tests/integration/test_run.py.\n"
    )

    lessons = extract_lessons_from_history(history)
    assert len(lessons) == 2
    # Should be sorted by run id, so run1's lesson comes first.
    assert lessons[0].evidence_run_id.startswith("20260428-0930")
    # plan_review.md → audience: planner; audit.md → audience: implementer
    assert lessons[0].role == "planner"
    assert lessons[1].role == "implementer"


def test_compile_lessons_json_is_valid_and_sorted() -> None:
    lessons = [
        Lesson(
            id="aaa",
            role="auditor",
            claim="Skipped rollback test",
            severity="error",
            evidence_run_id="20260428-1100-default",
            evidence_excerpt="raw",
            observed_at=OBSERVED,
            tags=["tests/integration/test_run.py"],
        ),
        Lesson(
            id="bbb",
            role="reviewer",
            claim="Step 3 misses migrations.py",
            severity="warn",
            evidence_run_id="20260428-0930-default",
            evidence_excerpt="raw",
            observed_at=OBSERVED,
            tags=["migrations.py"],
        ),
    ]
    rendered = compile_lessons_json(lessons)
    payload = json.loads(rendered)
    assert payload["version"] == 1
    assert payload["lesson_count"] == 2
    assert {lesson["id"] for lesson in payload["lessons"]} == {"aaa", "bbb"}


def test_compile_lessons_md_groups_by_role() -> None:
    lessons = [
        Lesson(
            id="aaa",
            role="auditor",
            claim="Skipped rollback test",
            severity="error",
            evidence_run_id="20260428-1100-default",
            evidence_excerpt="raw",
            observed_at=OBSERVED,
            tags=["tests/integration/test_run.py"],
        ),
        Lesson(
            id="bbb",
            role="reviewer",
            claim="Step 3 misses migrations.py",
            severity="warn",
            evidence_run_id="20260428-0930-default",
            evidence_excerpt="raw",
            observed_at=OBSERVED,
            tags=["migrations.py"],
        ),
    ]
    md = compile_lessons_md(lessons)
    assert "## Auditor" in md
    assert "## Reviewer" in md
    assert "[error]" in md
    assert "[warn]" in md


def test_compile_lessons_md_handles_empty() -> None:
    md = compile_lessons_md([])
    assert "No lessons yet" in md


def test_filter_lessons_for_role_prioritises_tag_overlap() -> None:
    lessons = [
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
        Lesson(
            id="ccc",
            role="reviewer",
            claim="Reviewer-only lesson",
            severity="warn",
            evidence_run_id="r3",
            evidence_excerpt="z",
            observed_at=OBSERVED,
            tags=["state.py"],
        ),
    ]
    highly, other = filter_lessons_for_role(
        lessons,
        role="planner",
        reads=["src/relay/state.py", "context.md"],
        max_n=10,
    )
    assert [lesson.id for lesson in highly] == ["aaa"]
    assert [lesson.id for lesson in other] == ["bbb"]


def test_filter_lessons_for_role_caps_at_max_n() -> None:
    lessons = [
        Lesson(
            id=f"l{i}",
            role="planner",
            claim=f"Lesson {i}",
            severity="warn",
            evidence_run_id=f"r{i}",
            evidence_excerpt="x",
            observed_at=OBSERVED,
            tags=[],
        )
        for i in range(20)
    ]
    highly, other = filter_lessons_for_role(
        lessons, role="planner", reads=[], max_n=5
    )
    assert len(highly) + len(other) <= 5


def test_render_lessons_section_returns_empty_when_no_lessons() -> None:
    assert render_lessons_section([], []) == ""


def test_render_lessons_section_includes_both_buckets() -> None:
    highly = [
        Lesson(
            id="aaa",
            role="planner",
            claim="Watch state.py",
            severity="warn",
            evidence_run_id="r1",
            evidence_excerpt="x",
            observed_at=OBSERVED,
            tags=["state.py"],
        )
    ]
    other = [
        Lesson(
            id="bbb",
            role="planner",
            claim="Tighten naming",
            severity="info",
            evidence_run_id="r2",
            evidence_excerpt="y",
            observed_at=OBSERVED,
            tags=[],
        )
    ]
    rendered = render_lessons_section(highly, other)
    assert "Highly relevant" in rendered
    assert "Other lessons" in rendered
    assert "Watch state.py" in rendered
    assert "Tighten naming" in rendered
