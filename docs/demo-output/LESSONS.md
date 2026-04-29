# Lessons (compiled by `relay distill`)

Distilled from past workflow runs in `.relay/history/`.
These are evidence-backed observations, not absolute rules — apply judgment.

Manual edits to this file are preserved across `relay distill` runs when
added under a `## Manual notes` section at the bottom.

## Planner (5)

- **[warn]** Explicitly include steps to review and test adjacent code paths for similar issues when addressing a bug. _(run 20260429-1445-bug-rca-fix-tz — files: src/api/orders.py, src/utils/datetime.py)_
- **[warn]** Include a specific failing test in the plan to demonstrate the bug before applying any fixes. _(run 20260429-1445-bug-rca-fix-tz)_
- **[warn]** Specify the commit hash or provide a detailed rollback procedure in the rollback strategy for clarity and ease of execution. _(run 20260429-1445-bug-rca-fix-tz)_
- **[info]** Set up the test environment to simulate different timezones to validate the robustness of timezone handling logic. _(run 20260429-1445-bug-rca-fix-tz)_
- **[info]** Consider using a more modern library like `dateutil` or Python's built-in `datetime` module with timezone support for handling timezone conversions. _(run 20260429-1445-bug-rca-fix-tz)_
