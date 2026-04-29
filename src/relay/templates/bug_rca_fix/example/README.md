# Example run — `bug-rca-fix`

This directory is a worked example of running the `bug-rca-fix` template
end-to-end on a small synthetic bug.

The artifacts under `artifacts/` are the actual output that a run would
produce, captured at the moment the workflow reached its terminal stage.
They are committed here so you can read them without running the workflow
yourself.

## The bug

A YAML config loader silently coerces the string `"false"` to a truthy
Python value, causing a feature flag to behave inverted in production.

## What you'll find

- `artifacts/repro.md` — minimal reproduction
- `artifacts/hypothesis.md` — root cause analysis
- `artifacts/plan.md` — fix plan (after one round of review)
- `artifacts/plan_review.md` — the reviewer's first pass (rejected) plus
  the second pass (approved)
- `artifacts/build_log.md` — what the implementer changed
- `artifacts/audit.md` — auditor's verification
- `LESSONS.md` — what `relay distill` extracts from this run plus a
  hypothetical earlier run on the same module

The `LESSONS.md` here is what a planner running on a future bug in the same
module would see auto-injected into its prompt (because the planner role
sets `inject_lessons: true`).
