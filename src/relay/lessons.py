"""Lessons compiler — distill role-typed lessons from past run artifacts.

The lessons compiler turns the markdown produced by past workflow runs into
typed, in-repo knowledge that the next planner can read. Two modes:

  * Heuristic (default, deterministic) — parses known section headers
    (Required Changes, Concerns, Catches, Suggestions) and extracts bullet
    points as lesson candidates. No LLM. CI-friendly.

  * LLM (--llm, opt-in) — calls the configured backend with a structured
    prompt to produce higher-quality typed lessons from the same artifacts.
    Falls back to heuristic if no backend or call fails.

Output is two artifacts at ``.relay/``:

  * ``LESSONS.md`` — human-readable, organised by role and severity
  * ``lessons.json`` — typed, machine-readable (consumed by prompt injection)
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

Severity = Literal["info", "warn", "error"]
Source = Literal["heuristic", "llm", "manual"]


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

class Lesson(BaseModel):
    """A single distilled lesson from a past run.

    ``id`` is a stable content hash so the same input always yields the same
    output, which keeps ``relay distill`` idempotent and diffs reviewable.
    """

    id: str
    role: str
    claim: str
    severity: Severity
    evidence_run_id: str
    evidence_excerpt: str
    observed_at: datetime
    tags: list[str] = []
    source: Source = "heuristic"


# ---------------------------------------------------------------------------
# Heuristic extraction
# ---------------------------------------------------------------------------

# Header → (severity, default-audience-role).
#
# Important: ``role`` here is the **audience** of the lesson — the role that
# benefits from hearing it next time, not the role that wrote the artifact.
# A reviewer's "Required Changes" is a lesson FOR the planner: it tells the
# planner what the reviewer rejected previously. Same with auditor catches:
# the lesson is for the implementer who has to avoid the catch next round.
#
# The artifact filename can override this with a more specific signal — see
# ``_ARTIFACT_TO_ROLE`` below.
_HEADER_PATTERNS: list[tuple[re.Pattern[str], Severity, str]] = [
    (re.compile(r"^#{1,3}\s+required\s+changes?\b.*$", re.IGNORECASE | re.MULTILINE), "warn", "planner"),
    (re.compile(r"^#{1,3}\s+catches?\b.*$", re.IGNORECASE | re.MULTILINE), "error", "implementer"),
    (re.compile(r"^#{1,3}\s+must[_\s-]?fix\b.*$", re.IGNORECASE | re.MULTILINE), "error", "implementer"),
    (re.compile(r"^#{1,3}\s+should[_\s-]?fix\b.*$", re.IGNORECASE | re.MULTILINE), "info", "implementer"),
    (re.compile(r"^#{1,3}\s+concerns?\b.*$", re.IGNORECASE | re.MULTILINE), "warn", "planner"),
    (re.compile(r"^#{1,3}\s+suggestions?\b.*$", re.IGNORECASE | re.MULTILINE), "info", "planner"),
    (re.compile(r"^#{1,3}\s+findings?\b.*$", re.IGNORECASE | re.MULTILINE), "warn", "implementer"),
    (re.compile(r"^#{1,3}\s+gotchas?\b.*$", re.IGNORECASE | re.MULTILINE), "warn", "implementer"),
    (re.compile(r"^#{1,3}\s+lessons?\s+learned\b.*$", re.IGNORECASE | re.MULTILINE), "info", "implementer"),
]

# Match the next heading at any level so we can slice a section out.
_NEXT_HEADER = re.compile(r"^#{1,6}\s+\S", re.MULTILINE)

# A top-level bullet line: must start at column 0 (no indent), with "- ",
# "* ", or "1. ". Indented bullets are folded in as continuation lines.
_BULLET_LINE = re.compile(r"^(?:[-*]|\d+\.)\s+(.+?)\s*$")

# A file path or filename: foo/bar.py, src/relay/state.py, README.md.
_FILE_TOKEN = re.compile(r"\b[\w./-]+\.[A-Za-z]{1,5}\b")

# Filename → audience role for the lessons extracted from that artifact.
# Mirrors the same audience-not-writer convention used by ``_HEADER_PATTERNS``.
# A review document's lessons are for the role that was reviewed; an
# author's own document's lessons are self-reflection for that author role.
_ARTIFACT_TO_ROLE = {
    "plan.md": "planner",            # planner's own retrospective bullets
    "plan_review.md": "planner",     # reviewer critiquing planner → audience planner
    "review.md": "planner",
    "build_log.md": "implementer",   # implementer's own gotchas
    "build_review.md": "implementer",  # auditor critiquing implementer
    "audit.md": "implementer",
    "rfc.md": "architect",
    "rfc_review.md": "architect",    # reviewer critiquing architect → audience architect
    "repro.md": "rca_agent",
    "hypothesis.md": "rca_agent",
}


@dataclass
class _ParseContext:
    role: str
    run_id: str
    observed_at: datetime
    artifact_filename: str


def _hash_id(role: str, claim: str, run_id: str) -> str:
    digest = hashlib.md5(f"{role}|{claim}|{run_id}".encode("utf-8")).hexdigest()
    return digest[:12]


def _strip_markdown(text: str) -> str:
    """Lightweight cleanup so claims read well in injected prompts."""
    text = text.strip()
    # Drop leading bold markers like "**Category**" then a separator.
    text = re.sub(r"^\*\*[^*]+\*\*\s*[—:-]\s*", "", text)
    # Collapse internal whitespace.
    text = re.sub(r"\s+", " ", text)
    # Trim trailing markdown punctuation.
    return text.rstrip(" .;,").strip()


def _extract_section(text: str, start: int) -> str:
    """Return the text between ``start`` and the next heading."""
    rest = text[start:]
    next_match = _NEXT_HEADER.search(rest, pos=1)
    if next_match:
        return rest[: next_match.start()]
    return rest


def _split_bullets(section_body: str) -> list[str]:
    """Pull bullets out of a section, folding continuation lines.

    A bullet starts at column 0 (or with a small indent) on a ``-``, ``*``,
    or ``N.`` marker. Subsequent lines that are deeper-indented or look like
    sub-bullets get folded into the current bullet.
    """
    lines = section_body.splitlines()
    bullets: list[str] = []
    current: list[str] = []

    def flush() -> None:
        if current:
            joined = " ".join(part.strip() for part in current if part.strip())
            if joined:
                bullets.append(joined)
            current.clear()

    for raw_line in lines:
        match = _BULLET_LINE.match(raw_line)
        if match:
            # Top-level bullet (starts at column 0).
            flush()
            current.append(match.group(1))
            continue
        if raw_line.strip() == "":
            # Blank lines end the current bullet.
            flush()
            continue
        if current:
            # Continuation / sub-detail line. Strip the indent and any
            # sub-bullet markers ("  - foo" → "foo").
            stripped = raw_line.strip()
            stripped = re.sub(r"^(?:[-*]|\d+\.)\s+", "", stripped)
            current.append(stripped)
    flush()
    return bullets


def _infer_role(artifact_filename: str, header_default_role: str, fallback_role: str) -> str:
    """Prefer the artifact filename signal; fall back to the header default."""
    if artifact_filename in _ARTIFACT_TO_ROLE:
        return _ARTIFACT_TO_ROLE[artifact_filename]
    return header_default_role or fallback_role


def _infer_tags(text: str) -> list[str]:
    """Extract file-token tags so relevance filters can match on touched files."""
    tags = sorted({m.group(0) for m in _FILE_TOKEN.finditer(text)})
    return tags


def parse_artifact_for_lessons(
    content: str,
    *,
    artifact_filename: str,
    fallback_role: str,
    run_id: str,
    observed_at: datetime,
) -> list[Lesson]:
    """Parse one markdown artifact for bullets under known lesson headers."""
    if not content.strip():
        return []

    lessons: list[Lesson] = []
    seen_ids: set[str] = set()

    for pattern, severity, header_default_role in _HEADER_PATTERNS:
        for match in pattern.finditer(content):
            section = _extract_section(content, match.end())
            for bullet in _split_bullets(section):
                claim = _strip_markdown(bullet)
                if not claim or len(claim) < 6:
                    continue
                role = _infer_role(artifact_filename, header_default_role, fallback_role)
                lesson_id = _hash_id(role, claim, run_id)
                if lesson_id in seen_ids:
                    continue
                seen_ids.add(lesson_id)
                lessons.append(
                    Lesson(
                        id=lesson_id,
                        role=role,
                        claim=claim,
                        severity=severity,
                        evidence_run_id=run_id,
                        evidence_excerpt=bullet[:280],
                        observed_at=observed_at,
                        tags=_infer_tags(claim),
                        source="heuristic",
                    )
                )
    return lessons


def extract_lessons_from_history(history_dir: Path) -> list[Lesson]:
    """Walk ``history/<run-id>/artifacts/`` and distil lessons from each run.

    Runs are processed in chronological order (lexicographic on the run-id,
    which starts with ``YYYYMMDD-HHMM``). Returns lessons sorted by
    ``(run_id, role, severity)`` for deterministic output.
    """
    if not history_dir.exists():
        return []

    all_lessons: list[Lesson] = []
    run_dirs = sorted(p for p in history_dir.iterdir() if p.is_dir())

    for run_dir in run_dirs:
        run_id = run_dir.name
        artifact_dir = run_dir / "artifacts"
        if not artifact_dir.exists():
            continue
        observed_at = _run_observed_at(run_id, run_dir)
        for artifact_path in sorted(artifact_dir.glob("*.md")):
            try:
                content = artifact_path.read_text(encoding="utf-8")
            except OSError:
                continue
            lessons = parse_artifact_for_lessons(
                content,
                artifact_filename=artifact_path.name,
                fallback_role=_ARTIFACT_TO_ROLE.get(artifact_path.name, "unknown"),
                run_id=run_id,
                observed_at=observed_at,
            )
            all_lessons.extend(lessons)

    severity_order = {"error": 0, "warn": 1, "info": 2}
    all_lessons.sort(key=lambda lesson: (lesson.evidence_run_id, lesson.role, severity_order[lesson.severity], lesson.id))
    return all_lessons


def _run_observed_at(run_id: str, run_dir: Path) -> datetime:
    """Best-effort timestamp from the run-id prefix; fall back to mtime."""
    match = re.match(r"^(\d{8})-(\d{4})", run_id)
    if match:
        date_str, time_str = match.groups()
        try:
            return datetime.strptime(f"{date_str}{time_str}", "%Y%m%d%H%M").replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    try:
        return datetime.fromtimestamp(run_dir.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return datetime.now(tz=timezone.utc)


# ---------------------------------------------------------------------------
# Compilation to outputs
# ---------------------------------------------------------------------------

def compile_lessons_json(lessons: list[Lesson]) -> str:
    """Render ``lessons.json``. Sorted; pretty-printed for diffability."""
    payload = {
        "version": 1,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "lesson_count": len(lessons),
        "lessons": [json.loads(lesson.model_dump_json()) for lesson in lessons],
    }
    return json.dumps(payload, indent=2, sort_keys=False) + "\n"


def compile_lessons_md(lessons: list[Lesson]) -> str:
    """Render the human-readable ``LESSONS.md`` grouped by role."""
    if not lessons:
        return _EMPTY_LESSONS_MD

    by_role: dict[str, list[Lesson]] = {}
    for lesson in lessons:
        by_role.setdefault(lesson.role, []).append(lesson)

    lines: list[str] = [
        "# Lessons (compiled by `relay distill`)",
        "",
        "Distilled from past workflow runs in `.relay/history/`.",
        "These are evidence-backed observations, not absolute rules — apply judgment.",
        "",
        "Manual edits to this file are preserved across `relay distill` runs when",
        "added under a `## Manual notes` section at the bottom.",
        "",
    ]
    severity_order = {"error": 0, "warn": 1, "info": 2}

    for role in sorted(by_role.keys()):
        role_lessons = sorted(by_role[role], key=lambda lesson: (severity_order[lesson.severity], lesson.id))
        lines.append(f"## {role.title()} ({len(role_lessons)})")
        lines.append("")
        for lesson in role_lessons:
            tag_suffix = f" — files: {', '.join(lesson.tags)}" if lesson.tags else ""
            lines.append(
                f"- **[{lesson.severity}]** {lesson.claim}"
                f" _(run {lesson.evidence_run_id}{tag_suffix})_"
            )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


_EMPTY_LESSONS_MD = """# Lessons (compiled by `relay distill`)

