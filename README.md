# Agent Relay

**Docker Compose for AI agents.** Define multi-agent workflows as config files. Orchestrate from your terminal. Works with any agent tool.

```
pip install agent-relay
```

---

## Quick Start (30 seconds)

```bash
# Initialize a 4-agent workflow (Planner → Reviewer → Implementer → Auditor)
relay init --template plan-review-implement-audit

# See the current state
relay status

# Get the prompt for the next agent — copy into Cursor, Codex, Aider, or any tool
relay next

# After the agent finishes, advance the workflow
relay advance

# Or launch the TUI dashboard
relay dash
```

That's it. No API keys required. No backend configuration. Just `relay next`, copy the prompt, paste into your agent tool, and `relay advance` when done.

---

## What It Does

Agent Relay coordinates multiple AI agents through a **file-based protocol**:

1. You define a **workflow** (stages, roles, transitions) in `workflow.yml`
2. Each role has **behavioral rules** and knows what files to read/write
3. A **state machine** tracks which agent should run next
4. Agents hand off work through **shared artifact files** (plans, reviews, build logs)

```
    ┌──────────┐     ┌──────────┐     ┌─────────────┐     ┌─────────┐
    │ PLANNER  │ ──► │ REVIEWER │ ──► │ IMPLEMENTER │ ──► │ AUDITOR │ ──► DONE
    │          │     │          │     │             │     │         │
    │ plan.md  │     │review.md │     │build_log.md │     │audit.md │
    └──────────┘     └──────────┘     └─────────────┘     └─────────┘
         ▲                │                                     │
         └── changes ─────┘                 ▲                   │
                                            └── changes ────────┘
```

## Why Not Just Use CrewAI / LangGraph / AutoGen?

| Feature | CrewAI / LangGraph | Agent Relay |
|---------|-------------------|-------------|
| How you define agents | Write Python code | Write YAML config |
| Runtime | Locked to their framework | **Works with any tool** (Cursor, Codex, Aider, Ollama, ChatGPT) |
| Where state lives | In memory / database | **In your repo** (version-controlled files) |
| Human in the loop | Afterthought | **First-class** (`relay next` → copy-paste → `relay advance`) |
| Entry point | Install SDK, write code, configure API keys | `pip install agent-relay && relay init` |

Agent Relay is the **glue layer** between your agent tools and your workflow. It doesn't replace your agents — it coordinates them.

---

## The Protocol

Everything lives in `.relay/` in your repo:

```
.relay/
  relay.yml                    # Global config (default workflow, backend)
  workflows/
    default/
      workflow.yml             # State machine definition
      state.yml                # Current state (auto-managed)
      roles/
        planner.yml            # Behavioral rules for planner agent
        reviewer.yml           # Behavioral rules for reviewer agent
        ...
      artifacts/
        context.md             # Project context (you fill this in)
        plan.md                # Written by planner, read by reviewer
        plan_review.md         # Written by reviewer, read by planner
        build_log.md           # Written by implementer
        ...
```

### workflow.yml

```yaml
name: "my-project"
version: 1

roles:
  planner:
    description: "Creates implementation plans"
    writes: [plan.md]
    reads: [context.md, plan_review.md]
    rules: roles/planner.yml

  reviewer:
    description: "Reviews plans for correctness"
    writes: [plan_review.md]
    reads: [context.md, plan.md]
    rules: roles/reviewer.yml

stages:
  plan_draft:    { agent: planner,  next: plan_review }
  plan_review:   { agent: reviewer, next: { approve: done, reject: plan_changes } }
  plan_changes:  { agent: planner,  next: plan_review }
  done:          { terminal: true }

initial_stage: plan_draft
limits:
  max_plan_iterations: 5
```

### roles/*.yml

```yaml
name: reviewer
system_prompt: |
  You are a Reviewer. Critically evaluate the plan for
  correctness, completeness, and feasibility.

output_format: |
  ## Verdict: APPROVE | REQUEST_CHANGES
  ## Summary: ...
  ## Required Changes: ...

verdict_field: "Verdict"
approve_value: "APPROVE"
reject_value: "REQUEST_CHANGES"
```

