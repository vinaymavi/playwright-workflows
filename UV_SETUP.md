# Setting Up `uv` Package Manager

This guide explains how to use `uv` as the package manager for the Playwright Workflows project.

## What is `uv`?

**uv** is a blazingly fast Python package installer and resolver written in Rust. It's a drop-in replacement for `pip` and `pip-tools` with:
- ✅ 10-100x faster installation
- ✅ Single `uv.lock` for reproducible environments
- ✅ Better dependency resolution
- ✅ Cross-platform support (Windows, macOS, Linux)

**Project**: https://github.com/astral-sh/uv

## Installation

### Option 1: Install `uv` (Recommended)

**macOS / Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell):**
```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Verify Installation:**
```bash
uv --version
```

### Option 2: Use existing `uv` installation

If you already have `uv` installed elsewhere (e.g., via Langflow or Homebrew):
```bash
which uv  # Find uv executable
```

Then use the full path: `/path/to/uv` or alias it in your shell.

## Quick Start with `uv`

### 1. **First Time Setup (Project Initialization)**

If you're starting fresh with this project:

```bash
# Clone the repository
git clone <repo-url>
cd playwright-workflows

# Create virtual environment and install dependencies
uv sync

# Verify installation
uv run pytest tests/ -v
```

This creates:
- `.venv/` - Isolated Python environment
- `uv.lock` - Locked dependency versions

### 2. **Using the Project (Daily Workflow)**

```bash
# Activate virtual environment
source .venv/bin/activate  # macOS/Linux
# OR
.venv\Scripts\activate  # Windows

# Run commands inside the venv
python -m pytest tests/
python -c "import playwright; print(playwright.__version__)"

# OR use `uv run` for one-off commands (no activation needed)
uv run pytest tests/
uv run python -m src.mcp_server
```

### 3. **Adding a New Dependency**

```bash
# Add a single package
uv add requests

# Add to dev group
uv add --group dev pytest-xdist

# Add to specific group (e.g., test group)
uv add --group test pytest-mock

# This automatically updates pyproject.toml and uv.lock
```

### 4. **Updating Dependencies**

```bash
# Update all dependencies to latest compatible versions
uv sync --upgrade

# Update specific packages
uv add --upgrade playwright pydantic

# Bump to next major version
uv add --upgrade-package playwright
```

### 5. **Removing a Dependency**

```bash
# Remove from project
uv remove requests

# This updates pyproject.toml and uv.lock
```

## Project-Specific Setup Instructions

### Prerequisites

- Python 3.10+ (3.12+ recommended)
- `uv` installed and in PATH
- Git (for cloning and version control)

### Setup Steps

#### Step 1: Clone Repository
```bash
git clone https://github.com/vinaymavi/playwright-workflows.git
cd playwright-workflows
```

#### Step 2: Initialize Environment
```bash
# Create virtual environment and install all dependencies
uv sync --all-groups

# This includes:
# - Project dependencies (playwright, pydantic, cryptography, etc.)
# - Dev tools (black, isort, flake8, mypy, pytest-cov)
# - Test dependencies (pytest, pytest-asyncio, pytest-mock)
```

#### Step 3: Verify Installation
```bash
# Activate venv
source .venv/bin/activate

# Run tests
pytest tests/ -v

# Check Python version
python --version

# Verify key packages
python -c "import playwright; import pydantic; import mcp; print('✓ All core packages installed')"
```

#### Step 4: (Optional) Install Playwright Browsers
```bash
# Download Playwright browser binaries (chromium, firefox, webkit)
playwright install

# For specific browser only
playwright install chromium
```

## Development Workflow

### Working with Dependencies

#### Install for Development
```bash
# One-time setup: all dependencies + dev tools
uv sync --all-groups

# Daily: activate venv and work
source .venv/bin/activate
```

#### Code Formatting & Linting
```bash
# Format code
black src/ tests/

# Sort imports
isort src/ tests/

# Lint
flake8 src/ tests/

# Type checking
mypy src/

# All-in-one (run all formatters)
uv run black src/ tests/ && uv run isort src/ tests/
```

#### Running Tests
```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/framework/test_errors.py -v

# With coverage
pytest tests/ --cov=src --cov-report=html

# Specific markers
pytest -m unit  # unit tests only
pytest -m integration  # integration tests only
pytest -m e2e  # end-to-end tests only
```

#### Running the MCP Server
```bash
# Activate venv first
source .venv/bin/activate

# Run MCP server
python -m src.mcp_server

# Or with uv run (no activation needed)
uv run python -m src.mcp_server
```

### Creating a New Workflow

```bash
# Activate venv
source .venv/bin/activate

