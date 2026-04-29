"""LLM-backed lesson distillation — uses an injected mock so CI is deterministic."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from relay.lessons import (
    _bullets_to_llm_user_prompt,
    _parse_llm_response,
    distill_with_llm,
)


def _seed_history(history: Path) -> None:
    run1 = history / "20260428-0930-bug" / "artifacts"
    run2 = history / "20260428-1100-bug" / "artifacts"
    run1.mkdir(parents=True)
    run2.mkdir(parents=True)
    (run1 / "plan_review.md").write_text(
        "## Verdict: REQUEST_CHANGES\n\n"
        "## Required Changes\n"
        "- Step 3 doesn't include a failing test for the bug in src/state.py.\n"
        "- Rollback section just says 'revert the commit'.\n"
    )
    (run2 / "plan_review.md").write_text(
        "## Verdict: REQUEST_CHANGES\n\n"
        "## Required Changes\n"
        "- Plan does not start with a failing test for src/api.py.\n"
        "- Rollback does not name what to revert.\n"
    )


def _llm_returning(payload: list[dict]) -> callable:
    def _call(system_prompt: str, user_prompt: str) -> str:
        # The mock validates that we send sane prompts before returning.
        assert "second-person" in system_prompt or "forward-looking" in system_prompt
        assert "Audience role: planner" in user_prompt
        assert "src/state.py" in user_prompt or "src/api.py" in user_prompt
        return json.dumps(payload)

    return _call


def test_distill_with_llm_groups_recurring_bullets(tmp_path: Path) -> None:
    history = tmp_path / "history"
    _seed_history(history)

    canned = [
        {
            "claim": "Always start the plan with a failing test that proves the bug.",
            "severity": "warn",
            "source_runs": ["20260428-0930-bug", "20260428-1100-bug"],
            "tags": ["src/state.py", "src/api.py"],
        },
        {
            "claim": "Always name the exact change set the rollback section will revert.",
            "severity": "warn",
            "source_runs": ["20260428-0930-bug", "20260428-1100-bug"],
            "tags": [],
        },
    ]

    lessons = distill_with_llm(history, llm=_llm_returning(canned))
    assert len(lessons) == 2
    claims = {lesson.claim for lesson in lessons}
    assert any("failing test" in c for c in claims)
    assert any("rollback" in c.lower() for c in claims)
    assert all(lesson.source == "llm" for lesson in lessons)
    assert all(lesson.role == "planner" for lesson in lessons)
    # Tags from the LLM response are preserved.
    state_tagged = next(lesson for lesson in lessons if "failing test" in lesson.claim)
    assert "src/state.py" in state_tagged.tags


def test_distill_with_llm_falls_back_to_heuristic_per_role_on_failure(tmp_path: Path) -> None:
    """If the LLM call raises, that role's lessons fall back to heuristic — not crash."""
    history = tmp_path / "history"
    _seed_history(history)

    def _broken_llm(system_prompt: str, user_prompt: str) -> str:
        raise RuntimeError("simulated transport error")

    lessons = distill_with_llm(history, llm=_broken_llm)
    # We get the heuristic-extracted bullets back — 4 from two runs.
    assert len(lessons) == 4
    assert all(lesson.source == "heuristic" for lesson in lessons)


def test_distill_with_llm_skips_invalid_response(tmp_path: Path) -> None:
    history = tmp_path / "history"
    _seed_history(history)

    def _garbage_llm(system_prompt: str, user_prompt: str) -> str:
        return "I refuse to comply with this format."

    lessons = distill_with_llm(history, llm=_garbage_llm)
    # Falls back to heuristic for that role.
    assert all(lesson.source == "heuristic" for lesson in lessons)
    assert len(lessons) == 4


def test_distill_with_llm_handles_fenced_json(tmp_path: Path) -> None:
    """Models often wrap JSON in ```json fences. The parser must tolerate that."""
    history = tmp_path / "history"
    _seed_history(history)

    canned = [
        {
            "claim": "Always include a failing test.",
            "severity": "warn",
            "source_runs": ["20260428-0930-bug"],
            "tags": [],
        }
    ]

    def _fenced_llm(system_prompt: str, user_prompt: str) -> str:
        return "Here's the JSON:\n```json\n" + json.dumps(canned) + "\n```\nDone."

    lessons = distill_with_llm(history, llm=_fenced_llm)
    assert len(lessons) == 1
    assert lessons[0].source == "llm"


def test_parse_llm_response_extracts_array_from_prose() -> None:
    body = """Here are my lessons:

[{"claim": "do X", "severity": "warn", "source_runs": ["r1"], "tags": []}]

That's all."""
    parsed = _parse_llm_response(body)
    assert isinstance(parsed, list)
    assert parsed[0]["claim"] == "do X"


def test_parse_llm_response_raises_when_no_array() -> None:
    with pytest.raises(ValueError):
        _parse_llm_response("no JSON here at all")


def test_bullets_to_user_prompt_includes_run_provenance() -> None:
    from datetime import datetime, timezone

    from relay.lessons import Lesson

    bullets = [
        Lesson(
            id="aaa",
            role="planner",
            claim="Step 3 missing test",
            severity="warn",
            evidence_run_id="20260428-0930-bug",
            evidence_excerpt="Step 3 missing test",
            observed_at=datetime(2026, 4, 28, tzinfo=timezone.utc),
        ),
    ]
    prompt = _bullets_to_llm_user_prompt("planner", bullets)
    assert "Audience role: planner" in prompt
    assert "20260428-0930-bug" in prompt
