"""Integration tests for `relay distill`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from relay.cli import app

runner = CliRunner()


def _seed_history(relay_dir: Path) -> None:
    """Drop two synthetic runs into .relay/history/."""
    run1 = relay_dir / "history" / "20260428-0930-default" / "artifacts"
    run2 = relay_dir / "history" / "20260428-1100-default" / "artifacts"
    run1.mkdir(parents=True)
    run2.mkdir(parents=True)
    (run1 / "plan_review.md").write_text(
        "## Required Changes\n"
        "- Step 3 doesn't account for migrations.py rollback.\n"
    )
    (run2 / "audit.md").write_text(
        "## Catches\n"
        "- Implementer skipped the rollback test in tests/integration/test_run.py.\n"
    )


def test_distill_creates_lessons_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    init_result = runner.invoke(app, ["init"])
    assert init_result.exit_code == 0, init_result.output

    _seed_history(tmp_path / ".relay")

    result = runner.invoke(app, ["distill"])
    assert result.exit_code == 0, result.output
    assert "Distilled" in result.output

    lessons_md = tmp_path / ".relay" / "LESSONS.md"
    lessons_json = tmp_path / ".relay" / "lessons.json"
    assert lessons_md.exists()
    assert lessons_json.exists()
    payload = json.loads(lessons_json.read_text())
    assert payload["lesson_count"] == 2
    roles = {lesson["role"] for lesson in payload["lessons"]}
    # Audience-not-writer: plan_review.md → planner; audit.md → implementer.
    assert roles == {"planner", "implementer"}


def test_distill_with_no_history_emits_empty_artefacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["distill"])
    assert result.exit_code == 0, result.output

    lessons_json = tmp_path / ".relay" / "lessons.json"
    payload = json.loads(lessons_json.read_text())
    assert payload["lesson_count"] == 0


def test_distill_is_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    _seed_history(tmp_path / ".relay")

    runner.invoke(app, ["distill"])
    first = (tmp_path / ".relay" / "lessons.json").read_text()
    runner.invoke(app, ["distill"])
    second = (tmp_path / ".relay" / "lessons.json").read_text()

    # Compare lesson IDs — generated_at timestamp differs intentionally.
    first_ids = sorted(lesson["id"] for lesson in json.loads(first)["lessons"])
    second_ids = sorted(lesson["id"] for lesson in json.loads(second)["lessons"])
    assert first_ids == second_ids
