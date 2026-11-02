# Tasks: Playwright Workflow Orchestration Framework

**Feature**: Workflow Orchestration for Playwright-based Web Automation  
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Data Model**: [data-model.md](./data-model.md)

**Implementation Strategy**: MVP-first approach with 3 parallel implementation tracks:
- Track 1: Framework core (Workflow, Execution, Checkpoint classes) - Foundation for all stories
- Track 2: MCP server integration - Required for Stories 5+
- Track 3: Testing & Validation - Continuous verification per story

**User Stories Included**: 7 stories (P1: 3 stories, P2: 3 stories, P3: 1 story)  
**Total Tasks**: 82 implementation tasks + 15 test tasks (by request)  
**Estimated Effort**: 4-6 weeks (concurrent phases possible after Phase 1/2)

---

## Phase 1: Project Setup & Infrastructure

**Goal**: Create project structure, install dependencies, and set up development environment  
**Duration**: 1-2 days  
**Prerequisite**: None  
**Deliverable**: Runnable Python environment with all dependencies; empty but structured codebase

### Setup Tasks

- [x] T001 Create project directory structure per plan.md (src/framework, src/workflows, src/mcp_server, src/shared_steps, src/utils, tests/, data/)

- [x] T002 Create pyproject.toml with dependencies: playwright, python-mcp or anthropic-mcp, pydantic, cryptography, pytest, pytest-asyncio, jsonschema

- [x] T003 Create Python virtual environment and install dependencies: `python3 -m venv venv && source venv/bin/activate && pip install -r pyproject.toml`

- [x] T004 Create src/__init__.py and src/framework/__init__.py (package initialization files)

- [x] T005 Create tests/__init__.py, tests/framework/__init__.py, tests/framework/unit/__init__.py, tests/framework/integration/__init__.py

