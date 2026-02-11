"""Anthropic backend — calls messages.create and writes response to artifact file."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console

from relay.backends.base import Backend, BackendResult, RunContext

console = Console()


class AnthropicBackend(Backend):
    """Backend that invokes Anthropic's Messages API to run the agent.

    Requires the `anthropic` extra: pip install agent-relay[anthropic]
    Set ANTHROPIC_API_KEY environment variable or pass api_key to constructor.
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
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
        return f"anthropic ({self._model})"

    async def invoke(self, context: RunContext) -> BackendResult:
        """Call Anthropic Messages API and write response to the artifact file."""
        try:
            from anthropic import AsyncAnthropic
        except ImportError:
            return BackendResult(
                success=False,
                error=(
                    "Anthropic package not installed. "
                    "Install with: pip install agent-relay[anthropic]"
                ),
            )

        console.print(f"[cyan]Invoking Anthropic ({self._model}) for {context.role.name}...[/cyan]")

        try:
            client = AsyncAnthropic(api_key=self._api_key)

            response = await client.messages.create(
                model=self._model,
                system=context.role.system_prompt,
                messages=[
                    {"role": "user", "content": context.prompt},
                ],
                temperature=self._temperature,
                max_tokens=self._max_tokens,
            )

            # Extract text from response content blocks
            content_parts = []
            for block in response.content:
                if hasattr(block, "text"):
                    content_parts.append(block.text)

            content = "\n".join(content_parts)
            if not content:
                return BackendResult(
                    success=False,
                    error="Anthropic returned empty response",
                )

            # Write response to the first non-glob write file
            output_file = self._write_output(context, content)

            console.print(
                f"[dim]Tokens: {response.usage.input_tokens} in, "
                f"{response.usage.output_tokens} out[/dim]"
            )

            console.print(f"[green]Anthropic response written to {output_file.name}[/green]")
            return BackendResult(success=True, output_file=output_file)

        except Exception as e:
            return BackendResult(
                success=False,
                error=f"Anthropic API error: {e}",
            )

    def _write_output(self, context: RunContext, content: str) -> Path:
        """Write the LLM response to the appropriate artifact file."""
        non_glob_writes = [w for w in context.writes if "*" not in w]
        if not non_glob_writes:
            output_path = context.artifact_dir / "output.md"
        else:
            output_path = context.artifact_dir / non_glob_writes[0]

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        return output_path
