"""Agent Relay CLI — relay init, status, next, run, reset, validate, export, dash."""

from __future__ import annotations

import asyncio
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from relay.protocol.artifacts import ensure_artifact_dir, read_artifacts
from relay.protocol.roles import RoleSpec
from relay.protocol.state import StateDocument, StateMachine, extract_verdict
from relay.protocol.validator import validate_workflow
from relay.protocol.workflow import WorkflowDefinition

app = typer.Typer(
    name="relay",
    help="Agent Relay — multi-agent workflow orchestrator.",
    no_args_is_help=True,
)
console = Console()

RELAY_DIR = ".relay"
DEFAULT_WORKFLOW = "default"


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _find_relay_dir() -> Path:
    """Find the .relay/ directory in the current or parent directories."""
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        candidate = parent / RELAY_DIR
        if candidate.is_dir():
            return candidate
    return cwd / RELAY_DIR


def _workflow_dir(relay_dir: Path, workflow_name: str | None) -> Path:
    """Resolve the workflow directory."""
    name = workflow_name or DEFAULT_WORKFLOW
    return relay_dir / "workflows" / name


def _load_workflow(wf_dir: Path) -> WorkflowDefinition:
    """Load and validate workflow.yml from a workflow directory."""
    wf_path = wf_dir / "workflow.yml"
    if not wf_path.exists():
        console.print(f"[red]Error: workflow.yml not found at {wf_path}[/red]")
        raise typer.Exit(1)
    raw = yaml.safe_load(wf_path.read_text())
    return WorkflowDefinition.model_validate(raw)


def _load_state(wf_dir: Path) -> StateDocument:
    """Load state.yml from a workflow directory."""
    return StateDocument.load(wf_dir / "state.yml")


def _load_role(wf_dir: Path, role_name: str, workflow: WorkflowDefinition) -> RoleSpec:
    """Load a role spec from the workflow directory."""
    role_def = workflow.roles.get(role_name)
    if not role_def:
        console.print(f"[red]Error: Role '{role_name}' not found in workflow[/red]")
        raise typer.Exit(1)
    role_path = wf_dir / role_def.rules
    if not role_path.exists():
        console.print(f"[red]Error: Role file not found: {role_path}[/red]")
        raise typer.Exit(1)
    raw = yaml.safe_load(role_path.read_text())
    return RoleSpec.model_validate(raw)


# ---------------------------------------------------------------------------
# Backend factory
# ---------------------------------------------------------------------------

