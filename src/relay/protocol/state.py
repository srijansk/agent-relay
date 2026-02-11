"""State machine engine — state document, transitions, verdict extraction."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from relay.protocol.roles import RoleSpec
from relay.protocol.workflow import StageDefinition, WorkflowDefinition


class StateDocument(BaseModel):
    """Current workflow state, persisted as state.yml."""
    stage: str
    iteration_counts: dict[str, int] = {}
    last_updated_by: str | None = None
    last_updated_at: datetime | None = None
    metadata: dict[str, Any] = {}

    def advance(self, new_stage: str, role: str) -> None:
        """Advance state to new_stage, increment iteration count, update metadata."""
        self.stage = new_stage
        self.iteration_counts[new_stage] = self.iteration_counts.get(new_stage, 0) + 1
        self.last_updated_by = role
        self.last_updated_at = datetime.now(tz=timezone.utc)

    def save(self, path: Path) -> None:
        """Persist state to a YAML file."""
        data = self.model_dump(mode="json")
        # Convert datetime to ISO string for YAML
        if data.get("last_updated_at"):
            data["last_updated_at"] = self.last_updated_at.isoformat()
        path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))

    @classmethod
    def load(cls, path: Path) -> StateDocument:
        """Load state from a YAML file."""
        if not path.exists():
            raise FileNotFoundError(
                f"State file not found: {path}\n"
                "Run 'relay init' to create a workflow, or 'relay reset' to restore state."
            )
        raw = yaml.safe_load(path.read_text())
        if not isinstance(raw, dict):
            raise ValueError(f"Malformed state file: {path}. Expected YAML mapping, got {type(raw).__name__}")
        return cls.model_validate(raw)

    @classmethod
    def create_initial(cls, initial_stage: str) -> StateDocument:
        """Create a fresh state document for a new workflow."""
        return cls(stage=initial_stage)


class StateMachine:
    """Drives workflow transitions based on state + workflow definition."""

    def __init__(self, workflow: WorkflowDefinition, state: StateDocument):
        self.workflow = workflow
        self.state = state

    @property
    def current_stage(self) -> StageDefinition:
        return self.workflow.stages[self.state.stage]

    @property
    def current_role_name(self) -> str | None:
        return self.current_stage.agent

    @property
    def is_terminal(self) -> bool:
        return self.current_stage.terminal

    @property
    def is_branching(self) -> bool:
        return isinstance(self.current_stage.next, dict)

    def get_iteration_count(self, stage_name: str) -> int:
        """Get how many times a stage has been entered."""
        return self.state.iteration_counts.get(stage_name, 0)

    def check_iteration_limit(self) -> tuple[bool, str | None]:
        """Check if any iteration limit has been reached.

        Returns (limit_reached, message).
        """
        stage_name = self.state.stage
        for limit_key, max_val in self.workflow.limits.items():
            # Match limit keys like "max_plan_iterations" to stage names containing "plan"
            # Or direct stage name match
            count = self.get_iteration_count(stage_name)
            if count >= max_val:
                return True, (
                    f"Iteration limit reached for '{stage_name}': "
                    f"{count}/{max_val} (limit: {limit_key})"
                )
        return False, None

    def resolve_linear_transition(self) -> str:
        """Resolve the next stage for a linear (non-branching) transition."""
        next_val = self.current_stage.next
        if isinstance(next_val, str):
            return next_val
        raise ValueError(
            f"Stage '{self.state.stage}' has branching transitions. "
            "Use resolve_branching_transition() instead."
        )

    def resolve_branching_transition(self, verdict: str) -> str:
        """Resolve the next stage based on a verdict value.

        Args:
            verdict: The extracted verdict (e.g., 'approve' or 'reject')

        Returns:
            The target stage name.

        Raises:
            ValueError: If the verdict doesn't match any branch.
        """
        next_map = self.current_stage.next
        if not isinstance(next_map, dict):
            raise ValueError(
                f"Stage '{self.state.stage}' has linear transitions. "
                "Use resolve_linear_transition() instead."
            )

        verdict_lower = verdict.strip().lower()
        if verdict_lower in next_map:
            return next_map[verdict_lower]

        available = ", ".join(sorted(next_map.keys()))
        raise ValueError(
            f"Verdict '{verdict}' doesn't match any branch. "
            f"Available branches: {available}"
        )

    def advance(self, target_stage: str, role: str) -> None:
        """Advance the state machine to a new stage."""
        if target_stage not in self.workflow.stages:
            raise ValueError(f"Unknown target stage: '{target_stage}'")
        self.state.advance(target_stage, role)


def extract_verdict(
    content: str,
    verdict_field: str,
    approve_value: str,
    reject_value: str,
) -> str | None:
    """Extract a verdict from markdown content.

    Searches for a heading line matching the verdict_field pattern and
    extracts the value. Returns 'approve' or 'reject' if matched,
    None if not found or ambiguous.

    Args:
        content: The markdown content to search.
        verdict_field: The field name to look for (e.g., "Verdict").
        approve_value: The value that means approval (e.g., "APPROVE").
        reject_value: The value that means rejection (e.g., "REQUEST_CHANGES").

    Returns:
        'approve', 'reject', or None if verdict couldn't be determined.
    """
    # Match patterns like: ## Verdict: APPROVE or # Verdict: REQUEST_CHANGES
    pattern = rf"^##?\s*{re.escape(verdict_field)}\s*[:：]\s*(.+)$"
    match = re.search(pattern, content, re.MULTILINE | re.IGNORECASE)

    if not match:
        return None

    raw_value = match.group(1).strip().upper()

    if approve_value.upper() in raw_value:
        return "approve"
    if reject_value.upper() in raw_value:
        return "reject"

    return None
