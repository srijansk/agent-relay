"""Workflow and role definition models — the core protocol."""

from __future__ import annotations

from pydantic import BaseModel, model_validator


class StageDefinition(BaseModel):
    """A single stage in the workflow state machine."""
    agent: str | None = None
    next: str | dict[str, str] | None = None
    terminal: bool = False

    @model_validator(mode="after")
    def validate_stage(self):
        if self.terminal and (self.agent or self.next):
            raise ValueError("Terminal stages cannot have 'agent' or 'next'")
        if not self.terminal and not self.agent:
            raise ValueError("Non-terminal stages must have an 'agent'")
        if not self.terminal and self.next is None:
            raise ValueError("Non-terminal stages must have 'next'")
        return self


class RoleDefinition(BaseModel):
    """A role referenced by stages in the workflow."""
    description: str
    writes: list[str]
    reads: list[str] = []
    rules: str  # path to role YAML relative to workflow dir


class WorkflowDefinition(BaseModel):
    """Top-level workflow definition parsed from workflow.yml."""
    name: str
    version: int = 1
    roles: dict[str, RoleDefinition]
    stages: dict[str, StageDefinition]
    initial_stage: str
    limits: dict[str, int] = {}

    @model_validator(mode="after")
    def validate_references(self):
        # Every stage.agent must reference an existing role
        for stage_name, stage in self.stages.items():
            if stage.agent and stage.agent not in self.roles:
                available = ", ".join(sorted(self.roles.keys()))
                raise ValueError(
                    f"Stage '{stage_name}' references unknown role '{stage.agent}'. "
                    f"Available roles: {available}"
                )

        # initial_stage must exist
        if self.initial_stage not in self.stages:
            raise ValueError(
                f"initial_stage '{self.initial_stage}' not found in stages"
            )

        # Every next target must reference an existing stage
        for stage_name, stage in self.stages.items():
            targets = _get_next_targets(stage)
            for t in targets:
                if t not in self.stages:
                    raise ValueError(
                        f"Stage '{stage_name}' transitions to unknown stage '{t}'"
                    )

        # Detect unreachable stages
        reachable: set[str] = set()
        queue = [self.initial_stage]
        reachable.add(self.initial_stage)
        while queue:
            current = queue.pop(0)
            for t in _get_next_targets(self.stages[current]):
                if t not in reachable:
                    reachable.add(t)
                    queue.append(t)
        unreachable = set(self.stages.keys()) - reachable
        if unreachable:
            raise ValueError(f"Unreachable stages: {unreachable}")

        return self


def _get_next_targets(stage: StageDefinition) -> list[str]:
    """Extract all target stage names from a stage's next field."""
    if stage.next is None:
        return []
    if isinstance(stage.next, str):
        return [stage.next]
    return list(stage.next.values())