def _create_backend(name: str, config: dict) -> "Backend":
    """Create a backend instance by name.

    Args:
        name: Backend name (manual, openai, anthropic, cursor)
        config: relay.yml config dict (may contain backend-specific settings)
    """
    from relay.backends.base import Backend

    backend_config = config.get("backend_config", {})

    if name == "manual":
        from relay.backends.manual import ManualBackend
        return ManualBackend()

    elif name == "openai":
        from relay.backends.openai_backend import OpenAIBackend
        return OpenAIBackend(
            model=backend_config.get("model", "gpt-4o"),
            api_key=backend_config.get("api_key"),
            temperature=backend_config.get("temperature", 0.2),
            max_tokens=backend_config.get("max_tokens", 16384),
        )

    elif name == "anthropic":
        from relay.backends.anthropic_backend import AnthropicBackend
        return AnthropicBackend(
            model=backend_config.get("model", "claude-sonnet-4-20250514"),
            api_key=backend_config.get("api_key"),
            temperature=backend_config.get("temperature", 0.2),
            max_tokens=backend_config.get("max_tokens", 16384),
        )

    elif name == "cursor":
        from relay.backends.cursor_backend import CursorBackend
        return CursorBackend(
            cursor_cmd=backend_config.get("cursor_cmd", "cursor"),
        )

    else:
        console.print(
            f"[red]Unknown backend: '{name}'. "
            f"Available: manual, openai, anthropic, cursor[/red]"
        )
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@app.command()
def init(
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Workflow name (default: 'default')"),
    template: Optional[str] = typer.Option(None, "--template", "-t", help="Template to use"),
) -> None:
    """Initialize a new workflow in the current directory."""
    relay_dir = Path.cwd() / RELAY_DIR
    wf_name = name or DEFAULT_WORKFLOW
    wf_dir = relay_dir / "workflows" / wf_name

    if wf_dir.exists():
        console.print(f"[yellow]Workflow '{wf_name}' already exists at {wf_dir}[/yellow]")
        raise typer.Exit(1)

    # Check for built-in template
    if template:
        templates_root = Path(__file__).parent / "templates"
        # Try exact match, then common variants, then substring match
        template_dir = None
        candidates = [
            template,
            template.replace("-", "_"),
            template.replace("_", "-"),
        ]
        for candidate in candidates:
            check = templates_root / candidate
            if check.exists():
                template_dir = check
                break

        if template_dir is None and templates_root.exists():
            # Fuzzy: check if any template name is a substring match
            # e.g., "plan-review-implement-audit" should match "plan_review_impl_audit"
            input_words = set(template.lower().replace("-", "_").split("_"))
            for d in templates_root.iterdir():
                if d.is_dir():
                    dir_words = set(d.name.lower().replace("-", "_").split("_"))
                    # If most words from the directory name appear in the input (or vice versa)
                    if dir_words.issubset(input_words) or len(dir_words & input_words) >= len(dir_words) * 0.7:
                        template_dir = d
                        break
        if template_dir is None:
            available = [d.name for d in templates_root.iterdir() if d.is_dir()] if templates_root.exists() else []
            console.print(f"[red]Template '{template}' not found. Available: {', '.join(available)}[/red]")
            raise typer.Exit(1)
        shutil.copytree(template_dir, wf_dir)
    else:
        # Create minimal workflow structure
        wf_dir.mkdir(parents=True)
        (wf_dir / "roles").mkdir()
        (wf_dir / "artifacts").mkdir()

        # Create minimal workflow.yml
        minimal_workflow = {
            "name": wf_name,
            "version": 1,
            "roles": {
                "worker": {
                    "description": "Executes the task",
                    "writes": ["output.md"],
                    "reads": ["context.md"],
                    "rules": "roles/worker.yml",
                }
            },
            "stages": {
                "working": {"agent": "worker", "next": "done"},
                "done": {"terminal": True},
            },
            "initial_stage": "working",
            "limits": {},
        }
        (wf_dir / "workflow.yml").write_text(
            yaml.dump(minimal_workflow, default_flow_style=False, sort_keys=False)
        )

        # Create minimal role file
        minimal_role = {
            "name": "worker",
            "system_prompt": "You are a helpful assistant. Complete the task described in context.md.",
        }
        (wf_dir / "roles" / "worker.yml").write_text(
            yaml.dump(minimal_role, default_flow_style=False, sort_keys=False)
        )

        # Create placeholder context
        (wf_dir / "artifacts" / "context.md").write_text(
            "# Context\n\nDescribe your task here.\n"
        )

    # Create initial state
    workflow = _load_workflow(wf_dir)
    state = StateDocument.create_initial(workflow.initial_stage)
    state.save(wf_dir / "state.yml")

    # Create relay.yml if it doesn't exist
    relay_yml = relay_dir / "relay.yml"
    if not relay_yml.exists():
        config = {
            "default_workflow": wf_name,
            "backend": "manual",
            "max_artifact_chars": 50000,
        }
        relay_yml.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False))

    console.print(f"[green]Workflow '{wf_name}' initialized at {wf_dir}[/green]")
    console.print(f"[dim]Next: run 'relay status' to see the current state[/dim]")


