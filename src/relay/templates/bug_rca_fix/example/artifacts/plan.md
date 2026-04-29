# plan.md

## Objective
The bug causes the `myapp` CLI tool to incorrectly interpret the feature flag `feature_flags.enable_new_router` as `True` when it is set to the quoted string `"false"` in `config.yaml`, leading to the unintended activation of the new router.

## Root cause
The root cause of the issue is that the `yaml.safe_load` function in `src/myapp/config.py` returns the value of `enable_new_router` as a string when it is quoted in the YAML file. In Python, any non-empty string is considered truthy, including the string `"false"`. As a result, the `if` statement in `src/myapp/router.py` evaluates this string as `True`, which causes the new router to be used instead of the legacy router.

## Change list
1. **src/myapp/config.py**: Modify the `load_config` function to include type coercion for boolean values. Specifically, convert the strings `"true"` and `"false"` to their respective boolean values `True` and `False`.
2. **tests/unit/test_config.py**: Add new test cases to verify that quoted strings `"true"` and `"false"` are correctly interpreted as boolean values for `enable_new_router`, `enable_metrics`, and `enable_audit`.

## Test plan
1. **New Tests**:
   - `test_enable_new_router_quoted_false`: Verify that when `enable_new_router` is set to the string `"false"`, it is interpreted as `False`.
   - `test_enable_new_router_quoted_true`: Verify that when `enable_new_router` is set to the string `"true"`, it is interpreted as `True`.
   - `test_enable_metrics_quoted_false`: Verify that when `enable_metrics` is set to the string `"false"`, it is interpreted as `False`.
   - `test_enable_metrics_quoted_true`: Verify that when `enable_metrics` is set to the string `"true"`, it is interpreted as `True`.
   - `test_enable_audit_quoted_false`: Verify that when `enable_audit` is set to the string `"false"`, it is interpreted as `False`.
   - `test_enable_audit_quoted_true`: Verify that when `enable_audit` is set to the string `"true"`, it is interpreted as `True`.

2. **Regression Checks**:
   - Ensure that existing tests for well-formed YAML files continue to pass.
   - Verify that the application behaves correctly with unquoted boolean values.

## Risk and rollback
- **Risks**: The main risk is that the type coercion logic might inadvertently affect other parts of the configuration that rely on string values. Care must be taken to ensure that only the intended boolean flags are coerced.
- **Rollback**: If issues arise, revert the changes in `src/myapp/config.py` and remove the new test cases from `tests/unit/test_config.py`. This will restore the original behavior, albeit with the known bug.