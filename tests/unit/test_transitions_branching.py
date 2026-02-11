"""Tests for branching transitions via StateMachine."""

import pytest

from relay.protocol.state import StateDocument, StateMachine
from relay.protocol.workflow import (
    RoleDefinition,
    StageDefinition,
    WorkflowDefinition,
)


def _build_branching_workflow(
    start_stage: str = "review",
) -> tuple[WorkflowDefinition, StateDocument]:
    """Build a workflow where 'review' is a branching stage.

    Returns the workflow and a state already positioned at *start_stage*.
    """
    workflow = WorkflowDefinition(
        name="branch-test",
        roles={
            "drafter": RoleDefinition(
                description="Writes drafts",
                writes=["draft.md"],
                rules="roles/drafter.yml",
            ),
            "reviewer": RoleDefinition(
                description="Reviews drafts",
                writes=["review.md"],
                rules="roles/reviewer.yml",
            ),
        },
        stages={
            "drafting": StageDefinition(agent="drafter", next="review"),
            "review": StageDefinition(
                agent="reviewer",
                next={"approve": "done", "reject": "drafting"},
            ),
            "done": StageDefinition(terminal=True),
        },
        initial_stage="drafting",
    )
    state = StateDocument.create_initial("drafting")
    if start_stage != "drafting":
        state.advance(start_stage, role="test")
    return workflow, state


class TestBranchingApprove:
    """'approve' verdict resolves to the approve target."""

    def test_approve(self):
        workflow, state = _build_branching_workflow("review")
        sm = StateMachine(workflow, state)
        assert sm.resolve_branching_transition("approve") == "done"


class TestBranchingReject:
    """'reject' verdict resolves to the reject target."""

    def test_reject(self):
        workflow, state = _build_branching_workflow("review")
        sm = StateMachine(workflow, state)
        assert sm.resolve_branching_transition("reject") == "drafting"


class TestBranchingUnknownVerdict:
    """An unrecognised verdict raises ValueError."""

    def test_unknown_verdict(self):
        workflow, state = _build_branching_workflow("review")
        sm = StateMachine(workflow, state)
        with pytest.raises(ValueError, match="doesn't match any branch"):
            sm.resolve_branching_transition("maybe")


class TestBranchingOnLinearRaises:
    """Calling resolve_branching_transition on a linear stage raises ValueError."""

    def test_raises_on_linear(self):
        workflow, state = _build_branching_workflow("drafting")
        sm = StateMachine(workflow, state)
        with pytest.raises(ValueError, match="linear transitions"):
            sm.resolve_branching_transition("approve")
