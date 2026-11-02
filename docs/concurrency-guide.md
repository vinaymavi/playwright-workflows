# Concurrency Guide

**Last Updated**: 2025-01-31  
**Status**: Complete  
**Audience**: Developers, framework users, operators

---

## Table of Contents

1. [Execution Isolation](#execution-isolation)
2. [Resource Quotas](#resource-quotas)
3. [Concurrency Limits](#concurrency-limits)
4. [Semaphore Management](#semaphore-management)
5. [Practical Examples](#practical-examples)
6. [Troubleshooting](#troubleshooting)
7. [Performance Tuning](#performance-tuning)

---

## Execution Isolation

### What is Execution Isolation?

Execution isolation ensures that each workflow execution runs independently with its own state, resources, and context. Multiple workflows can execute concurrently without interfering with each other.

### How It Works

Each workflow execution maintains:

1. **Unique execution ID**: Every execution gets a UUID for identification
2. **Isolated state file**: State stored in `data/executions/{execution_id}.json`
3. **Isolated checkpoints**: Checkpoints stored with per-execution index
4. **Dedicated browser context**: Each workflow gets its own Playwright browser context
5. **Independent log file**: Logs written to `logs/{execution_id}.log`

### Example: Concurrent Login Workflows

```python
from src.cli.batch_runner import BatchRunner

# Create 10 workflows that will run in parallel
batch_runner = BatchRunner(max_concurrent=5)

workflow_specs = [
    {
        "workflow_type": "login",
        "input": {
            "url": "http://localhost:8000",
            "username": f"user_{i}",
            "password": f"pass_{i}",
        }
    }
    for i in range(10)
]

# Run batch - each workflow is isolated
result = await batch_runner.run_batch(workflow_specs)

# Each execution ran independently
print(f"Succeeded: {result.succeeded}, Failed: {result.failed}")
```

### State Isolation Benefits

- **No race conditions**: Each execution has its own state file
- **File-level locking**: Atomic state updates prevent corruption
- **No data cross-contamination**: Input for workflow A doesn't affect workflow B
- **Predictable results**: Same input always produces same result

### Isolation Boundaries

```
Execution 1 (user_0@example.com)
├── State: data/executions/uuid-1.json
├── Checkpoints: index-uuid-1.json
├── Browser: Context 1
└── Logs: logs/uuid-1.log

Execution 2 (user_1@example.com)
├── State: data/executions/uuid-2.json
├── Checkpoints: index-uuid-2.json
├── Browser: Context 2
└── Logs: logs/uuid-2.log

(No sharing between executions)
```

---

## Resource Quotas

### What is a Resource Quota?

Resource quotas limit the amount of resources each workflow execution can consume:

- **max_browser_pages**: Maximum number of browser pages per execution
- **max_memory_mb**: Maximum memory per execution (future enhancement)
- **max_checkpoint_size_mb**: Maximum checkpoint data size (future enhancement)

### Default Quotas

```python
DEFAULT_QUOTAS = {
    "max_browser_pages": 5,
}
```

### Setting Quotas

#### Global Quota (all executions)

```python
from src.framework.concurrency_manager import ConcurrencyManager

manager = ConcurrencyManager(max_concurrent=5)

# Set global quota - applies to all executions
await manager.set_execution_quota(
    execution_id=None,  # None means apply to all future executions
    quota_type="max_browser_pages",
    quota_value=10
)
```

#### Per-Execution Quota

```python
# Set quota specific to one execution
await manager.set_execution_quota(
    execution_id="abc-123-def",
    quota_type="max_browser_pages",
    quota_value=3
)
```

#### Pre-Acquisition Quota (before execution starts)

```python
# Set quota before acquiring execution slot
manager = ConcurrencyManager(max_concurrent=5)

# Set quota first
await manager.set_execution_quota(
    execution_id="pre-exec-1",
    quota_type="max_browser_pages",
    quota_value=5
)

# Then acquire slot - quota will be enforced
slot = await manager.acquire_execution_slot("pre-exec-1")
```

### Quota Enforcement

Quotas are checked when resources are requested:

```python
# Example: Opening a new browser page
async def open_browser_page(execution_id):
    # ConcurrencyManager checks: "Does execution_id have quota for another page?"
    # If max_browser_pages = 5, and already has 4 pages: ✓ OK
    # If max_browser_pages = 5, and already has 5 pages: ✗ ERROR - quota exceeded
    page = await browser_context.new_page()
```

### Quota Error Handling

```python
from src.framework.errors import ResourceQuotaExceededError

try:
    slot = await manager.acquire_execution_slot(execution_id)
except ResourceQuotaExceededError as e:
    print(f"Quota exceeded: {e}")
    # Handle gracefully: queue for retry, reduce scope, or fail execution
```

### Recommended Quotas by Workflow Type

| Workflow Type | max_browser_pages | Notes |
|---|---|---|
| Simple login | 1-2 | Single page navigation |
| Form filling | 2-3 | May need extra pages for navigation |
| Multi-step form | 3-5 | Tabs/windows for comparison |
| Web scraping | 5-10 | Parallel page loading |
| API testing | 1 | Single page for API calls |

---

## Concurrency Limits

### What is Concurrency Limit?

The concurrency limit (`max_concurrent`) controls how many workflows can execute simultaneously. This prevents resource exhaustion and manages system load.

### Setting Concurrency Limit

```python
from src.cli.batch_runner import BatchRunner

# Max 5 workflows run at the same time
runner = BatchRunner(max_concurrent=5)

# When you have 10 workflows:
# Time 0-30s: Workflows 1-5 run
# Time 30-60s: Workflows 6-10 run
```

### How ConcurrencyManager Enforces Limits

```python
from src.framework.concurrency_manager import ConcurrencyManager

manager = ConcurrencyManager(max_concurrent=5)

# Try to run 10 workflows
for i in range(10):
    # Acquire slot - waits if max_concurrent is reached
    slot = await manager.acquire_execution_slot(f"exec-{i}")
    
    # Run workflow (while holding the slot)
    result = await run_workflow(f"exec-{i}")
    
    # Release slot - allows next workflow to acquire
    await manager.release_execution_slot(f"exec-{i}")
```

### Concurrency Limits by System Capacity

| System | Recommended max_concurrent | Notes |
|---|---|---|
| Laptop (8 core, 16GB RAM) | 3-5 | Browser contexts consume RAM |
| Desktop (16 core, 32GB RAM) | 10-15 | More resources available |
| CI/CD (GitHub Actions) | 2-3 | Limited VM resources |
| Production server (64 core) | 20-50 | Can handle high concurrency |

### Performance Impact

```python
# Scenario: 10 workflows, each takes 30 seconds

# max_concurrent=1 (sequential)
# Total time: ~300 seconds (5 minutes)
# Resource usage: Low
# Start time variance: None

# max_concurrent=5
# Total time: ~60 seconds (1 minute)
# Resource usage: Moderate
# Start time variance: Up to 60 seconds

# max_concurrent=10
# Total time: ~30 seconds
# Resource usage: High
# Start time variance: Max

# max_concurrent=50 (excessive)
# Total time: ~30 seconds
# Resource usage: System crash/timeout
# Start time variance: Max
```

---

## Semaphore Management

### What is a Semaphore?

A semaphore is a concurrency primitive that limits access to a resource. The ConcurrencyManager uses a semaphore to enforce the `max_concurrent` limit.

### How Semaphore Works

```python
# Semaphore with count=5 allows 5 concurrent acquisitions
semaphore = asyncio.Semaphore(5)

# First 5 calls to acquire() succeed immediately
await semaphore.acquire()  # OK (count=4 remaining)
await semaphore.acquire()  # OK (count=3 remaining)
await semaphore.acquire()  # OK (count=2 remaining)
await semaphore.acquire()  # OK (count=1 remaining)
await semaphore.acquire()  # OK (count=0 remaining)

# 6th call waits for a release()
await semaphore.acquire()  # WAITS until count > 0

# When another task releases, 6th call proceeds
# await semaphore.release()  # Called by another task
# (6th acquire() now proceeds, count=0 again)
```

### Deadlock Prevention

**Original Problem**: Deadlock when holding async lock during semaphore acquisition

```python
# ❌ WRONG - Can cause deadlock
async def acquire_slot_buggy(self):
    async with self._lock:  # Acquire lock
        if not self._is_executing(execution_id):
            # Waiting here with lock held = DEADLOCK!
            # Another task can't acquire lock to release slot
            await self._semaphore.acquire()
```

**Solution**: Three-phase pattern separates lock-protected sections from blocking operations

```python
# ✓ CORRECT - No deadlock
async def acquire_slot(self, execution_id):
    # Phase 1: Check state under lock (fast, non-blocking)
    async with self._lock:
        if not self._is_executing(execution_id):
            mark_as_pending(execution_id)
    
    # Phase 2: Acquire semaphore outside lock (can block, other tasks can proceed)
    await self._semaphore.acquire()
    
    # Phase 3: Register as executing under lock (fast)
    async with self._lock:
        mark_as_executing(execution_id)
```

### Tuning Semaphore Count

The semaphore count should equal `max_concurrent`:

```python
from src.framework.concurrency_manager import ConcurrencyManager

# Semaphore internally created with count = max_concurrent
manager = ConcurrencyManager(max_concurrent=10)
# → Semaphore(10) is created internally

# To change semaphore limit, change max_concurrent
# (No separate semaphore tuning needed)
```

---

## Practical Examples

### Example 1: Sequential vs Parallel Execution

```python
from src.cli.batch_runner import BatchRunner
import time

async def compare_execution_modes():
    # Scenario: 6 form-filling workflows
    workflow_specs = [
        {
            "workflow_type": "form_fill",
            "input": {
                "url": "http://example.com/form",
                "form_data": {"name": f"User {i}", "email": f"user{i}@example.com"}
            }
        }
        for i in range(6)
    ]
    
    # Mode 1: Sequential (max_concurrent=1)
    sequential_runner = BatchRunner(max_concurrent=1)
    start = time.time()
    seq_result = await sequential_runner.run_batch(workflow_specs)
    seq_time = time.time() - start
    print(f"Sequential: {seq_time:.2f}s for {seq_result.total_workflows} workflows")
    
    # Mode 2: Parallel (max_concurrent=3)
    parallel_runner = BatchRunner(max_concurrent=3)
    start = time.time()
    par_result = await parallel_runner.run_batch(workflow_specs)
    par_time = time.time() - start
    print(f"Parallel (3 concurrent): {par_time:.2f}s for {par_result.total_workflows} workflows")
    
    # Mode 3: Aggressive parallel (max_concurrent=6)
    aggressive_runner = BatchRunner(max_concurrent=6)
    start = time.time()
    agg_result = await aggressive_runner.run_batch(workflow_specs)
    agg_time = time.time() - start
    print(f"Aggressive (6 concurrent): {agg_time:.2f}s for {agg_result.total_workflows} workflows")
    
    # Results:
    # Sequential: ~180s (30s per workflow × 6)
    # Parallel (3): ~60s (two batches of 3, 30s each)
    # Aggressive (6): ~30s (one batch of 6, 30s total)
```

### Example 2: Quota-Limited Workflows

```python
from src.framework.concurrency_manager import ConcurrencyManager

async def run_with_quotas():
    manager = ConcurrencyManager(max_concurrent=5)
    
    # Set global quota: max 3 browser pages per execution
    await manager.set_execution_quota(
        execution_id=None,  # Global
        quota_type="max_browser_pages",
        quota_value=3
    )
    
    # Execution 1: Uses default quota (3 pages)
    slot1 = await manager.acquire_execution_slot("exec-1")
    await run_workflow_with_pages("exec-1", 3)  # OK
    await manager.release_execution_slot("exec-1")
    
    # Execution 2: Set custom quota (5 pages)
    await manager.set_execution_quota(
        execution_id="exec-2",
        quota_type="max_browser_pages",
        quota_value=5
    )
    slot2 = await manager.acquire_execution_slot("exec-2")
    await run_workflow_with_pages("exec-2", 5)  # OK
    await manager.release_execution_slot("exec-2")
```

### Example 3: Error Handling in Concurrent Execution

```python
from src.cli.batch_runner import BatchRunner

async def handle_errors_gracefully():
    runner = BatchRunner(max_concurrent=5)
    
    workflow_specs = [
        {
            "workflow_type": "login",
            "input": {
                "url": "http://localhost:8000",
                "username": f"user_{i}",
                "password": f"pass_{i}",
            }
        }
        for i in range(10)
    ]
    
    result = await runner.run_batch(workflow_specs)
    
    # Some succeeded, some failed
    print(f"Succeeded: {result.succeeded}/{result.total_workflows}")
    print(f"Failed: {result.failed}/{result.total_workflows}")
    
    # Inspect errors
    if result.errors:
        for error in result.errors:
            execution_id = error.get("execution_id")
            error_msg = error.get("error")
            print(f"Execution {execution_id} failed: {error_msg}")
    
    # Retry failed executions
    if result.failed > 0:
        failed_specs = [spec for spec in workflow_specs if spec not in result.results]
        retry_result = await runner.run_batch(failed_specs)
        print(f"Retry succeeded: {retry_result.succeeded}/{len(failed_specs)}")
```

### Example 4: Dynamic Concurrency Adjustment

```python
from src.framework.concurrency_manager import ConcurrencyManager

async def adjust_concurrency_dynamically():
    # Start with conservative limit
    manager = ConcurrencyManager(max_concurrent=3)
    
    # Monitor resource usage
    successful_batches = 0
    
    while workflow_queue:
        try:
            # Run batch with current concurrency limit
            slot = await manager.acquire_execution_slot(execution_id)
            result = await run_workflow(execution_id)
            await manager.release_execution_slot(execution_id)
            
            successful_batches += 1
            
            # If successful and resources available, increase concurrency
            if successful_batches >= 3:
                new_limit = min(manager.max_concurrent + 2, 20)
                manager = ConcurrencyManager(max_concurrent=new_limit)
                print(f"Increased concurrency to {new_limit}")
                
        except ResourceExhaustedError:
            # If resource error, decrease concurrency
            new_limit = max(manager.max_concurrent - 1, 1)
            manager = ConcurrencyManager(max_concurrent=new_limit)
            print(f"Decreased concurrency to {new_limit} due to resource error")
```

---

## Troubleshooting

### Issue: Workflows Hanging/Deadlocking

**Symptom**: Workflows start but never complete; waits indefinitely

**Causes**:
1. Semaphore held while waiting for lock
2. Circular wait between executions
3. Resource quota impossible to satisfy

**Solution**:
```python
# Enable verbose logging to trace execution
import logging
logging.basicConfig(level=logging.DEBUG)

# Use shorter timeout to detect hangs
# Manually increase timeout if workflows are legitimately slow
workflow_timeout = 60  # seconds
```

### Issue: Resource Quota Exceeded

**Symptom**: `ResourceQuotaExceededError: exceeded max_browser_pages`

**Causes**:
1. Quota set too low for workflow needs
2. Browser pages not being closed
3. Memory leak in pages

**Solution**:
```python
# Check current quota
quota = await manager._get_execution_quota(execution_id, "max_browser_pages")
print(f"Current quota: {quota}")

# Increase quota
await manager.set_execution_quota(
    execution_id=execution_id,
    quota_type="max_browser_pages",
    quota_value=10  # Increase from default 5
)

# Check for page leaks
async def cleanup_pages(context):
    for page in context.pages:
        if not page_in_use(page):
            await page.close()
```

### Issue: Some Workflows Fail, Others Succeed

**Symptom**: Partial failures in batch execution; unrelated workflows fail

**Causes**:
1. Race condition in shared resource (unlikely with proper isolation)
2. Environment issues (server down, network timeout)
3. Workflow-specific bug triggered by concurrency

**Solution**:
```python
# Retry failed executions individually
result = await runner.run_batch(workflow_specs)

if result.failed > 0:
    # Get failed execution details
    for error in result.errors:
        execution_id = error["execution_id"]
        
        # Find original spec
        original_spec = next(
            (s for s in workflow_specs if s["input"] == spec_input),
            None
        )
        
        # Retry with detailed logging
        await run_single_workflow_with_logging(original_spec, execution_id)
```

### Issue: Concurrency Limit Not Respected

**Symptom**: More workflows running simultaneously than `max_concurrent`

**Causes**:
1. Multiple BatchRunner instances with different limits
2. Manual execution outside of manager
3. External workflow runner ignoring concurrency

**Solution**:
```python
# Verify concurrency manager is used
manager = ConcurrencyManager(max_concurrent=5)

# All executions must use this manager
async def run_with_manager(execution_id):
    slot = await manager.acquire_execution_slot(execution_id)
    try:
        return await workflow.execute()
    finally:
        await manager.release_execution_slot(execution_id)

# Don't bypass manager
# ❌ BAD: workflow.execute()  # Ignores concurrency limit
# ✓ GOOD: await run_with_manager(execution_id)  # Respects limit
```

---

## Performance Tuning

### Optimization Checklist

- [ ] **Concurrency Limit**: Set to 1.5-2.5x CPU cores (e.g., 4 cores → max_concurrent=6-10)
- [ ] **Resource Quotas**: Match workflow requirements (test first with dry run)
- [ ] **Log Level**: Use INFO in production, DEBUG only when troubleshooting
- [ ] **Batch Size**: Process batches of 50-100, not 10000 at once
- [ ] **Memory Monitoring**: Monitor RSS after each batch to detect leaks
- [ ] **Network**: Ensure server can handle concurrent connections
- [ ] **Storage**: Check disk space for state files and logs

### Performance Tuning Steps

**Step 1: Establish Baseline**
```python
# Run 10 workflows sequentially, measure time
sequential_time = await run_batch_with_concurrency(10, max_concurrent=1)
print(f"Baseline (1 concurrent): {sequential_time}s")
```

**Step 2: Test Progressive Concurrency**
```python
for max_concurrent in [2, 3, 5, 10, 20]:
    execution_time = await run_batch_with_concurrency(10, max_concurrent)
    print(f"Max concurrent={max_concurrent}: {execution_time}s")
    
# Look for sweet spot where time decreases with diminishing returns
```

**Step 3: Monitor Resource Usage**
```python
import psutil

async def monitor_batch_execution():
    process = psutil.Process()
    
    result = await runner.run_batch(workflows)
    
    print(f"Peak memory: {process.memory_info().rss / 1024 / 1024:.0f} MB")
    print(f"Execution time: {result.total_time_seconds:.2f}s")
    
    # Repeat with different max_concurrent values
    # Find point where memory plateaus (indicates resource limit)
```

**Step 4: Fine-Tune**
```python
# Based on monitoring, set optimal max_concurrent
OPTIMAL_MAX_CONCURRENT = 8  # Adjust based on your results

runner = BatchRunner(max_concurrent=OPTIMAL_MAX_CONCURRENT)
```

### Common Performance Issues

| Issue | Cause | Solution |
|---|---|---|
| High memory usage | Too many concurrent contexts | Reduce `max_concurrent` |
| Timeout errors | Workflow taking longer than timeout | Increase timeout, or reduce `max_concurrent` to give each more resources |
| CPU always 100% | Too high `max_concurrent` | Reduce by 20-30% |
| Uneven execution time | Resource starvation | Check for resource leaks, reduce `max_concurrent` |
| Some workflows fail, others succeed | Quota too low | Increase quota for failing workflows |

---

## Best Practices

1. **Always acquire and release slots**: Forgetting to release blocks other executions
2. **Set realistic quotas**: Too low → frequent failures; too high → wasted resources
3. **Test concurrency settings**: Optimal value is environment-specific
4. **Monitor production**: Alert on concurrent execution failures
5. **Log execution details**: Include execution_id in all logs for debugging
6. **Handle partial failures**: Batch execution may have some succeed, some fail
7. **Clean up resources**: Close browser pages, clean temporary files
8. **Implement backpressure**: Don't queue unlimited workflows; pause intake when queue is full

---

## See Also

- [Framework Architecture](../architecture.md)
- [Workflow API Reference](../api-reference.md)
- [Error Handling Guide](./error-handling.md)
- [Testing Guide](../testing.md)