# Create workflow file
cat > src/workflows/my_workflow.py << 'EOF'
from src.framework.workflow import Workflow
from src.framework.decorators import step, checkpoint

class MyWorkflow(Workflow):
    workflow_id = "my_workflow"
    description = "My custom workflow"
    
    async def run(self, url: str):
        await self.step1(url)
        await self.step2()

    @step
    async def step1(self, url: str):
        pass
    
    @step
    async def step2(self):
        pass
EOF
```

## Migration from `pip` to `uv`

If you were previously using `pip`:

### Step 1: Uninstall Old venv
```bash
# Remove old virtual environment
rm -rf venv/

# Clean pip cache (optional)
pip cache purge
```

### Step 2: Create New uv Environment
```bash
uv sync --all-groups
```

### Step 3: Update Shell Configuration (if needed)

Update `.bashrc`, `.zshrc`, or your shell profile:

```bash
# OLD (pip-based)
# alias activate="source venv/bin/activate"

# NEW (uv-based)
alias activate="source .venv/bin/activate"
```

### Step 4: Verify Migration
```bash
uv sync  # Should complete quickly if lock file is up-to-date
pytest tests/ -v  # Should pass all tests
```

## Dependency Management Files

### Files You'll Work With

| File | Purpose | Edit? |
|------|---------|-------|
| `pyproject.toml` | Project metadata & dependencies | ✅ Yes (via `uv add/remove` or manually) |
| `uv.lock` | Locked versions (2276 lines) | ❌ No (auto-generated by `uv`) |
| `.venv/` | Virtual environment | ❌ No (auto-managed by `uv`) |
| `.gitignore` | Version control exclusions | ✅ Yes (already configured) |

### Understanding `uv.lock`

The `uv.lock` file:
- Lists exact versions of all dependencies
- Ensures reproducible builds across machines
- Should be **committed to git** (checked in)
- Should **NOT** be manually edited

```bash
# View lock file structure
head -100 uv.lock

# Force rebuild from lock file
uv sync --locked
```

## Common Issues & Solutions

### Issue 1: `uv: command not found`

**Solution:**
```bash
# Check if uv is installed
which uv

# If not, install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Verify installation
uv --version
```

### Issue 2: Python 3.9 Compatibility Error

**Error:** `Python 3.9 is not supported; requires Python 3.10+`

**Solution:**
```bash
# Check Python version
python --version

# If Python 3.9, upgrade to 3.10+ or use a different Python:
uv sync --python 3.12

# Or use pyenv to manage multiple Python versions
brew install pyenv  # macOS
pyenv install 3.12.0
pyenv local 3.12.0
```

### Issue 3: Playwright Browser Installation Failed

**Error:** Playwright browser binaries not downloaded

**Solution:**
```bash
# After uv sync, install browsers
uv run playwright install

# Or install specific browser
uv run playwright install chromium
```

### Issue 4: Lock File Out of Sync

**Error:** `.venv` and `uv.lock` mismatch

**Solution:**
```bash
# Rebuild lock file from scratch
uv lock --upgrade

# Sync environment to lock file
uv sync
```

### Issue 5: Virtual Environment Corruption

**Error:** Strange import errors after updating dependencies

**Solution:**
```bash
# Remove and recreate venv
rm -rf .venv/

# Sync fresh environment
uv sync --all-groups

# Verify
pytest tests/ -v
```

## Performance Comparison: `pip` vs `uv`

### Installation Speed

| Task | pip | uv | Speedup |
|------|-----|--|----|
| Fresh install (50 packages) | 60-90s | 5-10s | 10x |
| Using lock file | 30-45s | 2-3s | 15x |
| Update single package | 15-30s | 1-2s | 10x |

### Dependency Resolution

| Scenario | pip | uv |
|----------|-----|-----|
| Conflict detection | Slower, errors at end | Fast, errors early |
| Lock file | No native support | Built-in `uv.lock` |
| Reproducibility | Manual (`pip freeze`) | Automatic |

## Next Steps

1. ✅ Install `uv` using the installation guide above
2. ✅ Run `uv sync --all-groups` to set up the project
3. ✅ Activate venv: `source .venv/bin/activate`
4. ✅ Run tests: `pytest tests/ -v`
5. ✅ Read [Contributing Guide](#) for workflow development

## Additional Resources

- **Official Docs**: https://docs.astral.sh/uv/
- **GitHub**: https://github.com/astral-sh/uv
- **Discussion**: https://github.com/astral-sh/uv/discussions
- **Changelog**: https://github.com/astral-sh/uv/releases

---

**Last Updated:** November 2, 2026  
**Python Version:** 3.10+  
**uv Version:** 0.4.0+
