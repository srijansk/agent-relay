# RFC review

## Verdict: APPROVE

## Summary

Concrete proposal, alternatives are named with reasons, rollback is real
(flag flip, no data migration). Good cursor encoding versioning.

## Strengths

- Versioned cursor encoding (`v1:<base64>`) means we can iterate the
  encoding without silent breakage.
- Sunset header on legacy responses is the correct deprecation signal.
- Risk section explicitly defers rate-limiting to separate work rather
  than smuggling it in.

## Required Changes (if REQUEST_CHANGES)

(none on this pass — RFC was approved on first review)

## Suggestions

- Add an example payload in the RFC for the new response shape — readers
  shouldn't have to infer it from the description.
- Consider documenting `next_cursor: null` semantics explicitly (signals
  end-of-stream; clients should stop polling).
