"""Prompt composition — assembles prompts from role + state + artifacts."""

from __future__ import annotations

from relay.protocol.artifacts import read_artifacts
from relay.protocol.roles import RoleSpec
from relay.protocol.state import StateDocument
from relay.protocol.workflow import WorkflowDefinition

from pathlib import Path


def compose_prompt(
    workflow: WorkflowDefinition,
    state: StateDocument,
    role: RoleSpec,
    artifact_dir: Path,
    max_artifact_chars: int = 50_000,
) -> str:
    """Compose a complete prompt for the current agent role.

    Combines the role's system prompt, current state context,
    input artifact contents, and output instructions.
    """
    role_def = workflow.roles.get(state.stage and workflow.stages[state.stage].agent or "")
    reads = role_def.reads if role_def else []
    writes = role_def.writes if role_def else []

    # Read input artifacts
    artifacts = read_artifacts(artifact_dir, reads, max_artifact_chars)

    parts: list[str] = []

    # Header
    parts.append(f"You are: {role.name}")
    if role_def:
        parts.append(f"Role: {role_def.description}")
    parts.append("")

    # System prompt
    parts.append(role.system_prompt.strip())
    parts.append("")

    # State context
    stage_name = state.stage
    iteration = state.iteration_counts.get(stage_name, 0)
    max_iter = _find_iteration_limit(workflow, stage_name)
    parts.append("## Current State")
    parts.append(f"- Stage: {stage_name}")
    if max_iter is not None:
        parts.append(f"- Iteration: {iteration} / {max_iter}")
    else:
        parts.append(f"- Iteration: {iteration}")
    parts.append("")

    # Input files
    if artifacts:
        parts.append("## Input Files")
        for filename, content in artifacts.items():
            parts.append(f"--- {filename} ---")
            parts.append(content)
            parts.append("---")
            parts.append("")

    # Output instructions
    if writes:
        non_glob_writes = [w for w in writes if "*" not in w]
        if non_glob_writes:
            parts.append("## Your Task")
            parts.append(f"Write your output to: {non_glob_writes[0]}")
            if len(non_glob_writes) > 1:
                parts.append(f"Additional output files: {', '.join(non_glob_writes[1:])}")

    # Output format
    if role.output_format:
        parts.append("")
        parts.append("Use this format:")
        parts.append(role.output_format.strip())

    # Verdict instruction
    if role.verdict_field:
        parts.append("")
        parts.append(
            f"IMPORTANT: Your output MUST include a line: "
            f"## {role.verdict_field}: {role.approve_value} or {role.reject_value}"
        )

    return "\n".join(parts)


def _find_iteration_limit(workflow: WorkflowDefinition, stage_name: str) -> int | None:
    """Find the iteration limit that applies to a given stage, if any."""
    for limit_key, max_val in workflow.limits.items():
        # Simple heuristic: if limit key contains any word from the stage name
        stage_words = set(stage_name.lower().replace("_", " ").split())
        limit_words = set(limit_key.lower().replace("_", " ").replace("max", "").replace("iterations", "").split())
        if stage_words & limit_words:
            return max_val
    return None
