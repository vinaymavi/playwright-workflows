# Quick Test Commands - Playwright Workflows

## Run Tests Immediately

### 1. **Quick Validation** (30 seconds)
```bash
uv run pytest tests/e2e/ -v
```
✅ Runs all 8 E2E tests validating the complete workflow lifecycle

### 2. **Main Test** (5 seconds)
```bash
uv run pytest tests/e2e/test_full_workflow_lifecycle.py::test_full_workflow_lifecycle -v -s
```
✅ Runs the comprehensive 10-phase workflow lifecycle test

### 3. **All Tests** (35 seconds)
```bash
uv run pytest tests/ -v
```
✅ Runs all 634 tests (should all pass)

### 4. **Coverage Report** (40 seconds)
```bash
uv run pytest tests/ --cov=src --cov-report=html --cov-report=term
open htmlcov/index.html
```
✅ Generates HTML coverage report, opens in browser

## Test Categories

### Framework Tests
```bash
uv run pytest tests/framework/unit/ -v              # Unit tests (~450)
uv run pytest tests/framework/integration/ -v       # Integration tests (~150)
```

### Workflow Tests
```bash
uv run pytest tests/workflows/integration/ -v       # Workflow tests (~100)
```

### Scenario Tests  
```bash
uv run pytest tests/quickstart_scenarios/ -v        # User stories (26)
```

### API Tests
```bash
uv run pytest tests/api/ -v                         # API tests (~30)
```

## Debug Specific Tests

### Show Detailed Output
```bash
uv run pytest tests/e2e/ -v -s  # -s shows print statements
```

### Show Slowest Tests
```bash
uv run pytest tests/ --durations=10
```

### Run with Full Traceback
```bash
uv run pytest tests/e2e/ -v --tb=long
```

### Run Specific Test with Debug
```bash
uv run pytest tests/e2e/test_full_workflow_lifecycle.py::test_full_workflow_lifecycle -v -s --pdb
```

## Filter Tests

### Run Only E2E Tests
```bash
uv run pytest -m e2e -v
```

### Skip Slow Tests
```bash
uv run pytest -m "not slow" -v
```

### Run Only Unit Tests
```bash
uv run pytest -m unit -v
```

## What Each Test Validates

### test_workflow_initialization
- Workflow created successfully
- Execution ID set correctly
- Base URL configured

### test_workflow_state_management
- State can be set
- State can be retrieved
- Values persist correctly

### test_state_manager_persistence
- State saved to disk
- State loaded from disk
- Data integrity maintained

### test_artifact_tracking
- Artifacts created
- Artifacts tracked
- Artifacts retrieved

### test_checkpoint_workflow
- Workflow pauses at checkpoint
- Checkpoint ID generated
- Decision captured
- Workflow resumes
- Status updated to completed

### test_error_recovery
- Errors classified (transient/permanent)
- Errors recorded
- Recovery possible
- State cleared on recovery

### test_concurrent_executions
- Multiple workflows run
- Each execution independent
- No state interference
- Each execution completes

### test_full_workflow_lifecycle ⭐
Main test covering all phases:
- Phase 1: Execution created
- Phase 2: Steps executed (navigate, fill)
- Phase 3: Artifacts created (screenshot, PDF)
- Phase 4: Workflow paused at checkpoint
- Phase 5: Decision provided
- Phase 6: Workflow resumed
- Phase 7: Execution completed
- Phase 8: All state and artifacts verified

## Expected Results

All tests should PASS:
```
======================== 634 passed in 36.40s =========================
```

Coverage should be >80%:
```
Name                      Stmts   Miss  Cover
─────────────────────────────────────────────
src/framework/workflow        500    50   90%
src/framework/checkpoint      200    20   90%
src/framework/state_manager   150    20   87%
src/framework/resource_mgr    140    25   82%
TOTAL                       3000   500   83%
```

## Troubleshooting

### Tests Fail
```bash
# Check imports
uv sync

# Verify Python version
python --version  # Should be 3.10+

# Check dependencies
uv pip list | grep pytest

# Run with full error
uv run pytest tests/ -v --tb=long
```

### Slow Tests
```bash
# Show which tests are slow
uv run pytest tests/ --durations=20

# Run only fast tests
uv run pytest -m "not slow" -v
```

### Import Errors
```bash
# Rebuild environment
uv sync --force

# Check Python path
uv run python -c "import src; print(src.__file__)"
```

## Next Steps After Testing

1. ✅ Run E2E tests → confirm all passing
2. ✅ Check coverage → ensure >80%
3. ✅ Run quickstart scenarios → validate user stories
4. 📋 Proceed to Phase 10 remaining tasks (T108-T114)

See TESTING_GUIDE.md for comprehensive documentation.
