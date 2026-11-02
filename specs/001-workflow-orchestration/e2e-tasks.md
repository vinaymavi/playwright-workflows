# Tasks: E2E Workflow Integration (Agent ↔ MCP ↔ Workflows)

**Reference**: [E2E Gap Analysis](./e2e-integration-gap-analysis.md) | [Implementation Roadmap](./e2e-implementation-roadmap.md)

**Status**: Phase A (E2E Agent Integration) - IN PROGRESS

**Total Tasks**: 24 implementation tasks across 5 phases

---

## Phase A: E2E Agent Integration (3 days)

**Goal**: Enable Agent → MCP → Workflow → Checkpoint → Agent loop  
**Prerequisite**: Phases 1-10 complete (framework core + checkpoint system)  
**Deliverable**: Real end-to-end MCP communication with workflow control

### A.1 Checkpoint Notifications (4-6 hours)

- [x] A.1.1 Add `on_checkpoint_pause` callback hook to WorkflowMCPServer
  - Location: src/mcp_server/server.py
  - When workflow pauses: trigger callback with execution_id + checkpoint_request
  - Callback can send notification or log for agent
  - **COMPLETED**: Integrated NotificationService.checkpoint_requested() call in workflow.py checkpoint() method

- [x] A.1.2 Implement MCP notification mechanism (choose one approach)
  - Option A: Tool result hints in start_workflow response
  - Option B: Server-initiated notifications via MCP protocol
  - Option C: External event queue (file-based or pub-sub)
  - **Decision**: Using NotificationService with asyncio queue pattern (existing in codebase)

- [x] A.1.3 Update resolve_checkpoint tool documentation
  - Add example: Agent receives notification, calls resolve_checkpoint with execution_id
  - Add example: Multiple concurrent workflows, agent tracks each
  - **COMPLETED**: Added inline documentation in tools.py

- [x] A.1.4 Test checkpoint notification
  - Unit test: Mock callback receives checkpoint event
  - Verify: execution_id, checkpoint_id, question, metadata included
  - File: tests/mcp_server/test_checkpoint_notifications.py
  - **COMPLETED**: 3 notification service tests passing

### A.2 Execution Context in Checkpoint (4-6 hours)

- [x] A.2.1 Add `list_executions(status="paused")` MCP tool
  - Location: src/mcp_server/tools.py
  - Returns: List of paused executions with checkpoint context
  - Fields: execution_id, workflow_type, status, checkpoint_id, question, created_at
  - **COMPLETED**: Tool implemented with full filtering and pagination support

- [x] A.2.2 Include execution context in checkpoint notification
  - Add to checkpoint request: execution_id, workflow_type, current_step
  - Add to metadata: execution state snapshot (user inputs, step results)
  - Ensure agent has full context to make informed decision
  - **COMPLETED**: Checkpoint notification includes full CheckpointRequest (has all context fields)

- [x] A.2.3 Validate checkpoint state when resolving
  - Check: Execution status is PAUSED
  - Check: Checkpoint not expired
  - Return: Clear error if validation fails
  - File: src/mcp_server/tools.py
  - **COMPLETED**: resolve_checkpoint_impl validates execution and checkpoint existence

- [x] A.2.4 Test execution context
  - Unit test: list_executions returns correct structure
  - Integration test: Checkpoint request includes execution context
  - Integration test: Resolve with wrong execution_id returns error
  - File: tests/mcp_server/test_checkpoint_notifications.py
  - **COMPLETED**: 7 list_executions tests + 2 resolve_checkpoint validation tests

### A.3 Real E2E Test with MCP Stdio (6-8 hours)

- [ ] A.3.1 Create subprocess-based MCP server test fixture
  - Location: tests/mcp_server/conftest.py
  - Start MCP server in subprocess
  - Connect test client via stdio
  - Fixture manages startup/shutdown

- [ ] A.3.2 Write end-to-end integration test
  - File: tests/e2e/test_agent_mcp_workflow_integration.py
  - Test flow:
    1. Start MCP server
    2. Connect client
    3. Client calls start_workflow("login", {...})
    4. Workflow runs and hits checkpoint
    5. Client calls get_execution_status → status is "paused"
    6. Client calls list_executions(status="paused") → sees workflow
    7. Client calls resolve_checkpoint with decision
    8. Workflow resumes
    9. Client polls status until "completed"
    10. Verify final result

