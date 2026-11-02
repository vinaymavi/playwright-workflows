# E2E Workflow Integration - Implementation Roadmap

**Status**: Ready for Implementation  
**Created**: 2026-11-02  
**Reference**: See [Gap Analysis](./e2e-integration-gap-analysis.md) for detailed gaps

---

## Current State Summary

**Completed** (85% of MVP):
- ✅ Framework core (Workflow, Execution, Checkpoint classes)
- ✅ Checkpoint asyncio.Event signaling
- ✅ MCP server with tools for start/resolve/status
- ✅ 641 passing tests
- ✅ CLI runners and batch execution
- ✅ Session management and credential encryption

**Ready to Build** (6 identified gaps):
1. Real E2E workflow execution via MCP
2. Agent response routing to checkpoints
3. Concurrent workflow state isolation
4. Session recovery & re-authentication
5. Resource quota enforcement
6. Production MCP logging

---

## Quick Implementation Plan

### Phase A: E2E Agent Integration (3 days)

**Goal**: Enable Agent ↔ MCP ↔ Workflow ↔ Checkpoint ↔ Agent loop

#### A.1 Checkpoint Notifications (Day 1)

**What**: When workflow pauses at checkpoint, notify agent

**Changes**:
- [ ] Add `on_checkpoint_pause` callback to WorkflowMCPServer
- [ ] Implement MCP notifications or tool result hints
- [ ] Update resolve_checkpoint tool documentation

**Test**:
```python
@pytest.mark.asyncio
async def test_checkpoint_notification_to_agent():
    # Workflow hits checkpoint
    # MCP server sends notification
    # Test verifies notification received
```

**Effort**: 4-6 hours

#### A.2 Execution Context in Checkpoint (Day 1-2)

**What**: Agent knows which execution is paused and can resolve it

**Changes**:
- [ ] Add `list_executions(status="paused")` MCP tool
- [ ] Include execution context in checkpoint notification
- [ ] Validate checkpoint still exists when resolving

**Test**:
```python
@pytest.mark.asyncio
async def test_agent_lists_paused_executions():
    # Start 3 workflows, all pause at checkpoints
    # Agent calls list_executions(status="paused")
    # Returns 3 executions with checkpoint details
```

**Effort**: 4-6 hours

#### A.3 Real E2E Test (Day 2-3)

**What**: End-to-end test with real MCP stdio communication

**Changes**:
- [ ] Create MCP server subprocess in test
- [ ] Connect test client via stdio
- [ ] Test full workflow: start → checkpoint → resolve → resume

**Test**:
```python
@pytest.mark.asyncio
async def test_agent_controls_workflow_e2e():
    # Start MCP server in subprocess
    # Connect client
    # Call start_workflow
    # Workflow hits checkpoint, pauses
    # Call resolve_checkpoint
    # Workflow resumes and completes
    # Verify final state
```

**Effort**: 6-8 hours

**Branch**: `e2e-checkpoint-integration`  
**PR**: High priority - core feature

---

### Phase B: Concurrent Isolation (1 day)

**Goal**: 10+ concurrent workflows run without state corruption

#### B.1 Execution-Scoped Resources (0.5 day)

**What**: Each execution gets isolated temp directory, logs, state

**Changes**:
- [ ] Add `Execution.temp_dir` property
- [ ] Create directory on Execution.start()
- [ ] Clean up on Execution.finish()
- [ ] Verify file locks work with asyncio

**Test**:
```python
@pytest.mark.asyncio
async def test_concurrent_10_workflows_isolated():
    # Run 10 workflows concurrently
    # Each writes to temp file
    # Verify no cross-contamination
    # Verify temp directories created/cleaned
```

**Effort**: 4 hours

**Branch**: `concurrent-isolation`  
**PR**: Medium priority - required for safety

---

### Phase C: Session Recovery (2-3 days)

**Goal**: Long-running workflows survive session timeout

#### C.1 Session Age Tracking (0.5 day)

