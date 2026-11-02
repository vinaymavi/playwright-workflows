# Browser Initialization Fix - Workflow Runner

## Problem
When running workflows via the CLI, the error **"Page not initialized"** was thrown at the first step execution:
```
AttributeError: 'Page' object is None
```

This occurred because the workflow's `_page` attribute was never initialized before steps tried to use it.

## Root Cause
The `workflow_runner.py` was creating a workflow instance but **not setting up the Playwright browser, context, or page** before executing steps.

The workflow class has methods to set these (`set_page()`, `set_browser()`, `set_browser_context()`), but they were never being called by the CLI runner.

## Solution
Updated `src/cli/workflow_runner.py` to properly initialize Playwright before workflow execution:

### 1. Launch Browser
```python
browser = await playwright.chromium.launch(headless=True)
```

### 2. Create Browser Context
```python
session_manager = SessionManager(self.workflow.execution_id)
context = await session_manager.initialize_context(
    browser,
    self.workflow.base_url,
)
```

### 3. Create Page
```python
page = await context.new_page()
```

### 4. Set in Workflow
```python
self.workflow.set_page(page)
self.workflow.set_browser_context(context)
self.workflow.set_browser(browser)
```

### 5. Initialize Execution Tracking
```python
execution = Execution(
    execution_id=self.workflow.execution_id,
    base_url=self.workflow.base_url,
)
self.workflow.set_execution(execution)
```

## Changes Made
- **File**: `src/cli/workflow_runner.py`
- **Method**: `WorkflowRunner.run()`
- **Added imports**: `async_playwright`, `Execution`, `SessionManager`
- **Wrapped execution**: Browser lifecycle in `async with async_playwright():`

## Browser Installation
Playwright requires browser binaries to be installed:
```bash
uv run playwright install chromium
```

This downloads:
- Chrome for Testing (185.8 MiB)
- Chrome Headless Shell (99 MiB)
- FFmpeg (1.4 MiB)

## Testing
After the fix, workflows execute properly:

```bash
uv run python -m src.cli.workflow_runner login \
    --input '{"url":"https://example.com","username":"test","password":"pass"}'
```

Expected output:
- Browser launches successfully
- Page navigates to specified URL
- Workflow steps execute with proper page context
- Errors are now legitimate (e.g., selector not found) instead of initialization errors

## Workflow Lifecycle
1. CLI runner creates workflow instance
2. Runner initializes Playwright browser
3. Runner creates browser context (with session restoration)
4. Runner creates page
5. Runner sets page/browser/context in workflow
6. Runner starts execution
7. Workflow steps use `self._page` (now properly initialized)
8. Browser and context cleaned up via async context manager

## Notes
- SessionManager handles session persistence/restoration if available
- Browser runs in headless mode for CLI usage
- Context manager ensures proper cleanup even on errors
- Multiple workflows can run concurrently with separate execution IDs