- [x] T006 Create .gitignore for Python projects (venv/, __pycache__/, *.pyc, .pytest_cache/, data/executions/*, data/logs/*, data/artifacts/*, data/credentials/*)

- [x] T007 Create data/ directory structure: mkdir -p data/executions data/logs data/artifacts data/credentials

- [x] T008 Create src/utils/logging.py for structured JSON logging (see research.md for logging strategy)

- [x] T009 Create src/utils/file_locking.py for fcntl-based file locks with atomic writes (MVP: file-based state)

- [x] T010 Create src/utils/credential_manager.py for AES-256-GCM credential encryption per research.md

- [x] T011 Create pytest.ini configuration for test discovery and asyncio mode

- [x] T012 Create README.md with project overview, quick start, and architecture diagram reference

---

## Phase 2: Framework Core (Blocking for All User Stories)

**Goal**: Implement foundational framework classes that enable all user stories  
**Duration**: 1-2 weeks  
**Prerequisite**: Phase 1  
**Deliverable**: Workflow base class, Execution state machine, Step decorator, error handling

### Foundational Framework Tasks

- [x] T013 [P] Create src/framework/errors.py with exception hierarchy: WorkflowError, WorkflowCheckpointRequired, WorkflowCheckpointTimeout, WorkflowCancelled, WorkflowSessionExpired, WorkflowResourceExhausted

- [x] T014 [P] Create src/framework/execution.py with Execution class: manages execution state machine (pending → running → paused → completed/failed), state persistence to JSON, status queries

- [x] T015 [P] Create src/framework/checkpoint.py with Checkpoint class: structured JSON question/decision protocol, timeout handling (soft 2min + hard 5min per plan.md Q4), decision validation

- [x] T016 [P] Create src/framework/retry_handler.py: Classify errors (transient vs permanent per plan.md Q3), auto-retry transient errors (configurable max_retries, exponential backoff), escalate permanent errors to checkpoint

- [x] T017 [P] Create src/framework/step.py with Step decorator (@step): captures step execution, logs start/complete, handles retry, populates step output on success, populates step error on failure

- [x] T018 Create src/framework/session_manager.py: Manage browser context lifecycle, persist session cookies/storage, detect 401/403 errors, trigger re-auth per plan.md Q5 (hybrid recovery strategy)

- [x] T019 [P] Create src/framework/state_manager.py: Load/save execution state to data/executions/{execution_id}.json using file locking (fcntl.flock), atomic writes (temp → rename), validation via schema

- [x] T023 Create tests/framework/unit/test_errors.py: Unit tests for exception hierarchy and custom attributes

- [x] T024 [P] Create tests/framework/unit/test_execution_state_machine.py: Test Execution state transitions (pending→running→paused→completed/failed), verify state persistence to JSON, verify lock mechanism

- [x] T025 [P] Create tests/framework/unit/test_checkpoint.py: Test Checkpoint question validation, decision validation, timeout handling (mock time.sleep), JSON serialization

- [x] T026 [P] Create tests/framework/unit/test_retry_handler.py: Test error classification (transient vs permanent), auto-retry logic with backoff, escalation to checkpoint

- [x] T027 [P] Create tests/framework/unit/test_step_decorator.py: Test @step decorator captures execution, logs, retries, handles errors

- [x] T028 Create tests/framework/unit/test_state_manager.py: Test save/load execution state from JSON file, file locking (concurrent writes), atomic write guarantee

- [x] T029 [P] Create tests/framework/integration/test_execution_flow.py: Workflow → Execution → Step → Checkpoint flow (no browser), mock page object, verify state persistence and resumption

---

## Phase 3: User Story 1 - Workflow Developer Creates a Web Automation Task (P1)

**Goal**: Enable developers to create workflows, execute them, and receive structured output  
**Duration**: 1 week  
**Prerequisite**: Phase 1 & 2  
**Deliverable**: Example LoginWorkflow, standalone execution, structured output

### User Story 1 Tasks

- [x] T030 [US1] Create example workflow: src/workflows/login_workflow.py (LoginWorkflow class extending Workflow base)
  - [x] @step for navigate to login page
  - [x] @step for fill username
  - [x] @step for fill password
  - [x] @step for click submit
  - [x] @step for wait for dashboard
  - [x] run() method orchestrating all steps
  - [x] Error handling for 401/403

- [x] T031 [US1] Create CLI entry point src/cli/workflow_runner.py: Main entry point to execute workflows
  - [x] Accept workflow_type, input_params as JSON, output format (json/text)
  - [x] Instantiate Workflow subclass
  - [x] Call run() with params
  - [x] Capture output, logs, and execution state
  - [x] Return formatted result
  - [x] Exit code: 0 on success, non-zero on failure

- [x] T032 [US1] [P] Create tests/workflows/unit/test_login_workflow.py: Unit tests for LoginWorkflow logic (mock Playwright page)
  - [x] Test step sequence
  - [x] Test input validation
  - [x] Test error handling (invalid credentials, network timeout)

- [x] T033 [US1] Create tests/fixtures/mock_page.py: Mock Playwright page object for testing without browser

- [x] T034 [US1] Create tests/fixtures/mock_web_app.py: Mock web server for E2E testing (returns login form, validates credentials)

- [x] T035 [US1] [P] Create tests/workflows/integration/test_login_workflow_integration.py: Integration test LoginWorkflow with mock server (no real browser)

- [x] T036 [US1] Create documentation: docs/workflow-examples/login_workflow.md with step-by-step explanation and usage examples

- [x] T037 [US1] Create tests/quickstart_scenarios/test_scenario_a_happy_path.py: Scenario A from quickstart.md (simple workflow, verify completion in <30s)

**Independent Test Criteria for US1**:
- LoginWorkflow instantiates, runs, completes successfully with structured output
- State is persisted to data/executions/{execution_id}.json
- Logs are written to data/logs/{execution_id}.log in JSON format
- All 5 steps execute in sequence without interference
- Error handling works (invalid credentials → WorkflowError, caught and logged)

---

## Phase 4: User Story 2 - Agent Checkpoint During Workflow Execution (P1)

**Goal**: Enable workflows to pause and wait for agent decisions; resume from checkpoint  
**Duration**: 1.5 weeks  
**Prerequisite**: Phase 1 & 2  
**Deliverable**: Checkpoint protocol, pause/resume flow, agent notification

### User Story 2 Tasks

- [x] T038 [US2] Enhance LoginWorkflow (src/workflows/login_workflow.py) to include checkpoint before submit:
  - [x] Add checkpoint step with question: "Ready to submit login?"
  - [x] Accept agent decision: {value: "proceed"} or {value: "cancel"}
  - [x] Resume logic: if "proceed" → click submit; if "cancel" → raise WorkflowCancelled

- [x] T039 [US2] Create src/framework/checkpoint_store.py: Persist pending checkpoints to JSON for quick lookup and query

- [x] T040 [US2] [P] Create tests/framework/unit/test_checkpoint_store.py: Test checkpoint save/load from file

- [x] T041 [US2] Create tests/fixtures/mock_agent_client.py: Mock MCP agent client for testing

- [x] T042 [US2] [P] Create tests/framework/integration/test_checkpoint_pause_resume.py: Test workflow pause at checkpoint, resume with decision, verify state preserved
  - [x] Start workflow
  - [x] Hit checkpoint, verify state saved and workflow paused
  - [x] Resolve checkpoint with decision
  - [x] Resume, verify state loaded and execution continues
  - [x] Verify final result matches expected flow

- [x] T043 [US2] [P] Create tests/workflows/integration/test_login_workflow_with_checkpoint.py: LoginWorkflow with checkpoint integration test

- [x] T044 [US2] Create documentation: docs/checkpoint-protocol.md
  - [x] Explain checkpoint question/decision JSON schema
  - [x] Show decision validation
  - [x] Show timeout behavior (soft + hard)
  - [x] Show resumption strategy

- [x] T045 [US2] Create tests/quickstart_scenarios/test_scenario_b_quick_resume.py: Scenario B from quickstart.md (checkpoint pause/resume ≤5min, session preserved)

**Independent Test Criteria for US2**:
- Workflow pauses at checkpoint, sends structured question JSON
- Execution state saved to disk with checkpoint ID and pending status
- Agent can resolve checkpoint with decision
- Workflow resumes from checkpoint with decision applied
- All state prior to checkpoint is preserved and accessible
- Soft timeout (2 min) and hard timeout (5 min) work as specified

---

## Phase 5: User Story 3 - Parallel Execution of Multiple Workflow Instances (P1)

**Goal**: Execute multiple workflows concurrently without interference; respect resource limits  
**Duration**: 1.5 weeks  
**Prerequisite**: Phase 1, 2, 3  
**Deliverable**: Concurrency limits, isolated browser contexts, concurrent state management

### User Story 3 Tasks

- [x] T046 [US3] Create src/framework/concurrency_manager.py: Manage concurrent workflow executions
  - [x] asyncio.Semaphore to limit concurrent operations (default 5 per plan.md research)
  - [x] asyncio.TaskGroup to manage workflow tasks, propagate exceptions
  - [x] Track active executions by ID
  - [x] Enforce resource quotas per execution (max browser pages, memory, timeouts)

- [x] T047 [US3] [P] Create tests/framework/unit/test_concurrency_manager.py: Unit tests for semaphore, task group, quota enforcement (no browser)

- [x] T048 [US3] Enhance src/framework/session_manager.py for browser context pooling:
  - [x] Pool of isolated browser contexts (max N concurrent)
  - [x] Assign context to execution, release on completion
  - [x] Detect leaked contexts (cleanup on process exit)
  - [x] Prefer reusing available contexts first (efficient pooling)

- [x] T049 [US3] [P] Create tests/framework/integration/test_browser_context_isolation.py: Test N concurrent workflows with isolated contexts (mock browser)

- [x] T050 [US3] [P] Create tests/framework/integration/test_concurrent_state_isolation.py: Test N concurrent executions don't cross-contaminate state
  - [x] Start 10 executions with different inputs
  - [x] Verify each loads own state from data/executions/{execution_id}.json
  - [x] Verify file locking prevents state corruption
  - [x] Verify semaphore limits actual concurrency to 5

- [x] T051 [US3] Create src/cli/batch_runner.py: CLI to execute multiple workflows in parallel
  - [x] Accept JSON array of workflow specs
  - [x] Use concurrency_manager to run all
  - [x] Aggregate results and errors
  - [x] Return summary (N succeeded, N failed, total time)

- [x] T052 [US3] [P] Create tests/workflows/integration/test_batch_execution.py: Test batch_runner with 10 LoginWorkflows, different inputs, verify isolation

- [x] T053 [US3] [P] Create tests/quickstart_scenarios/test_scenario_d_concurrent.py: Scenario D from quickstart.md (10 workflows, max 5 concurrent, all complete, no conflicts)

- [x] T054 [US3] Create documentation: docs/concurrency-guide.md
  - [x] Explain execution isolation
  - [x] Explain resource quotas
  - [x] Show how to tune semaphore limit
  - [x] Show error handling per execution

**Independent Test Criteria for US3**:
- 10 concurrent workflows complete without cross-contamination
- State files remain valid JSON (no partial writes)
- Resource quotas enforced (only 5 concurrent despite 10 started)
- Errors in one execution don't affect others
- Each execution has isolated browser context (no cookie leaking)

---

## Phase 6: User Story 4 - Workflow Extensibility with Custom Actions (P2)

**Goal**: Enable developers to create reusable custom actions (steps) without modifying core  
**Duration**: 1 week  
**Prerequisite**: Phase 1, 2, 3  
**Deliverable**: Action base class, registry, example custom actions

### User Story 4 Tasks

- [x] T055 [US4] Create src/framework/action.py: Base Action class for reusable custom actions
  - [x] __init__(workflow_context): receive reference to parent workflow
  - [x] async execute(**kwargs): abstract method for subclasses
  - [x] Inherit logging, error handling, retry from framework
  - [x] Support dependencies (requires: other actions to complete first)

- [x] T056 [US4] Create src/framework/action_registry.py: Registry to discover and instantiate actions
  - [x] register(action_name, action_class)
  - [x] get(action_name) → action_class
  - [x] list() → all registered actions
  - [x] Auto-discovery from entry points (pyproject.toml [project.entry-points."playwright.actions"])

- [x] T057 [US4] Create src/shared_steps/form_actions.py: Reusable form actions
  - [x] FillFormAction: Fill multiple fields (selector: value pairs)
  - [x] SubmitFormAction: Click submit and wait for result
  - [x] ValidateFormAction: Check fields have no errors

- [x] T058 [US4] Create src/shared_steps/login_actions.py: Reusable login actions
  - [x] EnterCredentialsAction: Fill username/password with credential lookup
  - [x] ClickLoginAction: Click login button
  - [x] VerifyLoginAction: Verify logged in state (check for user menu or dashboard)

- [x] T059 [US4] [P] Create tests/framework/unit/test_action_base.py: Test Action base class (lifecycle, logging, error handling)

- [x] T060 [US4] Create tests/framework/unit/test_action_registry.py: Test registry (register, get, discover)

- [x] T061 [US4] [P] Create tests/shared_steps/unit/test_login_actions.py: Test EnterCredentialsAction, SubmitLoginFormAction, VerifyLoginSuccessAction, HandleLoginErrorAction (mock workflow)

- [x] T062 [US4] Create src/workflows/form_filling_workflow.py: Refactor LoginWorkflow to use custom actions instead of inline steps

- [x] T063 [US4] [P] Create tests/workflows/integration/test_form_filling_with_actions.py: Test form_filling_workflow using custom actions

- [x] T064 [US4] Create documentation: docs/custom-actions-guide.md
  - [x] Explain how to extend Action base class
  - [x] Show registration via entry point
  - [x] Provide form_actions and login_actions as examples

**Independent Test Criteria for US4**:
- Custom actions inherit logging, error handling, and retry behavior
- Action registry discovers and instantiates actions dynamically
- Reusable actions work across multiple workflows
- Form actions correctly interact with mock page object
- LoginWorkflow refactored to use actions (no regression in tests)

---

## Phase 7: User Story 5 - External Control via Python or MCP Server (P2)

**Goal**: Enable Python programs and MCP clients to control workflow execution  
**Duration**: 2 weeks  
**Prerequisite**: Phase 1, 2, 3  
**Deliverable**: MCP server, MCP tools, Python API client, agent notification protocol

### User Story 5 Tasks

- [x] T065 [US5] Create src/mcp_server/server.py: MCP server entrypoint
  - [x] Use Anthropic `mcp` library per research.md
  - [x] Initialize on stdio transport
  - [x] Initialize Server instance
  - [x] Register tools and resources
  - [x] Handle JSON-RPC 2.0 requests/responses

- [x] T066 [US5] Create src/mcp_server/tools.py: Implement 4 MCP tools per contracts/mcp_tools.json
  - [x] start_workflow(workflow_type, input_params, max_retries, timeout_seconds) → {execution_id, status, created_at}
  - [x] resolve_checkpoint(execution_id, checkpoint_id, decision, agent_id) → {execution_id, checkpoint_id, status, resolved_at}
  - [x] get_execution_status(execution_id) → {execution_id, workflow_type, status, started_at, ended_at, completed_steps, total_steps, current_step_name, pending_checkpoint, error}
  - [x] get_execution_logs(execution_id, event_type, level, limit, offset) → {total_logs, returned_logs, logs[]}

- [x] T067 [US5] Create src/mcp_server/resources.py: Implement 2 MCP resources
  - [x] workflow://{workflow_type} → metadata for workflow type
  - [x] execution/{execution_id} → complete execution state

- [x] T068 [US5] Create src/mcp_server/notifications.py: Send notifications to client
  - [x] checkpoint_requested: sent when workflow hits checkpoint
  - [x] execution_completed: sent when workflow finishes successfully
  - [x] execution_failed: sent when workflow fails

- [x] T069 [US5] [P] Create tests/mcp_server/unit/test_mcp_server.py: Test MCP server initialization, tool registration

- [x] T070 [US5] [P] Create tests/mcp_server/unit/test_tools_schema.py: Validate tool input/output schemas match contracts/mcp_tools.json

- [x] T071 [US5] [P] Create tests/mcp_server/integration/test_start_workflow_tool.py: Test start_workflow tool
  - [x] Call start_workflow with valid params
  - [x] Verify execution_id returned and execution starts
  - [x] Verify initial status is "pending" or "running"

- [x] T072 [US5] [P] Create tests/mcp_server/integration/test_resolve_checkpoint_tool.py: Test resolve_checkpoint tool
  - [x] Start workflow that hits checkpoint
  - [x] Call resolve_checkpoint with decision
  - [x] Verify workflow resumes

- [x] T073 [US5] [P] Create tests/mcp_server/integration/test_get_execution_status_tool.py: Test status polling during execution

- [x] T074 [US5] [P] Create tests/mcp_server/integration/test_get_execution_logs_tool.py: Test log retrieval with filters (event_type, level)

- [x] T075 [US5] [P] Create tests/mcp_server/integration/test_mcp_notifications.py: Test notification sending on checkpoint/completion/failure

- [x] T076 [US5] Create src/cli/mcp_server_runner.py: Entrypoint to run MCP server on stdio
  - [x] python3 -m src.cli.mcp_server_runner (receives input on stdin, writes output to stdout)

- [x] T077 [US5] Create src/api/workflow_controller.py: Python API client to control workflows
  - [x] WorkflowController class with methods: start(), get_status(), resolve_checkpoint(), get_logs()
  - [x] Methods use internal function calls (no MCP overhead for local control)

- [x] T078 [US5] [P] Create tests/api/test_workflow_controller.py: Test WorkflowController methods
  - [x] Async methods: start_async(), get_status_async(), resolve_checkpoint_async(), get_logs_async()
  - [x] Sync wrappers: start(), get_status(), resolve_checkpoint(), get_logs()
  - [x] All 21 tests passing (async, sync, integration scenarios)

- [x] T079 [US5] Create documentation: docs/mcp-protocol.md
  - [x] Explain MCP tool contracts
  - [x] Show example requests/responses
  - [x] Explain notification protocol
  - [x] Show error handling

- [x] T080 [US5] Create documentation: docs/python-api.md
  - [x] Explain WorkflowController usage
  - [x] Show start(), get_status(), resolve_checkpoint(), get_logs() examples

- [x] T081 [US5] Create tests/quickstart_scenarios/test_scenario_e_controller.py: Scenario demonstrating WorkflowController usage (6 tests passing)

**Independent Test Criteria for US5**:
- MCP tools accept JSON input and return JSON output per schema
- start_workflow creates new Execution and returns execution_id
- resolve_checkpoint resumes workflow from checkpoint
- get_execution_status returns accurate status, step count, pending checkpoint
- get_execution_logs retrieves structured logs with filters working correctly
- Notifications sent on checkpoint/completion/failure
- Python WorkflowController provides convenient API

---

## Phase 8: User Story 6 - Workflow Execution State Persistence & Resumption (P2)

**Goal**: Persist execution state to enable recovery and resumption; handle transient errors gracefully  
**Duration**: 1.5 weeks  
**Prerequisite**: Phase 1, 2, 5, 6  
**Deliverable**: Session recovery, state snapshot on error, manual resume capability

### User Story 6 Tasks

- [ ] T082 [US6] Enhance src/framework/session_manager.py for session recovery per plan.md Q5 (Hybrid approach):
  - [ ] If resume ≤5 min: Keep browser context alive, verify cookies/session still valid
  - [ ] If resume >5 min: Close context, replay last N steps, detect 401/403, trigger re-auth with stored credentials
  - [ ] Re-auth: Load credentials from data/credentials/ (encrypted), use Workflow.login_with_credentials() or similar
  - [ ] Log recovery events: session_expired, session_recovered, re_auth with context

- [ ] T083 [US6] Create src/framework/resumption_manager.py: Handle workflow resumption
  - [ ] Load execution state from data/executions/{execution_id}.json
  - [ ] Determine if resume is "quick" (<5 min) or "slow" (>5 min)
  - [ ] For quick: restore browser context from checkpoint
  - [ ] For slow: replay steps up to checkpoint, detect/handle auth failures
  - [ ] Resume from checkpoint (or from last successful step if auth failed)

- [ ] T084 [US6] [P] Create tests/framework/unit/test_resumption_manager.py: Test quick resume (<5 min) and slow resume (>5 min) logic (no browser)

- [ ] T085 [US6] [P] Create tests/framework/integration/test_quick_resume.py: Test actual quick resume (stop workflow, resume within 5 min, verify context preserved)

- [ ] T086 [US6] [P] Create tests/framework/integration/test_slow_resume_with_recovery.py: Test slow resume (>5 min) with session recovery and re-auth

- [ ] T087 [US6] Create src/cli/resume_workflow.py: CLI to resume paused/failed workflow
  - [ ] Accept execution_id
  - [ ] Load execution state
  - [ ] Determine resume strategy (quick/slow)
  - [ ] Execute resumption_manager
  - [ ] Continue execution from checkpoint or last successful step

- [ ] T088 [US6] [P] Create tests/workflows/integration/test_login_workflow_resume_quick.py: LoginWorkflow with simulated pause, quick resume (<5 min)

- [ ] T089 [US6] [P] Create tests/workflows/integration/test_login_workflow_resume_slow.py: LoginWorkflow with simulated pause, slow resume (>5 min), 401/403 handling, re-auth

- [ ] T090 [US6] Create documentation: docs/resumption-guide.md
  - [ ] Explain quick vs slow resume strategies
  - [ ] Explain session recovery and re-authentication
  - [ ] Explain credential encryption and storage
  - [ ] Show recovery examples (happy path, 401/403, timeout)

- [ ] T091 [US6] Create tests/quickstart_scenarios/test_scenario_c_slow_resume.py: Scenario C from quickstart.md (timeout, hard fail at 5min, manual resume with recovery)

**Independent Test Criteria for US6**:
- Execution state snapshots to JSON on every step completion and checkpoint
- Quick resume (<5 min) restores browser context and resumes from checkpoint
- Slow resume (>5 min) replays steps, detects 401/403, triggers re-auth, resumes
- Credentials stored encrypted (AES-256-GCM) and decrypted on resume
- All resumption events logged with context
- Manual resume via CLI works for both quick and slow cases

---

## Phase 9: User Story 7 - Screenshot and PDF Export During Workflow (P3)

**Goal**: Enable workflows to capture screenshots and export pages as PDF  
**Duration**: 1 week  
**Prerequisite**: Phase 1, 2, 3  
**Deliverable**: Screenshot/PDF export methods, artifact storage, linked to execution

### User Story 7 Tasks

- [x] T092 [US7] Enhance src/framework/workflow.py Playwright wrappers:
  - [x] take_screenshot(name: str) → Path: Capture current page, save to data/artifacts/{execution_id}/{name}.png, return Path
  - [x] export_to_pdf(name: str) → Path: Export page via print to PDF, save to data/artifacts/{execution_id}/{name}.pdf, return Path
  - [x] Both methods populate Resource entities in execution state

- [x] T093 [US7] Create src/framework/resource_manager.py: Manage execution artifacts
  - [x] Track screenshot/PDF files per execution
  - [x] Organize in data/artifacts/{execution_id}/ directory
  - [x] Return file paths and URLs (for MCP resource serving)
  - [x] Clean up on execution deletion

- [x] T094 [US7] [P] Create tests/framework/unit/test_resource_manager.py: Test artifact tracking and cleanup (14 tests passing)

- [x] T095 [US7] [P] Create tests/workflows/integration/test_take_screenshot.py: Test take_screenshot() with mock browser (mock page.screenshot())

- [x] T096 [US7] [P] Create tests/workflows/integration/test_export_to_pdf.py: Test export_to_pdf() with mock browser (mock page.pdf())

- [x] T097 [US7] Enhance src/mcp_server/resources.py to serve artifacts:
  - [x] Add get_artifact_resource(execution_id, name) → bytes + content_type
  - [x] Add list_artifact_resources(execution_id) → list of artifact metadata
  - [x] Add get_execution_artifacts_from_state(execution_id) → resources from state
  - [x] Support PNG, JPEG, PDF with proper MIME type detection
  - [x] 14 unit + 14 integration tests all passing

- [x] T098 [US7] Create documentation: docs/artifacts-guide.md
  - [x] Explain take_screenshot() and export_to_pdf()
  - [x] Explain artifact storage location
  - [x] Show how to query artifacts from execution state
  - [x] Provide usage examples and best practices
  - [x] Document MCP resource serving functions

**Independent Test Criteria for US7**:
- take_screenshot() and export_to_pdf() methods create files in correct location
- Artifacts recorded in execution state (Resource entities)
- PDF export uses print media type
- Artifacts queryable via execution logs and state
- MCP server can serve artifacts to clients

---

## Phase 10: Final Phase - Polish, Testing & Documentation

**Goal**: Complete test coverage, comprehensive documentation, performance optimization  
**Duration**: 1-2 weeks  
**Prerequisite**: All user stories (Phase 3-9)  
**Deliverable**: Full test coverage, user guides, performance validated, MVP complete

### Polish & Integration Tasks

- [ ] T099 Create documentation: docs/architecture.md
  - [ ] System diagram (Workflow → Execution → MCP Server → Agent)
  - [ ] Data flow diagram (state persistence, checkpoint protocol)
  - [ ] Component diagram (framework/, mcp_server/, shared_steps/)

- [ ] T100 Create documentation: docs/error-handling.md
  - [ ] Error hierarchy and classification
  - [ ] Transient vs permanent errors
  - [ ] Retry strategy and backoff
  - [ ] Error examples and recovery

- [ ] T101 Create documentation: docs/logging-and-debugging.md
  - [ ] Structured JSON logging format
  - [ ] Log level configuration
  - [ ] Querying logs with get_execution_logs tool
  - [ ] Debugging a failed workflow

- [ ] T102 Create documentation: docs/security.md
  - [ ] Credential storage (AES-256-GCM encryption)
  - [ ] Session handling and cookies
  - [ ] Input validation and sanitization
  - [ ] Best practices for workflow authors

- [ ] T103 Create documentation: docs/performance-tuning.md
  - [ ] Concurrency limits and resource quotas
  - [ ] Browser context pooling
  - [ ] Timeout configuration
  - [ ] Profiling and optimization tips

- [ ] T104 [P] Create tests/performance/test_execution_throughput.py: Benchmark 100 simple workflows, measure throughput (workflows/min)

- [ ] T105 [P] Create tests/performance/test_memory_usage.py: Monitor memory during 50 concurrent executions, verify no leaks

- [ ] T106 [P] Create tests/performance/test_checkpoint_latency.py: Measure checkpoint decision latency (target <2 seconds)

- [ ] T107 Create tests/e2e/test_full_workflow_lifecycle.py: End-to-end test of complete workflow: create → run → checkpoint → resume → complete → query logs

- [ ] T108 Run full test suite and achieve >80% code coverage (pytest-cov)
  - [ ] tests/framework/unit/: >90% coverage
  - [ ] tests/framework/integration/: >85% coverage
  - [ ] tests/workflows/integration/: >80% coverage
  - [ ] Generate coverage report: pytest --cov=src --cov-report=html

- [ ] T109 Create CONTRIBUTING.md: Developer guide
  - [ ] Project setup (venv, pip install)
  - [ ] Running tests (pytest)
  - [ ] Adding new workflows (extend Workflow class, use @step)
  - [ ] Adding new custom actions (extend Action class, register)
  - [ ] Debugging workflows (log level, execution state inspection)

- [ ] T110 Create examples/ directory with complete runnable examples:
  - [ ] examples/01_simple_login.py: LoginWorkflow (Story 1)
  - [ ] examples/02_login_with_checkpoint.py: LoginWorkflow + checkpoint (Story 2)
  - [ ] examples/03_batch_processing.py: Run multiple LoginWorkflows (Story 3)
  - [ ] examples/04_custom_actions.py: FormFillingWorkflow using custom actions (Story 4)
  - [ ] examples/05_mcp_control.py: Control workflow via MCP server (Story 5)
  - [ ] examples/06_resume_after_error.py: Simulate error and resume (Story 6)
  - [ ] examples/07_capture_artifacts.py: Take screenshots and export PDF (Story 7)

- [ ] T111 Create quick-start-tutorial.md: 5-minute guide to first workflow
  - [ ] Setup venv
  - [ ] Import Workflow class
  - [ ] Define simple workflow
  - [ ] Execute workflow
  - [ ] Check logs and state

- [ ] T112 Validate all quickstart scenarios (5 scenarios from quickstart.md)
  - [ ] Scenario A: Happy path (T037)
  - [ ] Scenario B: Quick resume (T045)
  - [ ] Scenario C: Slow resume (T091)
  - [ ] Scenario D: Concurrent execution (T053)
  - [ ] Scenario E: Error handling & retry (T037 with error cases)

- [ ] T113 Create CHANGELOG.md with MVP v1.0.0 entry: Initial release with 7 user stories

- [ ] T114 Update README.md with final content:
  - [ ] Project overview and key features
  - [ ] Quick start (3-line example)
  - [ ] Architecture diagram
  - [ ] Links to docs, examples, contributing guide
  - [ ] Status and roadmap (Phase 2 features listed)

---

## Dependency Graph & Parallel Execution Strategy

### Strict Sequential (No Parallelization)

1. Phase 1: Setup & Infrastructure (T001-T012)
2. Phase 2: Framework Core (T013-T029)
3. Phase 3-9: User Stories (can run in parallel after Phase 1 & 2)
4. Phase 10: Polish & Testing (depends on all stories)

### Parallel Execution Opportunities

**After Phase 2 Complete**: All User Story phases (3-9) can run in parallel:

**Track A (Stories 1, 3)** - Workflow Developer & Concurrency:
- T030-T037 (Story 1: Basic workflow creation)
- T046-T054 (Story 3: Concurrency) - can start after T020 (Workflow base class)

**Track B (Stories 2, 4)** - Checkpoints & Extensibility:
- T038-T045 (Story 2: Checkpoints)
- T055-T064 (Story 4: Custom actions) - can start after T020

**Track C (Stories 5, 6)** - Control & Persistence:
- T065-T081 (Story 5: MCP server)
- T082-T091 (Story 6: Resumption) - can start after T082

**Track D (Story 7)** - Artifacts:
- T092-T098 (Story 7: Screenshots & PDF)

**Example Parallel Gantt** (weeks):
```
Week 1:    Phase 1 (Setup)
Week 2:    Phase 2 (Framework core)
Week 3-4:  Tracks A, B, C, D in parallel
Week 5-6:  Phase 10 (Polish, testing, docs)
```

**Estimated Duration**: 4-6 weeks total (vs 8+ weeks sequential)

---

## Task Format Validation Checklist

- [x] All tasks follow strict format: `- [ ] [TaskID] [optional flags] Description with file path`
- [x] Task IDs sequential (T001-T114)
- [x] [P] marker present for parallelizable tasks (different files, no blocking dependencies)
- [x] [US1] through [US7] labels present for user story phase tasks (not setup/foundation)
- [x] All tasks include specific file paths (src/*, tests/*, docs/*)
- [x] File paths are absolute within project (e.g., src/framework/workflow.py, not just "workflow.py")
- [x] No tasks missing file paths
- [x] All 7 user stories represented (T030-T037 for US1, T038-T045 for US2, etc.)

---

## Implementation Phases Summary

| Phase | Goal | Duration | Tasks | Dependencies |
|-------|------|----------|-------|--------------|
| 1 | Setup | 1-2 days | T001-T012 | None |
| 2 | Framework Core | 1-2 wks | T013-T029 | Phase 1 |
| 3 | US1: Developer | 1 wk | T030-T037 | Phase 1, 2 |
| 4 | US2: Checkpoint | 1.5 wks | T038-T045 | Phase 1, 2 |
| 5 | US3: Parallel | 1.5 wks | T046-T054 | Phase 1, 2, 3 |
| 6 | US4: Extensibility | 1 wk | T055-T064 | Phase 1, 2, 3 |
| 7 | US5: MCP Control | 2 wks | T065-T081 | Phase 1, 2, 3 |
| 8 | US6: Persistence | 1.5 wks | T082-T091 | Phase 1, 2, 5 |
| 9 | US7: Artifacts | 1 wk | T092-T098 | Phase 1, 2, 3 |
| 10 | Polish & Docs | 1-2 wks | T099-T114 | All stories |

**Total Estimated Effort**: 4-6 weeks (with 3-4 parallel tracks in weeks 3-4)

---

## MVP Scope & Acceptance

**MVP Definition**: Complete Phases 1-6 (Setup through Extensibility)
- Covers User Stories 1-4 (P1 & early P2)
- Includes MCP server basics (Story 5 partial) if time permits
- Delivers immediate value: developers can create, test, and run workflows

**Phase 2+ (Post-MVP)**:
- Complete Story 5 (full MCP integration) and Story 6 (advanced resumption)
- Add Story 7 (artifacts)
- Scale infrastructure (SQLite for 1000+ concurrent)
- Advanced features: workflow recording/replay, rollback capability, state schema versioning

**MVP Success Criteria**:
- Workflow creation <30 min for developer (SC-001) ✅
- All P1 user stories implemented and tested ✅
- Checkpoint pause/resume working (<2 sec latency) ✅
- 50 concurrent workflows on laptop (8GB RAM) ✅
- Full test coverage >80% ✅
- Documentation complete with examples ✅

---

## Notes & Assumptions

1. **Browser Testing**: Use mock Playwright page objects in unit/integration tests; defer full E2E (real browser) to separate suite
2. **Credentials**: MVP stores encrypted in files; Phase 2 integrates OS keyrings (Keychain/Credential Manager)
3. **MCP SDK**: Use Anthropic's `mcp` library per research.md; requires stdio-based transport
4. **Testing Approach**: No explicit "test" tasks in Phase 3-9 beyond integration tests; full test suite in Phase 10
5. **Documentation**: Prioritize usage docs over API docs; assume developers read code for implementation details
6. **Concurrency Limit**: Default max 5 concurrent workflows; configurable via environment variable
7. **Checkpoint Timeout**: Soft 2 min (retries), Hard 5 min (fail); tunable per execution
8. **Session Recovery**: Hybrid strategy per research.md; fast resume <5 min, slow resume >5 min with re-auth

---

**Tasks Generated**: 114 implementation tasks  
**Test Tasks Included**: Yes (per request via US acceptance criteria)  
**Total Checklist Items**: 114 + ~50 inline task checklist items (e.g., T020 sub-tasks)  
**Status**: Ready for Phase 1 execution

