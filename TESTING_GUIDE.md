# Testing Guide

This document explains how to test the Playwright Workflows automation framework.

## Overview

The test suite consists of:
- **Unit Tests**: Framework components in isolation (634 tests)
- **Integration Tests**: Component interactions with fixtures
- **E2E Tests**: Full workflow lifecycle tests
- **Performance Tests**: Throughput, memory, and latency measurements
- **Quickstart Scenarios**: User story validation

## Quick Start

### Run All Tests
```bash
# Run entire test suite
uv run pytest tests/ -v

# Run with coverage report
uv run pytest tests/ --cov=src --cov-report=html

# Open coverage report
open htmlcov/index.html
```

### Run Specific Test Categories

```bash
# Unit tests only (fast)
uv run pytest tests/framework/unit/ -v

# Integration tests
uv run pytest tests/framework/integration/ -v

# E2E tests (workflow lifecycle)
uv run pytest tests/e2e/ -v

# Quickstart scenario tests
uv run pytest tests/quickstart_scenarios/ -v

# API tests
uv run pytest tests/api/ -v
```

## Test Structure

```
tests/
├── e2e/
│   └── test_full_workflow_lifecycle.py    # End-to-end workflow tests
├── framework/
│   ├── unit/                              # Framework component tests
│   │   ├── test_workflow.py              # Workflow class tests
│   │   ├── test_action.py                # Action mechanism tests
│   │   ├── test_checkpoint.py            # Checkpoint/pause/resume tests
│   │   ├── test_state_manager.py         # State persistence tests
│   │   ├── test_resource_manager.py      # Artifact tracking tests
│   │   ├── test_errors.py                # Error handling tests
│   │   ├── test_retry_handler.py         # Retry logic tests
│   │   └── ... (14 test files)
│   └── integration/
│       ├── test_checkpoint_pause_resume.py        # Pause/resume workflow
│       ├── test_quick_resume.py                   # Fast resumption
│       ├── test_slow_resume_with_recovery.py      # Complex recovery
│       └── ... (6 test files)
├── workflows/
│   └── integration/
│       ├── test_login_workflow.py                 # Login workflow tests
│       ├── test_form_filling_workflow.py          # Form filling tests
│       ├── test_login_workflow_with_checkpoint.py # Checkpoint tests
│       └── ... (14 test files)
├── api/
│   ├── test_workflow_controller.py                # API controller tests
│   └── test_execution_manager.py                  # Execution management
├── quickstart_scenarios/
│   ├── test_scenario_a_simple_execution.py       # Story 1: Simple execution
│   ├── test_scenario_b_quick_resume.py           # Story 2: Quick resumption
│   ├── test_scenario_c_batch_processing.py       # Story 3: Batch processing
│   ├── test_scenario_d_custom_actions.py         # Story 4: Custom actions
│   ├── test_scenario_e_mcp_control.py            # Story 5: MCP control
│   ├── test_scenario_f_resume_after_error.py     # Story 6: Error recovery
│   └── test_scenario_g_capture_artifacts.py      # Story 7: Artifact capture
└── conftest.py                                     # Shared pytest fixtures
```

## Test Markers

Tests are marked for easy filtering:

```bash
# Run only unit tests
uv run pytest -m unit

# Run only integration tests
uv run pytest -m integration

# Run only E2E tests
uv run pytest -m e2e

# Run only performance tests
uv run pytest -m performance

# Run only slow tests
uv run pytest -m slow

# Exclude slow tests
uv run pytest -m "not slow"
```

### Available Markers
- `@pytest.mark.unit`: Framework unit tests (no browser/MCP)
- `@pytest.mark.integration`: Integration tests with mocks
- `@pytest.mark.e2e`: Full end-to-end workflow tests
- `@pytest.mark.performance`: Performance/benchmark tests
- `@pytest.mark.slow`: Tests that take >1s to run

## Running E2E Tests

End-to-end tests validate the complete workflow lifecycle:

