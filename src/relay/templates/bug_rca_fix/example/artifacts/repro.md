# Reproduction

## Summary

Setting `feature_flags.enable_new_router: "false"` (string) in
`config.yaml` causes the new router to be enabled — the opposite of the
intended behaviour. Setting it to `false` (unquoted YAML boolean) works
correctly.

## Steps to reproduce

1. Create `config.yaml`:

   ```yaml
   feature_flags:
     enable_new_router: "false"
   ```

2. Start the application:

   ```
   python -m app.main --config config.yaml
   ```

3. Observe the startup log:

   ```
   [INFO] router=new
   ```

4. Expected:

   ```
   [INFO] router=legacy
   ```

## Environment

- Python 3.11.7
- PyYAML 6.0.1
- `app` commit `f02b44a`

## Evidence

- The check at `src/app/router.py:42` is `if config.feature_flags.enable_new_router:`
- Python's truthiness for the non-empty string `"false"` is `True`.
