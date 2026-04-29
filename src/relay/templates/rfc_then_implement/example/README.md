# Example run — `rfc-then-implement`

This directory contains the **real captured output** of running the
`rfc-then-implement` template end-to-end against `gpt-4o` via OpenAI.

## How this was generated

```bash
relay init --template rfc-then-implement
# write context.md describing the feature request
relay run --loop --backend openai
```

## What's here

- `artifacts/context.md` — feature request (cursor-based pagination on
  a public list endpoint)
- `artifacts/rfc.md` — the architect's draft RFC
- `artifacts/rfc_review.md` — reviewer's verdict
- `artifacts/build_log.md` — implementer's record
- `artifacts/audit.md` — auditor's verification

## On the empty `LESSONS.md`

Lessons compile from rejection sections (`## Required Changes`,
`## Catches`, `## MUST_FIX`) across past runs. This particular run
went APPROVE → APPROVE → APPROVE — there were no rejections to
distill, so `relay distill` correctly emitted an empty result.

To see populated lessons output, look at
`templates/bug_rca_fix/example/LESSONS.md` — that template's example
includes a second run that hit the iteration cap, so the reviewer's
`## Required Changes` bullets compiled into real warn-level lessons.

The compounding mechanism is identical for `rfc-then-implement`:
when reviewer or auditor reject, those bullets become lessons the
next architect / implementer reads in their prompt.
