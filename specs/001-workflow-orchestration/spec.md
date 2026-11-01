# Feature Specification: Playwright Workflow Orchestration Framework

**Feature Branch**: `001-workflow-orchestration`

**Created**: 2026-11-01

**Status**: Draft

**Input**: Setup Playwright-based workflow automation framework supporting parallel execution, agent-in-loop checkpoints, extensibility, and external control via Python programs or MCP servers.

## User Scenarios & Testing

### User Story 1 - Workflow Developer Creates a Web Automation Task (Priority: P1)

A Python developer needs to create a reusable workflow that automates a web application task (e.g., form filling, login, file upload). They should be able to define the workflow logic with minimal boilerplate, then execute it independently or as part of a larger system.

**Why this priority**: This is the core capability. Without the ability to easily create workflows, nothing else works. This is the MVP foundation.

**Independent Test**: Can be fully tested by creating a simple workflow (login + form fill), executing it standalone, and verifying it completes successfully. Delivers immediate value to developers.

**Acceptance Scenarios**:

1. **Given** a Python developer wants to automate a login task, **When** they create a workflow class inheriting from a base workflow, **Then** they can define steps using Playwright page methods and agent checkpoint calls
2. **Given** a completed workflow, **When** they instantiate and execute it with input parameters, **Then** the workflow executes sequentially through all defined steps
3. **Given** a workflow with network errors or browser issues, **When** an error occurs, **Then** the error is caught, logged structurally, and propagated to the caller with context

---

### User Story 2 - Agent Checkpoint During Workflow Execution (Priority: P1)

A workflow pauses at a checkpoint to ask a human operator or AI agent for a decision (e.g., "Should I proceed?", "Which option to select?"), then resumes based on the response. The workflow preserves all context and can resume from exactly that checkpoint.

**Why this priority**: Human-in-loop is a core requirement in the constitution. Without checkpoints, automation is too risky. This is equally foundational to Story 1.

**Independent Test**: Can be fully tested by creating a workflow with one agent checkpoint, triggering it, providing a decision, and verifying resumption. Delivers accountability and safety.

**Acceptance Scenarios**:

1. **Given** a running workflow with a checkpoint, **When** the checkpoint is reached, **Then** workflow pauses and sends structured JSON data (workflow state, question, context) to the agent
2. **Given** an agent response with a decision, **When** the response is received, **Then** workflow resumes from the checkpoint with the decision applied
3. **Given** workflow state at checkpoint, **When** the workflow resumes, **Then** all previous steps' state is available and unchanged

---

### User Story 3 - Parallel Execution of Multiple Workflow Instances (Priority: P1)

A controlling program (Python script or MCP server) triggers the same workflow multiple times in parallel (e.g., batch processing multiple user accounts). Each execution is isolated and does not interfere with others.

**Why this priority**: The constitution explicitly mandates concurrent execution support. High-value for scaling workflows to handle batch jobs.

**Independent Test**: Can be fully tested by launching 5 instances of the same workflow concurrently with different inputs, verifying all complete successfully without data/resource conflicts. Delivers batch processing capability.

**Acceptance Scenarios**:

1. **Given** a workflow that processes one user account, **When** a controlling program launches 10 instances in parallel with different account IDs, **Then** all 10 complete without cross-contamination or resource conflicts
2. **Given** parallel workflow instances, **When** each requests agent checkpoints, **Then** checkpoints from different executions are isolated (e.g., agent A handles execution 1, agent B handles execution 2)
3. **Given** resource constraints (e.g., max 3 concurrent browser instances), **When** 10 workflow instances are triggered, **Then** only 3 run concurrently and others queue

---

### User Story 4 - Workflow Extensibility with Custom Actions (Priority: P2)

A developer wants to add custom actions to workflows (e.g., "validate form", "extract table data", "upload file via drag-drop") without modifying the core framework. Custom actions inherit standard logging, error handling, and checkpoint capabilities.

**Why this priority**: Critical for long-term maintainability and adoption. Extensibility reduces duplication. Medium priority because Story 1 delivers basic extensibility (step definition), this adds convenience.

**Independent Test**: Can be fully tested by creating a custom action class, adding it to a workflow, executing it, and verifying it logs/errors correctly. Delivers framework reusability.

