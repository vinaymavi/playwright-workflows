<!-- SYNC IMPACT REPORT
Amended 2026-11-01 to add concurrent execution support.
- Version: 1.0.0 → 1.1.0 (MINOR)
- Ratification: 2026-11-01 (original)
- Modified principles: Principle VI (new), Technical Architecture (expanded)
- Added sections: Concurrency & Resource Management subsection
- Removed sections: None
- Deferred TODOs: None
-->

# Playwright Automation Workflows Constitution

## Core Principles

### I. Human-Agent-in-Loop Communication
Every workflow execution MUST support interactive communication with human operators and/or AI agents. Workflows MUST:
- Expose checkpoints where agents can intervene, review decisions, or approve actions
- Provide structured data exchanges (JSON) for agent decision-making
- Support pause/resume cycles without loss of context
- Log all agent interactions with timestamps and decision rationale for auditability

**Rationale**: Automation without human oversight creates unrecoverable failure states. Agent-in-loop ensures accountability, allows for judgment on edge cases, and enables continuous learning from workflow execution.

### II. Python-Native Implementation
All workflow automation code MUST be written in Python. The standard library and Playwright Python bindings are the primary implementation vehicle. This means:
- Core workflow orchestration logic in Python (not shell scripts or other languages)
- Playwright via `pytest`, `playwright`, and related Python packages
- Virtual environment management via `venv` or `uv` for reproducibility
- Type hints encouraged to improve maintainability

**Rationale**: Python's readability, ecosystem (Playwright, asyncio, logging), and broad availability across teams create consistency and reduce onboarding friction.

### III. Stateful Workflow Execution
Workflows MUST maintain and preserve execution state across agent interactions. This requires:
- Persistent state storage (JSON, database, or file-based) for each workflow run
- Clear state transitions documented in workflow logic
- Rollback capability when agent feedback requires corrections
- State schema versioning to handle workflow evolution

**Rationale**: Stateless workflows lose context in agent handoffs. Explicit state management enables recovery, audit trails, and incremental progress without re-executing completed steps.

### IV. Observability by Design
Every workflow and agent interaction MUST be observable through structured logging and events. Requirements:
- Structured logging (JSON format) with context (workflow_id, step, agent, timestamp)
- Event emission at workflow start, step completion, agent checkpoints, and errors
- Debugging support: verbose logs available on demand without re-running workflows
- Performance metrics captured (step duration, retries, agent response time)

**Rationale**: Complex workflows fail in production. Built-in observability enables diagnosis without reproducing failures, supports alerting, and provides evidence for post-mortems.

### V. Test Coverage for Workflow Logic
Workflow orchestration logic MUST be tested independent of Playwright browser automation. This means:
- Unit tests for agent decision logic, state transitions, and data validation
- Integration tests for agent-workflow communication patterns
- Fixture-based mock agents for testing without external service calls
- Workflow runs recorded/replayed for regression testing

**Rationale**: Browser automation tests are slow and brittle; orchestration bugs are often in decision logic, not page interactions. Separating concerns enables fast feedback and catches state management bugs early.

### VI. Concurrent Execution with Resource Isolation
Workflows MUST support multiple simultaneous executions without interference. This requires:
- Unique execution IDs for each workflow instance (UUID v4 or similar)
- Isolated state namespaces per execution (no cross-execution data sharing)
- Resource quotas per execution (memory, browser instances, agent timeout limits)
- Conflict detection for shared resources (e.g., accounts, files, API rate limits)
- Clear documentation of what state is global vs. execution-scoped

**Rationale**: Real-world automation often triggers multiple workflows concurrently (e.g., batch jobs, user-triggered parallel actions). Isolation prevents cascading failures, deadlocks, and hard-to-debug race conditions. Resource quotas prevent runaway processes from affecting other executions.

## Technical Architecture

### Language and Runtime Requirements
- **Primary Language**: Python 3.9+
- **Package Management**: `pip`, `uv`, or similar (document choice in project-level guidance)
- **Environment**: Virtual environments (`venv`) mandatory for all development
- **Playwright**: Python bindings; async/await style preferred for scalability

### Agent Interface Contract
Workflows communicate with agents via a standard interface:
- **Input**: JSON object with workflow state, pending decisions, and context
- **Output**: JSON object with agent decision, rationale, and any side effects
- **Transport**: HTTP APIs, message queues, or local function calls (document in guidance)
- **Timeouts**: All agent calls MUST have explicit timeouts; workflows MUST handle non-response

### Workflow Execution Model
- **Single Entry**: Each workflow has one public entry point accepting workflow-specific inputs
- **Async Support**: Workflows MUST support async execution to enable concurrency
- **Concurrent Instances**: Multiple executions of the same workflow MAY run simultaneously
- **Execution Isolation**: Each execution gets a unique ID; state MUST be isolated per execution
- **Resource Management**: Workflows MUST respect per-execution resource limits (e.g., max browser tabs, agent timeout budgets)
- **Error Handling**: All agent checkpoints must include failure paths; errors MUST not silently continue
- **Resumption**: Workflows MUST support restart from last completed checkpoint (within isolated execution context)

### Concurrency & Resource Management
Workflows designed for concurrent execution MUST:
- Generate a unique execution ID (`execution_id`) at workflow start
- Prefix all persistent state keys with `execution_id` to prevent cross-execution contamination
- Define resource limits per execution: max concurrent browser pages, agent call concurrency, memory usage
- Implement conflict detection for shared resources (e.g., if workflow A and B both modify the same file, detect and handle)
- Log resource usage per execution for capacity planning and cost attribution
- Provide clear documentation of what resources are global (e.g., connection pools) vs. execution-scoped

## Development Workflow

### Code Review Requirements
- Every pull request introducing workflow logic MUST include:
  - Workflow diagram or text description of new/changed steps
  - State schema changes documented (if any)
  - Agent communication example (sample JSON input/output)
  - Test cases for new decision logic

### Compliance Verification
- CI/CD MUST run the full test suite (unit + integration) before merge
- Workflows MUST pass at least one end-to-end execution in a staging environment before production deployment
- Breaking changes to agent interfaces MUST be deprecated with at least one release cycle notice

### Documentation
- Every workflow MUST have a README explaining its purpose, inputs, outputs, and agent checkpoints
- Agent interface schemas MUST be documented (JSON Schema, OpenAPI, or similar)
- Workflow examples MUST include common agent interactions (approve, reject, modify)

## Governance

**Constitution Authority**: This constitution defines non-negotiable principles for all workflow automation in this project. It supersedes team preferences or prior practices.

**Amendment Process**:
1. Propose amendment via GitHub Discussion or pull request comment
2. Rationale MUST address which principle(s) are affected and why current guidance is insufficient
3. Amendments require project maintainer approval and documented impact assessment
4. Version MUST be bumped according to semver (MAJOR for removals, MINOR for additions, PATCH for clarifications)
5. All contributors MUST be notified of governance changes

**Compliance Review**:
- Quarterly: Project lead reviews active workflows against constitution
- Ad-hoc: During code review, any principle violation MUST be addressed before merge
- Guidance: See `.specify/DEVELOPMENT.md` for runtime practices aligned with these principles

**Version**: 1.1.0 | **Ratified**: 2026-11-01 | **Last Amended**: 2026-11-01
