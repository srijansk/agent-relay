### Step 1: Define the Health Check Endpoint

**Objective**: Create a new endpoint `/healthz` in the FastAPI application.

**Files to Modify**: `src/obs_svc/app.py`

**Steps**:
1. Open `src/obs_svc/app.py`.
2. Define a new route `/healthz` that returns a JSON response with placeholders for `status`, `git_sha`, and `uptime_seconds`.

**Implementation**:
- I reviewed the existing structure of `app.py` to understand where to add the new route.
- I added a new function `get_health_status` that will handle the `/healthz` endpoint.
- This function currently returns a JSON response with static values for `status`, `git_sha`, and `uptime_seconds`.

**Code**:
```python
from fastapi import FastAPI
import time
import os

app = FastAPI()

# Record the start time of the application
start_time = time.time()

@app.get("/healthz")
async def get_health_status():
    return {
        "status": "ok",
        "git_sha": "unknown",
        "uptime_seconds": 0
    }
```

**Acceptance Criteria**: The endpoint is defined and returns a JSON response with placeholders for `status`, `git_sha`, and `uptime_seconds`.

**Next Steps**: Proceed to implement uptime calculation.

**Log**:
- Defined the `/healthz` endpoint in `src/obs_svc/app.py`.
- Added a placeholder response for `status`, `git_sha`, and `uptime_seconds`.

### Step 2: Implement Uptime Calculation

**Objective**: Calculate the uptime in seconds since the application started.

**Files to Modify**: `src/obs_svc/app.py`

**Steps**:
1. Use the `time` module to calculate the difference between the current time and the recorded `start_time`.

**Implementation**:
- I modified the `get_health_status` function to calculate the uptime in seconds by subtracting `start_time` from the current time.

**Code**:
```python
@app.get("/healthz")
async def get_health_status():
    uptime_seconds = int(time.time() - start_time)
    return {
        "status": "ok",
        "git_sha": "unknown",
        "uptime_seconds": uptime_seconds
    }
```

**Acceptance Criteria**: The endpoint returns the correct `uptime_seconds` based on the process start time.

**Next Steps**: Implement reading of the Git SHA from the environment variable.

**Log**:
- Implemented uptime calculation in `src/obs_svc/app.py`.
- The `/healthz` endpoint now returns the correct `uptime_seconds`.

### Step 3: Read Git SHA from Environment Variable

**Objective**: Retrieve the `GIT_SHA` from the environment variable and handle cases where it is absent.

**Files to Modify**: `src/obs_svc/app.py`

**Steps**:
1. Use the `os` module to read the `GIT_SHA` environment variable.
2. Default to `"unknown"` if the environment variable is not set.

**Implementation**:
- I added logic to read the `GIT_SHA` environment variable using `os.getenv`.
- If `GIT_SHA` is not set, it defaults to `"unknown"`.

**Code**:
```python
@app.get("/healthz")
async def get_health_status():
    git_sha = os.getenv("GIT_SHA", "unknown")
    uptime_seconds = int(time.time() - start_time)
    return {
        "status": "ok",
        "git_sha": git_sha,
        "uptime_seconds": uptime_seconds
    }
```

**Acceptance Criteria**: The endpoint returns the correct `git_sha` or `"unknown"` if the environment variable is not set.

**Next Steps**: Integrate the endpoint with the FastAPI application.

**Log**:
- Implemented reading of `GIT_SHA` from the environment variable in `src/obs_svc/app.py`.
- The `/healthz` endpoint now returns the correct `git_sha`.

### Step 4: Integrate Endpoint with FastAPI Application

**Objective**: Ensure the new endpoint is properly mounted on the existing FastAPI app instance.

**Files to Modify**: `src/obs_svc/app.py`

**Steps**:
1. Verify that the `/healthz` endpoint is correctly integrated and accessible.

**Implementation**:
- I confirmed that the `/healthz` endpoint is correctly defined and mounted on the FastAPI app instance.

**Acceptance Criteria**: The endpoint is accessible via HTTP requests.

**Next Steps**: Update and run tests.

**Log**:
- Verified the integration of the `/healthz` endpoint with the FastAPI application.

### Step 5: Update and Run Tests

**Objective**: Create new tests for the `/healthz` endpoint and ensure existing tests continue to pass.

**Files to Modify**: `tests/integration/test_healthz.py`, `tests/integration/test_webhooks.py`

**Steps**:
1. Create a new test file `test_healthz.py` for the `/healthz` endpoint.
2. Write tests to verify the response structure and content.
3. Run existing tests in `test_webhooks.py` to ensure no regressions.

**Implementation**:
- I created `test_healthz.py` and wrote tests to verify the `/healthz` endpoint's response.
- I ran all tests to ensure they pass.

**Code**:
```python
# tests/integration/test_healthz.py
from fastapi.testclient import TestClient
from src.obs_svc.app import app

client = TestClient(app)

def test_healthz_endpoint():
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] == "ok"
    assert "git_sha" in data
    assert "uptime_seconds" in data
    assert isinstance(data["uptime_seconds"], int)
```

**Acceptance Criteria**: All tests pass, including new tests for the `/healthz` endpoint.

**Log**:
- Created `tests/integration/test_healthz.py` and added tests for the `/healthz` endpoint.
- Ran all tests, including existing ones in `test_webhooks.py`, and confirmed they pass.

### Summary

- Implemented the `/healthz` endpoint in `src/obs_svc/app.py`.
- Calculated uptime and read `GIT_SHA` from the environment.
- Verified integration with FastAPI and wrote tests.
- All tests passed successfully.

**Next Steps**: None, as the implementation is complete.