**Acceptance Scenarios**:

1. **Given** a developer wants to create a reusable action (e.g., "validate email field"), **When** they define an action class with specified interface, **Then** the action can be used in any workflow
2. **Given** a custom action that fails, **When** it raises an exception, **Then** the exception is caught by the framework, logged structurally, and workflow error handling applies

---

### User Story 5 - External Control via Python or MCP Server (Priority: P2)

A Python program or MCP server controls workflow execution: it triggers workflows, receives status updates, handles agent checkpoints, and manages results. The control interface is language-neutral and stateless from the framework's perspective.

**Why this priority**: Required for integration into larger systems. Medium priority because it depends on Stories 1-3 being solid first.

**Independent Test**: Can be fully tested by creating a simple Python controller script that triggers one workflow, receives completion status, and handles the result. Delivers orchestration capability.

**Acceptance Scenarios**:

1. **Given** a Python program wants to trigger a workflow, **When** it calls the workflow entry point with input parameters, **Then** it receives a workflow execution ID and status URL
2. **Given** an MCP server client, **When** it sends an MCP request to start a workflow, **Then** the framework accepts it and processes it as if called via Python
3. **Given** a workflow with agent checkpoints, **When** a checkpoint is reached, **Then** the controller receives a notification with pending decision data and can submit a response

---

### User Story 6 - Workflow Execution State Persistence & Resumption (Priority: P2)

A workflow encounters a transient error mid-execution and stops. Later, an operator can resume the workflow from the last checkpoint without re-running completed steps. Full execution history is preserved for audit.

**Why this priority**: Supports reliability and auditability. Constitution principle III requires stateful execution. Medium priority because it's not needed for MVP but is essential for production use.

**Independent Test**: Can be fully tested by executing a workflow partway, simulating an error, persisting state, reloading, and resuming. Delivers reliability.

**Acceptance Scenarios**:

1. **Given** a workflow at step 5 of 10, **When** an error occurs at step 7, **Then** workflow state (steps 1-6) is persisted to storage
2. **Given** persisted workflow state, **When** an operator calls resume on the execution ID, **Then** workflow re-loads state and continues from step 7 (not from step 1)
3. **Given** completed workflow, **When** execution logs are queried, **Then** full history is returned (steps, agent decisions, errors, timing)

---

### User Story 7 - Screenshot and PDF Export During Workflow (Priority: P3)

During workflow execution, the framework provides methods to capture screenshots and export the current page as PDF. Results are stored and made available after execution.

**Why this priority**: Nice-to-have for verification/audit. Lower priority than core orchestration. Out of scope for MVP but high value for completeness.

**Independent Test**: Can be fully tested by executing a workflow with screenshot/PDF export steps and verifying files are created. Delivers audit trail.

**Acceptance Scenarios**:

1. **Given** a workflow step that navigates to a page, **When** the step calls `capture_screenshot()`, **Then** a PNG file is created with a unique name
2. **Given** a workflow with PDF export, **When** the step calls `export_to_pdf()`, **Then** the current page is rendered as PDF and stored

---

### Edge Cases

- What happens if an agent checkpoint receives no response within a timeout? (Workflow should fail gracefully and log timeout)
- How does the system handle a workflow that creates 100 browser pages? (Should enforce resource quota and fail/queue new instances)
- What if two parallel workflow instances try to modify the same file? (Conflict detection should flag and either serialize or reject)
- What happens if a workflow is interrupted mid-execution? (Should rollback or preserve state for manual recovery)
- How does the system handle nested workflows (one workflow calling another)? (Should maintain execution context and isolation)
- What if session expires during checkpoint pause (e.g., 5+ min wait)? (Framework should detect 401/403 on resume, replay steps, re-authenticate if credentials available)

## Requirements

### Functional Requirements

