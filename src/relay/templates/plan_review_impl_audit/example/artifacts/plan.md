# Implementation Plan

## Objective
Add a `GET /healthz` endpoint to the `obs-svc` FastAPI service that returns the service's health status, including the current git SHA and uptime in seconds.

## Scope
This task involves modifying the FastAPI application to include a new endpoint, ensuring that it reads environment variables correctly, calculates uptime, and integrates seamlessly with the existing application structure.

## Prerequisites
- Familiarity with FastAPI and Python.
- Access to the `obs-svc` codebase.
- Ability to set environment variables in the deployment environment.

## Implementation Steps

1. **Define the Health Check Endpoint**
   - **Description**: Create a new endpoint `/healthz` in the FastAPI application.
   - **Files to Modify**: `src/obs_svc/app.py`
   - **Dependencies**: None
   - **Complexity**: Low
   - **Acceptance Criteria**: The endpoint is defined and returns a JSON response with placeholders for `status`, `git_sha`, and `uptime_seconds`.

2. **Implement Uptime Calculation**
   - **Description**: Calculate the uptime in seconds since the application started.
   - **Files to Modify**: `src/obs_svc/app.py`
   - **Dependencies**: Python `time` module
   - **Complexity**: Medium
   - **Acceptance Criteria**: The endpoint returns the correct `uptime_seconds` based on the process start time.

3. **Read Git SHA from Environment Variable**
   - **Description**: Retrieve the `GIT_SHA` from the environment variable and handle cases where it is absent.
   - **Files to Modify**: `src/obs_svc/app.py`
   - **Dependencies**: Python `os` module
   - **Complexity**: Low
   - **Acceptance Criteria**: The endpoint returns the correct `git_sha` or `"unknown"` if the environment variable is not set.

4. **Integrate Endpoint with FastAPI Application**
   - **Description**: Ensure the new endpoint is properly mounted on the existing FastAPI app instance.
   - **Files to Modify**: `src/obs_svc/app.py`
   - **Dependencies**: FastAPI framework
   - **Complexity**: Low
   - **Acceptance Criteria**: The endpoint is accessible via HTTP requests.

5. **Update and Run Tests**
   - **Description**: Create new tests for the `/healthz` endpoint and ensure existing tests continue to pass.
   - **Files to Modify**: `tests/integration/test_healthz.py`, `tests/integration/test_webhooks.py`
   - **Dependencies**: pytest
   - **Complexity**: Medium
   - **Acceptance Criteria**: All tests pass, including new tests for the `/healthz` endpoint.

## Test Plan
- **Unit Tests**: Write unit tests for the uptime calculation and environment variable reading.
- **Integration Tests**: Add integration tests for the `/healthz` endpoint to verify the response structure and content.
- **Regression Tests**: Run existing tests in `tests/integration/test_webhooks.py` to ensure no regressions.

## Risks and Mitigations
- **Risk**: Incorrect uptime calculation could lead to inaccurate data.
  - **Mitigation**: Thoroughly test the uptime calculation logic.
- **Risk**: Environment variable `GIT_SHA` might not be set in some environments.
  - **Mitigation**: Default to `"unknown"` if the variable is not set and document this behavior.

## Rollback Plan
- Revert changes in `src/obs_svc/app.py` and any test files if the new endpoint causes issues.
- Ensure the service is redeployed without the `/healthz` endpoint to restore previous functionality.