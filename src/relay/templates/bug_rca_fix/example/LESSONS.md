# Lessons (compiled by `relay distill`)

Distilled from past workflow runs in `.relay/history/`.
These are evidence-backed observations, not absolute rules — apply judgment.

Manual edits to this file are preserved across `relay distill` runs when
added under a `## Manual notes` section at the bottom.

## Planner (3)

- **[warn]** While the plan mentions reviewing other endpoints and insertion logic, it should be more focused on the specific bug. Ensure that the changes are minimal and directly related to the bug described in the hypothesis _(run 20260429-0521-bug-rca-fix)_
- **[warn]** The plan should start with implementing a failing test that demonstrates the bug. This test should clearly show that the current implementation returns orders from the previous day when today's date is passed as the `since` parameter _(run 20260429-0521-bug-rca-fix)_
- **[warn]** The rollback plan should specify the exact commit hash to revert if the changes cause issues. This ensures a clear and quick rollback process _(run 20260429-0521-bug-rca-fix)_