- **FR-001**: Framework MUST provide a base workflow class that developers extend to define custom workflows
- **FR-002**: Workflows MUST support defining execution steps as methods or callable actions
- **FR-003**: Each workflow execution MUST receive a unique execution ID (UUID v4)
- **FR-004**: Workflow state MUST be isolated per execution ID (no cross-execution data sharing)
- **FR-005**: Framework MUST provide checkpoint API for pausing workflow and requesting agent decisions
- **FR-006**: Checkpoints MUST communicate with MCP server via JSON-RPC 2.0 (bidirectional MCP protocol); workflow subprocess connects to MCP server as MCP client; checkpoint sends request and receives decision response via MCP call
- **FR-007**: Workflows MUST support concurrent execution (multiple instances of same workflow running simultaneously)
- **FR-008**: Framework MUST enforce per-execution resource quotas (max browser pages, max concurrent agent calls, memory limits)
- **FR-009**: Framework MUST implement conflict detection for workflows accessing shared resources (files, APIs, accounts)
- **FR-010**: All workflow execution events MUST be logged in structured JSON format (workflow_id, execution_id, step, timestamp, status)
- **FR-011**: Framework MUST provide methods to capture screenshots (PNG) and export pages to PDF
- **FR-012**: Workflow state MUST be persistable to storage (JSON or database) for resumption after errors
- **FR-013**: Framework MUST support resuming workflows from last completed checkpoint using execution ID
- **FR-014**: Framework MUST provide Python API for triggering workflows and checking status
- **FR-015**: MCP Server (running as orchestrator) MUST implement standard MCP tools: `start_workflow`, `resolve_checkpoint`, `get_execution_status`, `get_execution_logs`; MCP server spawns workflows as subprocesses that connect back as MCP clients
- **FR-016**: Custom actions/steps MUST inherit framework's logging, error handling, and checkpoint capabilities without modification
- **FR-017**: Workflows MUST provide clear documentation of what state is global (e.g., connection pools) vs. execution-scoped
- **FR-018**: Framework MUST support timeout configuration for agent checkpoints (default reasonable value like 5 minutes)
- **FR-019**: Framework MUST support configurable retry logic per-step via decorator config: `max_retries` (default 3), `backoff_strategy` (exponential, linear, fixed), `retry_on_errors` (list of error types to retry), `fail_on_errors` (list to fail immediately without retry); transient errors retry automatically; permanent errors escalate to checkpoint
- **FR-020**: Framework MUST classify errors as transient (network, timeout, temporary resource unavailable) or permanent (validation, data missing, authorization); transient errors are auto-retried; permanent errors create checkpoint for agent decision
- **FR-021**: For checkpoint resume within soft timeout (2 min): Framework MUST keep browser context (page object, cookies, session tokens) alive; resume uses same authenticated session without re-login
- **FR-022**: For checkpoint resume after hard timeout (5+ min) or error recovery: Framework MUST implement partial replay (replay last N workflow steps before checkpoint); detect session expiration (401/403 responses); trigger re-authentication using stored secure credentials if session invalid
- **FR-023**: Framework MUST provide secure credential storage mechanism for workflows requiring re-authentication on resume (e.g., login credentials, API tokens); credentials encrypted at rest; never logged in plaintext
- **FR-024**: Framework MUST provide execution history and audit logs queryable by execution ID

- **Workflow**: A reusable automation logic defined by developer, composed of steps and checkpoints. Attributes: workflow_type, version, entry_point
- **Execution**: A single run of a workflow. Attributes: execution_id (UUID), workflow_type, input_params, start_time, status (pending/running/paused/completed/failed), state (JSON)
- **Step**: An atomic action in a workflow (navigate, click, fill form, call checkpoint, etc.). Attributes: step_id, name, duration, status, output
- **Checkpoint**: A pause point in workflow execution requesting agent decision. Attributes: checkpoint_id, workflow_state, question (JSON), response (JSON), agent_id, resolved_time, browser_context (page handle), session_cookies, checkpoint_step_number, timeout_strategy (keep_alive vs. replay)
- **Resource**: Shared or limited resource (browser instance, API connection, file). Attributes: resource_type, execution_id, allocation_time, quota_limit
- **ExecutionLog**: Structured event record. Attributes: timestamp, execution_id, step_id, event_type (start/complete/error/checkpoint), context (JSON)

## Success Criteria

### Measurable Outcomes

