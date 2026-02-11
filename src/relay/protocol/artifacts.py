"""Artifact file management — read, write, truncate."""

from __future__ import annotations

from pathlib import Path

DEFAULT_MAX_CHARS = 50_000


def read_artifact(path: Path, max_chars: int = DEFAULT_MAX_CHARS) -> str:
    """Read an artifact file, truncating if it exceeds max_chars.

    Returns the file content, possibly truncated with a marker.
    """
    if not path.exists():
        return ""

    content = path.read_text(encoding="utf-8")

    if len(content) <= max_chars:
        return content

    remaining = len(content) - max_chars
    return content[:max_chars] + f"\n\n[... truncated, {remaining:,} chars remaining]"


def read_artifacts(artifact_dir: Path, filenames: list[str], max_chars: int = DEFAULT_MAX_CHARS) -> dict[str, str]:
    """Read multiple artifact files from a directory.

    Returns a dict of {filename: content} for files that exist.
    Skips glob patterns (filenames containing '*').
    """
    result: dict[str, str] = {}
    for filename in filenames:
        if "*" in filename:
            continue  # Skip glob patterns
        filepath = artifact_dir / filename
        if filepath.exists():
            result[filename] = read_artifact(filepath, max_chars)
    return result


def ensure_artifact_dir(artifact_dir: Path) -> None:
    """Create the artifact directory if it doesn't exist."""
    artifact_dir.mkdir(parents=True, exist_ok=True)
