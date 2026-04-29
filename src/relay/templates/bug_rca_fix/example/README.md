# Example run — `bug-rca-fix`

This directory contains the **real captured output** of running the
`bug-rca-fix` template end-to-end against `gpt-4o` via OpenAI.

## How this was generated

```bash
relay init --template bug-rca-fix
# write context.md describing the bug
relay run --loop --backend openai
relay distill
```

## What's here

- `artifacts/context.md` — the bug report fed to the loop (a YAML config
  loader silently coerces the string `"false"` to a truthy Python value)
- `artifacts/repro.md` — minimal reproduction (rca_reproducer)
- `artifacts/hypothesis.md` — root cause analysis (rca_hypothesizer)
- `artifacts/plan.md` — fix plan (planner)
- `artifacts/plan_review.md` — reviewer's verdict (APPROVE on first pass
  on this run)
- `artifacts/build_log.md` — what the implementer changed
- `artifacts/audit.md` — auditor's verification (APPROVE)
- `LESSONS.md`, `lessons.json` — what `relay distill` produced from
  this run plus a second deliberately-degraded run on a different
  bug. The second run hit the iteration cap (reviewer kept rejecting
  on real grounds: missing failing test, vague rollback) — those
  rejections are exactly what the planner inherits next time.

## Notes on the captured artifacts

The artifacts are unedited raw model output. You may notice:

- `repro.md` is wrapped in ` ```markdown ` fences — that's the model's
  habit, not a bug in agent-relay. We leave it untouched so you see
  what `gpt-4o` actually produces.
- The reviewer approved on first pass for this particular bug. That's
  realistic when the context names files, expected behaviour, and
  constraints clearly. When the context is sparse, the reviewer
  rejects — see the `LESSONS.md` entries from the second run for
  examples of that.
