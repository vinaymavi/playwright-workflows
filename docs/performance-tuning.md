# Performance Tuning Guide

## Overview

This guide provides strategies for optimizing Playwright Workflows performance, including browser management, resource allocation, concurrency tuning, and profiling techniques.

## Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| Workflow startup | <500ms | Fresh browser context + page load |
| Step execution | <5s (median) | Network latency dependent |
| Checkpoint decision | <2s | Async evaluation |
| State persistence | <1s | Incremental JSON write |
| Concurrent executions | 50-100 | Per 8-core machine |
| Memory per execution | 50-100MB | Browser context overhead |
| Artifact serving | <200ms | MCP resource queries |

## Browser and Context Management

### Context Pooling

Reuse browser contexts to avoid expensive startup costs:

```python
from playwright_workflows.browser import ContextPool

# Create pool of reusable contexts
pool = ContextPool(
    browser=browser,
    pool_size=10,
    context_config={
        'viewport': {'width': 1280, 'height': 720},
        'user_agent': 'Mozilla/5.0...'
    }
)

class MyWorkflow(Workflow):
    async def run(self):
        # Get context from pool (already initialized)
        async with pool.acquire() as context:
            page = await context.new_page()
            await page.goto('https://example.com')
            # Page automatically closed when context returns to pool
```

**Performance improvement**: ~400ms savings per workflow (pool setup vs fresh context)

### Lazy Page Creation

Create pages only when needed:

```python
# ❌ INEFFICIENT: Create page upfront
class MyWorkflow(Workflow):
    async def run(self):
        self.page = await self.context.new_page()
        # Page loaded even if not all steps use it

# ✅ EFFICIENT: Create page per step
class MyWorkflow(Workflow):
    async def run(self):
        await self.step1()  # No page
        await self.step2()  # Creates page on demand
        await self.step3()  # Reuses page
    
    async def step1(self):
        # Just computations, no browser
        pass
    
    async def step2(self):
        self.page = await self.context.new_page()
        # Navigate and interact
```

### Viewport Optimization

Right-size browser viewport for your use case:

```python
# ❌ SLOW: High-resolution unnecessary for form filling
context = await browser.new_context(
    viewport={'width': 1920, 'height': 1440}
)

# ✅ FAST: Minimal viewport saves memory
context = await browser.new_context(
    viewport={'width': 1280, 'height': 720}
)

# ✅ FASTEST: Mobile viewport if not testing desktop
context = await browser.new_context(
    device_name='iPhone 12'
)
```

**Performance improvement**: ~20-30% memory reduction

### Headless Mode (Default)

Always use headless mode for server automation:

```python
# ✅ CORRECT: Headless for automation
browser = await playwright.chromium.launch(headless=True)

# ❌ WRONG: Headed mode wastes resources
browser = await playwright.chromium.launch(headless=False)
```

## Resource Limits and Quotas

### Memory Limits

```python
from playwright_workflows.resource_manager import ResourceManager

resource_manager = ResourceManager(
    max_memory_per_execution_mb=256,  # Limit to 256MB
    max_concurrent_browsers=10,        # Max 10 browsers
    max_artifacts_per_execution_mb=100 # Limit artifacts to 100MB
)

class MemoryAwareWorkflow(Workflow):
    async def run(self):
        # Monitor memory
        memory_usage = resource_manager.get_memory_usage(self.execution_id)
        if memory_usage > 200:  # 200MB threshold
            # Cleanup before continuing
            await self.cleanup_artifacts()
```

### Timeout Configuration

```python
class OptimizedWorkflow(Workflow):
    class Config:
        # Page navigation timeout
        navigation_timeout = 10000  # 10 seconds
        
        # Action timeout (click, fill, etc.)
        action_timeout = 5000  # 5 seconds
        
        # Expect timeout (for element visibility)
        expect_timeout = 3000  # 3 seconds
```

**Tuning strategy**:
- Start with longer timeouts (30s)
- Monitor actual step durations
- Reduce to P99 duration + 20%
- Test with real network latency

### Concurrent Execution Limits

```python
from playwright_workflows.execution import ExecutionManager

execution_manager = ExecutionManager(
    max_concurrent_executions=50,  # Limit concurrent runs
    max_queue_size=1000             # Queue size limit
)

# Or configure per workflow
class LoginWorkflow(Workflow):
    class Config:
        max_concurrent_instances = 20  # Max 20 parallel login attempts
```

**Tuning approach**:
1. Start with 10 concurrent
2. Monitor CPU/memory
3. Increase until CPU reaches 70-80%
4. Back off by 20%

## Checkpoint Optimization

### Async Checkpoint Evaluation

Make checkpoint decisions without blocking execution:

```python
# ❌ SLOW: Synchronous checkpoint
async def run(self):
    await self.take_screenshot()
    result = self.evaluate_checkpoint()  # Blocks
    if result.needs_intervention:
        await self.checkpoint()

# ✅ FAST: Async checkpoint
async def run(self):
    # Take screenshot and evaluate in parallel
    screenshot_task = asyncio.create_task(self.take_screenshot())
    eval_task = asyncio.create_task(self.evaluate_checkpoint_async())
    
    await asyncio.gather(screenshot_task, eval_task)
    
    if eval_task.result().needs_intervention:
        await self.checkpoint()
```

