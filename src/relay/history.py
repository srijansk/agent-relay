"""Persisted run history — snapshot artifacts when a workflow completes.

Until v0.2 the artifact directory at ``.relay/workflows/<name>/artifacts/``
was the working set: each iteration overwrote the previous bytes, and once
the workflow reached a terminal stage the artifacts were the only record.

v0.2 keeps that working-set semantics (so existing users see no change)
but adds a snapshot step: when a run reaches a terminal stage, the workflow
directory's artifacts and state are copied to ``.relay/history/<run-id>/``.
The compiled-lessons pipeline (``relay distill``) reads from there.

History is opt-in via ``relay.yml``::

    history:
      enabled: true     # default true for new workflows
"""

from __future__ import annotations

import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from relay.protocol.state import StateDocument
from relay.protocol.workflow import WorkflowDefinition

_RUN_ID_PATTERN = re.compile(r"^\d{8}-\d{4}-[a-z0-9-]+$")


def is_history_enabled(config: dict[str, Any] | None) -> bool:
    """Read ``history.enabled`` from a relay.yml config dict. Defaults to True."""
    if not config:
        return True
    history_cfg = config.get("history") or {}
    if not isinstance(history_cfg, dict):
        return True
    return bool(history_cfg.get("enabled", True))


def make_run_id(workflow_name: str, *, now: datetime | None = None) -> str:
    """Generate a sortable run id: ``YYYYMMDD-HHMM-<slug>``."""
    timestamp = (now or datetime.now(tz=timezone.utc)).strftime("%Y%m%d-%H%M")
    slug = _slugify(workflow_name)
    return f"{timestamp}-{slug}"


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    return text or "run"


def history_dir(relay_dir: Path) -> Path:
    return relay_dir / "history"


def snapshot_run(
    *,
    relay_dir: Path,
    workflow_dir: Path,
    workflow: WorkflowDefinition,
    state: StateDocument,
    run_id: str | None = None,
) -> Path:
    """Copy the current workflow state into ``.relay/history/<run-id>/``.

    Returns the snapshot directory path. Idempotent: if a run with the same
    id already exists we append a short suffix rather than clobbering.
    """
    run_id = run_id or make_run_id(workflow.name)
    snapshot_root = history_dir(relay_dir) / run_id
    snapshot_root = _ensure_unique(snapshot_root)
    snapshot_root.mkdir(parents=True, exist_ok=True)

    workflow_yml = workflow_dir / "workflow.yml"
    if workflow_yml.exists():
        shutil.copy2(workflow_yml, snapshot_root / "workflow.yml")

    roles_src = workflow_dir / "roles"
    if roles_src.exists() and roles_src.is_dir():
        shutil.copytree(roles_src, snapshot_root / "roles", dirs_exist_ok=True)

    artifacts_src = workflow_dir / "artifacts"
    if artifacts_src.exists() and artifacts_src.is_dir():
        artifacts_dst = snapshot_root / "artifacts"
        artifacts_dst.mkdir(exist_ok=True)
        for item in artifacts_src.iterdir():
            if not item.is_file():
                continue
            shutil.copy2(item, artifacts_dst / item.name)

    state.save(snapshot_root / "state.yml")

    summary = {
        "run_id": snapshot_root.name,
        "workflow": workflow.name,
        "final_stage": state.stage,
        "iteration_counts": dict(state.iteration_counts),
        "captured_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    (snapshot_root / "run.yml").write_text(
        yaml.dump(summary, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    return snapshot_root


def _ensure_unique(path: Path) -> Path:
    """If ``path`` exists, append ``-2``, ``-3`` ... until it doesn't."""
    if not path.exists():
        return path
    parent = path.parent
    base = path.name
    n = 2
    while True:
        candidate = parent / f"{base}-{n}"
        if not candidate.exists():
            return candidate
        n += 1


def list_runs(relay_dir: Path) -> list[Path]:
    """Return run snapshot directories in chronological order."""
    root = history_dir(relay_dir)
    if not root.exists():
        return []
    return sorted(p for p in root.iterdir() if p.is_dir() and _RUN_ID_PATTERN.match(p.name) is not None)
