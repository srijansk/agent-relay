"""Tests for invalid WorkflowDefinition construction — all should raise ValidationError."""

import pytest
from pydantic import ValidationError

from relay.protocol.workflow import (
    RoleDefinition,
    StageDefinition,
    WorkflowDefinition,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _role(**overrides) -> RoleDefinition:
    defaults = {"description": "desc", "writes": ["scratch"], "rules": "rules.yml"}
    defaults.update(overrides)
    return RoleDefinition(**defaults)


def _base_kwargs(**overrides) -> dict:
    """Return a valid WorkflowDefinition kwargs dict, then apply overrides."""
    base = {
        "name": "test-wf",
        "roles": {"worker": _role()},
        "stages": {
            "start": StageDefinition(agent="worker", next="done"),
            "done": StageDefinition(terminal=True),
        },
        "initial_stage": "start",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Missing required fields
# ---------------------------------------------------------------------------

class TestMissingRequiredFields:

    def test_missing_name(self):
        kwargs = _base_kwargs()
        del kwargs["name"]
        with pytest.raises(ValidationError, match="name"):
            WorkflowDefinition(**kwargs)

    def test_missing_roles(self):
        kwargs = _base_kwargs()
        del kwargs["roles"]
        with pytest.raises(ValidationError, match="roles"):
            WorkflowDefinition(**kwargs)

    def test_missing_stages(self):
        kwargs = _base_kwargs()
        del kwargs["stages"]
        with pytest.raises(ValidationError, match="stages"):
            WorkflowDefinition(**kwargs)

    def test_missing_initial_stage(self):
        kwargs = _base_kwargs()
        del kwargs["initial_stage"]
        with pytest.raises(ValidationError, match="initial_stage"):
            WorkflowDefinition(**kwargs)


# ---------------------------------------------------------------------------
# Stage references unknown role
# ---------------------------------------------------------------------------

class TestStageReferencesUnknownRole:

    def test_agent_not_in_roles(self):
        with pytest.raises(ValidationError, match="unknown role 'ghost'"):
            WorkflowDefinition(
                name="bad-role-ref",
                roles={"worker": _role()},
                stages={
                    "start": StageDefinition(agent="ghost", next="done"),
                    "done": StageDefinition(terminal=True),
                },
                initial_stage="start",
            )

    def test_one_valid_one_invalid_role(self):
        with pytest.raises(ValidationError, match="unknown role 'missing'"):
            WorkflowDefinition(
                name="partial-bad",
                roles={"worker": _role()},
                stages={
                    "s1": StageDefinition(agent="worker", next="s2"),
                    "s2": StageDefinition(agent="missing", next="done"),
                    "done": StageDefinition(terminal=True),
                },
                initial_stage="s1",
            )


# ---------------------------------------------------------------------------
# Stage transitions to unknown stage
# ---------------------------------------------------------------------------

class TestStageTransitionsToUnknownStage:

    def test_string_next_unknown(self):
        with pytest.raises(ValidationError, match="unknown stage 'nowhere'"):
            WorkflowDefinition(
                name="bad-next",
                roles={"worker": _role()},
                stages={
                    "start": StageDefinition(agent="worker", next="nowhere"),
                    "done": StageDefinition(terminal=True),
                },
                initial_stage="start",
            )

    def test_dict_next_unknown_target(self):
        with pytest.raises(ValidationError, match="unknown stage 'void'"):
            WorkflowDefinition(
                name="bad-branch",
                roles={"worker": _role()},
                stages={
                    "start": StageDefinition(
                        agent="worker",
                        next={"ok": "done", "fail": "void"},
                    ),
                    "done": StageDefinition(terminal=True),
                },
                initial_stage="start",
            )


# ---------------------------------------------------------------------------
# initial_stage not in stages
# ---------------------------------------------------------------------------

class TestInitialStageNotInStages:

    def test_initial_stage_missing(self):
        with pytest.raises(ValidationError, match="initial_stage 'missing'"):
            WorkflowDefinition(
                name="bad-initial",
                roles={"worker": _role()},
                stages={
                    "start": StageDefinition(agent="worker", next="done"),
                    "done": StageDefinition(terminal=True),
                },
                initial_stage="missing",
            )


# ---------------------------------------------------------------------------
# Terminal stage with agent set (should fail)
# ---------------------------------------------------------------------------

class TestTerminalStageWithAgent:

    def test_terminal_with_agent(self):
        with pytest.raises(ValidationError, match="Terminal stages cannot have 'agent'"):
            StageDefinition(agent="worker", terminal=True)

    def test_terminal_with_next(self):
        with pytest.raises(ValidationError, match="Terminal stages cannot have.*'next'"):
            StageDefinition(next="somewhere", terminal=True)

    def test_terminal_with_agent_and_next(self):
        with pytest.raises(ValidationError, match="Terminal stages cannot have"):
            StageDefinition(agent="worker", next="somewhere", terminal=True)


# ---------------------------------------------------------------------------
# Non-terminal stage without agent (should fail)
# ---------------------------------------------------------------------------

class TestNonTerminalWithoutAgent:

    def test_no_agent_no_terminal(self):
        with pytest.raises(ValidationError, match="Non-terminal stages must have an 'agent'"):
            StageDefinition(next="somewhere", terminal=False)

    def test_explicit_none_agent(self):
        with pytest.raises(ValidationError, match="Non-terminal stages must have an 'agent'"):
            StageDefinition(agent=None, next="somewhere", terminal=False)


# ---------------------------------------------------------------------------
# Non-terminal stage without next (should fail)
# ---------------------------------------------------------------------------

class TestNonTerminalWithoutNext:

    def test_no_next(self):
        with pytest.raises(ValidationError, match="Non-terminal stages must have 'next'"):
            StageDefinition(agent="worker", terminal=False)

    def test_explicit_none_next(self):
        with pytest.raises(ValidationError, match="Non-terminal stages must have 'next'"):
            StageDefinition(agent="worker", next=None, terminal=False)


# ---------------------------------------------------------------------------
# Unreachable stages
# ---------------------------------------------------------------------------

class TestUnreachableStages:

    def test_island_stage_unreachable(self):
        """A stage exists but no other stage transitions to it."""
        with pytest.raises(ValidationError, match="Unreachable stages"):
            WorkflowDefinition(
                name="unreachable",
                roles={"a": _role(), "b": _role()},
                stages={
                    "start": StageDefinition(agent="a", next="done"),
                    "island": StageDefinition(agent="b", next="done"),
                    "done": StageDefinition(terminal=True),
                },
                initial_stage="start",
            )

    def test_disconnected_subgraph(self):
        """Two stages form a subgraph not connected to initial_stage."""
        with pytest.raises(ValidationError, match="Unreachable stages"):
            WorkflowDefinition(
                name="disconnected",
                roles={"x": _role(), "y": _role()},
                stages={
                    "start": StageDefinition(agent="x", next="done"),
                    "orphan1": StageDefinition(agent="y", next="orphan2"),
                    "orphan2": StageDefinition(agent="y", next="orphan1"),
                    "done": StageDefinition(terminal=True),
                },
                initial_stage="start",
            )

    def test_all_reachable_no_error(self):
        """Sanity: fully connected graph should not raise."""
        wf = WorkflowDefinition(
            name="all-reachable",
            roles={"r": _role()},
            stages={
                "a": StageDefinition(agent="r", next={"left": "b", "right": "c"}),
                "b": StageDefinition(agent="r", next="done"),
                "c": StageDefinition(agent="r", next="done"),
                "done": StageDefinition(terminal=True),
            },
            initial_stage="a",
        )
        assert len(wf.stages) == 4
