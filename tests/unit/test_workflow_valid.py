"""Tests for valid WorkflowDefinition construction."""

import pytest

from relay.protocol.workflow import (
    RoleDefinition,
    StageDefinition,
    WorkflowDefinition,
)


# ---------------------------------------------------------------------------
# Helpers — reusable role / stage factories
# ---------------------------------------------------------------------------

def _role(description: str = "desc", writes: list[str] | None = None, rules: str = "rules.yml") -> dict:
    return {
        "description": description,
        "writes": writes or ["scratch"],
        "rules": rules,
    }


def _stage(agent: str | None = None, next_: str | dict | None = None, terminal: bool = False) -> dict:
    d: dict = {"terminal": terminal}
    if agent is not None:
        d["agent"] = agent
    if next_ is not None:
        d["next"] = next_
    return d


# ---------------------------------------------------------------------------
# Valid workflow tests
# ---------------------------------------------------------------------------

class TestMinimalValidWorkflow:
    """Minimal 2-stage workflow: start -> done."""

    def test_minimal_two_stage_workflow(self):
        wf = WorkflowDefinition(
            name="minimal",
            roles={"worker": RoleDefinition(**_role())},
            stages={
                "start": StageDefinition(agent="worker", next="done"),
                "done": StageDefinition(terminal=True),
            },
            initial_stage="start",
        )
        assert wf.name == "minimal"
        assert wf.version == 1
        assert wf.initial_stage == "start"
        assert wf.stages["done"].terminal is True
        assert wf.stages["start"].agent == "worker"


class TestFullFourAgentWorkflow:
    """Full pipeline: planner -> reviewer -> implementer -> auditor with branching."""

    def test_four_agent_branching_workflow(self):
        roles = {
            "planner": RoleDefinition(**_role("Plans work", ["plan"])),
            "reviewer": RoleDefinition(**_role("Reviews plan", ["review"], "reviewer.yml")),
            "implementer": RoleDefinition(**_role("Writes code", ["code"], "implementer.yml")),
            "auditor": RoleDefinition(**_role("Audits result", ["audit"], "auditor.yml")),
        }
        stages = {
            "plan": StageDefinition(agent="planner", next="review"),
            "review": StageDefinition(
                agent="reviewer",
                next={"approved": "implement", "rejected": "plan"},
            ),
            "implement": StageDefinition(agent="implementer", next="audit"),
            "audit": StageDefinition(
                agent="auditor",
                next={"pass": "done", "fail": "implement"},
            ),
            "done": StageDefinition(terminal=True),
        }
        wf = WorkflowDefinition(
            name="full-pipeline",
            version=2,
            roles=roles,
            stages=stages,
            initial_stage="plan",
        )
        assert wf.version == 2
        assert set(wf.roles.keys()) == {"planner", "reviewer", "implementer", "auditor"}
        assert len(wf.stages) == 5
        assert wf.stages["review"].next == {"approved": "implement", "rejected": "plan"}


class TestWorkflowWithLimits:
    """Workflow that sets execution limits."""

    def test_limits_are_stored(self):
        wf = WorkflowDefinition(
            name="with-limits",
            roles={"worker": RoleDefinition(**_role())},
            stages={
                "start": StageDefinition(agent="worker", next="done"),
                "done": StageDefinition(terminal=True),
            },
            initial_stage="start",
            limits={"max_iterations": 10, "timeout_seconds": 300},
        )
        assert wf.limits == {"max_iterations": 10, "timeout_seconds": 300}

    def test_default_limits_empty(self):
        wf = WorkflowDefinition(
            name="no-limits",
            roles={"worker": RoleDefinition(**_role())},
            stages={
                "start": StageDefinition(agent="worker", next="done"),
                "done": StageDefinition(terminal=True),
            },
            initial_stage="start",
        )
        assert wf.limits == {}


class TestTerminalStageNoAgentNoNext:
    """Terminal stage should have no agent and no next."""

    def test_terminal_stage_fields(self):
        stage = StageDefinition(terminal=True)
        assert stage.terminal is True
        assert stage.agent is None
        assert stage.next is None

    def test_terminal_stage_in_workflow(self):
        wf = WorkflowDefinition(
            name="terminal-test",
            roles={"worker": RoleDefinition(**_role())},
            stages={
                "start": StageDefinition(agent="worker", next="end"),
                "end": StageDefinition(terminal=True),
            },
            initial_stage="start",
        )
        end = wf.stages["end"]
        assert end.terminal is True
        assert end.agent is None
        assert end.next is None


class TestLinearTransitions:
    """next is a plain string — linear chain of stages."""

    def test_three_stage_linear_chain(self):
        roles = {
            "a": RoleDefinition(**_role()),
            "b": RoleDefinition(**_role()),
        }
        wf = WorkflowDefinition(
            name="linear",
            roles=roles,
            stages={
                "step1": StageDefinition(agent="a", next="step2"),
                "step2": StageDefinition(agent="b", next="finish"),
                "finish": StageDefinition(terminal=True),
            },
            initial_stage="step1",
        )
        assert wf.stages["step1"].next == "step2"
        assert wf.stages["step2"].next == "finish"
        assert isinstance(wf.stages["step1"].next, str)


class TestBranchingTransitions:
    """next is a dict — stage can branch to different targets."""

    def test_dict_next_with_multiple_branches(self):
        roles = {
            "decider": RoleDefinition(**_role()),
            "handler": RoleDefinition(**_role()),
        }
        wf = WorkflowDefinition(
            name="branching",
            roles=roles,
            stages={
                "decide": StageDefinition(
                    agent="decider",
                    next={"yes": "handle", "no": "done"},
                ),
                "handle": StageDefinition(agent="handler", next="done"),
                "done": StageDefinition(terminal=True),
            },
            initial_stage="decide",
        )
        assert isinstance(wf.stages["decide"].next, dict)
        assert wf.stages["decide"].next == {"yes": "handle", "no": "done"}

    def test_single_entry_dict_next(self):
        wf = WorkflowDefinition(
            name="single-branch",
            roles={"r": RoleDefinition(**_role())},
            stages={
                "s1": StageDefinition(agent="r", next={"ok": "end"}),
                "end": StageDefinition(terminal=True),
            },
            initial_stage="s1",
        )
        assert wf.stages["s1"].next == {"ok": "end"}


class TestRoleDefinitionFields:
    """Verify RoleDefinition stores all fields correctly."""

    def test_role_with_reads(self):
        role = RoleDefinition(
            description="Reader role",
            writes=["output"],
            reads=["input", "config"],
            rules="reader.yml",
        )
        assert role.description == "Reader role"
        assert role.writes == ["output"]
        assert role.reads == ["input", "config"]
        assert role.rules == "reader.yml"

    def test_role_reads_defaults_empty(self):
        role = RoleDefinition(description="Simple", writes=["w"], rules="r.yml")
        assert role.reads == []
