# Debugging Guide for Playwright Workflows

This guide explains how to debug workflow execution issues, especially when elements are not found or timeouts occur.

## Quick Start: Running in Debug Mode

### 1. Enable Debug Logging

Add `--debug` flag to your CLI command:

```bash
python -m src.cli.workflow_runner login \
    --input '{"url":"https://vidyutsuraksha.org/","username":"test","password":"pass"}' \
    --debug
```

This will:
- Enable verbose logging with timestamps and context
- Capture element selectors and page content
- Save screenshots before failures
- Log DOM queries and navigation events

### 2. Inspect Page State

When a step fails, the debug mode will automatically:
- **Take a screenshot** of the current page state
- **Save the full HTML** of the page
- **Log the actual page content** to help identify selectors
- **Show available elements** on the page

### 3. Common Issues & Solutions

#### Issue: Element Not Found (Selector Timeout)

**Problem**: `Page.fill: Timeout 10000ms exceeded` when filling `#txtLogin`

**Debug Steps**:

1. **Take a screenshot before attempting fill**:
   ```bash
   # The debug mode does this automatically, but you can also manually add:
   await page.screenshot(path=f"debug_{timestamp}_before_fill.png")
   ```

2. **Log the page content**:
   ```bash
   # Check what HTML is actually on the page
   # The debug logs will show this automatically
   ```

3. **Inspect the actual DOM**:
   ```bash
   # Use browser dev tools to find the correct selector
   # Or enable page_content logging in debug mode
   ```

4. **Common selector mistakes**:
   - CSS selector changed due to page load
   - Element is inside an iframe (requires frame navigation)
   - Element has dynamic classes that change
   - Element loads after JavaScript execution
   - Element is hidden or covered by another element

#### Issue: Page Load Incomplete

**Problem**: Elements appear to exist but can't be filled

**Solution**: Add explicit waits before element interaction

```python
# Wait for network idle
await page.wait_for_load_state('networkidle')

# Wait for specific element
await page.wait_for_selector('#txtLogin', timeout=5000)

# Wait for element to be stable (visible and not animating)
await page.locator('#txtLogin').wait_for(state='visible')
```

## Debug Mode Features

### Available Debug Flags

```bash
python -m src.cli.workflow_runner login \
    --input '{"url":"...","username":"...","password":"..."}' \
    --debug \
    --save-screenshots \
    --headless false  # See the browser in action
```

### Debug Output Locations

All debug artifacts are saved in:
```
data/executions/{execution_id}/debug/
├── screenshots/
│   ├── step_001_navigate_before.png
│   ├── step_001_navigate_after.png
│   ├── step_002_fill_username_before.png
│   └── step_002_fill_username_error.png
├── html/
│   ├── step_001_navigate.html
│   └── step_002_fill_username.html
├── logs/
│   └── debug.log
└── page_content.json
```

### Enabling Debug in Code

In your workflow, enable debug mode explicitly:

```python
from src.workflows.login_workflow import LoginWorkflow

workflow = LoginWorkflow(
    debug=True,  # Enable debug mode
    save_screenshots=True,  # Save screenshots
    headless=False,  # See the browser
    verbose=True  # Extra logging
)

execution_id = await workflow.run(
    url="https://vidyutsuraksha.org/",
    username="test",
    password="pass"
)
```

## Manual Debugging Techniques

### 1. Browser Developer Tools

Run without `--headless` to see the browser:

```bash
python -m src.cli.workflow_runner login \
    --input '{"url":"https://vidyutsuraksha.org/","username":"test","password":"pass"}' \
    --headless false
```

Then:
- Open DevTools (F12 or Cmd+Option+I)
- Inspect elements to find correct selectors
- Check Console for JavaScript errors
- Monitor Network tab for failed requests

### 2. Add Breakpoints to Workflow

Edit your workflow and add debug steps:

```python
@step("Debug Check Point")
async def debug_checkpoint(self):
    """Stop and log page state for debugging."""
    # Take screenshot
    await self._page.screenshot(path="debug_checkpoint.png")
    
    # Log page HTML
    html = await self._page.content()
    print(f"Page HTML:\n{html}")
    
    # Log all text content
    text = await self._page.evaluate("document.body.innerText")
    print(f"Page Text:\n{text}")
    
    # Wait for user interaction
    await asyncio.sleep(30)  # Give time to inspect browser
```

### 3. Query Selectors Programmatically

Add this to any step to diagnose selectors:

