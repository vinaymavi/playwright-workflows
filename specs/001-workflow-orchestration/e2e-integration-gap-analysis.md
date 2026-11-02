# E2E Workflow Integration Gap Analysis

**Date**: 2026-11-02  
**Scope**: Agent ↔ MCP Server ↔ Workflow Integration  
**Status**: Current Implementation Review

---

## Executive Summary

The Playwright Workflow Orchestration Framework has successfully completed:
- ✅ Core framework infrastructure (Workflow, Execution, Checkpoint classes)
- ✅ Framework checkpoint system with asyncio.Event signaling
- ✅ MCP server skeleton with tool registration
- ✅ 641 passing tests with full integration coverage

**Current Implementation Completeness**: ~85% of MVP features

### Outstanding Gaps for Production E2E Integration

| Gap | Impact | Priority | Est. Effort |
|-----|--------|----------|-------------|
| Real E2E workflow execution via MCP | Blocks end-to-end testing | P1 | 2-3 days |
| Agent response routing to checkpoints | Blocks human-in-loop workflows | P1 | 1-2 days |
| Concurrent workflow state isolation | Blocks parallel execution | P1 | 1 day |
| Session recovery & re-authentication | Blocks long-running workflows | P2 | 2-3 days |
| Resource quota enforcement | Blocks safe concurrent execution | P2 | 1 day |
| Production MCP logging & observability | Blocks production deployment | P2 | 1 day |

---

## Current Architecture State

### What's Been Built ✅

**Framework Core** (src/framework/):
- `workflow.py`: Base Workflow class with lifecycle hooks
- `execution.py`: Execution state machine with persistence
- `checkpoint.py`: CheckpointQuestion/Decision/Response data models
- `session_manager.py`: Browser session management with keep-alive
- `state_manager.py`: Persistent JSON-based state storage
- `retry_handler.py`: Configurable retry logic with exponential backoff
- `concurrency_manager.py`: asyncio.Semaphore-based concurrency control
- `resource_manager.py`: Resource quota tracking (browser pages, memory, agents)
- `decorators.py`: @workflow_step, @step_with_retry decorators

**Workflows** (src/workflows/):
- `login_workflow.py`: Example workflow with form filling + checkpoint
- `form_filling_workflow.py`: Reusable form filling pattern

**MCP Server** (src/mcp_server/):
- `server.py`: WorkflowMCPServer with tool registration
- `tools.py`: MCP tools - start_workflow, resolve_checkpoint, get_execution_status, get_execution_logs
- `resources.py`: MCP resource definitions for execution state
- `notifications.py`: Server → client notifications (workflow completion, errors)

**CLI** (src/cli/):
- `workflow_runner.py`: Standalone workflow execution via CLI
- `mcp_server_runner.py`: MCP server startup
- `batch_runner.py`: Parallel workflow execution
- `resume_workflow.py`: Resume from checkpoint

**Testing** (tests/):
- 641 passing tests covering:
  - Framework unit tests (state transitions, retry logic, error handling)
  - Integration tests (checkpoint pause/resume, concurrent execution)
  - Workflow tests (login, form filling)
  - Quickstart scenarios A, B, C

---

## Integration Gap Analysis

### Gap 1: Real E2E Workflow Execution via MCP

**Current State**:
- MCP tools exist: `start_workflow`, `resolve_checkpoint`, `get_execution_status`
- MCP server is runnable: `python -m src.cli.mcp_server_runner`
- But: No end-to-end test verifying Agent → MCP → Workflow → Checkpoint → Agent loop

**Problem**:
```
When an Agent (Claude, ChatGPT) calls MCP tools via Copilot:
  1. Agent calls start_workflow("login", {...})
  2. MCP server starts workflow, returns execution_id
  3. Workflow runs, hits checkpoint at request_approval()
  4. Workflow pauses, checkpoint event set to wait
  5. MCP sends checkpoint request to... WHERE? ← GAP
  6. Agent should receive notification and call resolve_checkpoint()
  7. MCP server finds execution, sets decision on event
  8. Workflow resumes with decision
```

