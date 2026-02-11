"""Tests for valid RoleSpec construction."""

import pytest

from relay.protocol.roles import RoleSpec


class TestRoleValidFullFields:
    """Valid role with all fields populated."""

    def test_all_fields(self):
        role = RoleSpec(
            name="reviewer",
            system_prompt="You are a code reviewer.",
            output_format="markdown",
            verdict_field="Verdict",
            approve_value="APPROVE",
            reject_value="REQUEST_CHANGES",
        )
        assert role.name == "reviewer"
        assert role.system_prompt == "You are a code reviewer."
        assert role.output_format == "markdown"
        assert role.verdict_field == "Verdict"
        assert role.approve_value == "APPROVE"
        assert role.reject_value == "REQUEST_CHANGES"


class TestRoleValidMinimal:
    """Valid role with only required fields (no verdict config)."""

    def test_minimal_fields(self):
        role = RoleSpec(
            name="planner",
            system_prompt="You create plans.",
        )
        assert role.name == "planner"
        assert role.system_prompt == "You create plans."
        assert role.output_format is None
        assert role.verdict_field is None
        assert role.approve_value is None
        assert role.reject_value is None


class TestRoleValidVerdictConfig:
    """Valid role with all three verdict fields set together."""

    def test_verdict_config_all_set(self):
        role = RoleSpec(
            name="approver",
            system_prompt="You approve or reject.",
            verdict_field="Decision",
            approve_value="LGTM",
            reject_value="NOPE",
        )
        assert role.verdict_field == "Decision"
        assert role.approve_value == "LGTM"
        assert role.reject_value == "NOPE"
