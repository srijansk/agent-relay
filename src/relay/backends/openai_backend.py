"""OpenAI backend — calls chat.completions.create and writes response to artifact file."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console

from relay.backends.base import Backend, BackendResult, RunContext

console = Console()


class OpenAIBackend(Backend):
    """Backend that invokes an OpenAI chat completion to run the agent.

    Requires the `openai` extra: pip install agent-relay[openai]
    Set OPENAI_API_KEY environment variable or pass api_key to constructor.
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 16384,
    ):
        self._model = model
        self._api_key = api_key
        self._temperature = temperature
        self._max_tokens = max_tokens

    @property
    def name(self) -> str:
        return f"openai ({self._model})"

    async def invoke(self, context: RunContext) -> BackendResult:
        """Call OpenAI chat completion and write response to the artifact file."""
        try:
            from openai import AsyncOpenAI
        except ImportError:
            return BackendResult(
                success=False,
                error=(
                    "OpenAI package not installed. "
                    "Install with: pip install agent-relay[openai]"
                ),
            )

        console.print(f"[cyan]Invoking OpenAI ({self._model}) for {context.role.name}...[/cyan]")

        try:
            client = AsyncOpenAI(api_key=self._api_key)

            messages = [
                {"role": "system", "content": context.role.system_prompt},
                {"role": "user", "content": context.prompt},
            ]

            response = await client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
            )

            content = response.choices[0].message.content
            if not content:
                return BackendResult(
                    success=False,
                    error="OpenAI returned empty response",
                )

            # Write response to the first non-glob write file
            output_file = self._write_output(context, content)

            usage = response.usage
            if usage:
                console.print(
                    f"[dim]Tokens: {usage.prompt_tokens} in, "
                    f"{usage.completion_tokens} out, "
                    f"{usage.total_tokens} total[/dim]"
                )

            console.print(f"[green]OpenAI response written to {output_file.name}[/green]")
            return BackendResult(success=True, output_file=output_file)

        except Exception as e:
            return BackendResult(
                success=False,
                error=f"OpenAI API error: {e}",
            )

    def _write_output(self, context: RunContext, content: str) -> Path:
        """Write the LLM response to the appropriate artifact file."""
        non_glob_writes = [w for w in context.writes if "*" not in w]
        if not non_glob_writes:
            # Fallback: write to a generic output file
            output_path = context.artifact_dir / "output.md"
        else:
            output_path = context.artifact_dir / non_glob_writes[0]

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        return output_path
