# Module Execution Cheat Sheet

## TL;DR - The Answer to Your Question

```bash
# ✅ This: python -m src.cli.workflow_runner
# ❌ Not this: python src/cli/workflow_runner.py
```

**Why?** The `-m` flag tells Python "handle package imports properly"

---

## The Core Issue

Your project uses **package imports**:

```python
from src.framework import Workflow
from src.utils.logging import setup_logger
```

### Without `-m` flag:
```
sys.path = ['src/cli', ...]      ← Missing project root
                ↓
from src.framework import Workflow ← Can't find 'src'
                ↓
❌ ModuleNotFoundError: No module named 'src'
```

### With `-m` flag:
```
sys.path = ['/path/to/repo', ...]  ← Project root included
                ↓
from src.framework import Workflow ← Finds 'src'
                ↓
✅ Works perfectly
```

---

## Visual Explanation

```
Analogy:
You ask a friend for a book from your library.

❌ Wrong way: "Go find the book in my bedroom"
   They search only the bedroom, miss books in other rooms

✅ Right way: "Go to my library entrance, then find the book"
   They start from the main entrance, can access all books

Python -m flag = "Start from the project entrance"
Direct file = "Start from this one file"
```

---

## Why It Matters

| Scenario | `python -m` | Direct File |
|----------|-----------|------------|
| Run from home | ✅ Works | ❌ Fails |
| Run from /tmp | ✅ Works | ❌ Fails |
| Docker | ✅ Safe | ⚠️ Risky |
| GitHub Actions | ✅ Works | ❌ Fails |
| Production | ✅ Yes | ❌ No |

---

## When to Use Each

### Use `python -m` (ALWAYS)
- ✅ Production code
- ✅ CI/CD pipelines
- ✅ Docker containers
- ✅ Scripts others will run
- ✅ When you care if it works

### Use Direct File (NEVER, except...)
- ⚠️ Quick debugging from repo root
- ⚠️ Never in production
- ⚠️ Never for shared code

---

## Quick Examples

### Your CLI Tools

```bash
# Single workflow
python -m src.cli.workflow_runner \
    --workflow-type login \
    --url https://example.com

# Batch 10 parallel
python -m src.cli.batch_runner \
    --input workflows.json \
    --max-concurrent 10

# MCP server
python -m src.cli.mcp_server_runner

# Resume workflow
python -m src.cli.resume_workflow exec-123
```

---

## Technical Explanation

### `-m` Flag Does This:
1. Recognizes `src.cli.workflow_runner` as a module path
2. Converts dots to directories: `src/cli/workflow_runner.py`
3. **Adds current directory to sys.path** ← Key part!
4. Loads all `__init__.py` files
5. Executes with proper module context

### Direct File Does This:
1. Sees `src/cli/workflow_runner.py` as just a file
2. Sets minimal sys.path
3. Might skip `__init__.py`
4. Executes as basic script
5. ❌ Imports often fail

---

## Key Difference: sys.path

```python
# With: python -m src.cli.workflow_runner
sys.path = [
    '/path/to/playwright-workflows',  ← Project root!
    '/lib/python3.11',
    ...
]
# from src.framework import Workflow ✓

# Without: python src/cli/workflow_runner.py  
sys.path = [
    'src/cli',  ← Only this directory
    '/lib/python3.11',
    ...
]
# from src.framework import Workflow ✗
```

---

## Real-World Failure Example

```bash
cd /home/user

# This works
$ python -m src.cli.workflow_runner --help
usage: workflow_runner.py [-h] ...
✅ Success

# This fails
$ python /path/to/src/cli/workflow_runner.py --help
Traceback (most recent call last):
  ...
ModuleNotFoundError: No module named 'src'
❌ Failure
```

---

## Best Practice

The Python ecosystem and community recommend **always** using `-m`:

- ✅ Django: `python -m django runserver`
- ✅ FastAPI: `python -m uvicorn main:app`
- ✅ pytest: `python -m pytest`
- ✅ pip: `python -m pip install ...`
- ✅ Your code: `python -m src.cli.workflow_runner`

It's the **industry standard** because it's reliable and reproducible.

---

## Summary

```
Question: "Why python -m instead of direct file?"

Answer: "-m = module mode = proper Python setup"

Result: Works everywhere ✓ vs. "works on my machine" ✗
```

---

## Read More

Full details in: [CLI_RUNBOOK.md](CLI_RUNBOOK.md)
- How Python module execution works (detailed)
- Comparison of all execution methods
- Setting up scripts and entry points
- Docker and CI/CD examples
- Troubleshooting guide
