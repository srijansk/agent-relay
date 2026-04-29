"""Lessons compiler — distill role-typed lessons from past run artifacts.

The lessons compiler turns the markdown produced by past workflow runs into
typed, in-repo knowledge that the next planner can read. Two modes:

  * Heuristic (default, deterministic) — parses known section headers
    (Required Changes, Concerns, Catches, MUST_FIX, Findings, ...) and
    extracts bullet points as lesson candidates. No LLM. CI-friendly.
    Each rejection bullet becomes one Lesson, hashed for idempotency.

  * LLM (``--llm``, opt-in) — sends the same harvested rejection bullets
    to the configured backend with a structured prompt that asks the
    model to:
      - group bullets that describe the same recurring concern,
      - rewrite each group as a single forward-looking second-person
        lesson ("Always include a failing test before fixing a bug"),
      - drop run-specific noise that won't recur,
      - preserve provenance (which run-ids contributed).
    Falls back to heuristic if the backend is unavailable or the response
    is malformed — the heuristic is the floor.

Output is two artifacts at ``.relay/``:

  * ``LESSONS.md`` — human-readable, organised by role and severity
  * ``lessons.json`` — typed, machine-readable (consumed by prompt injection)
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

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


# ---------------------------------------------------------------------------
# LLM-backed distillation
# ---------------------------------------------------------------------------

# Pluggable callable for the actual LLM round-trip. Tests inject a fake; the
# CLI injects ``call_llm_for_distill`` (below) which speaks to OpenAI or
# Anthropic. The signature is intentionally narrow so a mock is one line.
LlmCaller = Any  # Callable[[str, str], str] — system prompt + user prompt → response text


_LLM_SYSTEM_PROMPT = """You are a Lessons Compiler for a multi-agent code-workflow system.

