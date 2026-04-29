# Lessons (compiled by `relay distill`)

Distilled from past workflow runs in `.relay/history/`.
These are evidence-backed observations, not absolute rules — apply judgment.

Manual edits to this file are preserved across `relay distill` runs when
added under a `## Manual notes` section at the bottom.

## Implementer (1)

- **[error]** Show before/after test output in `build_log.md`, not just
  claim "the test passes" _(run 20260318-1042-bug-rca-fix — files: build_log.md)_

## Planner (2)

- **[warn]** When fixing a config-loader bug, also cover adjacent flags
  flagged in `hypothesis.md` — otherwise the next bug ships next quarter
  _(run 20260428-0930-bug-rca-fix — files: hypothesis.md, config.py)_
- **[info]** Consider property tests over the cartesian product of YAML
  scalar types × flag names _(run 20260428-0930-bug-rca-fix)_

## Manual notes

(Add notes here. They are preserved across `relay distill` runs.)
