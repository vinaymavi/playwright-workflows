# Element Not Found Issue - Root Cause & Solution

## Problem Summary

When running the login workflow against `https://vidyutsuraksha.org/`, the workflow fails with:
```
Page.fill: Timeout 10000ms exceeded.
Call log:
  - waiting for locator("#txtLogin")
```

## Root Cause (Discovered via Debug Mode)

The page **does NOT have** an element with ID `#txtLogin`. 

### What We Found

When running with `--debug` flag, the actual input fields on the page are:

```
Input 0: id='__EVENTTARGET', name='__EVENTTARGET', type='hidden'
Input 1: id='__EVENTARGUMENT', name='__EVENTARGUMENT', type='hidden'
Input 2: id='__VIEWSTATE', name='__VIEWSTATE', type='hidden'
Input 3: id='__VIEWSTATEGENERATOR', name='__VIEWSTATEGENERATOR', type='hidden'
Input 4: id='__EVENTVALIDATION', name='__EVENTVALIDATION', type='hidden'
Input 5: id='lightTheme', name='ctl00$lightTheme', type='submit'
Input 6: id='Button1', name='ctl00$Button1', type='submit'
Input 7: id='searchBox', name='searchBox', type='text'
```

**No `#txtLogin` field exists!**

This page uses ASP.NET with a different form structure than what the workflow expects.

## How to Debug & Find Correct Selector

### Step 1: Run with Debug Mode

```bash
python -m src.cli.workflow_runner login \
    --input '{"url":"https://vidyutsuraksha.org/","username":"test","password":"pass"}' \
    --debug \
    --headless false
```

This will:
- ✅ Show the browser
- ✅ Log all available input fields
- ✅ Capture screenshots
- ✅ Save HTML of the page

### Step 2: Inspect Browser Manually

When the browser opens:
1. Press F12 to open DevTools
2. Use Element Inspector (top-left icon in DevTools)
3. Click on the username input field
4. Note the HTML element id/name/selector

### Step 3: Check Debug Output

Look for lines showing:
```
Input N: id='xxx', name='yyy', type='zzz'
```

The page shows there's no dedicated username/password fields for login. This could mean:
1. Login form is on a different page
2. Form uses different field IDs
3. Form might be in an iframe
4. Form loads dynamically via JavaScript

## Solutions

### Option 1: Use Headless Mode to Inspect

```bash
python -m src.cli.workflow_runner login \
    --input '{"url":"https://vidyutsuraksha.org/","username":"test","password":"pass"}' \
    --debug \
    --headless false
```

Then manually find the correct selectors.

### Option 2: Update Workflow with Correct Selectors

After finding the actual login form and selectors, update `src/workflows/login_workflow.py`:

```python
@step(name="Fill Username", max_retries=1)
async def fill_username(self) -> None:
    """Fill in the username field."""
    if not self.input:
        raise WorkflowError("Input not provided")
    
    # Replace with correct selector
    await self.fill("input[name='username']", self.input.username)
    # OR
    await self.fill("#username", self.input.username)
    # OR
    await self.fill("[placeholder='Username']", self.input.username)
```

### Option 3: Test Different Sites

Try the workflow with a site that has the expected form structure:
```bash
python -m src.cli.workflow_runner login \
    --input '{"url":"https://example.com","username":"test","password":"pass"}' \
    --debug \
    --headless false
```

## New Debug Features Added

### CLI Flags

```bash
# Enable debug mode (verbose logging + automatic screenshots)
--debug

# See the browser in action (default: headless)
--headless false

# Save screenshots on errors
--save-screenshots

# Colorized output
--log-format color
```

### Example: Full Debug Session

```bash
python -m src.cli.workflow_runner login \
    --input '{"url":"https://vidyutsuraksha.org/","username":"test","password":"pass"}' \
    --debug \
    --headless false \
    --log-format color \
    --output-format text
```

### Debug Artifacts

All debug information is saved to:
```
data/debug/{execution_id}/
├── screenshots/
│   ├── fill_txtlogin_error_20261102_094210.png
│   └── ...
├── html/
│   ├── fill_txtlogin_error_20261102_094210.html
│   └── ...
└── logs/
    └── debug.log
```

## Key Findings from Debug Output

The page at `https://vidyutsuraksha.org/` appears to be:
- An ASP.NET application (based on __VIEWSTATE, __EVENTVALIDATION fields)
- Likely not a simple username/password login form
- May require different approach or page structure analysis

## Next Steps

1. **Manually inspect the site** using `--headless false`
2. **Find the actual login form** and its field selectors
3. **Update the workflow** with correct selectors
4. **Test with debug mode** to verify changes work
5. **Run production mode** once working

## Testing the Fix

After updating selectors:

```bash
# Test with debug mode first
python -m src.cli.workflow_runner login \
    --input '{"url":"https://vidyutsuraksha.org/","username":"test","password":"pass"}' \
    --debug

# Then run production
python -m src.cli.workflow_runner login \
    --input '{"url":"https://vidyutsuraksha.org/","username":"test","password":"pass"}'
```

## Documentation

For more detailed debugging techniques, see:
- [DEBUGGING_GUIDE.md](./DEBUGGING_GUIDE.md) - Comprehensive debugging reference
- [DEBUG_QUICK_START.md](./DEBUG_QUICK_START.md) - Quick reference guide

## Summary

The new debug mode has successfully identified that:
- ❌ Element `#txtLogin` does NOT exist on the page
- ✅ The page has different form structure than expected  
- ✅ Debug mode shows exactly what elements ARE available
- ✅ You can now update the workflow with correct selectors

This is a **success** - we found the root cause and have tools to fix it!
