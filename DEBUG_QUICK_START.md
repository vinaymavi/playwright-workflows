# Quick Debug Reference

## Problem You're Facing

Element `#txtLogin` is not found on the page (timeout after 10 seconds).

## Quick Solutions

### 1. **See What's Actually On The Page** (Recommended First Step)

Run with debug mode to see all input fields:

```bash
python -m src.cli.workflow_runner login \
    --input '{"url":"https://vidyutsuraksha.org/","username":"test","password":"pass"}' \
    --debug \
    --headless false
```

This will:
- ✅ Open the browser so you can see it
- ✅ Take screenshots of each step
- ✅ Log all input fields found on the page
- ✅ Save HTML before/after each action
- ✅ Show you the actual selectors available

**Output** will show something like:
```
Input 0: id='txtLogin', name='username', type='text', placeholder='Username', visible=True
Input 1: id='txtPassword', name='password', type='password', placeholder='Password', visible=True
```

### 2. **Check Screenshots**

After running with `--debug`, check:
```
data/executions/{execution_id}/debug/screenshots/
```

View the HTML files:
```
data/executions/{execution_id}/debug/html/
```

### 3. **Inspect in Browser Manually**

Run with `--headless false` to see the browser:
```bash
python -m src.cli.workflow_runner login \
    --input '{"url":"https://vidyutsuraksha.org/","username":"test","password":"pass"}' \
    --headless false
```

Then:
1. Open DevTools (F12 or Cmd+Option+I)
2. Use Inspector tool (element picker icon)
3. Click on the username input field
4. Check the HTML to find correct selector (id, name, class, etc.)

### 4. **Update Workflow with Correct Selector**

Once you find the correct selector, update the workflow:

```python
# In login_workflow.py, find the fill_username step:

# OLD (not found):
await self.fill("#txtLogin", self.input.username)

# NEW (correct selector from inspection):
await self.fill("input[name='username']", self.input.username)
# OR
await self.fill("#username", self.input.username)
# OR
await self.fill("[placeholder='Username']", self.input.username)
```

## All Debug Flags

```bash
python -m src.cli.workflow_runner login \
    --input '{...}' \
    --debug                # Enable verbose logging + automatic screenshots
    --headless false       # See browser (default: true/headless)
    --save-screenshots     # Save screenshots on error (automatic with --debug)
    --log-format color     # Colorized output (default: json)
    --output-format text   # Text output (default: json)
```

## What Debug Mode Saves

```
data/executions/{execution_id}/debug/
├── screenshots/         # PNG screenshots before/after each action
├── html/               # Full HTML of page at each step
└── console output      # Logged element details
```

## Why Element Not Found?

Common reasons:
1. ❌ **Wrong selector** - ID/name doesn't match actual HTML
2. ❌ **Element not loaded yet** - Need to wait longer
3. ❌ **Inside iframe** - Element is in nested frame
4. ❌ **Hidden/covered** - Element exists but not visible
5. ❌ **Dynamic classes** - Class names change with JS
6. ❌ **Wrong page** - Navigation went to different URL

## Example Debug Session

```bash
# Step 1: Run with debug to see what's available
$ python -m src.cli.workflow_runner login \
    --input '{"url":"https://vidyutsuraksha.org/","username":"test","password":"pass"}' \
    --debug \
    --headless false \
    --log-format color

# Step 2: Browser opens, you can inspect
# Step 3: DevTools shows selector is "input[name='loginUser']" not "#txtLogin"
# Step 4: Check debug files
$ cat data/executions/*/debug/html/fill_txtlogin_error_*.html

# Step 5: Update workflow.py with correct selector
# Step 6: Re-run without debug to verify
$ python -m src.cli.workflow_runner login \
    --input '{"url":"https://vidyutsuraksha.org/","username":"test","password":"pass"}' \
    --output-format text
```

## For The Current Issue

The site `https://vidyutsuraksha.org/` probably doesn't have element `#txtLogin`.

Run this to see what selectors exist:

```bash
python -m src.cli.workflow_runner login \
    --input '{"url":"https://vidyutsuraksha.org/","username":"test","password":"pass"}' \
    --debug \
    --headless false
```

Then look in the output for:
```
Input 0: id='?', name='?', type='text'
Input 1: id='?', name='?', type='password'
```

Update `src/workflows/login_workflow.py` with the correct selectors from the debug output.

## Need More Help?

1. Check `DEBUGGING_GUIDE.md` for detailed troubleshooting
2. Review debug screenshots and HTML files
3. Use browser DevTools to inspect elements
4. Check network tab for failed requests or redirects