@app.command()
def status(
    workflow: Optional[str] = typer.Option(None, "--workflow", "-w", help="Workflow name"),
) -> None:
    """Show the current workflow state."""
    relay_dir = _find_relay_dir()
    wf_dir = _workflow_dir(relay_dir, workflow)

    if not wf_dir.exists():
        console.print("[red]No workflow found. Run 'relay init' first.[/red]")
        raise typer.Exit(1)

    wf = _load_workflow(wf_dir)
    state = _load_state(wf_dir)
    machine = StateMachine(wf, state)

    # Build status display
    table = Table(title=f"Workflow: {wf.name}", show_header=False, border_style="cyan")
    table.add_column("Key", style="bold")
    table.add_column("Value")

    table.add_row("Stage", state.stage)

    if machine.is_terminal:
        table.add_row("Status", "[green]DONE[/green]")
    else:
        role_name = machine.current_role_name or "unknown"
        table.add_row("Active Role", role_name)
        if machine.is_branching:
            table.add_row("Type", "Branching (verdict required)")
        else:
            table.add_row("Type", "Linear")

    if state.iteration_counts:
        counts_str = ", ".join(f"{k}: {v}" for k, v in state.iteration_counts.items())
        table.add_row("Iterations", counts_str)

    if state.last_updated_by:
        table.add_row("Last Updated By", state.last_updated_by)
    if state.last_updated_at:
        table.add_row("Last Updated", state.last_updated_at.isoformat())

    limit_reached, limit_msg = machine.check_iteration_limit()
    if limit_reached:
        table.add_row("Warning", f"[yellow]{limit_msg}[/yellow]")

    console.print(table)


@app.command()
def next(
    workflow: Optional[str] = typer.Option(None, "--workflow", "-w", help="Workflow name"),
) -> None:
    """Print the prompt for the next agent to run."""
    from relay.prompt import compose_prompt

    relay_dir = _find_relay_dir()
    wf_dir = _workflow_dir(relay_dir, workflow)

    wf = _load_workflow(wf_dir)
    state = _load_state(wf_dir)
    machine = StateMachine(wf, state)

    if machine.is_terminal:
        console.print("[green]Workflow is complete. Nothing to do.[/green]")
        raise typer.Exit(0)

    role_name = machine.current_role_name
    if not role_name:
        console.print("[red]Error: Current stage has no agent assigned.[/red]")
        raise typer.Exit(1)

    role = _load_role(wf_dir, role_name, wf)
    artifact_dir = wf_dir / "artifacts"

    # Load config for max_artifact_chars
    relay_yml = relay_dir / "relay.yml"
    max_chars = 50000
    if relay_yml.exists():
        config = yaml.safe_load(relay_yml.read_text()) or {}
        max_chars = config.get("max_artifact_chars", 50000)

    prompt = compose_prompt(wf, state, role, artifact_dir, max_chars)

    # Print with syntax highlighting
    console.print()
    console.print(Panel(
        prompt,
        title=f"[bold cyan]Prompt for: {role_name}[/bold cyan]",
        subtitle="Copy this into your agent tool",
        border_style="cyan",
        expand=True,
    ))
    console.print()
    console.print(
        f"[dim]After the agent finishes, run 'relay advance' "
        f"to move to the next stage.[/dim]"
    )


@app.command()
def advance(
    workflow: Optional[str] = typer.Option(None, "--workflow", "-w", help="Workflow name"),
    verdict: Optional[str] = typer.Option(None, "--verdict", "-v", help="Override verdict (approve/reject)"),
) -> None:
    """Advance the workflow to the next stage after an agent completes."""
    relay_dir = _find_relay_dir()
    wf_dir = _workflow_dir(relay_dir, workflow)

    wf = _load_workflow(wf_dir)
    state = _load_state(wf_dir)
    machine = StateMachine(wf, state)

    if machine.is_terminal:
        console.print("[green]Workflow is already complete.[/green]")
        raise typer.Exit(0)

    role_name = machine.current_role_name or "unknown"

    if machine.is_branching:
        # Need a verdict to determine the branch
        resolved_verdict = verdict
        if not resolved_verdict:
            # Try to extract from output file
            role = _load_role(wf_dir, role_name, wf)
            if role.verdict_field:
                role_def = wf.roles[role_name]
                non_glob_writes = [w for w in role_def.writes if "*" not in w]
                for filename in non_glob_writes:
                    filepath = wf_dir / "artifacts" / filename
                    if filepath.exists():
                        content = filepath.read_text()
                        resolved_verdict = extract_verdict(
                            content, role.verdict_field, role.approve_value, role.reject_value
                        )
                        if resolved_verdict:
                            break

        if not resolved_verdict:
            console.print(
                "[yellow]Could not detect verdict from output files.[/yellow]\n"
                "Choose manually:"
            )
            next_map = machine.current_stage.next
            if isinstance(next_map, dict):
                for key in next_map:
                    console.print(f"  [{key[0]}] {key}")
            resolved_verdict = typer.prompt("Verdict").strip().lower()

        target = machine.resolve_branching_transition(resolved_verdict)
    else:
        target = machine.resolve_linear_transition()

    machine.advance(target, role_name)
    state.save(wf_dir / "state.yml")

    console.print(f"[green]Advanced: {role_name} → {target}[/green]")

    # Show next step
    if wf.stages[target].terminal:
        console.print("[bold green]Workflow complete![/bold green]")
    else:
        next_role = wf.stages[target].agent
        console.print(f"[dim]Next agent: {next_role}. Run 'relay next' to see the prompt.[/dim]")


