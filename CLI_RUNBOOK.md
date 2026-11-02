# CLI Runbook: Understanding Module Execution

## Quick Answer

```bash
# ✅ CORRECT - Using Python's -m flag (module execution)
python -m src.cli.workflow_runner --workflow-type login ...

# ❌ WRONG - Direct file execution
python src/cli/workflow_runner.py --workflow-type login ...

# ❌ WRONG - Direct path execution
src/cli/workflow_runner.py --workflow-type login ...
```

## Why Use `python -m` Instead of Direct File Execution?

### The Difference

| Method | Command | How It Works | Use Case |
|--------|---------|--------------|----------|
| **`-m` flag** | `python -m src.cli.workflow_runner` | **Module execution** - runs Python module from anywhere | Production, scripts, CI/CD |
| **Direct file** | `python src/cli/workflow_runner.py` | **File execution** - runs script from current directory | Legacy, one-offs, debugging |
| **Shebang** | `./src/cli/workflow_runner.py` | **Direct execution** - requires `#!/usr/bin/env python` shebang | Shell scripts, cron jobs |

### Why `-m` is Better

**1. Package imports work correctly**
```python
# This works with -m flag
from src.framework import Workflow

# This might fail with direct file execution
# because Python doesn't know src/ is a package
```

**2. Works from any directory**
```bash
# You can run from anywhere
cd /home/user
python -m src.cli.workflow_runner ...

# Direct file only works from repo root
cd /home/user
python /path/to/src/cli/workflow_runner.py ...  # Needed absolute path
```

**3. Proper module initialization**
```bash
# -m flag
python -m src.cli.workflow_runner
# Python sets sys.path correctly, loads __init__.py files

# Direct file
python src/cli/workflow_runner.py
# Python might skip __init__.py, break imports
```

**4. Entry point consistency**
```python
# Your __init__.py initializes the module
# -m ensures this runs
if __name__ == "__main__":
    main()  # This gets called correctly with -m
```

## How Python Module Execution Works

### Directory Structure
```
playwright-workflows/          # Project root (working directory)
├── src/
│   ├── __init__.py           # Makes src a package
│   ├── cli/
│   │   ├── __init__.py       # Makes cli a package
│   │   └── workflow_runner.py
│   └── framework/
│       ├── __init__.py
│       └── ...
└── pyproject.toml            # Project metadata
```

### Step-by-Step: `-m src.cli.workflow_runner`

```
1. Python sees "-m src.cli.workflow_runner"
   ↓
2. Converts dots to path: src/cli/workflow_runner.py
   ↓
3. Adds current directory to sys.path (if not there)
   ↓
4. Loads and executes all __init__.py files in order:
   - src/__init__.py
   - src/cli/__init__.py
   ↓
5. Executes workflow_runner.py module
   ↓
6. Imports work correctly:
   from src.framework import Workflow  ✓
   from src.utils.logging import setup_logger  ✓
```

### Step-by-Step: Direct File Execution `python src/cli/workflow_runner.py`

```
1. Python sees file path: src/cli/workflow_runner.py
   ↓
2. Sets __name__ = "__main__" (like -m does)
   ↓
3. MIGHT SKIP __init__.py files in some cases
   ↓
4. Tries to execute, but imports might fail:
   from src.framework import Workflow  ✗ (depends on sys.path)
   ✗ ModuleNotFoundError: No module named 'src'
```

## When to Use Each Method

### Use `python -m` (Recommended)

**✅ Production deployments**
```bash
python -m src.cli.batch_runner --input workflows.json
```

**✅ Docker containers**
```dockerfile
CMD ["python", "-m", "src.cli.mcp_server_runner"]
```

**✅ CI/CD pipelines**
```yaml
- run: python -m src.cli.workflow_runner --workflow-type login ...
```

**✅ Installed packages**
```bash
# If you package this, users run:
python -m playwright_workflows.cli.workflow_runner
```

**✅ Scripts and automation**
```bash
#!/bin/bash
python -m src.cli.batch_runner --input "$1"
```

### Use Direct File Execution (Legacy)

**⚠️ Only if:**
- Running from repo root directory
- You manually set PYTHONPATH
- Debugging import issues
- One-off quick tests

```bash
# Only works from repo root
cd /path/to/playwright-workflows
python src/cli/workflow_runner.py ...

# OR set PYTHONPATH manually
export PYTHONPATH=/path/to/playwright-workflows:$PYTHONPATH
python src/cli/workflow_runner.py ...
```

## Real-World Examples

### Example 1: Run Single Login Test
```bash
# ✅ Correct - works from anywhere
python -m src.cli.workflow_runner \
    --workflow-type login \
    --url https://example.com \
    --username testuser \
    --password testpass

# ❌ Wrong - only works from repo root
python src/cli/workflow_runner.py ...
```

### Example 2: Batch Process 100 Workflows
```bash
# ✅ Correct - works from anywhere, proper imports
python -m src.cli.batch_runner \
    --input workflows.json \
    --max-concurrent 10

# ❌ Wrong - might have import errors
python src/cli/batch_runner.py ...
```

