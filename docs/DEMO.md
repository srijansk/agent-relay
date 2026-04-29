# `agent-relay` demo

Two demos live here:

1. **The mechanical loop** (no API key needed) — shows how the workflow drives,
   and how compiled lessons get injected into a planner's prompt.
2. **The compounding effect** (your API key needed) — runs two related bugs
   end-to-end and shows that Run 2's plan addresses things Run 1 got rejected on.

The first one is the part you can verify by reading. The second one is the
part you have to run yourself, because the empirical claim ("the planner
gets better with more runs") is only meaningful when measured on your
machine, against your model.

---

## 1. Mechanical loop (~30 seconds, no API key)

```bash
$ pip install git+https://github.com/srijansk/agent-relay.git

$ mkdir relay-demo && cd relay-demo
$ relay init --template bug-rca-fix
Workflow 'default' initialized at .relay/workflows/default
Next: run 'relay status' to see the current state

$ relay status
        Workflow: bug-rca-fix
┌─────────────┬───────────────┐
│ Stage       │ reproduce     │
│ Active Role │ rca_reproducer│
│ Type        │ Linear        │
└─────────────┴───────────────┘

$ relay next                      # prints the prompt to paste into your tool

╭──────────────── Prompt for: rca_reproducer ────────────────╮
│ You are: rca_reproducer                                    │
│ Role: Reproduces the bug deterministically                 │
│                                                            │
│ You are the Reproducer. Your sole responsibility is to     │
│ produce a minimal, deterministic reproduction of the bug   │
│ described in `context.md` and write it to `repro.md`.      │
│ ...                                                        │
╰────────────────────────────────────────────────────────────╯

# (paste into Claude Code / Cursor / ChatGPT / Aider; agent writes repro.md)

$ relay advance                   # state machine moves to `hypothesize`
Advanced: rca_reproducer → hypothesize
Next agent: rca_hypothesizer. Run 'relay next' to see the prompt.
```

That's the whole interface. Six commands (`init`, `status`, `next`, `advance`,
`run`, `distill`) drive any workflow defined in `workflow.yml`.

---

## 2. The lessons section appears in the prompt

This is provable without ever calling an LLM. We can read what `relay next`
produces before vs after lessons exist.

```bash
# Set up. Use the bug-rca-fix template, which sets inject_lessons: true on
# the planner role.
$ relay init --template bug-rca-fix

# Without any history, the planner's prompt has no lessons section.
$ relay advance && relay advance && relay next | grep -A 2 "Lessons from past runs"
# (no match — section absent)

# Drop a synthetic past run into .relay/history/ with a real Required Changes
# bullet, then distill.
$ mkdir -p .relay/history/20260428-0930-bug-rca-fix/artifacts
$ cat > .relay/history/20260428-0930-bug-rca-fix/artifacts/plan_review.md <<EOF
## Verdict: REQUEST_CHANGES

## Required Changes
- The plan ignores the rollback section. Always name the change set the
  rollback would revert.
EOF
$ relay distill
Distilled 1 lesson(s) from 1 run(s) (heuristic).

# Now `relay next` for the planner stage includes a "Lessons from past runs"
# section, with the bullet attributed to the planner audience (because the
# bullet came from a reviewer's Required Changes).
$ relay next | grep -A 4 "Lessons from past runs"
## Lessons from past runs

Bullets below were distilled from previous workflow runs in this repo.
They are evidence, not rules — apply judgment.
```

This is what "compounding" looks like at the prompt-injection level: the
planner is reading lessons distilled from previous reviewer rejections
*before* it writes its plan. The agent's behavioural improvement is a
function of how good the planner is at reading those lessons.

The mechanism is also enforced by an end-to-end test:
[`tests/e2e/test_lessons_compounding.py`](../tests/e2e/test_lessons_compounding.py)
sets up a 2-run scenario and asserts a Run-1 reviewer rejection surfaces
in Run-2's planner prompt.

---

## 3. The empirical compounding effect (your API key)

Whether the planner *uses* the lessons usefully is empirical. To see it:

```bash
# Use either backend.
export OPENAI_API_KEY=sk-...
./scripts/capture-compounding-demo.sh

# Or:
export ANTHROPIC_API_KEY=sk-ant-...
PROVIDER=anthropic MODEL=claude-sonnet-4-6 ./scripts/capture-compounding-demo.sh
```

The script is at [`scripts/capture-compounding-demo.sh`](../scripts/capture-compounding-demo.sh).
It:

1. Runs `bug-rca-fix` on a bug with intentionally thin context. The reviewer
   typically rejects on missing failing-test or vague rollback. The loop
   reaches its iteration cap; the rejected artifacts get snapshotted to
   `.relay/history/`.
2. Calls `relay distill --llm` (or heuristic if you pass `USE_LLM_DISTILL=0`)
   and writes `.relay/LESSONS.md`.
3. Runs `bug-rca-fix` on a different bug in the same task class. Because
   `inject_lessons: true` is set on the planner role, Run 2's planner sees
   Run 1's lessons in its prompt.
4. Saves both `plan.md` files at `/tmp/relay-compounding-demo/run{1,2}-plan.md`
   so you can diff them.

The empirical claim — *Run 2's plan addresses Run 1's rejection categories
from the start* — is what you'll want to confirm yourself. The strength of
the effect depends on your model. Sonnet 4.6 and gpt-4o both show it
clearly; smaller models will benefit but less reliably.

---

## 4. What the captured examples in this repo show

Each template ships with a real run captured against `gpt-4o`:

| Template | Where | What it shows |
|---|---|---|
| `bug-rca-fix` | [`templates/bug_rca_fix/example/`](../src/relay/templates/bug_rca_fix/example/) | Happy-path 5-stage bug fix + a second sparse-context run that produced rejections; LESSONS.md compiled from both |
| `rfc-then-implement` | [`templates/rfc_then_implement/example/`](../src/relay/templates/rfc_then_implement/example/) | RFC → review → implement → audit, all approved on first pass (real model output, no rejections — LESSONS.md is empty by design) |
| `plan-review-implement-audit` | [`templates/plan_review_impl_audit/example/`](../src/relay/templates/plan_review_impl_audit/example/) | Healthz endpoint built end-to-end; LESSONS.md compiled from a happy-path run plus a sparse-context run that hit the implementer cap |

Read the artifacts. They are unedited model output. The reviewer's
"Required Changes" sections in the rejection runs are exactly what
`relay distill` turned into the LESSONS.md you see committed alongside.

---

## Recording your own GIF / cast (optional, for share-ables)

If you want a GIF of the loop running:

```bash
brew install asciinema agg            # or apt install
asciinema rec demo.cast               # records your terminal session
agg demo.cast demo.gif                # converts to gif
```

Then drop the GIF into the README and link the cast file. We don't
ship one in this repo because the loop output is text-first and
readable as-is — the markdown above is the canonical demo.