@app.command()
def run(
    workflow: Optional[str] = typer.Option(None, "--workflow", "-w", help="Workflow name"),
    loop: bool = typer.Option(False, "--loop", help="Run the full loop until done or limit hit"),
    backend_name: Optional[str] = typer.Option(None, "--backend", "-b", help="Backend to use"),
) -> None:
    """Run the next agent using the configured backend."""
    from relay.prompt import compose_prompt

    relay_dir = _find_relay_dir()
    wf_dir = _workflow_dir(relay_dir, workflow)

    wf = _load_workflow(wf_dir)
    artifact_dir = wf_dir / "artifacts"
    ensure_artifact_dir(artifact_dir)

    # Load config
    relay_yml = relay_dir / "relay.yml"
    max_chars = 50000
    config: dict = {}
    if relay_yml.exists():
        config = yaml.safe_load(relay_yml.read_text()) or {}
        max_chars = config.get("max_artifact_chars", 50000)

    # Select backend — CLI flag > relay.yml config > default (manual)
    effective_backend = backend_name or config.get("backend", "manual")
    backend = _create_backend(effective_backend, config)

    async def _run_once() -> bool:
        """Run one agent cycle. Returns True if should continue, False if done."""
        state = _load_state(wf_dir)
        machine = StateMachine(wf, state)

        if machine.is_terminal:
            console.print("[bold green]Workflow complete![/bold green]")
            return False

        # Check iteration limits
        limit_reached, limit_msg = machine.check_iteration_limit()
        if limit_reached:
            console.print(f"[yellow]Warning: {limit_msg}[/yellow]")
            if loop:
                console.print("[yellow]Stopping loop due to iteration limit.[/yellow]")
                return False
            if not typer.confirm("Continue anyway?"):
                return False

        role_name = machine.current_role_name
        if not role_name:
            console.print("[red]Error: Current stage has no agent.[/red]")
            return False

        role = _load_role(wf_dir, role_name, wf)
        role_def = wf.roles[role_name]

        # Compose prompt
        prompt = compose_prompt(wf, state, role, artifact_dir, max_chars)

        # Build run context
        from relay.backends.base import RunContext
        reads = read_artifacts(artifact_dir, role_def.reads, max_chars)
        context = RunContext(
            stage=state.stage,
            role=role,
            prompt=prompt,
            artifact_dir=artifact_dir,
            reads=reads,
            writes=role_def.writes,
            working_directory=Path.cwd(),
        )

        # Invoke backend
        result = await backend.invoke(context)

        if not result.success:
            console.print(f"[red]Agent failed: {result.error}[/red]")
            return False

        # Resolve transition
        if machine.is_branching:
            resolved_verdict = None
            if role.verdict_field and result.output_file and result.output_file.exists():
                content = result.output_file.read_text()
                resolved_verdict = extract_verdict(
                    content, role.verdict_field, role.approve_value, role.reject_value
                )

            if not resolved_verdict:
                console.print("[yellow]Could not detect verdict.[/yellow]")
                next_map = machine.current_stage.next
                if isinstance(next_map, dict):
                    for key in next_map:
                        console.print(f"  [{key[0]}] {key}")
                resolved_verdict = typer.prompt("Verdict").strip().lower()

            target = machine.resolve_branching_transition(resolved_verdict)
        else:
            target = machine.resolve_linear_transition()

        machine.advance(target, role_name)
        state.save(wf_dir / "state.yml")
        console.print(f"[green]Advanced: {role_name} → {target}[/green]")

        return not wf.stages[target].terminal

    # Run
    if loop:
        should_continue = True
        while should_continue:
            should_continue = asyncio.run(_run_once())
    else:
        asyncio.run(_run_once())


