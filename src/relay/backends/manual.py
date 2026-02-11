"""Manual backend — prints prompt and waits for user confirmation."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

from relay.backends.base import Backend, BackendResult, RunContext

console = Console()


class ManualBackend(Backend):
    """Backend that prints the prompt and waits for the user to run it manually.

    In this mode, the user copies the prompt into their agent tool (Cursor, Codex, etc.),
    waits for the agent to finish, then signals completion.

    Completion detection:
    1. Watches the role's write files for modifications.
    2. Falls back to waiting for user to press Enter.
    """

    def __init__(self, timeout_seconds: int = 1800, settle_seconds: float = 2.0):
        self._timeout = timeout_seconds
        self._settle = settle_seconds

    @property
    def name(self) -> str:
        return "manual"

    async def invoke(self, context: RunContext) -> BackendResult:
        """Print the prompt, wait for file changes or user confirmation."""
        # Print the prompt
        console.print()
        console.print(Panel(
            context.prompt,
            title=f"[bold cyan]Prompt for {context.role.name}[/bold cyan]",
            subtitle="Copy this into your agent tool",
            border_style="cyan",
            expand=True,
        ))
        console.print()

        # Show what files to watch
        non_glob_writes = [w for w in context.writes if "*" not in w]
        if non_glob_writes:
            files_str = ", ".join(non_glob_writes)
            console.print(f"[dim]Watching for changes to: {files_str}[/dim]")

        console.print(
            "[bold yellow]Press Enter when the agent has finished "
            "(or wait for file changes to be detected)...[/bold yellow]"
        )

        # Wait for either: file change detected OR user presses Enter
        output_file = None
        if non_glob_writes:
            output_path = context.artifact_dir / non_glob_writes[0]
            result = await self._wait_for_completion(output_path)
            if result:
                output_file = output_path
        else:
            # No specific files to watch, just wait for Enter
            await asyncio.get_event_loop().run_in_executor(None, input)

        console.print("[green]Agent completed.[/green]")
        return BackendResult(success=True, output_file=output_file)

    async def _wait_for_completion(self, watch_path: Path) -> bool:
        """Wait for a file to be modified, or for user to press Enter.

        Returns True if file change detected, False if user pressed Enter.
        """
        initial_mtime = watch_path.stat().st_mtime if watch_path.exists() else 0

        # Run file watching and input waiting concurrently
        loop = asyncio.get_event_loop()

        async def watch_file():
            while True:
                await asyncio.sleep(1)
                if watch_path.exists():
                    current_mtime = watch_path.stat().st_mtime
                    if current_mtime > initial_mtime:
                        # Wait for writes to settle
                        await asyncio.sleep(self._settle)
                        return True
            return False

        async def wait_for_enter():
            await loop.run_in_executor(None, input)
            return False

        # Race: whichever completes first
        done, pending = await asyncio.wait(
            [asyncio.create_task(watch_file()), asyncio.create_task(wait_for_enter())],
            return_when=asyncio.FIRST_COMPLETED,
        )

        # Cancel pending tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, EOFError):
                pass

        result = done.pop().result()
        return result