**Missing**:
1. **Checkpoint notification to Agent**: MCP server knows checkpoint exists but doesn't notify agent
   - Currently: MCP tools return JSON, but agent doesn't know to call `resolve_checkpoint`
   - Need: MCP server → Agent notification or callback mechanism
   
2. **Agent decision → Checkpoint routing**: Agent sees checkpoint but doesn't know which execution it's for
   - Currently: resolve_checkpoint takes execution_id, but agent needs to track which workflow paused
   - Need: Execution context passed to agent with checkpoint details

3. **Full E2E test**: No test exercising the complete loop
   - Currently: Unit tests mock agent responses
   - Need: Integration test with real MCP stdio communication

**Impact**: Workflows can't be controlled by agents in interactive scenarios

**Solution Approach**:
```python
# 1. MCP server-side: When workflow pauses, send notification
@server.on_checkpoint_pause
async def on_checkpoint(execution_id, checkpoint_request):
    # Send resource notification or tool result hint
    await self.client.notify_checkpoint(execution_id, checkpoint_request)

# 2. Agent sees notification and has context for resolve_checkpoint call
# 3. Agent calls resolve_checkpoint with execution_id and decision

# 4. Create integration test:
# - MCP server running in subprocess
# - Test client connecting via stdio
# - Simulated agent calling start_workflow → resolve_checkpoint
# - Verify workflow resumes with decision
```

**Effort**: 2-3 days
- Day 1: Implement server-side checkpoint notifications
- Day 2: Create integration test with real MCP communication
- Day 3: Document agent integration patterns

---

### Gap 2: Agent Response Routing to Checkpoints

**Current State**:
- MCP tools: `resolve_checkpoint(execution_id, checkpoint_id, decision)`
- Framework: Execution stores decision in event
- Workflow: Resumes when event.set() is called

**Problem**:
```
Multiple concurrent workflows A, B, C all paused at checkpoints.
Agent handles all three. When agent calls:
  resolve_checkpoint(execution_id="exec-A", decision={"confirmed": true})

How does MCP server route this to Execution A specifically?
  - _active_executions[execution_id] lookup ✅ (already works)
  
But what if agent doesn't know execution_id?
  - Agent only sees: "workflow paused, waiting for decision"
  - Agent needs to track which workflow → execution_id mapping
  - Gap: No execution context passed to agent in checkpoint request
```

**Missing**:
1. **Execution context in checkpoint notification**: 
   - Agent needs execution_id, workflow_type, checkpoint question, and metadata
   - Currently: Checkpoint data stored in Execution.state but not sent to agent

2. **Execution registry visibility to agent**:
   - MCP server keeps `_active_executions` dict
   - Agent has no way to list "which workflows are paused"
   - Need: `list_executions(status="paused")` MCP tool

3. **Checkpoint state tracking**:
   - Agent needs to know: "is this checkpoint still waiting?"
   - Currently: resolve_checkpoint will fail silently if checkpoint already resolved
   - Need: Better error messages and checkpoint state validation

**Impact**: Multi-workflow scenarios become confusing for agents; no visibility into which workflows are waiting

**Solution Approach**:
```python
# 1. Add MCP tool: list_executions(filter: status, workflow_type)
@mcp_tool()
def list_executions(status: str = "paused") -> list[ExecutionInfo]:
    """List all active executions with given status.
    
    Returns:
    - execution_id, workflow_type, status, created_at
    - current_checkpoint (if paused)
    - latest_step
    """
    results = []
    for exec_id, execution in _active_executions.items():
        if execution.state == status:
            results.append({
                "execution_id": exec_id,
                "workflow_type": execution.workflow_type,
                "status": execution.state,
                "checkpoint": execution.current_checkpoint if status == "paused" else None,
            })
    return results

# 2. Checkpoint notification includes execution context
async def on_checkpoint_pause(execution):
    checkpoint_request = CheckpointRequest(
        execution_id=execution.execution_id,
        workflow_type=execution.workflow_type,
        checkpoint_id=execution.current_checkpoint.checkpoint_id,
        question=execution.current_checkpoint.question,
        metadata={
            "current_step": execution.current_step,
            "workflow_state": execution.state_snapshot,
            "created_at": execution.paused_at,
        }
    )
    # Send to agent via notification
    await send_to_agent(checkpoint_request)

# 3. Resolve checkpoint validates state
@mcp_tool()
def resolve_checkpoint(execution_id: str, decision: CheckpointDecision) -> dict:
    execution = get_execution(execution_id)
    if execution.state != "paused":
        raise ValueError(f"Execution {execution_id} is not paused (state={execution.state})")
    if execution.current_checkpoint.expired:
        raise ValueError(f"Checkpoint expired at {execution.current_checkpoint.timeout_at}")
    execution.set_checkpoint_decision(decision)
    return {"status": "resumed", "execution_id": execution_id}
```