### Example 3: Start MCP Server
```bash
# ✅ Correct - server runs from anywhere
python -m src.cli.mcp_server_runner

# ❌ Wrong - imports might fail
python src/cli/mcp_server_runner.py
```

### Example 4: Resume Workflow
```bash
# ✅ Correct
python -m src.cli.resume_workflow exec-123

# ❌ Wrong
python src/cli/resume_workflow.py exec-123
```

## Understanding sys.path

### With `-m` flag
```python
# Python automatically manages sys.path
# Your working directory is added
# Package imports are resolved correctly

# Run from anywhere:
$ pwd
/home/user/documents

$ python -m src.cli.workflow_runner ...
# Still works! Python finds src/cli/workflow_runner.py
# in your project directory
```

### Without `-m` flag
```python
# Python uses file path
# sys.path might not include project root
# Imports might fail

# Run from repo root:
$ pwd
/path/to/playwright-workflows

$ python src/cli/workflow_runner.py
# Works because Python finds imports

# Run from elsewhere:
$ python /path/to/playwright-workflows/src/cli/workflow_runner.py
# Might fail - sys.path doesn't include /path/to/playwright-workflows
```

## Comparison Table

| Aspect | `-m module` | Direct File | Shebang |
|--------|-----------|-------------|---------|
| **Works from any dir** | ✅ Yes | ❌ No* | ✅ Yes |
| **Import handling** | ✅ Perfect | ⚠️ Iffy | ✅ Good |
| **Package init** | ✅ Runs | ⚠️ Maybe | ✅ Runs |
| **sys.path** | ✅ Auto | ⚠️ Manual | ✅ Auto |
| **Production ready** | ✅ Yes | ❌ No | ✅ Yes |
| **CI/CD friendly** | ✅ Yes | ❌ No | ✅ Yes |
| **Docker** | ✅ Yes | ⚠️ Hard | ✅ Yes |
| **Typing/LSP** | ✅ Good | ✅ Good | ⚠️ Mediocre |

*Unless you set PYTHONPATH or use absolute paths

## Setting Up CLI Scripts

### Option 1: Use `python -m` (Recommended)

**Create a shell script wrapper:**
```bash
#!/bin/bash
# scripts/run_workflow.sh

python -m src.cli.workflow_runner "$@"
```

**Usage:**
```bash
chmod +x scripts/run_workflow.sh
./scripts/run_workflow.sh --workflow-type login ...
```

### Option 2: Use Entry Points (Best for Distribution)

**pyproject.toml:**
```toml
[project.scripts]
workflow-runner = "src.cli.workflow_runner:main"
batch-runner = "src.cli.batch_runner:main"
mcp-server = "src.cli.mcp_server_runner:main"
resume-workflow = "src.cli.resume_workflow:resume_workflow"
```

**After installation:**
```bash
pip install -e .

# Now you can run from anywhere:
workflow-runner --workflow-type login ...
batch-runner --input workflows.json ...
mcp-server
resume-workflow exec-123
```

### Option 3: Docker

**Dockerfile:**
```dockerfile
FROM python:3.11

WORKDIR /app
COPY . .

RUN pip install -e .

# Use -m for proper module execution
ENTRYPOINT ["python", "-m"]
CMD ["src.cli.mcp_server_runner"]
```

**Run:**
```bash
docker run my-workflows:latest
# Executes: python -m src.cli.mcp_server_runner
```

## Troubleshooting

### Issue: `ModuleNotFoundError: No module named 'src'`

**Cause:** Running direct file without proper sys.path

**Solution:**
```bash
# ❌ Wrong
python src/cli/workflow_runner.py

# ✅ Correct
python -m src.cli.workflow_runner
```

### Issue: `ImportError: cannot import name 'Workflow'`

**Cause:** __init__.py not loaded

**Solution:**
```bash
# Make sure src/cli/__init__.py exists
# Make sure src/framework/__init__.py exists
# Use -m flag
python -m src.cli.workflow_runner
```

### Issue: Works locally, fails in CI/CD

**Cause:** CI/CD using direct file execution from wrong directory

**Solution:**
```yaml
# ❌ Wrong
- run: python src/cli/workflow_runner.py

# ✅ Correct
- run: python -m src.cli.workflow_runner
```

## Key Takeaways

1. **Always use `python -m <module.path>`** for production code
   - Works from any directory
   - Handles imports correctly
   - CI/CD friendly
   - Industry standard

2. **Never use direct file execution** for distributed code
   - Import issues
   - Directory dependent
   - Not reproducible

3. **For CLI tools, prefer entry points**
   - Most user-friendly
   - Automatic installation
   - Works everywhere

4. **Test from different directories**
   ```bash
   cd /tmp
   python -m src.cli.workflow_runner ...  # Should work!
   ```

## See Also

- [Python Documentation: Running Modules](https://docs.python.org/3/using/cmdline.html#cmdoption-m)
- [PEP 338: Executing modules as scripts](https://www.python.org/dev/peps/pep-0338/)
- [setuptools entry_points](https://setuptools.pypa.io/en/latest/userguide/entry_points.html)
