"""Workflow validation — relay validate command logic."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from relay.protocol.roles import RoleSpec
from relay.protocol.workflow import WorkflowDefinition


def validate_workflow(workflow_dir: Path) -> list[str]:
    """Validate a workflow directory.

    Returns a list of error messages. Empty list means valid.
    """
    errors: list[str] = []

    # Check workflow.yml exists
    workflow_path = workflow_dir / "workflow.yml"
    if not workflow_path.exists():
        errors.append(f"Missing workflow.yml in {workflow_dir}")
        return errors

    # Parse workflow.yml
    try:
        raw = yaml.safe_load(workflow_path.read_text())
        workflow = WorkflowDefinition.model_validate(raw)
    except yaml.YAMLError as e:
        errors.append(f"Invalid YAML in workflow.yml: {e}")
        return errors
    except ValidationError as e:
        for err in e.errors():
            loc = " -> ".join(str(x) for x in err["loc"]) if err["loc"] else "root"
            errors.append(f"workflow.yml [{loc}]: {err['msg']}")
        return errors

    # Validate each role file exists and parses
    for role_name, role_def in workflow.roles.items():
        role_path = workflow_dir / role_def.rules
        if not role_path.exists():
            errors.append(f"Role '{role_name}': rules file not found: {role_def.rules}")
            continue

        try:
            role_raw = yaml.safe_load(role_path.read_text())
            RoleSpec.model_validate(role_raw)
        except yaml.YAMLError as e:
            errors.append(f"Role '{role_name}': invalid YAML in {role_def.rules}: {e}")
        except ValidationError as e:
            for err in e.errors():
                loc = " -> ".join(str(x) for x in err["loc"]) if err["loc"] else "root"
                errors.append(f"Role '{role_name}' [{loc}]: {err['msg']}")

    return errors