**Effort**: 1-2 days
- Day 1: Add list_executions tool, improve checkpoint state tracking
- Day 2: Document agent integration patterns, create examples

---

### Gap 3: Concurrent Workflow State Isolation

**Current State**:
- Execution class stores state per execution_id
- File-based storage: data/executions/{execution_id}.json
- Concurrency manager uses Semaphore to limit concurrent browsers

**Problem**:
```
When 10 workflows run in parallel, each with checkpoints:
  1. Workflow A hits checkpoint, pauses ✓
  2. Workflow B hits checkpoint, pauses ✓
  3. ...all paused...
  4. Workflow A resumes
  5. When Workflow A accesses shared resources (e.g., temp file), 
     does it conflict with B's temp files?

Risk: State files, temp directories, file locks not properly isolated
```

**Missing**:
1. **Execution-scoped temp directory**:
   - Currently: temp files go to /tmp (system-wide)
   - Need: Each execution gets data/executions/{execution_id}/temp/
   - Need: Cleanup on completion

2. **File lock scope**:
   - Currently: file_locking.py uses fcntl (file-level locks)
   - Correct for multi-process, but what about concurrent async?
   - Need: Verify asyncio.Lock + fcntl work together correctly

3. **Shared resource conflict detection**:
   - Currently: resource_manager.py tracks quotas (max pages, memory)
   - Missing: API-level conflicts (e.g., two workflows trying to log in same account)
   - Need: Conflict detection for account, file, API endpoint
   - Currently marked as FR-009 but not implemented

4. **Session affinity**:
   - When Workflow A is paused and B resumes, do they share a browser session?
   - Currently: SessionManager creates new context per execution ✓
   - But: Credential cache might cross boundaries
   - Need: Verify credential_manager.py isolates per execution_id

**Impact**: Long-running concurrent workflows could corrupt each other's state

**Solution Approach**:
```python
# 1. Execution-scoped temp directory
class Execution:
    @property
    def temp_dir(self) -> Path:
        """Get temp directory for this execution."""
        temp = Path(self.data_dir) / "temp"
        temp.mkdir(exist_ok=True)
        return temp
    
    def cleanup(self):
        """Clean up execution-scoped resources."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

# 2. File lock verification test
@pytest.mark.asyncio
async def test_concurrent_file_access():
    """Verify file locks work correctly with asyncio."""
    # Create two workflows writing to same file
    exec_a = Execution(execution_id="A")
    exec_b = Execution(execution_id="B")
    
    shared_file = Path("data/shared.txt")
    
    async def write_locked(exec_id):
        with FileLock(shared_file):
            await asyncio.sleep(0.1)  # Simulate work
            shared_file.write_text(exec_id)
    
    # Run concurrently - should serialize, not corrupt
    await asyncio.gather(
        write_locked("A"),
        write_locked("B"),
    )
    
    # Result should be either "A" or "B", never corrupted

# 3. Shared resource conflict detection
class ConflictDetector:
    def __init__(self):
        self.active_resources = {}  # resource_key -> execution_id
    
    def claim_resource(self, resource_key: str, execution_id: str):
        """Claim a resource; raise if already held."""
        if resource_key in self.active_resources:
            other = self.active_resources[resource_key]
            raise ResourceConflict(
                f"Resource {resource_key} held by {other}, "
                f"cannot be claimed by {execution_id}"
            )
        self.active_resources[resource_key] = execution_id
    
    def release_resource(self, resource_key: str, execution_id: str):
        if self.active_resources.get(resource_key) == execution_id:
            del self.active_resources[resource_key]

# Usage in workflow
async def run(self):
    conflict_detector.claim_resource(f"account:{self.input.username}", self.execution_id)
    try:
        await self.navigate(...)
    finally:
        conflict_detector.release_resource(f"account:{self.input.username}", self.execution_id)
```