@app.command()
def reset(
    workflow: Optional[str] = typer.Option(None, "--workflow", "-w", help="Workflow name"),
    clean: bool = typer.Option(False, "--clean", help="Also wipe all artifacts"),
) -> None:
    """Reset the workflow to its initial stage."""
    relay_dir = _find_relay_dir()
    wf_dir = _workflow_dir(relay_dir, workflow)

    if not wf_dir.exists():
        console.print("[red]No workflow found. Run 'relay init' first.[/red]")
        raise typer.Exit(1)

    wf = _load_workflow(wf_dir)
    state = StateDocument.create_initial(wf.initial_stage)
    state.save(wf_dir / "state.yml")

    if clean:
        artifact_dir = wf_dir / "artifacts"
        if artifact_dir.exists():
            for f in artifact_dir.iterdir():
                if f.is_file() and f.name != "context.md" and f.name != "acceptance_checklist.md":
                    f.unlink()
        console.print("[green]Workflow reset (state + artifacts wiped).[/green]")
    else:
        console.print("[green]Workflow reset to initial stage.[/green]")


@app.command()
def validate(
    workflow: Optional[str] = typer.Option(None, "--workflow", "-w", help="Workflow name"),
) -> None:
    """Validate the workflow definition for errors."""
    relay_dir = _find_relay_dir()
    wf_dir = _workflow_dir(relay_dir, workflow)

    if not wf_dir.exists():
        console.print("[red]No workflow found at {wf_dir}[/red]")
        raise typer.Exit(1)

    errors = validate_workflow(wf_dir)

    if errors:
        console.print(f"[red]Found {len(errors)} error(s):[/red]")
        for err in errors:
            console.print(f"  [red]• {err}[/red]")
        raise typer.Exit(1)
    else:
        console.print("[green]Workflow is valid.[/green]")


@app.command()
def dash(
    workflow: Optional[str] = typer.Option(None, "--workflow", "-w", help="Workflow name"),
) -> None:
    """Launch the TUI dashboard."""
    from relay.tui.app import RelayDashboard

    relay_dir = _find_relay_dir()
    wf_dir = _workflow_dir(relay_dir, workflow)

    if not wf_dir.exists():
        console.print("[red]No workflow found. Run 'relay init' first.[/red]")
        raise typer.Exit(1)

    dashboard = RelayDashboard(workflow_dir=wf_dir)
    dashboard.run()


@app.command()
def export(
    format: str = typer.Argument(..., help="Export format (cursor, markdown)"),
    workflow: Optional[str] = typer.Option(None, "--workflow", "-w", help="Workflow name"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output directory"),
) -> None:
    """Export workflow to tool-specific formats."""
    relay_dir = _find_relay_dir()
    wf_dir = _workflow_dir(relay_dir, workflow)

    if not wf_dir.exists():
        console.print("[red]No workflow found. Run 'relay init' first.[/red]")
        raise typer.Exit(1)

    output_dir = Path(output) if output else Path.cwd()

    if format == "cursor":
        from relay.exporters.cursor import export_to_cursor
        created = export_to_cursor(wf_dir, output_dir)
        console.print(f"[green]Exported to Cursor format ({len(created)} files):[/green]")
        for f in created:
            console.print(f"  {f.relative_to(output_dir)}")
    else:
        console.print(f"[red]Unknown format: {format}. Available: cursor[/red]")
        raise typer.Exit(1)
