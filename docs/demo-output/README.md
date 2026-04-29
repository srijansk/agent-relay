# Compounding-effect demo — captured evidence

This directory contains the **real artifacts** produced by running
[`scripts/capture-compounding-demo.sh`](../../scripts/capture-compounding-demo.sh)
against `gpt-4o` on 2026-04-29. They show — concretely — that a planner who
can read lessons distilled from past reviewer rejections approves on the
first try where a planner without those lessons does not.

## What was run

Two `bug-rca-fix` workflows, in order, in a fresh repo:

1. **Run 1** (no lessons available) — a timezone-handling bug on
   `/v1/orders?since=...`, given with **intentionally thin context**
   (just enough to identify the file and the symptom).
2. `relay distill --llm` over Run 1's history — produces 5 forward-looking
   second-person lessons (file: [`LESSONS.md`](LESSONS.md)).
3. **Run 2** (lessons in planner's prompt) — a different bug in the same
   class: a feature-flag config-coercion issue on `enable_metrics: "false"`.

## What the lessons looked like

`relay distill --llm` produced these 5 lessons from Run 1 ([`LESSONS.md`](LESSONS.md)):

```
## Planner (5)

- [warn] Explicitly include steps to review and test adjacent code paths
  for similar issues when addressing a bug.
- [warn] Include a specific failing test in the plan to demonstrate the
  bug before applying any fixes.
- [warn] Specify the commit hash or provide a detailed rollback procedure
  in the rollback strategy for clarity and ease of execution.
- [info] Set up the test environment to simulate different timezones to
  validate the robustness of timezone handling logic.
- [info] Consider using a more modern library like `dateutil` ...
```

The first three lessons are the substantive ones — direct compressions of
bullets the reviewer flagged as "Required Changes" in Run 1.

## Side-by-side: what the planner produced

| | Run 1 (no lessons in prompt) | Run 2 (5 lessons in prompt) |
|---|---|---|
| Plan file | [`run-1-no-lessons/plan.md`](run-1-no-lessons/plan.md) | [`run-2-with-lessons/plan.md`](run-2-with-lessons/plan.md) |
| Failing-test-first? | Mentions a "Failing Test" but reviewer flagged it as not concrete enough | **Yes** — names `test_check_metrics_enabled_with_quoted_false` explicitly as the new test that demonstrates the bug |
| Rollback specificity | "Revert the changes by checking out the previous commit using its hash. Ensure that the commit hash is documented before making changes." (vague — what commit? what file?) | **"Revert the commit that modifies `src/myapp/router.py`"** (names the file and the change set) |
| Adjacent paths | Mentions "Review and test any other date parsing or filtering functions" generically; reviewer said this wasn't enough | **References "Adjacent paths" from `hypothesis.md`** explicitly and adds tests for "other configuration flags that might be affected by similar issues" |
| Reviewer verdict | **REQUEST_CHANGES** ([`run-1-no-lessons/plan_review.md`](run-1-no-lessons/plan_review.md)) | **APPROVE on first pass** ([`run-2-with-lessons/plan_review.md`](run-2-with-lessons/plan_review.md)) |

## What the reviewer said about Run 2

The reviewer's APPROVE message ([`run-2-with-lessons/plan_review.md`](run-2-with-lessons/plan_review.md)) cites each of the three substantive lessons by name:

> The plan addresses the bug as described in the hypothesis by modifying
> the `check_metrics_enabled` function to correctly interpret the string
> `"false"` as a boolean `False`. **The plan includes a failing test-first
> approach** with specific tests to verify the fix and prevent regressions.
> **The rollback strategy is concrete, specifying the file and nature of
> the change to be reverted.** The plan also **considers adjacent paths
> that might be affected by similar issues**, ensuring comprehensive
> coverage.

That's not a coincidence. Those three sentences map 1:1 to the three
warn-level lessons that were in the planner's prompt before it wrote the
plan.

## Iteration counts

- **Run 1** — planner went through its iteration cap on the plan-review
  loop (see Run 1's plan_review for the unresolved Required Changes).
- **Run 2 (planner side)** — APPROVE on iteration 1.
- **Run 2 (implementer side)** — went through 3 implementation iterations
  before hitting the implement cap. The implement-side audit checks are a
  different surface than what the lessons currently cover; future work
  could extract implementer-audience lessons from auditor catches the same
  way we extract planner-audience lessons from reviewer rejections.

## Caveats for honest reading

- A single-trial demo. Run it on your own key with your own task class to
  see how it behaves on your code. The strength of the effect depends on
  the model and on how well your reviewer roles state their approve criteria.
- The two bugs (timezone handling vs. config coercion) are different
  domains but both fall under "missing-failing-test / vague-rollback /
  adjacent-paths" review patterns — which is exactly the kind of class
  the lessons compress over.
- Run-2's implementer-side iteration cap shows the loop's other guard
  rails are still working; lessons accelerate planning but don't
  eliminate audit findings (and shouldn't).

## Reproduce locally

```bash
export OPENAI_API_KEY=sk-...     # or ANTHROPIC_API_KEY=sk-ant-...
./scripts/capture-compounding-demo.sh
# Captures land at /tmp/relay-compounding-demo/run{1,2}-plan.md
```