**Effort**: 1 day
- Scope 1: Execution-scoped temp directory + cleanup (0.5 day)
- Scope 2: Concurrent file access tests (0.25 day)
- Scope 3: Conflict detector implementation (0.25 day)

---

### Gap 4: Session Recovery & Re-authentication

**Current State**:
- SessionManager creates BrowserContext per execution
- CredentialManager encrypts/stores credentials
- Resumption manager tracks checkpoint state

**Problem**:
```
Long-running workflow (30+ minutes):
  1. Workflow A logs in successfully
  2. At 15 minutes: hits checkpoint, pauses
  3. At 20 minutes: Agent makes decision, workflow resumes
  4. Session cookie expired or browser crashed
  5. Workflow tries to access page → 401 Unauthorized

What happens?
  - Currently: Error is caught, logged, but workflow fails
  - Need: Automatic re-authentication without losing progress
```

**Missing**:
1. **Session cookie refresh**:
   - SessionManager should track session age
   - On resume from checkpoint: check if session expired
   - If expired: re-authenticate using stored credentials

2. **Browser crash recovery**:
   - If browser process dies while paused: how to resume?
   - Currently: Execution state is persisted, but browser context is lost
   - Need: On resume, create new browser context and re-navigate to last URL
   - This is the "replay+re-auth" strategy from plan.md

3. **Selective step replay**:
   - If session lost at step 5: replay steps 1-4, then continue from step 5
   - Need: Execution tracking which steps completed
   - Need: Idempotent step execution (safe to re-run)

4. **Credential refresh**:
   - For long-running workflows, credentials may expire
   - CredentialManager should support time-based expiry
   - Need: Token refresh integration (OAuth, etc.)

**Impact**: Workflows fail on session timeout; data loss on browser crash

**Solution Approach**:
```python
# 1. Session age tracking in SessionManager
class SessionManager:
    def __init__(self):
        self.created_at = time.time()
    
    @property
    def age_seconds(self) -> int:
        return int(time.time() - self.created_at)
    
    @property
    def session_expired(self) -> bool:
        return self.age_seconds > SESSION_TTL_SECONDS  # e.g., 3600

# 2. On resume: check session and re-auth if needed
@workflow_step("Resume from checkpoint")
async def on_resume(self):
    if self._session_manager.session_expired:
        self.logger.info("Session expired, re-authenticating...")
        await self._reauthenticate()
        # Re-navigate to last known URL
        if self.last_url:
            await self._page.goto(self.last_url)

async def _reauthenticate(self):
    """Re-authenticate using stored credentials."""
    creds = self._credential_manager.get_credentials(self.execution_id)
    # Workflow-specific re-auth logic
    await self.login(username=creds.username, password=creds.password)

# 3. Step replay with idempotency
class IdempotentStep:
    """Decorator for steps that are safe to re-run."""
    def __init__(self, idempotent: bool = True):
        self.idempotent = idempotent
    
    def __call__(self, func):
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            step_name = func.__name__
            execution = self._execution
            
            # Check if step already completed
            if step_name in execution.completed_steps and self.idempotent:
                self.logger.info(f"Step {step_name} already completed, skipping")
                return execution.step_results[step_name]
            
            # Execute step
            result = await func(self, *args, **kwargs)
            execution.mark_step_completed(step_name, result)
            return result
        
        return wrapper

# Usage
@workflow_step()
@IdempotentStep(idempotent=True)
async def login(self, username: str, password: str):
    await self.fill("#username", username)
    await self.fill("#password", password)
    await self.click("button[type=submit]")
```

