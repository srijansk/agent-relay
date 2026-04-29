# Changelog

All notable changes to agent-relay are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.2.0] — 2026-04-28

### Added

- **Persisted run history.** Completed workflow runs are snapshotted to
  `.relay/history/<run-id>/` (configurable via `history.enabled` in
  `relay.yml`; default `true`). Snapshot contains a frozen copy of
  `workflow.yml`, `roles/`, `artifacts/`, and `state.yml`, plus a
  `run.yml` summary.
- **`relay distill` command.** Compiles role-typed lessons from
  `.relay/history/` into `.relay/LESSONS.md` (human) and
  `.relay/lessons.json` (machine). Heuristic mode is deterministic and
  CI-friendly; `--llm` mode is opt-in (placeholder in 0.2; falls back to
  heuristic).
- **Lessons auto-load into planner prompts.** Roles can opt in via
  `inject_lessons: true` in `roles/<name>.yml`. The injected section
  separates "Highly relevant" (lessons whose tags overlap the role's
  reads) from "Other lessons from past work in this role." Capped via
  `lessons.max_per_role` in `relay.yml` (default 10).
- **`bug-rca-fix` template.** 5-stage workflow: reproduce → hypothesise
  → plan → review → implement → verify. Includes a worked example run
  under `templates/bug_rca_fix/example/`.
- **`rfc-then-implement` template.** RFC-driven workflow with explicit
  alternatives and rollback. Worked example included.
- **`plan-review-implement-audit` template.** Updated to set
  `inject_lessons: true` on the planner role; added a worked example
  link path. No breaking changes to the existing template structure.
- **`relay export claude-code` command.** Generates `.claude/agents/`
  subagent files (one per role, with YAML frontmatter) and
  `.claude/commands/relay-*.md` slash commands wrapping the CLI.
- **Audience-not-writer semantics for lessons.** The role attribution on
  a lesson is the audience that benefits from it (the role learning
  from past work), not the role that authored the artifact. A reviewer's
  Required Changes are lessons FOR the planner; auditor's Catches are
  lessons FOR the implementer.

### Changed

- `compose_prompt` accepts `lessons_path` and `max_lessons` so the CLI
  can inject lessons when configured. Backward compatible — existing
  callers that don't pass these get the v0.1 behaviour.
- `RoleSpec` gains a default-`False` `inject_lessons` field. Existing
  role files without the field continue to load.

### Notes

- v0.2 ships 157 tests across unit / integration / e2e (up from 119 in
  v0.1). The e2e suite includes a compounding test that verifies a
  reviewer's rejection from run 1 surfaces in run 2's planner prompt.

## [0.1.0] — 2026-02-25

Initial release. File-based protocol, state machine, four backends
(manual / OpenAI / Anthropic / Cursor CLI), Cursor exporter, optional
LLM-powered orchestrator, TUI dashboard.