```bash
# Run all E2E tests
uv run pytest tests/e2e/ -v -s

# Run specific E2E test
uv run pytest tests/e2e/test_full_workflow_lifecycle.py::test_full_workflow_lifecycle -v -s
```

### What E2E Tests Validate

The main E2E test `test_full_workflow_lifecycle` exercises:

1. **Workflow Creation**: Initialize execution context
2. **Step Execution**: Navigate, fill, submit steps
3. **Artifact Creation**: Screenshots and PDF exports
4. **Checkpoint**: Create checkpoint and pause workflow
5. **Resumption**: Resume workflow with human/AI decision
6. **Continuation**: Execute remaining steps
7. **Completion**: Mark workflow as completed
8. **Verification**: Verify all state and artifacts persisted

```python
# Example E2E test flow
async def test_full_workflow_lifecycle():
    # Phase 1: Create execution
    state_manager.save(execution_id, initial_state)
    
    # Phase 2: Run initial steps
    # ...execute navigate, fill steps...
    
    # Phase 3: Create artifact
    # ...create screenshot...
    
    # Phase 4: Checkpoint
    checkpoint_state["status"] = "paused_at_checkpoint"
    state_manager.save(execution_id, checkpoint_state)
    
    # Phase 5: Resume
    resumed_state["status"] = "resumed"
    state_manager.save(execution_id, resumed_state)
    
    # Phase 6: Complete
    final_state["status"] = "completed"
    state_manager.save(execution_id, final_state)
    
    # Phase 7: Verify
    assert final["status"] == "completed"
    assert len(artifacts) == 2
```

## Test Fixtures

Common fixtures provided by `conftest.py`:

```python
@pytest.fixture
def mock_browser():
    """Mock browser context for testing."""

@pytest.fixture
def workflow():
    """Sample workflow instance."""

@pytest.fixture
def state_manager():
    """StateManager for persistence testing."""

@pytest.fixture
def resource_manager():
    """ResourceManager for artifact testing."""

@pytest.fixture
def action_registry():
    """ActionRegistry with test actions."""
```

## Coverage Requirements

Target coverage by component:

| Component | Target |
|-----------|--------|
| `src/framework/workflow.py` | >90% |
| `src/framework/checkpoint.py` | >90% |
| `src/framework/state_manager.py` | >85% |
| `src/framework/resource_manager.py` | >85% |
| `src/framework/errors.py` | >80% |
| Overall | >80% |

### Generate Coverage Report

```bash
# Run tests with coverage
uv run pytest tests/ --cov=src --cov-report=html --cov-report=term

# View HTML report
open htmlcov/index.html

# Show coverage by file
uv run pytest tests/ --cov=src --cov-report=term-missing
```

## Quickstart Scenario Tests

Validate all 7 user stories:

```bash
# Run all scenario tests
uv run pytest tests/quickstart_scenarios/ -v

# Run specific scenario
uv run pytest tests/quickstart_scenarios/test_scenario_a_simple_execution.py -v
```

### Scenario Mappings

| Scenario | File | Story | Tests |
|----------|------|-------|-------|
| A | `test_scenario_a_simple_execution.py` | Story 1: Simple execution | 3 |
| B | `test_scenario_b_quick_resume.py` | Story 2: Quick resumption | 5 |
| C | `test_scenario_c_batch_processing.py` | Story 3: Batch processing | 4 |
| D | `test_scenario_d_custom_actions.py` | Story 4: Custom actions | 3 |
| E | `test_scenario_e_mcp_control.py` | Story 5: MCP control | 3 |
| F | `test_scenario_f_resume_after_error.py` | Story 6: Error recovery | 4 |
| G | `test_scenario_g_capture_artifacts.py` | Story 7: Artifact capture | 4 |

## Performance Testing

Performance tests measure throughput, memory, and latency:

```bash
# Run performance tests (may take several minutes)
uv run pytest tests/performance/ -v -s

# Run specific performance test
uv run pytest tests/performance/test_execution_throughput.py -v -s
```