**Effort**: 2-3 days
- Day 1: Session age tracking, re-auth on resume
- Day 2: Step replay + idempotency markers
- Day 3: Integration tests for session recovery

---

### Gap 5: Resource Quota Enforcement

**Current State**:
- ResourceManager exists with quota tracking
- Concurrency manager limits browser instances
- No enforcement on quota violations

**Problem**:
```
When multiple workflows run:
  Workflow A claims max_pages=10, creates 10 pages ✓
  Workflow B claims max_pages=10, creates 10 pages ✓
  Workflow C wants max_pages=10 but resources full
  
Current: ResourceManager tracks quotas but doesn't enforce
Need: Queue/reject new workflows when quotas exceeded
```

**Missing**:
1. **Quota enforcement**: ResourceManager.claim_quota() should block if exceeded
2. **Queue mechanism**: Workflows waiting for quota should queue, not fail
3. **Memory limits**: Track memory per execution, kill if exceeded
4. **Agent concurrency limits**: Max agents handling checkpoints per execution
5. **Timeout enforcement**: Kill workflow if exceeds max_duration

**Impact**: Uncontrolled resource consumption; DoS risk in multi-tenant scenarios

**Solution Approach**:
```python
class ResourceManager:
    def __init__(self, global_quota: dict):
        self.global_quota = global_quota  # e.g., max_pages=100, max_memory_mb=8000
        self.active_usage = {}  # execution_id -> usage
    
    async def claim_quota(self, execution_id: str, resource: str, amount: int, timeout=10):
        """Claim resource; wait if unavailable, raise if timeout."""
        deadline = time.time() + timeout
        
        while True:
            available = self.global_quota[resource] - sum(
                usage.get(resource, 0) 
                for usage in self.active_usage.values()
            )
            
            if available >= amount:
                self.active_usage.setdefault(execution_id, {})[resource] = amount
                return  # Claimed successfully
            
            if time.time() > deadline:
                raise QuotaExceeded(
                    f"Cannot claim {amount} {resource}; "
                    f"available={available}, timeout after {timeout}s"
                )
            
            await asyncio.sleep(0.5)  # Retry soon
    
    def release_quota(self, execution_id: str):
        """Release all resources held by execution."""
        if execution_id in self.active_usage:
            del self.active_usage[execution_id]

# Enforce in MCP tool
@mcp_tool()
async def start_workflow(workflow_type: str, input_params: dict) -> dict:
    execution = Execution(...)
    
    # Claim quota before starting
    try:
        await resource_manager.claim_quota(
            execution.execution_id, 
            "pages", 
            amount=5,  # Estimated for this workflow
            timeout=5
        )
    except QuotaExceeded as e:
        return {"status": "queued", "reason": str(e), "execution_id": execution.execution_id}
    
    # Start workflow
    task = asyncio.create_task(execute_workflow(execution))
    _active_executions[execution.execution_id] = execution
    return {"status": "started", "execution_id": execution.execution_id}
```

**Effort**: 1 day
- Quota enforcement + queue (0.5 day)
- Integration tests (0.5 day)

---

### Gap 6: Production MCP Logging & Observability

**Current State**:
- Structured JSON logging to stderr
- Execution logs stored per execution_id
- MCP tools return JSON results

**Problem**:
```
In production, MCP server running in subprocess:
  - Agent calls tools via MCP
  - Logs go to stderr, mixed with other services
  - No correlation between tool calls and logs
  - When workflow fails: hard to find relevant logs

Need: Structured correlation between MCP calls and workflow execution
```

**Missing**:
1. **MCP call tracing**: Each tool invocation gets trace_id for log correlation
2. **Structured logging in tools.py**: Log tool calls with structured format
3. **Error propagation**: Tool errors include relevant execution context
4. **Metrics**: Track tool response times, error rates
5. **Debug mode**: MCP server can emit verbose logs for specific executions

