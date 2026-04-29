# Context

## Project Name

`obs-svc` — a small FastAPI service that processes incoming webhook
events and forwards them to downstream consumers.

## Feature request

Add a `GET /healthz` endpoint that returns:

```json
{
  "status": "ok",
  "git_sha": "<short SHA, 7 chars>",
  "uptime_seconds": <integer>
}
```

`uptime_seconds` is wall-clock seconds since the process started.
`git_sha` is read once at startup from the env var `GIT_SHA`; if the
env var is absent, return the literal string `"unknown"`.

## Constraints

- The service uses FastAPI; mount the route on the existing app instance
  in `src/obs_svc/app.py`.
- Existing tests in `tests/integration/test_webhooks.py` must continue
  to pass.
- No new dependencies (FastAPI + stdlib are sufficient).
