# Example run — `plan-review-implement-audit`

This directory contains the **real captured output** of running the
`plan-review-implement-audit` template end-to-end against `gpt-4o`
via OpenAI.

## How this was generated

```bash
relay init --template plan-review-implement-audit
# write context.md and acceptance_checklist.md
relay run --loop --backend openai
relay distill
```

## What's here

- `artifacts/context.md` — feature request (add `GET /healthz`
  endpoint to a FastAPI service)
- `artifacts/acceptance_checklist.md` — explicit acceptance criteria
  the reviewer + auditor check against
- `artifacts/plan.md` — implementation plan
- `artifacts/plan_review.md` — reviewer's verdict (APPROVE on second
  pass after addressing required changes)
- `artifacts/build_log.md` — what the implementer changed
- `artifacts/build_review.md` — auditor's verification (APPROVE)
- `LESSONS.md`, `lessons.json` — distilled from this run plus a
  second deliberately-sparse-context run that hit the implement
  iteration cap. The auditor's `## MUST_FIX` and `## SHOULD_FIX`
  sections from that run are what compiled into the implementer-
  audience lessons here.

## Notes

The `plan-review-implement-audit` template's reviewer and auditor
roles were calibrated in v0.2 to default toward APPROVE when explicit
acceptance criteria are met (rather than always asking for more
polish). Without that calibration, LLM reviewers tend to interpret
"be strict but fair" as "always REQUEST_CHANGES" — see the
v0.2 design spec at `docs/specs/2026-04-28-v0.2-design.md` for the
reasoning.
