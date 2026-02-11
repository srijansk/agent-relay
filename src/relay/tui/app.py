"""Agent Relay TUI — terminal dashboard for workflow monitoring."""

from __future__ import annotations

from pathlib import Path

import yaml
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, Static, RichLog

from relay.protocol.state import StateDocument, StateMachine
from relay.protocol.workflow import WorkflowDefinition, _get_next_targets


class WorkflowHeader(Static):
    """Displays workflow name, stage, and iteration info."""

    def __init__(self, wf: WorkflowDefinition, state: StateDocument, **kwargs):
        super().__init__(**kwargs)
        self.wf = wf
        self.state = state

    def render(self) -> Text:
        machine = StateMachine(self.wf, self.state)
        text = Text()
        text.append("  Workflow: ", style="bold")
        text.append(f"{self.wf.name}", style="cyan bold")
        text.append("    Stage: ", style="bold")
        if machine.is_terminal:
            text.append(f"{self.state.stage}", style="green bold")
        else:
            text.append(f"{self.state.stage}", style="yellow bold")
        if self.state.last_updated_by:
            text.append("    Last: ", style="dim")
            text.append(f"{self.state.last_updated_by}", style="dim")
        return text


class StageMap(Static):
    """Visual representation of the workflow state machine."""

    def __init__(self, wf: WorkflowDefinition, state: StateDocument, **kwargs):
        super().__init__(**kwargs)
        self.wf = wf
        self.state = state

    def render(self) -> Text:
        text = Text()
        text.append("\n")

        # Build a simple linear display of stages
        # Highlight the current stage
        stages = list(self.wf.stages.keys())
        current = self.state.stage

        for i, stage_name in enumerate(stages):
            stage = self.wf.stages[stage_name]
            is_current = stage_name == current

            # Stage box
            if is_current:
                text.append(f" [{stage_name}] ", style="bold reverse cyan")
            elif stage.terminal:
                text.append(f" [{stage_name}] ", style="dim green")
            else:
                text.append(f" [{stage_name}] ", style="dim")

            # Arrow to next (if not last)
            if i < len(stages) - 1:
                targets = _get_next_targets(stage)
                if targets:
                    text.append(" → ", style="dim")

        text.append("\n")

        # Show role info for current stage
        machine = StateMachine(self.wf, self.state)
        if not machine.is_terminal and machine.current_role_name:
            role_name = machine.current_role_name
            role_def = self.wf.roles.get(role_name)
            text.append("\n  Active: ", style="bold")
            text.append(f"{role_name}", style="cyan")
            if role_def:
                text.append("\n  Reading: ", style="dim")
                text.append(
                    ", ".join(role_def.reads) if role_def.reads else "none",
                    style="dim",
                )
                text.append("\n  Writing: ", style="dim")
                text.append(", ".join(role_def.writes), style="dim")

        # Show iteration counts
        if self.state.iteration_counts:
            text.append("\n\n  Iterations: ", style="bold")
            parts = [f"{k}: {v}" for k, v in self.state.iteration_counts.items()]
            text.append(", ".join(parts), style="dim")

        return text


class RelayDashboard(App):
    """Main TUI application for Agent Relay."""

    TITLE = "Agent Relay"
    CSS = """
    Screen {
        layout: vertical;
    }
    #header-info {
        height: 3;
        padding: 0 1;
        background: $surface;
        border-bottom: solid $primary;
    }
    #stage-map {
        height: auto;
        min-height: 8;
        padding: 1 2;
        background: $surface;
        border-bottom: solid $primary;
    }
    #activity {
        padding: 1 2;
    }
    """

    BINDINGS = [
        Binding("n", "show_next", "Next Prompt"),
        Binding("s", "refresh_status", "Refresh"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, workflow_dir: Path, **kwargs):
        super().__init__(**kwargs)
        self.workflow_dir = workflow_dir
        self.wf = self._load_workflow()
        self.state = self._load_state()

    def _load_workflow(self) -> WorkflowDefinition:
        raw = yaml.safe_load((self.workflow_dir / "workflow.yml").read_text())
        return WorkflowDefinition.model_validate(raw)

    def _load_state(self) -> StateDocument:
        return StateDocument.load(self.workflow_dir / "state.yml")

    def compose(self) -> ComposeResult:
        yield Header()
        yield WorkflowHeader(self.wf, self.state, id="header-info")
        yield StageMap(self.wf, self.state, id="stage-map")
        yield RichLog(id="activity", wrap=True, highlight=True, markup=True)
        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one("#activity", RichLog)
        log.write("[bold]Activity Log[/bold]")
        log.write("─" * 60)
        if self.state.last_updated_by:
            ts = (
                self.state.last_updated_at.strftime("%H:%M")
                if self.state.last_updated_at
                else "?"
            )
            log.write(f"  {ts}  {self.state.last_updated_by}  → {self.state.stage}")
        machine = StateMachine(self.wf, self.state)
        if machine.is_terminal:
            log.write("[green bold]  Workflow complete![/green bold]")
        else:
            log.write(f"  Waiting for: [cyan]{machine.current_role_name}[/cyan]")
            log.write("  Run [bold]relay next[/bold] to see the prompt.")

    def action_refresh_status(self) -> None:
        self.state = self._load_state()
        # Refresh widgets
        header = self.query_one("#header-info", WorkflowHeader)
        header.state = self.state
        header.refresh()
        stage_map = self.query_one("#stage-map", StageMap)
        stage_map.state = self.state
        stage_map.refresh()
        log = self.query_one("#activity", RichLog)
        log.write("[dim]Status refreshed[/dim]")

    def action_show_next(self) -> None:
        log = self.query_one("#activity", RichLog)
        log.write(
            "[yellow]Run 'relay next' in a terminal to see the full prompt.[/yellow]"
        )
