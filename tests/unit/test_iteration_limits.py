"""Tests for StateMachine.check_iteration_limit() and match_limit_to_stage()."""

import pytest

from relay.protocol.state import StateDocument, StateMachine, match_limit_to_stage
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
        state.advance("drafting", role="drafter")
        state.advance("drafting", role="drafter")
        sm = StateMachine(workflow, state)
        reached, msg = sm.check_iteration_limit()
        assert reached is True
        assert msg is not None
        assert "drafting" in msg
        assert "2/2" in msg


class TestLimitMatchesOnlyRelevantStage:
    """Regression test for Bug #1: limits must only match their intended stage."""

    def test_plan_review_not_blocked_by_impl_limit(self):
        """plan_review at count=3 should NOT trigger max_impl_iterations=3."""
        workflow = WorkflowDefinition(
            name="multi-limit-test",
            roles={
                "planner": RoleDefinition(description="Plans", writes=["plan.md"], rules="r.yml"),
                "reviewer": RoleDefinition(description="Reviews", writes=["review.md"], rules="r.yml"),
                "implementer": RoleDefinition(description="Implements", writes=["log.md"], rules="r.yml"),
                "auditor": RoleDefinition(description="Audits", writes=["audit.md"], rules="r.yml"),
            },
            stages={
                "plan_draft": StageDefinition(agent="planner", next="plan_review"),
                "plan_review": StageDefinition(agent="reviewer", next={"approve": "plan_approved", "reject": "plan_changes"}),
                "plan_changes": StageDefinition(agent="planner", next="plan_review"),
                "plan_approved": StageDefinition(agent="implementer", next="audit_review"),
                "audit_review": StageDefinition(agent="auditor", next={"approve": "done", "reject": "impl_changes"}),
                "impl_changes": StageDefinition(agent="implementer", next="audit_review"),
                "done": StageDefinition(terminal=True),
            },
            initial_stage="plan_draft",
            limits={"max_plan_iterations": 5, "max_impl_iterations": 3},
        )
        state = StateDocument(
            stage="plan_review",
            iteration_counts={"plan_review": 3},
        )
        sm = StateMachine(workflow, state)
        reached, msg = sm.check_iteration_limit()
        # plan_review count=3 is under max_plan_iterations=5, should NOT be blocked
        assert reached is False, f"plan_review incorrectly blocked: {msg}"

    def test_impl_changes_blocked_by_impl_limit(self):
        """impl_changes at count=3 SHOULD trigger max_impl_iterations=3."""
        workflow = WorkflowDefinition(
            name="multi-limit-test",
            roles={
                "planner": RoleDefinition(description="Plans", writes=["plan.md"], rules="r.yml"),
                "implementer": RoleDefinition(description="Implements", writes=["log.md"], rules="r.yml"),
            },
            stages={
                "plan_draft": StageDefinition(agent="planner", next="impl_work"),
                "impl_work": StageDefinition(agent="implementer", next="done"),
                "done": StageDefinition(terminal=True),
            },
            initial_stage="plan_draft",
            limits={"max_plan_iterations": 5, "max_impl_iterations": 3},
        )
        state = StateDocument(
            stage="impl_work",
            iteration_counts={"impl_work": 3},
        )
        sm = StateMachine(workflow, state)
        reached, msg = sm.check_iteration_limit()
        assert reached is True, "impl_work at count=3 should be blocked by max_impl_iterations=3"


class TestMatchLimitToStage:
    """Unit tests for the match_limit_to_stage helper."""

    def test_exact_word_match(self):
        result = match_limit_to_stage({"max_plan_iterations": 5}, "plan_draft")
        assert result == ("max_plan_iterations", 5)

    def test_prefix_match_impl_to_implement(self):
        result = match_limit_to_stage({"max_impl_iterations": 3}, "implement_step")
        assert result is not None
        assert result[1] == 3

    def test_prefix_match_implement_to_impl(self):
        result = match_limit_to_stage({"max_implement_iterations": 3}, "impl_changes")
        assert result is not None
        assert result[1] == 3

    def test_no_match(self):
        result = match_limit_to_stage({"max_plan_iterations": 5}, "audit_review")
        assert result is None

    def test_best_match_wins(self):
        limits = {"max_plan_iterations": 5, "max_impl_iterations": 3}
        result = match_limit_to_stage(limits, "plan_review")
        assert result == ("max_plan_iterations", 5)