- [ ] A.3.3 Test checkpoint notification delivery
  - Verify: MCP server notifies on checkpoint
  - Verify: Client receives checkpoint details
  - Verify: Agent can act on notification

- [ ] A.3.4 Document agent integration patterns
  - Update: README.md with "Agent Integration Guide"
  - Add: Examples of agent-workflow communication
  - Add: Troubleshooting guide for checkpoint issues

**Effort**: 3 days  
**Branch**: `e2e-checkpoint-integration`  
**PR Description**: Enable agent control of workflows via real MCP communication

---

## Phase B: Concurrent Isolation (1 day)

**Goal**: 10+ concurrent workflows run without state corruption  
**Prerequisite**: Phase A  
**Deliverable**: Verified isolation with execution-scoped resources

### B.1 Execution-Scoped Resources (4 hours)

- [ ] B.1.1 Add `Execution.temp_dir` property
  - Location: src/framework/execution.py
  - Returns: data/executions/{execution_id}/temp directory
  - Creates: Directory on first access
  - Implementation: Use Path.mkdir(parents=True, exist_ok=True)

- [ ] B.1.2 Add `Execution.cleanup()` method
  - Location: src/framework/execution.py
  - Removes: Temp directory and all contents
  - Called: On workflow completion/cancellation
  - Safe: Uses shutil.rmtree with ignore_errors=True

- [ ] B.1.3 Update Workflow base class
  - Use: `self._execution.temp_dir` for any temp files
  - Remove: References to /tmp for execution-specific files
  - Documentation: All temp files go through execution.temp_dir

- [ ] B.1.4 Add asyncio + fcntl locking verification test
  - Location: tests/framework/integration/test_concurrent_file_locking.py
  - Test: Multiple workflows write to shared file with FileLock
  - Verify: No data corruption with concurrent asyncio.gather()
  - Verify: File locks serialize writes correctly

**Effort**: 0.5 days  
**Notes**: Critical for safety in concurrent scenarios

### B.2 Concurrent Isolation Tests (3 hours)

- [ ] B.2.1 Create 10-concurrent-workflows integration test
  - File: tests/framework/integration/test_10_concurrent_workflows.py
  - Setup: Create 10 LoginWorkflow instances with different execution_ids
  - Execute: Run all 10 concurrently with asyncio.gather()
  - Verify: All succeed without cross-contamination
  - Verify: Each has isolated temp_dir and state file
  - Check: No shared resource corruption

- [ ] B.2.2 Concurrent checkpoint isolation test
  - File: tests/framework/integration/test_concurrent_checkpoints.py
  - Setup: 5 workflows, each hits checkpoint
  - Verify: Each checkpoint is independent
  - Verify: Resolving one doesn't affect others
  - Verify: Concurrent state access is safe

**Effort**: 0.5 days  
**Deliverable**: Confidence that production concurrent use is safe

**Effort**: 1 day total  
**Branch**: `concurrent-isolation`  
**PR Description**: Verify concurrent workflow isolation with execution-scoped resources

---

## Phase C: Session Recovery & Re-authentication (2-3 days)

**Goal**: Long-running workflows survive session timeout  
**Prerequisite**: Phase A + B  
**Deliverable**: Session tracking, re-auth on resume, step replay

### C.1 Session Age Tracking (2 hours)

- [ ] C.1.1 Add session lifetime tracking to SessionManager
  - Location: src/framework/session_manager.py
  - Add: `created_at` timestamp in __init__
  - Add: `age_seconds` property
  - Add: `session_expired` property (checks age > SESSION_TTL_SECONDS)
  - Add: Configure SESSION_TTL_SECONDS constant (e.g., 3600 seconds = 1 hour)

- [ ] C.1.2 Document session lifetime configuration
  - Add: Configuration section to plan.md
  - Document: How to adjust SESSION_TTL_SECONDS per workflow
  - Document: How to detect and recover from expired sessions

