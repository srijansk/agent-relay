# Context

Bug: feature-flag value `enable_metrics: "false"` (quoted) is treated
as truthy in `src/myapp/config.py`. We want the same robustness that
the planner produces for any future flag.

- `src/myapp/config.py` calls yaml.safe_load and returns the dict.
- `src/myapp/router.py` reads the flag.