### Efficient State Serialization

Minimize state file size:

```python
# ❌ SLOW: Large state snapshots
state = {
    'page_html': full_html,  # 500KB+
    'all_screenshots': [...]  # Multiple images
}

# ✅ FAST: Minimal state
state = {
    'checkpoint_data': {
        'page_url': 'https://...',
        'page_title': 'Title',
        'form_values': {...}
    },
    'screenshot_path': 'artifacts/latest.png'  # Reference, not content
}
```

**Performance improvement**: ~100ms per checkpoint write

## Database Query Optimization

### Index Configuration

If using database for execution tracking:

```sql
-- Create indexes for common queries
CREATE INDEX idx_execution_status 
ON executions(status, created_at DESC);

CREATE INDEX idx_execution_workflow 
ON executions(workflow_class, created_at DESC);

CREATE INDEX idx_execution_user 
ON executions(user_id, created_at DESC);
```

### Query Optimization

```python
# ❌ SLOW: N+1 query problem
executions = execution_manager.list_executions()
for execution in executions:
    logs = execution_manager.get_logs(execution.id)  # Query per execution

# ✅ FAST: Batch query
executions = execution_manager.list_executions()
execution_ids = [e.id for e in executions]
all_logs = execution_manager.get_logs_batch(execution_ids)
```

## Network Optimization

### Parallel Resource Loading

```python
# ✅ GOOD: Load resources in parallel
async def load_page_fast():
    # Let browser parallelize requests
    await page.goto('https://example.com', wait_until='networkidle')
    # Browser automatically loads CSS, JS in parallel

# ❌ SLOW: Sequential resource loading
async def load_page_slow():
    await page.goto('https://example.com', wait_until='domcontentloaded')
    await page.wait_for_load_state('networkidle')
    # Extra round-trip
```

### CDN and Caching

```python
# ✅ GOOD: Leverage browser caching
context = await browser.new_context(
    extra_http_headers={
        'Cache-Control': 'max-age=3600'
    }
)

# Subsequent navigations use cached resources
await page.goto('https://example.com')  # Full load
await page.goto('https://example.com')  # Cached load (~50ms)
```

### Connection Pooling

```python
# ✅ GOOD: Reuse TCP connections
context = await browser.new_context(
    extra_http_headers={
        'Connection': 'keep-alive'
    }
)

# Or use HTTP/2 (automatic in modern browsers)
```

## Step Execution Optimization

### Batch Operations

```python
# ❌ SLOW: Multiple fills with round trips
await page.fill('#username', 'user')
await page.fill('#password', 'pass')
await page.fill('#email', 'user@example.com')

# ✅ FAST: Batch with evaluate
await page.evaluate('''
    document.getElementById('username').value = 'user';
    document.getElementById('password').value = 'pass';
    document.getElementById('email').value = 'user@example.com';
''')
```

**Performance improvement**: ~500ms for 10 fields

### Selector Optimization

```python
# ❌ SLOW: Complex CSS selectors
await page.click('div.container > form#login > div > button:nth-child(2)')

# ✅ FAST: Specific ID or simple class
await page.click('#login-submit')

# ✅ FAST: Test ID (best practice for automation)
await page.click('[data-testid="login-button"]')
```

### Waiting Strategies

```python
# ❌ SLOW: Wait for arbitrary time
await page.wait_for_timeout(3000)  # 3 second pause

# ✅ FAST: Wait for specific condition
await page.wait_for_selector('.success-message', timeout=10000)

# ✅ FASTEST: Combine conditions
await page.click('#submit')
await page.wait_for_navigation(timeout=10000)
```

## Artifact Management

### Lazy Screenshot Capture

Only capture screenshots when needed:

```python
class PerformanceWorkflow(Workflow):
    async def run(self):
        await self.login()  # No screenshot
        
        # Only screenshot on error or checkpoint
        try:
            await self.fill_form()
        except Exception as e:
            await self.take_screenshot()  # On error
            raise
```

### Compressed Artifact Storage

```python
from playwright_workflows.artifacts import ArtifactManager

artifact_manager = ArtifactManager(
    compression='gzip',        # Compress screenshots
    quality_jpeg=80,           # 80% JPEG quality (vs 95%)
    max_artifact_size_mb=50
)

# JPEG compression reduces ~80% file size (slight quality loss)
# PNG compression good for exact preservation
```

### Artifact Lifecycle

```python
# Auto-cleanup old artifacts
artifact_manager.cleanup(
    older_than_days=30,        # Remove artifacts >30 days old
    keep_minimum=100           # Always keep at least 100
)
```

## Profiling and Monitoring

### Step Duration Profiling