**Effort**: 2 hours

### C.2 Re-authentication on Resume (6 hours)

- [ ] C.2.1 Add `Workflow._reauthenticate()` method
  - Location: src/framework/workflow.py or subclass
  - Signature: `async def _reauthenticate(self) -> None`
  - Virtual method: Subclasses override with workflow-specific re-auth
  - LoginWorkflow: Implement login step again using stored credentials

- [ ] C.2.2 Update Workflow resume behavior
  - Location: src/framework/workflow.py (on checkpoint resume)
  - Check: If SessionManager.session_expired
  - Call: await self._reauthenticate()
  - Navigate: To last known URL if available
  - Document: Session recovery flow in workflow docstring

- [ ] C.2.3 Update LoginWorkflow re-auth implementation
  - Location: src/workflows/login_workflow.py
  - Implement: _reauthenticate() calls login() with stored credentials
  - Verify: Re-login successful before resuming workflow
  - Log: Session recovery event with timestamp

- [ ] C.2.4 Test session timeout recovery
  - File: tests/workflows/integration/test_session_recovery.py
  - Test scenario:
    1. Start workflow, log in successfully
    2. Pause at checkpoint (session fresh)
    3. Artificially expire session (advance clock or clear cookies)
    4. Resolve checkpoint (resume workflow)
    5. Workflow detects session expired
    6. Workflow calls _reauthenticate()
    7. Re-login successful
    8. Workflow continues from checkpoint
    9. Workflow completes successfully

**Effort**: 6 hours

### C.3 Step Replay & Idempotency (6 hours)

- [ ] C.3.1 Add `IdempotentStep` decorator
  - Location: src/framework/decorators.py
  - Decorator: Mark steps as safe to re-run
  - Signature: `@IdempotentStep(idempotent=True)` on step function
  - Behavior: Skip execution if step already completed

- [ ] C.3.2 Track completed steps in Execution
  - Location: src/framework/execution.py
  - Add: `completed_steps` dict (step_name → result)
  - Add: `mark_step_completed(step_name, result)` method
  - Persist: Save completed_steps to execution JSON

- [ ] C.3.3 Implement IdempotentStep logic
  - Location: src/framework/decorators.py
  - Check: If step_name in execution.completed_steps
  - If yes: Return cached result, skip execution
  - If no: Execute step, cache result, mark completed
  - Log: "Step {name} already completed, skipping"

- [ ] C.3.4 Mark workflow steps as idempotent
  - Location: src/workflows/login_workflow.py
  - Mark: login step (safe to re-run)
  - Mark: form_fill step (safe to re-run if validation added)
  - Document: Which steps are idempotent and why

- [ ] C.3.5 Test step replay
  - File: tests/framework/integration/test_step_replay.py
  - Test: Execute step twice, verify cached result on second run
  - Test: Step side effects don't duplicate (e.g., login only happens once)
  - Test: Workflow resumes from correct step after replay

**Effort**: 6 hours

**Total Phase C Effort**: 2-3 days  
**Branch**: `session-recovery`  
**PR Description**: Handle long-running workflows with session recovery and step replay

---

## Phase D: Resource Quota Enforcement (1 day)

**Goal**: Workflows queue when resources constrained; no DoS  
**Prerequisite**: Phase C  
**Deliverable**: Quota enforcement with fair queueing

### D.1 Quota Claims & Queue (4 hours)

- [ ] D.1.1 Implement ResourceManager.claim_quota() with queue
  - Location: src/framework/resource_manager.py
  - Signature: `async def claim_quota(self, resource: str, amount: int, timeout: int) -> None`
  - Behavior:
    - If available: Claim immediately, return
    - If unavailable: Add to queue, wait for availability
    - On timeout: Raise QuotaExceeded with clear message
  - Use: asyncio.Event for queue signaling

- [ ] D.1.2 Implement ResourceManager.release_quota()
  - Location: src/framework/resource_manager.py
  - Signature: `def release_quota(self, execution_id: str) -> None`
  - Behavior: Release all resources held by execution
  - Trigger: Process queue, wake first waiting workflow

