"""Tests for the Orchestrator — context log, parsing, enrichment, persistence."""

from pathlib import Path

import pytest
import yaml

from relay.orchestrator import (
    Orchestrator,
    OrchestratorNote,
    PostStepResult,
    PreStepResult,
)


class TestOrchestratorNote:
    def test_creation_with_defaults(self):
        note = OrchestratorNote(
            stage="plan_draft",
            role="planner",
            action="proceeded",
            summary="Created initial plan",
        )
        assert note.stage == "plan_draft"
        assert note.concerns == []
        assert note.timestamp  # auto-set

    def test_creation_with_concerns(self):
        note = OrchestratorNote(
            stage="plan_review",
            role="reviewer",
            action="corrected",
            summary="Found gaps in plan",
            concerns=["missing test plan", "no rollback strategy"],
        )
        assert len(note.concerns) == 2


class TestPreStepParsing:
    def test_parse_proceed_yes(self):
        orch = Orchestrator(intent="test intent")
        result = orch._parse_pre_step(
            "PROCEED: yes\nENRICHMENT: Focus on the database schema first.\nREASONING: This aligns with the intent."
        )
        assert result.proceed is True
        assert "database schema" in result.prompt_enrichment
        assert result.reasoning

    def test_parse_proceed_no(self):
        orch = Orchestrator(intent="test intent")
        result = orch._parse_pre_step(
            "PROCEED: no\nENRICHMENT: none\nREASONING: This step is not needed."
        )
        assert result.proceed is False
        assert result.prompt_enrichment == ""

    def test_parse_enrichment_none(self):
        orch = Orchestrator(intent="test intent")
        result = orch._parse_pre_step(
            "PROCEED: yes\nENRICHMENT: none\nREASONING: All good."
        )
        assert result.prompt_enrichment == ""

    def test_parse_malformed_response(self):
        orch = Orchestrator(intent="test intent")
        result = orch._parse_pre_step("Some random text with no structure")
        assert result.proceed is True  # default is safe (proceed)


class TestPostStepParsing:
    def test_parse_aligned(self):
        orch = Orchestrator(intent="test intent")
        result = orch._parse_post_step(
            "ALIGNED: yes\nRERUN: no\nCONCERNS: none\nSUMMARY: Plan covers all steps.\nREASONING: Output matches intent."
        )
        assert result.aligned is True
        assert result.should_rerun is False
        assert result.concerns == []
        assert "Plan covers" in result.summary

    def test_parse_misaligned_with_rerun(self):
        orch = Orchestrator(intent="test intent")
        result = orch._parse_post_step(
            "ALIGNED: no\nRERUN: yes\nCONCERNS: missing security considerations, no error handling\nSUMMARY: Plan is incomplete.\nREASONING: Key areas missing."
        )
        assert result.aligned is False
        assert result.should_rerun is True
        assert len(result.concerns) == 2
        assert "security" in result.concerns[0]

    def test_parse_concerns_single(self):
        orch = Orchestrator(intent="test intent")
        result = orch._parse_post_step(
            "ALIGNED: yes\nRERUN: no\nCONCERNS: watch for scope creep\nSUMMARY: OK.\nREASONING: Fine."
        )
        assert len(result.concerns) == 1

    def test_parse_malformed_response(self):
        orch = Orchestrator(intent="test intent")
        result = orch._parse_post_step("Just some unstructured text")
        assert result.aligned is True  # default is safe (aligned)
        assert result.should_rerun is False


class TestEnrichmentForPrompt:
    def test_enrichment_with_no_notes(self):
        orch = Orchestrator(intent="Build a REST API for user management")
        enrichment = orch.get_enrichment_for_prompt()
        assert "Intent" in enrichment
        assert "REST API" in enrichment
        assert "Prior Steps" not in enrichment

    def test_enrichment_with_notes(self):
        orch = Orchestrator(intent="Build a REST API")
        orch.notes = [
            OrchestratorNote(
                stage="plan_draft",
                role="planner",
                action="proceeded",
                summary="Created API design with 5 endpoints",
            ),
            OrchestratorNote(
                stage="plan_review",
                role="reviewer",
                action="corrected",
                summary="Found missing auth endpoint",
                concerns=["no authentication planned"],
            ),
        ]
        enrichment = orch.get_enrichment_for_prompt()
        assert "Prior Steps" in enrichment
        assert "planner" in enrichment
        assert "no authentication planned" in enrichment

    def test_enrichment_limits_to_last_5(self):
        orch = Orchestrator(intent="Test")
        orch.notes = [
            OrchestratorNote(stage=f"s{i}", role=f"r{i}", action="proceeded", summary=f"Step {i}")
            for i in range(10)
        ]
        enrichment = orch.get_enrichment_for_prompt()
        assert "Step 5" in enrichment
        assert "Step 9" in enrichment
        assert "Step 0" not in enrichment  # Older than last 5


class TestLogPersistence:
    def test_save_and_load(self, tmp_path):
        log_path = tmp_path / "orch_log.yml"

        orch = Orchestrator(intent="Test intent", log_path=log_path)
        orch.notes = [
            OrchestratorNote(
                stage="plan_draft",
                role="planner",
                action="proceeded",
                summary="Made a plan",
                concerns=["watch scope"],
            ),
        ]
        orch._save_log()

        assert log_path.exists()
        raw = yaml.safe_load(log_path.read_text())
        assert len(raw) == 1
        assert raw[0]["role"] == "planner"

        # Load into a new orchestrator
        orch2 = Orchestrator(intent="Test intent", log_path=log_path)
        assert len(orch2.notes) == 1
        assert orch2.notes[0].summary == "Made a plan"

    def test_load_nonexistent_log(self, tmp_path):
        log_path = tmp_path / "nonexistent.yml"
        orch = Orchestrator(intent="Test", log_path=log_path)
        assert len(orch.notes) == 0

    def test_save_without_log_path(self):
        orch = Orchestrator(intent="Test")
        orch.notes.append(
            OrchestratorNote(stage="s", role="r", action="proceeded", summary="test")
        )
        orch._save_log()  # Should not raise


class TestOrchestratorConfig:
    def test_default_provider(self):
        orch = Orchestrator(intent="test")
        assert orch.provider == "openai"
        assert orch.model == "gpt-4o"

    def test_custom_provider(self):
        orch = Orchestrator(intent="test", provider="anthropic", model="claude-sonnet-4-20250514")
        assert orch.provider == "anthropic"
        assert orch.model == "claude-sonnet-4-20250514"

    def test_invalid_provider_raises_on_call(self):
        orch = Orchestrator(intent="test", provider="invalid")
        import asyncio
        with pytest.raises(ValueError, match="must be 'openai' or 'anthropic'"):
            asyncio.run(orch._call_llm("system", "prompt"))