### Performance Targets

- **Workflow Startup**: < 500ms
- **Step Execution**: < 5s (median)
- **Checkpoint Decision**: < 2s
- **State Persistence**: < 1s
- **Concurrent Executions**: 50-100 on 8-core machine
- **Memory per Execution**: 50-100MB

## Debugging Tests

### Verbose Output

```bash
# Show print statements
uv run pytest tests/e2e/ -v -s

# Show full diff on assertion failures
uv run pytest tests/ -v --tb=long

# Show local variables on errors
uv run pytest tests/ -v -l
```

### Debug Specific Test

```bash
# Run single test with debugging
uv run pytest tests/e2e/test_full_workflow_lifecycle.py::test_full_workflow_lifecycle -v -s --pdb

# Run with coverage for specific test
uv run pytest tests/e2e/test_full_workflow_lifecycle.py --cov=src --cov-report=term-missing -v
```

### Print Debugging

```python
# Add debug output in tests
def test_example():
    result = workflow.run()
    print(f"DEBUG: result = {result}")  # Shows with -s flag
    assert result is not None
```

## Continuous Integration

### GitHub Actions Workflow

Tests run automatically on every push:

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install uv
      - run: uv sync
      - run: uv run pytest tests/ --cov=src
```

## Test Best Practices

### Writing Tests

1. **Use descriptive names**: `test_checkpoint_pauses_execution_correctly`
2. **One assertion per test** (or related assertions)
3. **Use fixtures** for common setup
4. **Mark slow tests**: `@pytest.mark.slow`
5. **Test error paths**: transient vs permanent errors

### Example Test Structure

```python
@pytest.mark.asyncio
async def test_workflow_checkpoint_pauses_execution(
    state_manager,
    resource_manager,
):
    """Test that checkpoint pauses workflow execution.
    
    Validates:
    - Workflow status changes to paused_at_checkpoint
    - Checkpoint ID is recorded
    - State is persisted
    """
    execution_id = str(uuid4())
    
    # Arrange: Create workflow state
    state = {
        "execution_id": execution_id,
        "status": "running",
    }
    state_manager.save(execution_id, state)
    
    # Act: Trigger checkpoint
    current = state_manager.load(execution_id)
    current["status"] = "paused_at_checkpoint"
    current["checkpoint_id"] = str(uuid4())
    state_manager.save(execution_id, current)
    
    # Assert: Verify state changed
    paused = state_manager.load(execution_id)
    assert paused["status"] == "paused_at_checkpoint"
    assert paused["checkpoint_id"] is not None
```

## Troubleshooting

### Test Failures

```bash
# Run with full traceback
uv run pytest tests/ -v --tb=long

# Run with local variables on error
uv run pytest tests/ -v -l

# Run specific failing test
uv run pytest tests/framework/unit/test_workflow.py::test_name -v
```

### Slow Tests

```bash
# Show slowest tests
uv run pytest tests/ --durations=10

# Skip slow tests
uv run pytest -m "not slow"
```

### Import Errors

```bash
# Verify dependencies
uv sync

# Run with Python path debugging
uv run python -c "import src; print(src.__path__)"
```

## Test Statistics

Current test suite:

- **Total Tests**: 634
- **Unit Tests**: ~450
- **Integration Tests**: ~150
- **E2E Tests**: 8
- **Quickstart Scenarios**: 26
- **Average Runtime**: ~36 seconds
- **Coverage**: >80% overall

Run `uv run pytest tests/ --collect-only | grep "test session starts" -A 5` to see current test count.

## Next Steps

After running tests successfully:

1. **Review coverage reports** (`htmlcov/index.html`)
2. **Check test performance** with `--durations=10`
3. **Validate all scenarios pass** in quickstart tests
4. **Deploy to staging** for integration testing

See [docs/testing.md](docs/testing.md) for advanced testing patterns and [docs/debugging.md](docs/debugging.md) for workflow debugging techniques.