- **SC-001**: Developers can create a new workflow (login + form fill + screenshot) in under 30 minutes using framework APIs
- **SC-002**: A single workflow can execute 100 concurrent instances with no cross-execution data contamination
- **SC-003**: Workflows with agent checkpoints resume from last checkpoint within 2 seconds of checkpoint resolution
- **SC-004**: Framework captures and makes searchable execution logs for 100% of workflow runs (zero log loss)
- **SC-005**: 95% of agent checkpoint responses are received within 5 minutes (default timeout)
- **SC-006**: Custom action definitions reduce boilerplate code by 40% compared to inline step definitions
- **SC-007**: Workflow error recovery (resumption after transient error) succeeds 99% of the time
- **SC-008**: Framework handles up to 50 concurrent workflow instances on a standard laptop (4 CPU, 8GB RAM) without OOM
- **SC-009**: Developers report framework "easy to extend" or "very easy to extend" (7+ on 10-point scale) in user survey
- **SC-010**: MCP server interface is compatible with standard MCP clients (tested with at least 2 MCP implementations)

## Assumptions

- **Tech Stack**: Python 3.9+ is available; `asyncio` and `pytest` are project standards (per constitution); Playwright is installed
- **Agent Communication & MCP Architecture**: LLM (Claude/ChatGPT/Copilot) communicates with MCP server via JSON-RPC 2.0 (standard MCP protocol over stdio). MCP server spawns workflow subprocesses; workflows connect back to MCP server as MCP clients using JSON-RPC 2.0. Checkpoint requests flow: Workflow → MCP server (MCP call) → LLM (MCP notification) → User/LLM decides → Desktop app → MCP server (MCP response) → Workflow (MCP return). Soft timeout 2 min (triggers auto-retry), Hard timeout 5 min (notification to desktop app, workflow can resume if decision provided or marked failed if not).
- **Session & Security on Resume**: Workflows with checkpoints on session-authenticated sites MUST store login credentials securely (encrypted at rest). On resume within soft timeout (2 min), browser context kept alive (cookies/session valid). On resume after hard timeout (5+ min) or crash, framework replays last N steps, detects session expiration (401/403), re-authenticates using stored credentials, then continues. CSRF tokens refresh during replay.
- **Shared Resources**: File uploads/downloads go to a shared workspace directory (project-configurable); database access uses project's standard connection pool
- **Execution Isolation**: OS-level file permissions are sufficient for isolation; no need for containerization (but framework design should not prevent it)
- **Scale Expectations**: MVP targets 50 concurrent workflows; future versions may target 1000+
- **Error Handling**: Transient network errors are retried automatically; permanent errors require agent intervention or are logged for manual triage
- **Observability**: Structured JSON logs are written to local files or external logging service (configurable); no built-in UI dashboard (external tools can ingest logs)
- **Extensibility**: Developers are familiar with Python class inheritance and decorators; documentation assumes Python 3.6+ knowledge
- **External Control**: MCP server is optional; Python API is the primary control method for MVP
- **State Persistence**: MVP uses file-based JSON storage per execution; future versions may migrate to SQLite for enhanced querying and transaction support at scale
- **Project Structure**: Directory organization follows component-type pattern: `src/framework/` (core classes), `src/workflows/` (user workflows), `src/mcp_server/` (MCP orchestrator), `src/shared_steps/` (reusable step library), `src/utils/` (utilities). Each workflow is a Python package with `__init__.py`, `steps.py`, `fixtures.py`, `conftest.py`. Tests mirror source: `tests/framework/unit/`, `tests/framework/integration/`, `tests/workflows/e2e/`. Execution state lives in `data/executions/`, logs in `data/logs/`, artifacts in `data/artifacts/`, encrypted credentials in `data/credentials/`.

## Clarifications

### Session 2026-11-01

- **Q1: State Persistence Backend** → **A: File-based JSON for MVP (execution_id.json in shared directory), with SQLite upgrade path documented for scale ≥1000 concurrent workflows** — Provides simplicity for MVP while maintaining upgrade path; file-based JSON portable and Python-native; SQLite deferred to future when transaction guarantees and indexed log queries become critical at higher concurrency.

- **Q2: MCP Server ↔ Workflow Communication Protocol** → **A: Bidirectional MCP (Workflow subprocess connects back to MCP server as MCP client using JSON-RPC 2.0 over socket/pipe; both workflow and server use standard MCP protocol)** — Unified protocol across LLM ↔ MCP server ↔ Workflow (all JSON-RPC 2.0/MCP); enables recursive workflow composition; aligns with MCP ecosystem standards; subprocess can trigger tools on MCP server, request checkpoint decisions, and receive responses via JSON-RPC.