**What**: Track session lifetime, detect expiry

**Changes**:
- [ ] Add `SessionManager.created_at` timestamp
- [ ] Add `SessionManager.session_expired` property
- [ ] Configure SESSION_TTL_SECONDS

**Effort**: 2 hours

#### C.2 Re-authentication on Resume (1 day)

**What**: When resuming from paused state, re-auth if session expired

**Changes**:
- [ ] Add `Workflow._reauthenticate()` method
- [ ] Call on resume if session expired
- [ ] Update LoginWorkflow to implement re-auth

**Test**:
```python
@pytest.mark.asyncio
async def test_workflow_resumes_after_session_timeout():
    # Start workflow, log in successfully
    # Pause at checkpoint (session valid)
    # Artificially expire session
    # Resolve checkpoint (resume workflow)
    # Workflow should re-authenticate
    # Verify login successful
```

**Effort**: 6 hours

#### C.3 Step Replay & Idempotency (1 day)

**What**: Safe to re-run steps without duplicating side effects

**Changes**:
- [ ] Add `@IdempotentStep` decorator
- [ ] Track completed steps in Execution
- [ ] Skip already-completed idempotent steps
- [ ] Mark LoginWorkflow steps as idempotent

**Effort**: 6 hours

**Branch**: `session-recovery`  
**PR**: Medium priority - required for long workflows

---

### Phase D: Resource Quota Enforcement (1 day)

**Goal**: Workflows queue when resources constrained; no DoS

#### D.1 Quota Claims & Queue (0.5 day)

**What**: ResourceManager enforces global quota limits

**Changes**:
- [ ] Add `ResourceManager.claim_quota(resource, amount, timeout)`
- [ ] Add wait queue with async.Event
- [ ] Update start_workflow tool to claim quota
- [ ] Return "queued" if quota unavailable

**Effort**: 4 hours

#### D.2 Quota Enforcement Tests (0.5 day)

**What**: Verify quota limits are enforced

**Changes**:
- [ ] Test: Single workflow claims quota successfully
- [ ] Test: Second workflow waits if over quota
- [ ] Test: Queue processes when quota available

**Effort**: 3 hours

**Branch**: `resource-quotas`  
**PR**: Low priority - can defer to Phase 2

---

### Phase E: Production Observability (1 day)

**Goal**: Correlate MCP calls to workflow logs for debugging

#### E.1 Trace Context (0.5 day)

**What**: Add trace_id to correlate MCP calls and logs

**Changes**:
- [ ] Use contextvars.ContextVar for trace_id
- [ ] Generate trace_id in MCP tool entry
- [ ] Include trace_id in all logs
- [ ] Return trace_id in tool results for client

**Effort**: 4 hours

#### E.2 Debug Mode (0.5 day)

**What**: Enable verbose logging for specific executions

**Changes**:
- [ ] Add `set_execution_debug(execution_id, enabled)` tool
- [ ] Log level adjusts when debug enabled
- [ ] Document debug mode usage

**Effort**: 3 hours

**Branch**: `observability`  
**PR**: Low priority - can defer to Phase 2

---

## Priority & Timeline

### Recommended Sequence

```
Week 1 (Days 1-3):
  ✅ Phase A: E2E Agent Integration
     - Checkpoint notifications
     - Execution context
     - Real E2E test
     - DELIVERABLE: Agent can control workflows via MCP

Week 1 (Day 4):
  ✅ Phase B: Concurrent Isolation  
     - Execution-scoped resources
     - Concurrency tests
     - DELIVERABLE: 10 concurrent workflows work correctly

Week 2 (Days 1-2):
  ✅ Phase C: Session Recovery
     - Session age tracking
     - Re-auth on resume
     - Step replay & idempotency
     - DELIVERABLE: Long-running workflows survive timeout

Week 2 (Day 3):
  ⏭️ Phase D: Resource Quotas (defer if time-pressed)
     - Quota enforcement
     - Queue mechanism
     - DELIVERABLE: Workflows queue when resources full

Week 2 (Day 4):
  ⏭️ Phase E: Observability (defer if time-pressed)
     - Trace context
     - Debug mode
     - DELIVERABLE: Production logs are debuggable
```