- [ ] D.1.3 Update start_workflow MCP tool
  - Location: src/mcp_server/tools.py
  - Call: `resource_manager.claim_quota()` before starting
  - Handle: QuotaExceeded → return {"status": "queued", "reason": ...}
  - Log: Queue position and estimated wait time

- [ ] D.1.4 Test quota enforcement
  - File: tests/framework/test_resource_quota.py
  - Test: Single workflow claims quota successfully
  - Test: Second workflow waits if over quota
  - Test: Queue processes fairly (FIFO)
  - Test: Timeout raises error with clear message

**Effort**: 4 hours

### D.2 Quota Enforcement Tests (3 hours)

- [ ] D.2.1 Create quota stress test
  - File: tests/framework/integration/test_quota_stress.py
  - Setup: Trigger 20 workflows, max quota = 5
  - Verify: Only 5 run concurrently
  - Verify: Others queue and start as resources available
  - Verify: All 20 complete successfully

- [ ] D.2.2 Document quota configuration
  - Update: plan.md with quota configuration
  - Add: Examples of custom quota settings
  - Add: Monitoring tips for queue depth

**Effort**: 3 hours

**Total Phase D Effort**: 1 day  
**Branch**: `resource-quotas`  
**PR Description**: Enforce resource quotas with fair queueing

---

## Phase E: Production MCP Logging & Observability (1 day)

**Goal**: Correlate MCP calls to workflow logs for debugging  
**Prerequisite**: Phase A  
**Deliverable**: Trace context and debug mode

### E.1 Trace Context (4 hours)

- [ ] E.1.1 Add trace_id context variable
  - Location: src/utils/logging.py
  - Import: contextvars
  - Create: `trace_id = contextvars.ContextVar('trace_id', default=None)`
  - Usage: All MCP tool calls set trace_id

- [ ] E.1.2 Update MCP tools with trace_id
  - Location: src/mcp_server/tools.py
  - Entry point: Each tool generates/sets trace_id
  - Logging: Include trace_id in all log records
  - Response: Return trace_id in tool result for client

- [ ] E.1.3 Update structured logging to include trace_id
  - Location: src/utils/logging.py
  - Format: Add `"trace_id": trace_id` to JSON log structure
  - Availability: trace_id in all logs during tool execution

- [ ] E.1.4 Test trace correlation
  - File: tests/mcp_server/test_trace_correlation.py
  - Test: Tool call generates unique trace_id
  - Test: All workflow logs include same trace_id
  - Test: Different tool calls have different trace_ids

**Effort**: 4 hours

### E.2 Debug Mode (3 hours)

- [ ] E.2.1 Add debug mode to WorkflowMCPServer
  - Location: src/mcp_server/server.py
  - Add: `debug_execution_ids` set
  - Add: `set_debug_execution(execution_id, enabled)` method
  - Behavior: When debug enabled, use DEBUG log level for that execution

- [ ] E.2.2 Create set_execution_debug MCP tool
  - Location: src/mcp_server/tools.py
  - Signature: `set_execution_debug(execution_id: str, enabled: bool) -> dict`
  - Returns: {"execution_id": ..., "debug": ...}
  - Effect: Enable verbose logging for specific execution

- [ ] E.2.3 Test debug mode
  - File: tests/mcp_server/test_debug_mode.py
  - Test: Debug mode generates more logs
  - Test: Set/unset debug works correctly
  - Test: Non-debug executions not affected

**Effort**: 3 hours

**Total Phase E Effort**: 1 day  
**Branch**: `observability`  
**PR Description**: Add trace correlation and debug mode for production MCP logging

---

## Summary

| Phase | Goal | Effort | Priority |
|-------|------|--------|----------|
| A | E2E Agent Integration | 3 days | P1 |
| B | Concurrent Isolation | 1 day | P1 |
| C | Session Recovery | 2-3 days | P2 |
| D | Resource Quotas | 1 day | P2 |
| E | Observability | 1 day | P2 |

**Fast Track** (4-5 days): Phases A + B  
**Complete** (8-10 days): All phases A-E