The `verdict_field` enables **automatic branching**: Relay reads the agent's output, extracts the verdict, and follows the correct branch in the state machine.

---

## CLI Commands

| Command | What it does |
|---------|-------------|
| `relay init` | Create a new workflow |
| `relay init --template plan-review-implement-audit` | Use the built-in 4-agent template |
| `relay init --name feature-x` | Create a named workflow (multiple per repo) |
| `relay status` | Show current stage, active role, iterations |
| `relay next` | Print the prompt for the next agent |
| `relay advance` | Advance to the next stage (auto-extracts verdict for branching) |
| `relay run` | Run with backend (manual: print + wait) |
| `relay run --loop` | Run the full loop until done or limit hit |
| `relay dash` | TUI dashboard |
| `relay reset` | Reset to initial stage |
| `relay reset --clean` | Reset + wipe artifacts |
| `relay validate` | Check workflow.yml for errors |
| `relay export cursor` | Export to Cursor `.mdc` rules + prompts |

## Multiple Workflows

Run multiple workflows in the same repo:

```bash
relay init --name ark-m0 --template plan-review-implement-audit
relay init --name ark-m1 --template plan-review-implement-audit

relay status --workflow ark-m0
relay next --workflow ark-m1
```

---

## Built-in Templates

### plan-review-implement-audit

The classic 4-agent loop:

- **Planner** creates an implementation plan
- **Reviewer** critically reviews it (APPROVE / REQUEST_CHANGES)
- **Implementer** builds it, maintaining a build log
- **Auditor** verifies correctness, catches shortcuts (APPROVE / REQUEST_CHANGES)

```bash
relay init --template plan-review-implement-audit
```

More templates coming: `code-review`, `research-write-edit`, `debug-fix-verify`.

---

## Export to Cursor

If you use Cursor IDE, you can export your workflow to Cursor-native format:

```bash
relay export cursor
```

This generates `.cursor/rules/*.mdc` files and `.cursor/prompts/*.txt` files that you can use directly in Cursor's agent sessions.

---

## Backends (How Agents Get Invoked)

Agent Relay supports multiple backends for invoking agents:

| Backend | Command | What it does |
|---------|---------|-------------|
| **manual** (default) | `relay run` | Prints prompt, waits for you to paste into your tool and press Enter |
| **openai** | `relay run --backend openai` | Calls OpenAI API (gpt-4o by default), writes response to artifact file |
| **anthropic** | `relay run --backend anthropic` | Calls Anthropic API (Claude), writes response to artifact file |
| **cursor** | `relay run --backend cursor` | Invokes Cursor CLI (requires `cursor` in PATH) |

### Fully automated loop

```bash
# Run the entire workflow end-to-end with OpenAI
export OPENAI_API_KEY=sk-...
relay run --loop --backend openai

# Or with Anthropic
export ANTHROPIC_API_KEY=sk-ant-...
relay run --loop --backend anthropic
```

### Configure the default backend

Set it in `.relay/relay.yml`:

```yaml
default_workflow: default
backend: openai
backend_config:
  model: gpt-4o-mini
  temperature: 0.2
  max_tokens: 16384
```

### Install backend dependencies

```bash
pip install agent-relay[openai]      # For OpenAI backend
pip install agent-relay[anthropic]   # For Anthropic backend
```

---

## How It Works (Under the Hood)

1. **Protocol layer**: Pydantic v2 models validate `workflow.yml` and `roles/*.yml` with clear error messages
2. **State machine**: Tracks the current stage, resolves transitions (linear or branching via verdict extraction)
3. **Verdict extraction**: Regex parses agent output for `## Verdict: APPROVE` patterns
4. **Backends**: Pluggable agent invocation — manual, OpenAI, Anthropic, Cursor CLI
5. **TUI**: Textual-based dashboard shows live workflow state

---

## Development

```bash
git clone https://github.com/your-org/agent-relay.git
cd agent-relay
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

---

## License

MIT