```python
@step("Find Login Elements")
async def find_login_elements(self):
    """Log all potential login input fields."""
    
    # Find by ID
    id_element = await self._page.query_selector("#txtLogin")
    print(f"Found by #txtLogin: {id_element is not None}")
    
    # Find by name
    name_element = await self._page.query_selector("input[name='username']")
    print(f"Found by name: {name_element is not None}")
    
    # Find by type
    type_elements = await self._page.query_selector_all("input[type='text']")
    print(f"Found {len(type_elements)} text inputs")
    
    # Find by aria-label
    aria_element = await self._page.query_selector("[aria-label*='username']")
    print(f"Found by aria-label: {aria_element is not None}")
    
    # Find by placeholder
    placeholder_element = await self._page.query_selector("input[placeholder*='User']")
    print(f"Found by placeholder: {placeholder_element is not None}")
```

### 4. Inspect Page Load States

```python
@step("Check Page Load State")
async def check_page_state(self):
    """Verify page is fully loaded."""
    
    # Check current URL
    current_url = self._page.url
    print(f"Current URL: {current_url}")
    
    # Get page title
    title = await self._page.title()
    print(f"Page title: {title}")
    
    # Check for errors in console
    console_messages = []
    
    def on_console(msg):
        console_messages.append(msg)
    
    self._page.on("console", on_console)
    await asyncio.sleep(1)  # Wait for console messages
    
    for msg in console_messages:
        print(f"Console [{msg.type}]: {msg.text}")
```

## Troubleshooting Common Errors

### Error: "Page.fill: Timeout exceeded"

**Causes**:
1. Element doesn't exist with given selector
2. Element is hidden or not visible
3. Page is still loading JavaScript
4. Element is in an iframe

**Solution**:
```python
# Add these waits before filling
await self._page.wait_for_load_state('networkidle')
await self._page.wait_for_selector('#txtLogin', timeout=5000)

# Or use a more robust approach
try:
    await self._page.locator('#txtLogin').fill(username, timeout=5000)
except Exception as e:
    # Debug: Try alternative selectors
    alt_selectors = [
        'input[name="username"]',
        'input[type="text"]',
        '[placeholder*="username"]'
    ]
    for selector in alt_selectors:
        element = await self._page.query_selector(selector)
        if element:
            print(f"Found element with: {selector}")
            await self._page.fill(selector, username)
            break
```

### Error: "Navigation timeout"

**Solution**:
```python
# Increase timeout or wait for specific condition
try:
    await self._page.goto(url, wait_until='networkidle', timeout=30000)
except Exception:
    # Page loaded partially, continue anyway
    await self._page.wait_for_load_state('load')
```

### Error: "Execution context was destroyed"

**Solution**:
```python
# Add retry logic with fresh context
@with_retry(max_retries=3, backoff_factor=2)
async def fill_with_retry(self, selector, value):
    """Fill with automatic retry on context destruction."""
    try:
        await self._page.fill(selector, value)
    except Exception as e:
        if "context was destroyed" in str(e):
            # Wait before retry
            await asyncio.sleep(1)
            raise  # Trigger retry
        else:
            raise  # Don't retry other errors
```

## Performance Debugging

### Check Element Query Performance

```python
import time

@step("Performance Check")
async def check_performance(self):
    """Measure time to find elements."""
    
    selectors = [
        '#txtLogin',
        'input[type="text"]',
        '[placeholder*="User"]'
    ]
    
    for selector in selectors:
        start = time.time()
        element = await self._page.query_selector(selector)
        elapsed = time.time() - start
        
        print(f"Selector '{selector}': {elapsed*1000:.2f}ms, found={element is not None}")
```

## Environment-Specific Debugging

### Different Sites Have Different Issues

**Solution**: Create site-specific debug profiles

```python
# In login_workflow.py
DEBUG_PROFILES = {
    'vidyutsuraksha.org': {
        'headless': False,
        'save_screenshots': True,
        'step_delays': 2000,  # ms between steps
        'selectors': {
            'username': '#username',  # Site-specific
            'password': '#password',
            'login_btn': '.login-button'
        }
    },
    'example.com': {
        'headless': False,
        'save_screenshots': True,
        'selectors': {
            'username': 'input[name="user"]',
            'password': 'input[name="pass"]',
            'login_btn': 'button[type="submit"]'
        }
    }
}
```

## Next Steps

1. **Enable debug mode** and capture the screenshots/HTML
2. **Inspect the captured HTML** to find correct selectors
3. **Use browser DevTools** to confirm selectors work
4. **Update workflow** with correct selectors
5. **Re-run workflow** in debug mode to verify

## Getting Help

When reporting issues, include:
- [ ] Debug mode screenshots (from `data/executions/*/debug/screenshots/`)
- [ ] HTML dump (from `data/executions/*/debug/html/`)
- [ ] Full log output (with `--debug` flag)
- [ ] URL being tested
- [ ] Expected vs actual behavior
