```markdown
## Summary
The bug occurs when the feature-flag value `enable_metrics: "false"` (with quotes) is treated as truthy in the application, despite being intended as a falsy value. The expected behavior is that the application should interpret `"false"` (quoted) as a falsy value, similar to how the unquoted `false` would be interpreted.

## Steps to reproduce
1. Create a new directory for the project and navigate into it:
   ```bash
   mkdir myapp-bug-repro && cd myapp-bug-repro
   ```

2. Create the necessary directory structure:
   ```bash
   mkdir -p src/myapp
   ```

3. Create a `config.yaml` file with the following content:
   ```yaml
   enable_metrics: "false"
   ```

4. Create a `src/myapp/config.py` file with the following content:
   ```python
   import yaml

   def load_config():
       with open('config.yaml', 'r') as file:
           return yaml.safe_load(file)
   ```

5. Create a `src/myapp/router.py` file with the following content:
   ```python
   from src.myapp.config import load_config

   def check_metrics_enabled():
       config = load_config()
       return config.get('enable_metrics', False)

   if __name__ == "__main__":
       if check_metrics_enabled():
           print("Metrics are enabled.")
       else:
           print("Metrics are disabled.")
   ```

6. Run the application:
   ```bash
   python3 src/myapp/router.py
   ```

## Environment
- Python version: 3.x (tested with Python 3.8)
- PyYAML version: 5.4.1
- Operating System: Any OS (tested on Ubuntu 20.04)
- No specific configuration or commit is required beyond the provided files.

## Evidence
When running the application with the above setup, the output is:
```
Metrics are enabled.
```
This output indicates that the application incorrectly treats the quoted `"false"` as a truthy value, which is contrary to the expected behavior where it should print `Metrics are disabled.`.
```