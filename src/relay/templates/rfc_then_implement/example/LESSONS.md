# Lessons (compiled by `relay distill`)

Distilled from past workflow runs in `.relay/history/`.
These are evidence-backed observations, not absolute rules — apply judgment.

Manual edits to this file are preserved across `relay distill` runs when
added under a `## Manual notes` section at the bottom.

## Implementer (2)

- **[error]** Do not deviate silently from the approved RFC; amend the RFC
  if the deviation is justified _(run 20260428-1130-rfc-then-implement — files: items.py)_
- **[error]** Add tests for malformed input on every new public-API surface
  _(run 20260428-1130-rfc-then-implement — files: cursors.py)_

## Architect (2)

- **[info]** Add an example payload for any new response shape proposed
  in the RFC _(run 20260428-1130-rfc-then-implement)_
- **[info]** Document end-of-stream semantics explicitly when proposing
  cursor pagination _(run 20260428-1130-rfc-then-implement)_

## Manual notes

(Add notes here. They are preserved across `relay distill` runs.)