```python
import time
from functools import wraps

def profile_step(func):
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        start = time.time()
        try:
            return await func(self, *args, **kwargs)
        finally:
            duration = time.time() - start
            # Log duration
            self.logger.info(f"{func.__name__} took {duration:.3f}s")
            # Alert if slow
            if duration > 5:
                self.logger.warning(f"{func.__name__} SLOW: {duration:.3f}s")
    return wrapper

class ProfiledWorkflow(Workflow):
    @profile_step
    async def fill_form(self):
        # Automatically logged
        pass
```

### Execution Timeline

```python
# Get execution timeline
execution = execution_manager.get_execution('exec-123')
timeline = execution.get_timeline()

for entry in timeline:
    print(f"{entry['step']}: {entry['duration_ms']}ms")

# Example output:
# login: 2340ms
# fill_form: 1250ms
# submit: 500ms
# wait_result: 3100ms
```

### Memory Profiling

```python
import tracemalloc

tracemalloc.start()

# Run workflow
execution = workflow.run()

current, peak = tracemalloc.get_traced_memory()
print(f"Current: {current / 1024 / 1024:.1f}MB")
print(f"Peak: {peak / 1024 / 1024:.1f}MB")

tracemalloc.stop()
```

## Performance Tuning Checklist

```markdown
## Performance Optimization Checklist

### Browser Configuration
- [ ] Use context pooling for repeated workflows
- [ ] Set appropriate viewport size (1280x720 optimal)
- [ ] Use headless mode
- [ ] Configure page timeouts (10s navigation, 5s actions)

### Step Execution
- [ ] Use specific selectors (ID or data-testid)
- [ ] Avoid arbitrary waits (use wait_for_selector)
- [ ] Batch form fills with evaluate when possible
- [ ] Use navigation waits instead of manual delays

### Resource Management
- [ ] Set memory limits per execution
- [ ] Monitor and limit concurrent executions
- [ ] Cleanup artifacts regularly
- [ ] Use compressed artifact storage (JPEG at 80%)

### Checkpoints
- [ ] Evaluate checkpoints asynchronously
- [ ] Minimize state size (reference artifacts, not content)
- [ ] Checkpoint only when needed

### Monitoring
- [ ] Profile step durations
- [ ] Monitor peak memory usage
- [ ] Track concurrent execution counts
- [ ] Alert on slow steps (>5s)

### Database (if applicable)
- [ ] Create execution indexes
- [ ] Use batch queries
- [ ] Archive old executions
```

## Performance Benchmarks

Run periodic benchmarks to track performance:

```python
# Benchmark simple form workflow
import timeit

def benchmark_login_workflow():
    times = []
    for _ in range(10):
        start = time.time()
        execution = LoginWorkflow().run()
        times.append(time.time() - start)
    
    print(f"Mean: {sum(times) / len(times):.2f}s")
    print(f"Median: {sorted(times)[len(times)//2]:.2f}s")
    print(f"P99: {sorted(times)[int(len(times) * 0.99)]:.2f}s")

benchmark_login_workflow()
```

Expected results for simple workflows:
- Mean: 3-5s
- P99: 8-12s (with network variance)

## Troubleshooting Performance Issues

### Issue: Workflow Takes >10s

```python
# 1. Profile steps
timeline = execution.get_timeline()
slow_step = max(timeline, key=lambda e: e['duration_ms'])
print(f"Slowest step: {slow_step['step']} ({slow_step['duration_ms']}ms)")

# 2. Check selector efficiency
logs = execution.get_logs(component='browser')
for log in logs:
    if 'selector' in str(log):
        print(f"Selector: {log['metadata'].get('selector')}")

# 3. Review network logs
network_logs = execution.get_logs(component='network')
print(f"Total network time: {sum(l['duration_ms'] for l in network_logs)}ms")
```

### Issue: High Memory Usage

```python
# 1. Check artifact sizes
artifacts = execution.get_artifacts()
total_size = sum(a['file_size_bytes'] for a in artifacts)
print(f"Total artifacts: {total_size / 1024 / 1024:.1f}MB")

# 2. Check screenshot frequency
screenshots = [a for a in artifacts if 'screenshot' in a['type']]
print(f"Screenshots: {len(screenshots)}")

# 3. Reduce quality or compression
artifact_manager.quality_jpeg = 75
```

### Issue: Timeouts Under Load

```python
# 1. Monitor CPU utilization
while workflow_running:
    cpu_percent = psutil.cpu_percent(interval=1)
    print(f"CPU: {cpu_percent}%")
    if cpu_percent > 80:
        print("⚠️  CPU constrained - reduce concurrent executions")

# 2. Reduce concurrent execution limit
execution_manager.max_concurrent_executions = 25

# 3. Increase timeouts
workflow.Config.navigation_timeout = 15000
```

## Summary

Key performance optimization strategies:

1. **Context pooling** (~400ms savings)
2. **Right-sized viewports** (~20-30% memory)
3. **Efficient selectors** (~500ms on forms)
4. **Minimal state serialization** (~100ms per checkpoint)
5. **Async checkpoints** (no execution blocking)
6. **Resource monitoring** (catch issues early)
7. **Profiling** (data-driven optimization)

Achieve 50-100 concurrent workflows on standard hardware with these techniques.