Your job: given critique bullets from past workflow runs (one role's audience),
produce a small set of forward-looking, second-person lessons that the next
agent of that role should read before starting its task.

Rules:
1. GROUP bullets that describe the same recurring concern. One lesson per group.
2. WRITE each lesson in second-person, forward-looking imperative voice:
     YES: "Always include a failing test before fixing a bug."
     YES: "Don't disable an existing test to make the suite pass; fix the root cause."
     NO:  "Step 3 doesn't specify the migration order in run 20260428-0930."
3. SEVERITY:
     - "error" for hard mistakes (disabled tests, ignored constraints, security shortcuts)
     - "warn"  for recurring planning/scope gaps (missing rollback, missing failing test)
     - "info"  for polish-level concerns (naming, comments, doc nits)
4. DROP bullets that are run-specific and unlikely to recur on a different task.
5. PRESERVE provenance: include every run-id whose bullet contributed.
6. Infer file/path TAGS from bullet text where possible.

Return ONLY a JSON array of lesson objects, no prose. Schema:
[
  {
    "claim": "<forward-looking second-person sentence>",
    "severity": "error" | "warn" | "info",
    "source_runs": ["<run-id>", "..."],
    "tags": ["<file-or-module>", "..."]
  }
]
"""


def _bullets_to_llm_user_prompt(role: str, bullets: list[Lesson]) -> str:
    """Render the heuristic-extracted bullets as the LLM input."""
    lines = [
        f"# Audience role: {role}",
        f"# {len(bullets)} bullets from past runs:",
        "",
    ]
    for lesson in bullets:
        run_id = lesson.evidence_run_id
        text = lesson.evidence_excerpt or lesson.claim
        lines.append(f"- (run {run_id}) [{lesson.severity}] {text}")
    return "\n".join(lines)


def _parse_llm_response(text: str) -> list[dict[str, Any]]:
    """Pull the JSON array out of an LLM response.

    The model may wrap the array in markdown fences or prose. Be lenient.
    """
    # Strip markdown fences if present.
    fence_match = re.search(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL)
    candidate = fence_match.group(1) if fence_match else text
    # Find the first '[' through the last ']'.
    first = candidate.find("[")
    last = candidate.rfind("]")
    if first < 0 or last <= first:
        raise ValueError("No JSON array found in LLM response")
    payload = candidate[first : last + 1]
    parsed = json.loads(payload)
    if not isinstance(parsed, list):
        raise ValueError("LLM response was not a JSON array")
    return parsed


def call_llm_for_distill(
    *,
    provider: str,
    model: str,
    api_key: str | None,
    system_prompt: str,
    user_prompt: str,
    timeout_s: float = 60.0,
) -> str:
    """Call the configured LLM provider with a system + user prompt.

    Synchronous (the distill command is one-shot, not a hot loop).
    Returns the model's response text. Raises on transport / API errors.
    """
    if provider == "openai":
        from openai import OpenAI  # imported lazily so heuristic mode has no openai dep

        client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"), timeout=timeout_s)
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=4000,
        )
        return resp.choices[0].message.content or ""

    if provider == "anthropic":
        import anthropic

        client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"), timeout=timeout_s)
        resp = client.messages.create(
            model=model,
            max_tokens=4000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        # Anthropic returns a list of content blocks; concatenate text-typed ones.
        chunks: list[str] = []
        for block in resp.content:
            text = getattr(block, "text", None)
            if text:
                chunks.append(text)
        return "".join(chunks)

    raise ValueError(f"Unsupported provider for distill: {provider}")


def distill_with_llm(
    history_dir: Path,
    *,
    llm: LlmCaller,
) -> list[Lesson]:
    """Distill lessons by sending heuristic-extracted bullets to an LLM.

    Strategy:
      1. Walk history with the heuristic extractor — gives raw bullets, role
         attribution, and run-id provenance.
      2. Group by audience role.
      3. For each role, ask the LLM to compress the bullets into forward-
         looking second-person lessons (groups of related bullets become
         one lesson; provenance is preserved as ``source_runs``).
      4. Convert the LLM's structured output into ``Lesson`` records, marked
         ``source="llm"``.
      5. If the LLM call fails for a role, fall back to that role's heuristic
         bullets — the heuristic is the floor. Other roles' LLM output is
         unaffected.

    ``llm`` is a callable ``(system_prompt, user_prompt) -> response_text`` so
    tests can inject a deterministic mock. The CLI passes a closure over
    ``call_llm_for_distill``.
    """
    raw_lessons = extract_lessons_from_history(history_dir)
    if not raw_lessons:
        return []

    by_role: dict[str, list[Lesson]] = {}
    for lesson in raw_lessons:
        by_role.setdefault(lesson.role, []).append(lesson)

    distilled: list[Lesson] = []
    severity_rank = {"error": 0, "warn": 1, "info": 2}

    for role in sorted(by_role.keys()):
        bullets = by_role[role]
        user_prompt = _bullets_to_llm_user_prompt(role, bullets)
        try:
            response = llm(_LLM_SYSTEM_PROMPT, user_prompt)
            payload = _parse_llm_response(response)
        except Exception:  # noqa: BLE001 — fall back per-role rather than crash distill
            distilled.extend(bullets)
            continue

        observed_at = max((lesson.observed_at for lesson in bullets), default=datetime.now(tz=timezone.utc))
        for entry in payload:
            claim = str(entry.get("claim", "")).strip()
            if not claim:
                continue
            severity = entry.get("severity", "warn")
            if severity not in severity_rank:
                severity = "warn"
            source_runs = entry.get("source_runs") or []
            if not isinstance(source_runs, list) or not source_runs:
                source_runs = list({lesson.evidence_run_id for lesson in bullets})
            tags = entry.get("tags") or []
            if not isinstance(tags, list):
                tags = []
            tags = [str(t) for t in tags if t]

            primary_run = sorted(str(r) for r in source_runs)[0]
            evidence = "; ".join(f"({lesson.evidence_run_id}) {lesson.claim}" for lesson in bullets[:3])[:280]
            lesson_id = _hash_id(role, claim, ",".join(sorted(str(r) for r in source_runs)))
            distilled.append(
                Lesson(
                    id=lesson_id,
                    role=role,
                    claim=claim,
                    severity=severity,
                    evidence_run_id=primary_run,
                    evidence_excerpt=evidence,
                    observed_at=observed_at,
                    tags=tags,
                    source="llm",
                )
            )

    distilled.sort(key=lambda lesson: (lesson.role, severity_rank[lesson.severity], lesson.id))
    return distilled
