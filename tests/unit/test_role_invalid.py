"""Tests for invalid RoleSpec construction."""

import pytest
from pydantic import ValidationError

from relay.protocol.roles import RoleSpec


class TestRoleMissingSystemPrompt:
    """system_prompt is required — omitting it should fail."""

    def test_missing_system_prompt(self):
        with pytest.raises(ValidationError):
            RoleSpec(name="broken")


class TestRolePartialVerdictFieldAndApprove:
    """verdict_field set but approve_value missing — should fail."""

    def test_verdict_field_without_approve(self):
        with pytest.raises(ValidationError, match="all be set or all be unset"):
            RoleSpec(
                name="partial",
                system_prompt="Some prompt.",
                verdict_field="Verdict",
                reject_value="REJECT",
                # approve_value intentionally missing
            )


class TestRolePartialOnlyReject:
    """Only reject_value set — should fail."""

    def test_only_reject_value(self):
        with pytest.raises(ValidationError, match="all be set or all be unset"):
            RoleSpec(
                name="partial",
                system_prompt="Some prompt.",
                reject_value="REJECT",
                # verdict_field and approve_value missing
            )