- **Q3: Retry Policy for Transient Errors** → **A: Configurable auto-retry (Option A) — Each step specifies retry policy via configuration (max_attempts, backoff_strategy, retry_on_errors, fail_on_errors); framework auto-retries on transient errors; permanent errors escalate to agent checkpoint** — Balances resilience (transients absorbed in-process) with visibility (permanent errors visible); reduces agent fatigue from repeated transient failures; developers control classification (transient vs. permanent) per-step via decorator config.

- **Q4: Checkpoint Timeout Behavior** → **A: Fail with State Preserved (Option A) with soft/hard timeout strategy: Soft timeout 2 minutes (triggers auto-retry), Hard timeout 5 minutes (workflow marked failed, state persisted). MCP server auto-retries checkpoint to LLM up to 3 times. At 4.5 min mark (before hard timeout), MCP notifies desktop app to show checkpoint UI. Human can provide decision via desktop app UI or manual MCP resolve_checkpoint call. Workflow resumes with decision.** — Provides LLM multiple attempts before failure; clear operator notification; enables human intervention; preserves full audit trail of timeout and recovery.

- **Q5: Session & Security Handling During Checkpoint Pause/Resume** → **A: Hybrid approach (Options A + C): Keep browser context alive if input received within 5 min (Option A — page object, cookies, session, CSRF token all preserved). If input received after 5 min hard timeout or on crash/error recovery, implement partial replay (Option C — replay last N steps, refill form, detect session expiration, trigger re-auth if needed). Framework detects if session invalid on resume (401/403) and automatically re-authenticates using stored secure credentials before continuing.** — Handles both common case (quick responses) and recovery case (late responses/crashes); preserves security; detects and recovers from session expiration; enables reliable multi-step workflows on secure websites.

### Session 2026-11-01 (Second Round)

- **Q1: Workflow Code Structure Approach** → **A: Module package approach (Option B) — Each workflow is a Python package (e.g., `workflows/login_workflow/` with `__init__.py`, `steps.py`, `fixtures.py`, `conftest.py`)** — Scales for teams; enables step reuse within and across workflows; supports granular testing; aligns with Python conventions; supports both simple single-step and complex multi-step workflows.

- **Q2: Root-Level Folder Organization** → **A: Component-type organization (Option A) — Root structure: `src/framework/` (core base classes, checkpoint manager, retry logic), `src/workflows/` (user-defined workflows, each as subpackage), `src/mcp_server/` (MCP server and tools), `src/shared_steps/` (reusable step library), `src/utils/` (logging, errors, helpers)** — Clear separation of concerns; easy to locate framework vs. user code; supports independent testing; scales as codebase grows; aligns with Python project conventions.

- **Q3: Framework Component Internal Organization** → **A: Individual modules per concept (Option A) — `framework/workflow.py`, `framework/checkpoint.py`, `framework/execution.py`, `framework/retry_handler.py`, `framework/session_manager.py`, `framework/errors.py`, `framework/decorators.py`** — Follows single responsibility principle; clean imports (e.g., `from framework.checkpoint import Checkpoint`); easier to test in isolation; standard Python pattern for scalable frameworks.

- **Q4: Test Organization Structure** → **A: Mirror source structure with test types (Option A) — `tests/framework/unit/`, `tests/framework/integration/`, `tests/workflows/unit/`, `tests/workflows/e2e/`, `tests/mcp_server/integration/`** — Developers know where tests live for each component; supports scoped test runs (e.g., `pytest tests/framework/unit/` for fast feedback); aligns with pytest conventions; test discovery is intuitive.

- **Q5: Execution State and Artifacts Storage** → **A: Fixed directory structure (Option A) — Centralized directories: `data/executions/` (execution state JSON per execution_id), `data/logs/` (structured logs), `data/artifacts/` (screenshots, PDFs, temp files), `data/credentials/` (encrypted credentials for re-auth)** — Simple; portable; predictable; developers know where to find state files for debugging; operations can implement backup/cleanup policies; supports file locking for concurrent access.
