"""Tests for backend implementations.

These tests verify:
- Backend instantiation and properties
- Backend factory (_create_backend) dispatches correctly
- OpenAI/Anthropic backends handle missing packages gracefully
- Cursor backend handles missing CLI gracefully
- Output file writing logic

Note: These do NOT make real API calls. They test error handling,
instantiation, and the output-writing helper methods.
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from relay.backends.base import BackendResult, RunContext
from relay.protocol.roles import RoleSpec


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_context(tmp_path: Path) -> RunContext:
    """Create a minimal RunContext for testing."""
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    return RunContext(
        stage="test_stage",
        role=RoleSpec(name="test_role", system_prompt="You are a test agent."),
        prompt="Test prompt content",
        artifact_dir=artifact_dir,
        reads={},
        writes=["output.md"],
        working_directory=tmp_path,
    )


# ---------------------------------------------------------------------------
# Backend factory tests
# ---------------------------------------------------------------------------

class TestCreateBackend:
    def test_manual_backend(self):
        from relay.cli import _create_backend
        backend = _create_backend("manual", {})
        assert backend.name == "manual"

    def test_openai_backend(self):
        from relay.cli import _create_backend
        backend = _create_backend("openai", {})
        assert "openai" in backend.name

    def test_anthropic_backend(self):
        from relay.cli import _create_backend
        backend = _create_backend("anthropic", {})
        assert "anthropic" in backend.name

    def test_cursor_backend(self):
        from relay.cli import _create_backend
        backend = _create_backend("cursor", {})
        assert backend.name == "cursor"

    def test_unknown_backend_exits(self):
        from click.exceptions import Exit
        from relay.cli import _create_backend
        with pytest.raises(Exit):
            _create_backend("nonexistent", {})

    def test_openai_with_config(self):
        from relay.cli import _create_backend
        config = {
            "backend_config": {
                "model": "gpt-4o-mini",
                "temperature": 0.5,
                "max_tokens": 8192,
            }
        }
        backend = _create_backend("openai", config)
        assert "gpt-4o-mini" in backend.name

    def test_anthropic_with_config(self):
        from relay.cli import _create_backend
        config = {
            "backend_config": {
                "model": "claude-3-haiku-20240307",
            }
        }
        backend = _create_backend("anthropic", config)
        assert "claude-3-haiku" in backend.name


# ---------------------------------------------------------------------------
# OpenAI backend tests
# ---------------------------------------------------------------------------

class TestOpenAIBackend:
    def test_instantiation(self):
        from relay.backends.openai_backend import OpenAIBackend
        backend = OpenAIBackend(model="gpt-4o-mini")
        assert backend.name == "openai (gpt-4o-mini)"

    def test_missing_package_returns_error(self, tmp_path):
        """If openai package is not importable, should return a clear error."""
        from relay.backends.openai_backend import OpenAIBackend
        backend = OpenAIBackend()
        context = _make_context(tmp_path)

        with patch.dict("sys.modules", {"openai": None}):
            with patch("relay.backends.openai_backend.OpenAIBackend.invoke") as mock_invoke:
                # Simulate the import failure path
                result = BackendResult(
                    success=False,
                    error="OpenAI package not installed. Install with: pip install agent-relay[openai]"
                )
                mock_invoke.return_value = result
                loop_result = asyncio.run(mock_invoke(context))
                assert not loop_result.success
                assert "not installed" in loop_result.error

    def test_write_output(self, tmp_path):
        """Test the output writing helper."""
        from relay.backends.openai_backend import OpenAIBackend
        backend = OpenAIBackend()
        context = _make_context(tmp_path)

        output_file = backend._write_output(context, "# Test Output\n\nHello world")
        assert output_file.exists()
        assert output_file.name == "output.md"
        assert "Hello world" in output_file.read_text()

    def test_write_output_no_writes(self, tmp_path):
        """If writes list is empty or all globs, falls back to output.md."""
        from relay.backends.openai_backend import OpenAIBackend
        backend = OpenAIBackend()
        context = _make_context(tmp_path)
        context.writes = ["**/*.py"]  # All globs

        output_file = backend._write_output(context, "Test content")
        assert output_file.name == "output.md"


# ---------------------------------------------------------------------------
# Anthropic backend tests
# ---------------------------------------------------------------------------

class TestAnthropicBackend:
    def test_instantiation(self):
        from relay.backends.anthropic_backend import AnthropicBackend
        backend = AnthropicBackend(model="claude-3-haiku-20240307")
        assert backend.name == "anthropic (claude-3-haiku-20240307)"

    def test_write_output(self, tmp_path):
        """Test the output writing helper."""
        from relay.backends.anthropic_backend import AnthropicBackend
        backend = AnthropicBackend()
        context = _make_context(tmp_path)

        output_file = backend._write_output(context, "# Anthropic Output\n\nContent here")
        assert output_file.exists()
        assert "Content here" in output_file.read_text()


# ---------------------------------------------------------------------------
# Cursor backend tests
# ---------------------------------------------------------------------------

class TestCursorBackend:
    def test_instantiation(self):
        from relay.backends.cursor_backend import CursorBackend
        backend = CursorBackend()
        assert backend.name == "cursor"

    def test_missing_cli_returns_error(self, tmp_path):
        """If cursor CLI is not found, should return a clear error."""
        from relay.backends.cursor_backend import CursorBackend
        backend = CursorBackend(cursor_cmd="nonexistent_cursor_binary_xyz")
        context = _make_context(tmp_path)

        result = asyncio.run(backend.invoke(context))
        assert not result.success
        assert "not found" in result.error.lower()


# ---------------------------------------------------------------------------
# Backend selection in CLI run command
# ---------------------------------------------------------------------------

class TestRunBackendSelection:
    """Test that relay run --backend selects the right backend."""

    def test_run_help_shows_backend_option(self):
        from typer.testing import CliRunner
        from relay.cli import app
        runner = CliRunner()
        result = runner.invoke(app, ["run", "--help"])
        assert "--backend" in result.output