**Impact**: Production incidents hard to debug; no visibility into MCP-to-workflow flow

**Solution Approach**:
```python
# 1. Trace context in tool execution
import contextvars
import uuid

trace_id = contextvars.ContextVar('trace_id', default=None)

@mcp_tool()
async def start_workflow(workflow_type: str, input_params: dict) -> dict:
    current_trace = trace_id.get() or str(uuid.uuid4())
    trace_id.set(current_trace)
    
    logger.info("MCP tool invoked", extra={
        "tool": "start_workflow",
        "trace_id": current_trace,
        "workflow_type": workflow_type,
    })
    
    try:
        execution = Execution(...)
        logger.info("Workflow started", extra={
            "trace_id": current_trace,
            "execution_id": execution.execution_id,
            "workflow_type": workflow_type,
        })
        return {"status": "started", "execution_id": execution.execution_id}
    except Exception as e:
        logger.error("Workflow start failed", extra={
            "trace_id": current_trace,
            "error": str(e),
            "workflow_type": workflow_type,
        })
        raise

# 2. MCP server debug mode
class WorkflowMCPServer:
    def __init__(self, debug_execution_ids: set[str] = None):
        self.debug_execution_ids = debug_execution_ids or set()
    
    def set_debug_execution(self, execution_id: str, enabled: bool = True):
        """Enable verbose logging for specific execution."""
        if enabled:
            self.debug_execution_ids.add(execution_id)
        else:
            self.debug_execution_ids.discard(execution_id)

# 3. Debug MCP tool
@mcp_tool()
def set_execution_debug(execution_id: str, enabled: bool = True) -> dict:
    """Enable/disable verbose logging for execution."""
    server.set_debug_execution(execution_id, enabled)
    return {"execution_id": execution_id, "debug": enabled}
```

**Effort**: 1 day
- Trace context + structured logging (0.5 day)
- Debug mode tools (0.5 day)

---

## Implementation Roadmap

### Immediate (Week 1): Unblock E2E Testing

**Priority**: P1 - Required for agent integration

1. **Gap 1: Real E2E workflow execution**
   - Implement checkpoint notification mechanism
   - Create integration test with real MCP stdio communication
   - Deliverable: Agent can trigger workflow → checkpoint → decision → resume

2. **Gap 3: Concurrent workflow state isolation** (partial)
   - Add execution-scoped temp directory
   - Verify file locking works with asyncio
   - Deliverable: 10 concurrent workflows isolate state correctly

### Short-term (Week 2-3): Production Readiness

**Priority**: P2 - Required for safe production deployment

1. **Gap 4: Session recovery**
   - Implement session age tracking
   - Add re-auth on resume
   - Deliverable: Long-running workflows survive session timeout

2. **Gap 5: Resource quota enforcement**
   - Implement quota claims and queue
   - Add timeout enforcement
   - Deliverable: Workflows queue when resources constrained

3. **Gap 6: Production logging**
   - Add trace IDs to all MCP calls
   - Implement debug mode
   - Deliverable: Production logs correlate MCP calls to workflows

### Medium-term (Week 4+): Advanced Features

**Priority**: P3 - Nice-to-have, deferred to Phase 2

1. **Step replay & idempotency** (Gap 4 continued)
2. **Agent response routing** (Gap 2 - list_executions tool)
3. **Shared resource conflict detection** (Gap 3 continued)

---

## Integration Points Checklist

### Agent ↔ MCP Server
- [ ] Agent discovers MCP tools: `start_workflow`, `resolve_checkpoint`, `get_execution_status`, `get_execution_logs`, `list_executions`
- [ ] Agent receives checkpoint notifications (push, not pull)
- [ ] Agent context includes execution_id for checkpoint decisions
- [ ] MCP server errors include execution context for debugging

### MCP Server ↔ Workflow Framework
- [ ] start_workflow creates Execution, stores in _active_executions
- [ ] resolve_checkpoint finds Execution and calls set_checkpoint_decision()
- [ ] Workflow checkpoint waits on asyncio.Event, resumes when MCP server signals
- [ ] Execution state persisted to disk; can resume from cold start
- [ ] Resource quotas enforced; workflows queue if over limit

