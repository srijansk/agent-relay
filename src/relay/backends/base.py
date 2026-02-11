"""Backend interface — abstract base for agent invocation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from relay.protocol.roles import RoleSpec


@dataclass
class RunContext:
    """Context passed to a backend when invoking an agent."""
    stage: str
    role: RoleSpec
    prompt: str
    artifact_dir: Path
    reads: dict[str, str]
    writes: list[str]
    working_directory: Path


@dataclass
class BackendResult:
    """Result returned by a backend after agent invocation."""
    success: bool
    output_file: Path | None = None
    error: str | None = None


class Backend(ABC):
    """Abstract base class for agent backends."""

    @abstractmethod
    async def invoke(self, context: RunContext) -> BackendResult:
        """Run the agent and return when done.

        Implementations should:
        1. Present the prompt to the agent (print, API call, etc.)
        2. Wait for the agent to complete
        3. Return a BackendResult with success/failure and output file path
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of this backend."""
        ...