No lessons yet. Run a workflow end-to-end so `.relay/history/` accumulates
runs, then re-run `relay distill`.
"""


# ---------------------------------------------------------------------------
# Loading + relevance filtering for prompt injection
# ---------------------------------------------------------------------------

def load_lessons(lessons_path: Path) -> list[Lesson]:
    """Load lessons.json. Returns empty list if missing or malformed."""
    if not lessons_path.exists():
        return []
    try:
        payload = json.loads(lessons_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    raw = payload.get("lessons", []) if isinstance(payload, dict) else []
    out: list[Lesson] = []
    for entry in raw:
        try:
            out.append(Lesson.model_validate(entry))
        except Exception:
            continue
    return out


def filter_lessons_for_role(
    lessons: list[Lesson],
    *,
    role: str,
    reads: list[str],
    max_n: int = 10,
) -> tuple[list[Lesson], list[Lesson]]:
    """Split lessons into (highly_relevant, other_relevant) for a given role.

    Highly relevant: this role + any tag overlaps the role's ``reads`` list.
    Other: this role, no overlap.

    The combined size is capped at ``max_n``, with highly-relevant filling
    first. Higher severity wins ties.
    """
    role_lessons = [lesson for lesson in lessons if lesson.role == role]
    severity_order = {"error": 0, "warn": 1, "info": 2}

    read_tokens: set[str] = set()
    for read_path in reads:
        read_tokens.add(read_path)
        # Also match by basename so "src/relay/state.py" matches "state.py".
        read_tokens.add(Path(read_path).name)

    highly: list[Lesson] = []
    other: list[Lesson] = []
    for lesson in role_lessons:
        overlap = bool(set(lesson.tags) & read_tokens) if lesson.tags else False
        if overlap:
            highly.append(lesson)
        else:
            other.append(lesson)

    highly.sort(key=lambda lesson: (severity_order[lesson.severity], -lesson.observed_at.timestamp()))
    other.sort(key=lambda lesson: (severity_order[lesson.severity], -lesson.observed_at.timestamp()))

    remaining = max(0, max_n - len(highly))
    return highly[:max_n], other[:remaining]


def render_lessons_section(
    highly: list[Lesson],
    other: list[Lesson],
) -> str:
    """Render the markdown block injected into a planner prompt."""
    if not highly and not other:
        return ""

    lines: list[str] = [
        "## Lessons from past runs",
        "",
        "Bullets below were distilled from previous workflow runs in this repo.",
        "They are evidence, not rules — apply judgment.",
        "",
    ]

    if highly:
        lines.append("**Highly relevant** (touch files you're working with):")
        for lesson in highly:
            lines.append(_format_lesson_bullet(lesson))
        lines.append("")

    if other:
        lines.append("**Other lessons from past work in this role:**")
        for lesson in other:
            lines.append(_format_lesson_bullet(lesson))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _format_lesson_bullet(lesson: Lesson) -> str:
    return (
        f"- [{lesson.severity}] {lesson.claim}"
        f" _(run {lesson.evidence_run_id})_"
    )
