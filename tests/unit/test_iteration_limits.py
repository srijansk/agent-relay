"""Tests for StateMachine.check_iteration_limit()."""

import pytest

from relay.protocol.state import StateDocument, StateMachine
from relay.protocol.workflow import (
    RoleDefinition,
    StageDefinition,
    WorkflowDefinition,
)


def _build_workflow_with_limits(
    limits: dict[str, int],
) -> tuple[WorkflowDefinition, StateDocument]:
    """Build a minimal workflow with configurable iteration limits."""
    workflow = WorkflowDefinition(
        name="limit-test",
        roles={
            "drafter": RoleDefinition(
                description="Writes drafts",
                writes=["draft.md"],
                rules="roles/drafter.yml",
            ),
        },
        stages={
            "drafting": StageDefinition(agent="drafter", next="done"),
            "done": StageDefinition(terminal=True),
        },
        initial_stage="drafting",
        limits=limits,
    )
    state = StateDocument.create_initial("drafting")
    return workflow, state


class TestNoLimitsConfigured:
    """When no limits are set, check_iteration_limit returns (False, None)."""

    def test_no_limits(self):
        workflow, state = _build_workflow_with_limits({})
        sm = StateMachine(workflow, state)
        reached, msg = sm.check_iteration_limit()
        assert reached is False
        assert msg is None


class TestUnderLimit:
    """When iteration count is below the limit, returns (False, None)."""

    def test_under_limit(self):
        workflow, state = _build_workflow_with_limits({"max_drafting": 3})
        # Enter drafting once (count becomes 1)
        state.advance("drafting", role="drafter")
        sm = StateMachine(workflow, state)
        reached, msg = sm.check_iteration_limit()
        assert reached is False
        assert msg is None


class TestAtLimit:
    """When iteration count reaches the limit, returns (True, message)."""

    def test_at_limit(self):
        workflow, state = _build_workflow_with_limits({"max_drafting": 2})
        # Enter drafting twice (count becomes 2, which equals the limit)
        state.advance("drafting", role="drafter")
        state.advance("drafting", role="drafter")
        sm = StateMachine(workflow, state)
        reached, msg = sm.check_iteration_limit()
        assert reached is True
        assert msg is not None
        assert "drafting" in msg
        assert "2/2" in msg
