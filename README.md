# agent-relay

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-165%20passing-brightgreen.svg)](#testing)

> **Multi-agent workflows that learn from their own past runs.**
> Plans, reviews, build logs, and audits land in your repo as committed
> artifacts. `relay distill` compiles them into role-typed lessons your
> next planner reads — so the same task class gets cheaper every time.

```bash
pip install git+https://github.com/srijansk/agent-relay.git
```

---

## In 30 seconds

```bash
# Initialise a 5-stage bug-fix workflow (reproduce → hypothesise → plan → fix → verify)
relay init --template bug-rca-fix

# See the prompt for whichever role is active
relay next                       # paste it into Claude Code, Cursor, Codex...

# After the agent writes its artifact (plan.md / audit.md / ...), advance
relay advance

# When the workflow completes, it snapshots to .relay/history/<run-id>/.
# Compile lessons from accumulated history at any time:
relay distill                    # heuristic: parse rejection bullets, role-typed
relay distill --llm              # LLM-backed: groups bullets, rewrites in second-person

# Run the next workflow on a similar bug — the planner's prompt now includes
# every lesson the reviewer flagged in past runs, scoped to files you're touching.
```

You can also let agent-relay drive the whole loop end-to-end with a backend:

```bash
export ANTHROPIC_API_KEY=...
relay run --loop --backend anthropic
```

**See it run:** [`docs/DEMO.md`](docs/DEMO.md) walks the full mechanical loop
(no API key). For real-model evidence,
[`docs/demo-output/`](docs/demo-output/) contains a captured run where Run 2
(with 5 LLM-distilled lessons in the planner's prompt) was approved on first
pass after Run 1 (no lessons) needed multiple iterations — the reviewer's
APPROVE message cites each lesson by name. Reproduce on your own key with
[`scripts/capture-compounding-demo.sh`](scripts/capture-compounding-demo.sh).

---

## What's different

Every other multi-agent framework hides workflow state inside its runtime —
LangGraph checkpoints, CrewAI processes, Claude Code session files,
AGENTS.md as a single hand-written file. **agent-relay puts the state, the
artifacts, and the compiled lessons in your git repo as markdown.**

| | agent-relay | LangGraph / CrewAI / AutoGen | Claude Code subagents | AGENTS.md | agentic-stack |
|---|---|---|---|---|---|
| Workflow defined as | YAML | Python code | Markdown agents | One markdown file | SOUL.md configs |
| State lives in | `.relay/` (git) | Runtime / DB | Session store | n/a | `.agent/memory/` |
| Artifacts visible in PRs | **Yes** | No | No | n/a | Partial |
| Role-typed lessons compiled from past runs | **Yes** | No | No | No (one global file) | Memory layers, not workflow-typed |
| Tool-agnostic (Claude Code, Cursor, Codex, etc.) | **Yes** | Locked to its runtime | Claude Code only | Multi-tool but no workflow primitive | Multi-harness adapter |
| Human-edits-the-knowledge | **Yes** (LESSONS.md is markdown) | Indirect | Indirect | Yes | Via graduate / reject CLI |

## Why bother committing the workflow to git?

Two reasons. The first one is obvious; the second is the reason for v0.2.

1. **Audit trail.** Every PR carries the plan the agents wrote, the
   reviewer's verdict, the implementer's build log, the auditor's catches.
   A human reviewer can argue with each agent at the artifact level instead
   of just inspecting the final code.

2. **Compounding improvement.** When `relay distill` runs over your
   `.relay/history/`, it produces typed lessons:
   - the *reviewer's* rejections become lessons FOR the planner ("don't
     skip the rollback test next time"),
   - the *auditor's* catches become lessons FOR the implementer ("show
     before/after test output, don't just claim a fix worked"),
   - their tags pick up file paths so a planner working on `state.py`
     gets `state.py`-relevant lessons highlighted as "highly relevant"
     in its next prompt.

   The lessons are markdown in your repo. You can edit them. PR reviewers
   can edit them. Stale lessons get pruned the way you'd prune any other
   document. The agents read what your team writes back in.

---

## Templates (v0.2)

| Template | What it's for |
|---|---|
| [`bug-rca-fix`](src/relay/templates/bug_rca_fix/example) | 5-stage bug fix: reproduce → hypothesise → plan → review → implement → verify. Highest signal for the lessons loop because reviewer rejections and auditor catches are exactly what compounds. |
| [`rfc-then-implement`](src/relay/templates/rfc_then_implement/example) | Design-then-build: RFC → review → implement → audit. Useful for changes that need explicit alternatives + rollback before code is written. |
| [`plan-review-implement-audit`](src/relay/templates/plan_review_impl_audit) | The classic 4-role loop. Generic enough for most non-trivial features. |

Each template ships with a worked example under `example/` — actual
artifacts from a representative run plus the `LESSONS.md` that
`relay distill` produces from it. **Read those before customising.**

---

## CLI

| Command | What it does |
|---|---|
| `relay init [--template NAME]` | Create a new workflow from a built-in template, or a minimal custom one |
| `relay status` | Print the current stage, active role, iteration counters |
| `relay next` | Print the prompt for the active role (with lessons auto-loaded if enabled) |
| `relay advance [--verdict approve\|reject]` | Advance the state machine after the role finishes |
| `relay run [--loop] [--backend NAME]` | Drive the workflow with a backend (manual / openai / anthropic / cursor) |
| `relay distill [--llm]` | Compile typed lessons from `.relay/history/` into `LESSONS.md` + `lessons.json` |
| `relay export claude-code` | Generate `.claude/agents/*.md` + `.claude/commands/relay-*.md` |
| `relay export cursor` | Generate `.cursor/rules/*.mdc` + prompts |
| `relay validate` | Check `workflow.yml` for errors |
| `relay reset [--clean]` | Reset to the initial stage (optionally wipe artifacts) |
| `relay dash` | Launch the TUI dashboard |

---

## How lessons compounding actually works

**Run 1.** You use `bug-rca-fix` to fix a bug in `src/app/config.py`. The
reviewer rejects the first plan with: *"plan ignores adjacent flags
`enable_metrics` and `enable_audit` in the same loader — fix them too."*
The planner addresses it on the second pass; the workflow ships.

When the workflow reaches `done`, agent-relay snapshots to
`.relay/history/20260428-0930-bug-rca-fix/`. The artifacts (plan, review,
audit, build log) are committed as part of your PR.

**`relay distill`** parses the snapshot and writes:

```markdown
## Planner (1)
- **[warn]** When fixing a config-loader bug, also cover adjacent flags
  flagged in hypothesis.md — otherwise the next bug ships next quarter.
  _(run 20260428-0930-bug-rca-fix — files: hypothesis.md, config.py)_
```

**Run 2.** A week later, a different bug in the same loader. You re-run
`relay init --template bug-rca-fix`. When the planner stage activates,
`relay next` prints a prompt that includes:

```markdown
## Lessons from past runs
**Highly relevant** (touch files you're working with):
- [warn] When fixing a config-loader bug, also cover adjacent flags
  flagged in hypothesis.md — otherwise the next bug ships next quarter.
  _(run 20260428-0930-bug-rca-fix)_
```

The planner sees the lesson before it writes the plan. Reviewer rejection
rates on the same task class go down across runs because the planner
inherited what the reviewer caught last time.

The lessons file is markdown. If a lesson is wrong, edit it. If a lesson
is stale, delete it. The agent reads what your team curates.

---

## Configuration

`.relay/relay.yml`:

```yaml
default_workflow: default
backend: manual                # manual | openai | anthropic | cursor
max_artifact_chars: 50000

history:
  enabled: true                # snapshot completed runs to .relay/history/

lessons:
  max_per_role: 10             # cap injected lessons per planner prompt

# Optional: backend config
backend_config:
  model: claude-sonnet-4-5
  temperature: 0.2
```

Per-role opt-in for lessons injection (`roles/planner.yml`):

```yaml
name: planner
system_prompt: |
  ...
inject_lessons: true            # default false
```

The shipped `bug-rca-fix`, `rfc-then-implement`, and
`plan-review-implement-audit` templates all set this on planner / architect
roles. Other roles default to off — your choice when authoring custom
workflows.

---

## Testing

```bash
git clone https://github.com/srijansk/agent-relay.git
cd agent-relay
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,openai,anthropic]"
pytest
```

165 tests across unit / integration / e2e. CI is fully deterministic: the
heuristic distillation does no network I/O, and the LLM-backed distillation
is unit-tested with an injected fake `llm` callable so no real API calls
are made during `pytest`. To exercise live LLM distill, set
`OPENAI_API_KEY` or `ANTHROPIC_API_KEY` and run
`relay distill --llm` against a populated `.relay/history/`.

---

## Status

- v0.2.0 — adds persisted history, lessons compiler, planner auto-load,
  two new templates (`bug-rca-fix`, `rfc-then-implement`), Claude Code
  exporter
- v0.1.0 — file-based protocol, state machine, manual / OpenAI / Anthropic
  / Cursor backends, intelligent orchestrator

See [CHANGELOG.md](CHANGELOG.md) and
[`docs/specs/2026-04-28-v0.2-design.md`](docs/specs/2026-04-28-v0.2-design.md)
for the design behind v0.2.

## Contributing

Open an issue to discuss what you'd like to change. PRs welcome — the same
`bug-rca-fix` and `plan-review-implement-audit` templates that ship in
this repo are how the maintainers ship features here.

## License

MIT — see [LICENSE](LICENSE).
