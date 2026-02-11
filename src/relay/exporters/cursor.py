"""Export workflow to Cursor-native format (.mdc rules + prompts)."""

from __future__ import annotations

from pathlib import Path

import yaml

from relay.protocol.roles import RoleSpec
from relay.protocol.workflow import WorkflowDefinition


def export_to_cursor(workflow_dir: Path, output_dir: Path) -> list[Path]:
    """Export a workflow to Cursor-native format.

    Creates:
    - .cursor/rules/{role_name}.mdc for each role
    - .cursor/prompts/{role_name}.txt for each role
    - .cursor/workflow/state.yml (initial state)
    - .cursor/workflow/00_context.md (if context.md exists in artifacts)

    Returns list of created files.
    """
    wf_path = workflow_dir / "workflow.yml"
    raw = yaml.safe_load(wf_path.read_text())
    workflow = WorkflowDefinition.model_validate(raw)

    created_files: list[Path] = []

    rules_dir = output_dir / ".cursor" / "rules"
    prompts_dir = output_dir / ".cursor" / "prompts"
    workflow_out = output_dir / ".cursor" / "workflow"

    rules_dir.mkdir(parents=True, exist_ok=True)
    prompts_dir.mkdir(parents=True, exist_ok=True)
    workflow_out.mkdir(parents=True, exist_ok=True)

    for role_name, role_def in workflow.roles.items():
        # Load role spec
        role_path = workflow_dir / role_def.rules
        if not role_path.exists():
            continue
        role_raw = yaml.safe_load(role_path.read_text())
        role = RoleSpec.model_validate(role_raw)

        # Generate .mdc rule file
        mdc_content = _generate_mdc(role_name, role, role_def, workflow)
        mdc_path = rules_dir / f"{role_name}.mdc"
        mdc_path.write_text(mdc_content)
        created_files.append(mdc_path)

        # Generate prompt file
        prompt_content = _generate_prompt(role_name, role_def)
        prompt_path = prompts_dir / f"{role_name}.txt"
        prompt_path.write_text(prompt_content)
        created_files.append(prompt_path)

    # Generate state.yml
    state_content = _generate_state_yml(workflow)
    state_path = workflow_out / "state.yml"
    state_path.write_text(state_content)
    created_files.append(state_path)

    # Copy context.md if it exists
    context_src = workflow_dir / "artifacts" / "context.md"
    if context_src.exists():
        context_dst = workflow_out / "00_context.md"
        context_dst.write_text(context_src.read_text())
        created_files.append(context_dst)

    return created_files


def _generate_mdc(
    role_name: str,
    role: RoleSpec,
    role_def,
    workflow: WorkflowDefinition,
) -> str:
    """Generate a Cursor .mdc rule file for a role."""
    lines = [
        "---",
        f'description: "{role_name.title()} Agent — {role_def.description}"',
        "alwaysApply: false",
        "---",
        "",
        f"# {role_name.title()} Agent Rules",
        "",
        role.system_prompt.strip(),
        "",
        "## File Ownership",
        "",
        f"**Reads**: {', '.join(role_def.reads) if role_def.reads else 'none'}",
        f"**Writes**: {', '.join(role_def.writes)}",
        "",
    ]

    if role.output_format:
        lines.extend([
            "## Output Format",
            "",
            role.output_format.strip(),
            "",
        ])

    if role.verdict_field:
        lines.extend([
            "## Verdict",
            "",
            f"Your output MUST include: `## {role.verdict_field}: {role.approve_value}` or `## {role.verdict_field}: {role.reject_value}`",
            "",
        ])

    return "\n".join(lines)


def _generate_prompt(role_name: str, role_def) -> str:
    """Generate a copy-paste prompt for a role."""
    reads_str = ", ".join(f".cursor/workflow/{f}" for f in role_def.reads) if role_def.reads else ""
    writes_str = ", ".join(f".cursor/workflow/{f}" for f in role_def.writes)

    parts = [
        f"Act as the {role_name.title()} Agent. Follow the rules defined in @.cursor/rules/{role_name}.mdc exactly.",
        "",
        f"Start by reading .cursor/workflow/state.yml to check the current stage.",
    ]

    if reads_str:
        parts.append(f"Then read: {reads_str}.")

    parts.append(f"Write your output to: {writes_str}. Update state.yml when done.")

    return "\n".join(parts)


def _generate_state_yml(workflow: WorkflowDefinition) -> str:
    """Generate an initial state.yml for Cursor workflow."""
    lines = [
        "# Multi-Agent Workflow State Machine",
        f"# Generated from: {workflow.name}",
        "",
        f"stage: {workflow.initial_stage}",
        "plan_version: 0",
        "approved_plan_version: null",
        "last_updated_by: null",
        "last_updated_at: null",
        "plan_iteration_count: 0",
        "impl_iteration_count: 0",
    ]

    for key, val in workflow.limits.items():
        lines.append(f"{key}: {val}")

    return "\n".join(lines)
