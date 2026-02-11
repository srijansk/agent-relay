"""Tests for linear (non-branching) transitions via StateMachine."""

import pytest

from relay.protocol.state import StateDocument, StateMachine
from relay.protocol.workflow import (
    RoleDefinition,
    StageDefinition,
    WorkflowDefinition,
)


def _build_linear_workflow() -> tuple[WorkflowDefinition, StateDocument]:
    """Build a minimal workflow: drafting -> review -> done."""
    workflow = WorkflowDefinition(
        name="linear-test",
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
            "review": StageDefinition(agent="reviewer", next="done"),
            "done": StageDefinition(terminal=True),
        },
        initial_stage="drafting",
    )
    state = StateDocument.create_initial("drafting")
    return workflow, state


def _build_branching_workflow() -> tuple[WorkflowDefinition, StateDocument]:
    """Build a workflow where 'review' is a branching stage."""
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
    return workflow, state


class TestLinearTransitionResolves:
    """resolve_linear_transition returns the correct next stage for a linear stage."""

    def test_resolves_next(self):
        workflow, state = _build_linear_workflow()
        sm = StateMachine(workflow, state)
        assert sm.resolve_linear_transition() == "review"


class TestLinearOnBranchingRaises:
    """Calling resolve_linear_transition on a branching stage raises ValueError."""

    def test_raises_on_branching(self):
        workflow, state = _build_branching_workflow()
        # Advance to the branching stage
        state.advance("review", role="drafter")
        sm = StateMachine(workflow, state)

        with pytest.raises(ValueError, match="branching transitions"):
            sm.resolve_linear_transition()