**Fast Track** (Priority 1 only): 4-5 days
- Phase A: E2E integration ✅
- Phase B: Concurrent isolation ✅

**Complete** (Priorities 1-3): 8-10 days
- Phase A: E2E integration ✅
- Phase B: Concurrent isolation ✅
- Phase C: Session recovery ✅
- Phase D: Resource quotas (optional)
- Phase E: Observability (optional)

---

## Definition of Done

### For Each Phase

**Code**:
- [ ] All changes implement exactly the gap description
- [ ] No breaking changes to existing APIs
- [ ] Type hints on all new functions
- [ ] Docstrings on public methods

**Tests**:
- [ ] Unit tests for framework changes
- [ ] Integration tests for full flow
- [ ] Concurrent execution tests
- [ ] All 641 existing tests still pass
- [ ] New tests pass locally and in CI

**Documentation**:
- [ ] Update plan.md with changes
- [ ] Add docstring examples
- [ ] Update README.md if user-facing
- [ ] Add comments for complex logic

**Commit**:
- [ ] Clear commit messages with feature description
- [ ] Reference gap number if applicable
- [ ] Co-authored-by trailer

---

## Risk & Mitigation

### Risk 1: MCP Communication Issues

**Risk**: Real MCP stdio communication might have edge cases  
**Mitigation**: Extensive integration tests with real subprocess  
**Fallback**: Keep mock-based tests as regression suite

### Risk 2: Session Timeout Complexity

**Risk**: Re-auth logic might not cover all edge cases  
**Mitigation**: Start with LoginWorkflow example; generalize later  
**Fallback**: Defer session recovery to Phase 2, document workaround

### Risk 3: Resource Quota Deadlock

**Risk**: Queue wait might deadlock if quotas never available  
**Mitigation**: Always include timeout in claim_quota(); log and error  
**Fallback**: Start with log-only mode, add enforcement later

---

## Success Metrics

### After Phase A
- ✅ Agent can trigger workflow via MCP
- ✅ Workflow pauses at checkpoint
- ✅ Agent resolves checkpoint
- ✅ Workflow resumes and completes
- ✅ E2E test passes
- ✅ No regression in existing tests

### After Phase B
- ✅ 10 concurrent workflows isolate state correctly
- ✅ No cross-contamination in temp files/logs
- ✅ All 641 tests still pass

### After Phase C
- ✅ Workflow survives 30+ minute run
- ✅ Session timeout detected and re-auth triggered
- ✅ Completed steps not re-executed
- ✅ Long-running integration test passes

### After Phase D
- ✅ Workflows queue when over resource limit
- ✅ Queue processes fairly
- ✅ Quota limits enforced
- ✅ No resource starvation

### After Phase E
- ✅ All MCP calls have trace_id
- ✅ Production logs correlate to MCP calls
- ✅ Debug mode enables verbose logging per execution

---

## Related Issues & PRs

- [Gap Analysis](./e2e-integration-gap-analysis.md) - Detailed gap descriptions
- [Specification](./spec.md) - Feature requirements
- [Implementation Plan](./plan.md) - Architecture overview
- [Constitution](/../.specify/memory/constitution.md) - Project principles

---

## Notes for Future Phases

### Phase 2+ Enhancements
- Distributed MCP servers (one server, multiple workflows)
- SQLite state storage (scale from 50 to 1000+ concurrent)
- Workflow versioning & migration
- Tape-replay for regression testing
- Shared resource conflict detection
- Agent load balancing across checkpoints

### Technical Debt
- Replace file-based state with SQLite
- Add OpenTelemetry instrumentation
- Migrate from contextvars to full tracing
- Add workflow DSL (reduce Python boilerplate)