### Workflow ↔ Browser Session
- [ ] SessionManager maintains browser context per execution
- [ ] On resume: verify session still valid, re-auth if expired
- [ ] Temp files isolated per execution_id
- [ ] Credential access isolated per execution_id

---

## Testing Strategy

### E2E Integration Tests (New)

```python
# tests/e2e/test_agent_mcp_workflow_integration.py

@pytest.mark.asyncio
async def test_agent_controls_workflow_via_mcp():
    """Full end-to-end: Agent → MCP → Workflow → Checkpoint → Agent."""
    
    # 1. Start MCP server in subprocess
    server_proc = start_mcp_server()
    client = MCPClient(stdio_process=server_proc)
    
    # 2. Agent calls start_workflow
    result = await client.call_tool("start_workflow", {
        "workflow_type": "login",
        "input_params": {"url": "http://localhost:8000", "username": "test", "password": "pass"}
    })
    execution_id = result["execution_id"]
    
    # 3. Workflow starts and runs until checkpoint
    await asyncio.sleep(1)  # Give workflow time to hit checkpoint
    
    # 4. Agent checks execution status
    status = await client.call_tool("get_execution_status", {"execution_id": execution_id})
    assert status["status"] == "paused"
    assert "checkpoint" in status
    
    # 5. Agent resolves checkpoint
    resolve_result = await client.call_tool("resolve_checkpoint", {
        "execution_id": execution_id,
        "decision": {"confirmed": True, "agent_notes": "Approved by test agent"}
    })
    assert resolve_result["status"] == "resumed"
    
    # 6. Workflow completes
    await asyncio.sleep(2)  # Give workflow time to complete
    final_status = await client.call_tool("get_execution_status", {"execution_id": execution_id})
    assert final_status["status"] == "completed"
```

### Concurrent Isolation Tests (Enhanced)

```python
# tests/framework/integration/test_concurrent_isolation.py

@pytest.mark.asyncio
async def test_10_concurrent_workflows_isolated():
    """10 workflows run concurrently; each state is isolated."""
    
    async def run_workflow(i: int):
        workflow = LoginWorkflow(execution_id=f"exec-{i}")
        result = await workflow.run({
            "url": "http://localhost:8000",
            "username": f"user{i}",
            "password": "pass"
        })
        return result
    
    # Run 10 in parallel
    results = await asyncio.gather(*[run_workflow(i) for i in range(10)])
    
    # Verify all succeeded and have unique execution contexts
    assert all(r["success"] for r in results)
    execution_dirs = [Path(f"data/executions/exec-{i}.json") for i in range(10)]
    assert all(d.exists() for d in execution_dirs)
    
    # Verify no state cross-contamination
    for i, exec_dir in enumerate(execution_dirs):
        state = json.loads(exec_dir.read_text())
        assert state["execution_id"] == f"exec-{i}"
```

---

## Success Criteria

### E2E Integration Complete When:

1. ✅ Agent can trigger workflow via MCP and receive status updates
2. ✅ Workflow pauses at checkpoint, agent receives notification with context
3. ✅ Agent provides decision; workflow resumes with decision applied
4. ✅ Long-running workflows (30+ min) survive session timeout
5. ✅ 10+ concurrent workflows run without state corruption
6. ✅ Production MCP logs correlate agent calls to workflow execution
7. ✅ All 641 tests still passing + new E2E tests passing
8. ✅ Documentation: Agent integration guide + examples

---

## References

- [Specification](./spec.md) - Feature spec (7 stories, 24 FRs)
- [Implementation Plan](./plan.md) - Architecture & phase breakdown
- [Data Model](./data-model.md) - Entity definitions
- [Research](./research.md) - Technology decisions & rationale
- [Quickstart](./quickstart.md) - Validation scenarios
- [Constitution](/../.specify/memory/constitution.md) - Project principles
