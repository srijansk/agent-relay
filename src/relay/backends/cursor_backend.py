"""Cursor backend — invokes Cursor CLI as a subprocess."""

from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path

from rich.console import Console

from relay.backends.base import Backend, BackendResult, RunContext

console = Console()


class CursorBackend(Backend):
    """Backend that invokes the Cursor IDE CLI to run an agent session.

    Requires the `cursor` CLI to be installed and available in PATH.
    The Cursor CLI is used to start a headless agent session with the composed prompt.

    Falls back to ManualBackend behavior if Cursor CLI is not found.
    """

    def __init__(self, cursor_cmd: str = "cursor"):
        self._cursor_cmd = cursor_cmd

    @property
    def name(self) -> str:
        return "cursor"

    async def invoke(self, context: RunContext) -> BackendResult:
        """Invoke Cursor CLI with the prompt, wait for completion."""
        # Check if cursor CLI is available
        if not shutil.which(self._cursor_cmd):
            return BackendResult(
                success=False,
                error=(
                    f"Cursor CLI ('{self._cursor_cmd}') not found in PATH. "
                    "Install Cursor and ensure the CLI is available, "
                    "or use a different backend (--backend manual, --backend openai)."
                ),
            )

        console.print(f"[cyan]Invoking Cursor CLI for {context.role.name}...[/cyan]")

        # Write prompt to a temp file (Cursor CLI reads from file)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, prefix="relay_prompt_"
        ) as f:
            f.write(context.prompt)
            prompt_file = Path(f.name)

        try:
            # Invoke Cursor CLI
            # Note: The exact Cursor CLI interface may vary between versions.
            # Common patterns:
            #   cursor --prompt "text"
            #   cursor agent --message "text"
            #   cursor composer --prompt-file file.md
            # We try the most common pattern first.
            proc = await asyncio.create_subprocess_exec(
                self._cursor_cmd,
                "agent",
                "--message",
                context.prompt,
                "--working-directory",
                str(context.working_directory),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(context.working_directory),
            )

            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                stderr_text = stderr.decode() if stderr else "unknown error"
                # If the CLI command format isn't supported, provide guidance
                if "unknown" in stderr_text.lower() or "error" in stderr_text.lower():
                    return BackendResult(
                        success=False,
                        error=(
                            f"Cursor CLI returned exit code {proc.returncode}.\n"
                            f"stderr: {stderr_text}\n\n"
                            "The Cursor CLI interface may have changed. "
                            "Try using --backend manual or --backend openai instead."
                        ),
                    )
                return BackendResult(
                    success=False,
                    error=f"Cursor CLI error (exit {proc.returncode}): {stderr_text}",
                )

            # Check if output file was created
            non_glob_writes = [w for w in context.writes if "*" not in w]
            output_file = None
            for filename in non_glob_writes:
                filepath = context.artifact_dir / filename
                if filepath.exists():
                    output_file = filepath
                    break

            if output_file:
                console.print(f"[green]Cursor completed. Output: {output_file.name}[/green]")
            else:
                console.print("[green]Cursor completed.[/green]")

            return BackendResult(success=True, output_file=output_file)

        except FileNotFoundError:
            return BackendResult(
                success=False,
                error=f"Cursor CLI ('{self._cursor_cmd}') not found.",
            )
        except Exception as e:
            return BackendResult(
                success=False,
                error=f"Cursor CLI error: {e}",
            )
        finally:
            # Clean up temp file
            prompt_file.unlink(missing_ok=True)
