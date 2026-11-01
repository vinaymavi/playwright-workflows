# Research & Technology Selection

**Feature**: Playwright Workflow Orchestration Framework  
**Date**: 2026-11-01  
**Status**: Phase 0 Output - All NEEDS CLARIFICATION items resolved

---

## 1. Python MCP (Model Context Protocol) SDK

### Decision

**Use Anthropic's Official `mcp` SDK for MCP server implementation**

### Installation & Setup

```bash
pip install "mcp[cli]"
# or
pip install mcp anthropic
```

### Minimal Server Skeleton (JSON-RPC 2.0 over stdio)

```python
from mcp.server import Server, Request
import logging
import json

# CRITICAL: Use logging to stderr, never print() to stdout
# stdout is reserved for JSON-RPC 2.0 protocol messages
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, stream=sys.stderr)

class WorkflowMCPServer:
    def __init__(self):
        self.server = Server("WorkflowOrchestrator")
        self._setup_tools()
    
    def _setup_tools(self):
        @self.server.call_tool()
        async def start_workflow(name: str, arguments: dict) -> list:
            """MCP tool: start a Playwright workflow"""
            logger.info(f"Tool called: {name} with args: {arguments}")
            workflow_type = arguments.get("workflow_type")
            params = arguments.get("input_params", {})
            
            # Call framework to start workflow
            execution_id = await self.framework.start_workflow(workflow_type, params)
            
            return [{"type": "text", "text": json.dumps({"execution_id": execution_id})}]
    
    def run_stdio(self):
        """Run server using stdio transport (standard MCP mode)"""
        self.server.run_stdio()

if __name__ == "__main__":
    server = WorkflowMCPServer()
    server.run_stdio()
```

### Key Technical Points

| Aspect | Details |
|--------|---------|
| **JSON-RPC Version** | 2.0 (official spec) |
| **Transport** | stdio (stdin/stdout for JSON-RPC, stderr for logs) |
| **Bidirectional Support** | ✅ YES — Server can expose tools; client can call server tools AND server can call client tools |
| **Type Hints** | Required; docstrings auto-convert to JSON schema |
| **Logging** | Use `logging.getLogger()` → stderr; never `print()` to stdout |

### Alternatives Considered & Rejected

| Alternative | Why Rejected |
|-------------|-------------|
| Custom JSON-RPC implementation | Maintenance burden; no benefit over battle-tested SDK |
| `python-mcp` (legacy) | Deprecated in favor of official Anthropic SDK |
| `yodlr-mcp` | Limited documentation; smaller community |

### Rationale

- **Official source**: Anthropic maintains and updates this SDK
- **Best documentation**: https://py.sdk.modelcontextprotocol.io/
- **Community adoption**: Growing standard; other frameworks build on it
- **Bidirectional support**: Essential for workflows calling back to MCP server for checkpoint decisions

---

## 2. Async Concurrency for Playwright + asyncio

### Decision

**Use `asyncio.Semaphore` + `asyncio.TaskGroup` for orchestrating 50+ concurrent Playwright browser instances**

### Architecture Pattern

```python
import asyncio
from playwright.async_api import async_playwright

async def run_workflow(page, workflow_id: str, semaphore: asyncio.Semaphore):
    """Run a single workflow with concurrency gating."""
    async with semaphore:  # Acquire execution slot
        # Workflow logic here
        await page.goto(f"https://example.com/workflow/{workflow_id}")
        result = await page.content()
        return result

async def main(workflow_ids: list, max_concurrent: int = 50):
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context()
        
        async with asyncio.TaskGroup() as tg:
            for workflow_id in workflow_ids:
                page = await context.new_page()
                tg.create_task(run_workflow(page, workflow_id, semaphore))
        
        await browser.close()

# Run 100 workflows, max 50 concurrent
asyncio.run(main(workflow_ids=list(range(100))))
```

### Concurrency Control Components

| Component | Purpose | Usage |
|-----------|---------|-------|
| **`asyncio.Semaphore(N)`** | Limits concurrent operations to N | Controls resource usage (CPU, browser instances) |
| **`async with semaphore`** | Acquire/release slot | Deadlock-free resource management |
| **`asyncio.TaskGroup` (Python 3.11+)** | Structured concurrency | Ensures all tasks finish; propagates exceptions; prevents dangling tasks |

### Browser Pooling Libraries

| Library | Use Case | Pros | Cons |
|---------|----------|------|------|
| **`playwright-page-pool`** (PyPI) | Page-level pooling within one browser | Simple, memory-efficient | Single context |
| **`playwright-pool`** (GitHub: tgscan) | Full browser instance pooling | Process isolation (anti-bot) | Higher memory |
| **Manual Semaphore** (recommended for MVP) | Direct control, no new dependency | Explicit, transparent | Slightly more code |

### Alternatives Considered & Rejected

| Alternative | Why Rejected |
|-------------|-------------|
| **ThreadPoolExecutor** | GIL (Global Interpreter Lock) blocks true parallelism; I/O not accelerated by threads |
| **multiprocessing.Pool** | Playwright requires spawning new browser processes; overkill for I/O-bound workflows |
| **gevent** | Maintenance risk; unsupported Python 3.12+; asyncio is now Python standard |

### Rationale

- **Native Python**: `asyncio` is in standard library
- **Structured concurrency**: TaskGroup prevents resource leaks (Python 3.11+)
- **Scalable**: Tested patterns for thousands of concurrent tasks
- **Familiar**: Most async Python developers know asyncio
- **Integrates with Playwright**: Playwright's async API designed for asyncio

---

## 3. Session Recovery & CSRF Token Handling

### 3.1 Secure Credential Storage (AES-256-GCM)

**Decision**: Use `cryptography` library with AES-256-GCM and PBKDF2 key derivation

```python
import os
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import json

class SecureCredentialStore:
    def __init__(self, master_password: str):
        self.master_password = master_password
    
    def derive_key(self, salt: bytes) -> bytes:
        """Derive 256-bit key from password using PBKDF2-SHA256."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,  # 256 bits
            salt=salt,
            iterations=200_000,  # High iterations for security
        )
        return kdf.derive(self.master_password.encode())
    
    def encrypt(self, credentials: dict) -> dict:
        """Encrypt credentials; return encrypted blob."""
        salt = os.urandom(16)
        nonce = os.urandom(12)
        key = self.derive_key(salt)
        
        cipher = AESGCM(key)
        plaintext = json.dumps(credentials).encode()
        ciphertext = cipher.encrypt(nonce, plaintext, None)  # None = no AAD
        
        return {
            "salt": salt.hex(),
            "nonce": nonce.hex(),
            "ciphertext": ciphertext.hex(),
            "algorithm": "aes-256-gcm"
        }
    
    def decrypt(self, encrypted_blob: dict) -> dict:
        """Decrypt credentials."""
        salt = bytes.fromhex(encrypted_blob["salt"])
        nonce = bytes.fromhex(encrypted_blob["nonce"])
        ciphertext = bytes.fromhex(encrypted_blob["ciphertext"])
        
        key = self.derive_key(salt)
        cipher = AESGCM(key)
        plaintext = cipher.decrypt(nonce, ciphertext, None)
        
        return json.loads(plaintext.decode())
```

### 3.2 Session Cookie Persistence via Playwright

```python
import json
from pathlib import Path

async def save_session_state(context, execution_id: str):
    """Save browser context state (cookies, localStorage, session storage)."""
    state = await context.storage_state()
    state_file = Path(f"data/executions/{execution_id}/session_state.json")
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(state, indent=2))
    return state_file

async def restore_session_state(browser, execution_id: str):
    """Restore browser context from saved state."""
    state_file = Path(f"data/executions/{execution_id}/session_state.json")
    if state_file.exists():
        state = json.loads(state_file.read_text())
        context = await browser.new_context(storage_state=state)
        return context
    else:
        # No saved session; create new
        return await browser.new_context()
```

### 3.3 CSRF Token Refresh During Step Replay

```python
from bs4 import BeautifulSoup
import re

async def extract_csrf_token(page) -> str:
    """Extract CSRF token from current page using common patterns."""
    html = await page.content()
    soup = BeautifulSoup(html, 'html.parser')
    
    # Try common input field names
    for input_field in soup.find_all('input', {'name': ['csrf_token', '_csrf', 'token', 'authenticity_token']}):
        token = input_field.get('value')
        if token:
            return token
    
    # Try meta tags (common in modern SPAs)
    meta_tag = soup.find('meta', {'name': 'csrf-token'})
    if meta_tag:
        return meta_tag.get('content')
    
    raise ValueError("CSRF token not found on page")

async def replay_workflow_steps_with_csrf_refresh(page, workflow_steps: list):
    """
    Replay workflow steps from checkpoint, refreshing CSRF tokens before each POST/PUT/DELETE.
    
    workflow_steps format:
    [
        {"action": "navigate", "url": "..."},
        {"action": "fill", "selector": "...", "value": "..."},
        {"action": "post_form", "selector": "..."},
    ]
    """
    for step in workflow_steps:
        if step['action'] == 'navigate':
            await page.goto(step['url'])
        
        elif step['action'] == 'fill':
            await page.fill(step['selector'], step['value'])
        
        elif step['action'] == 'post_form':
            # Refresh CSRF before POST
            csrf_token = await extract_csrf_token(page)
            
            # Inject token into form (common patterns)
            await page.fill('input[name="csrf_token"]', csrf_token, timeout=1000)
            await page.fill('input[name="_csrf"]', csrf_token, timeout=1000)
            
            await page.click(step['selector'])
            # Wait for page load/response
            await page.wait_for_load_state('networkidle')
```

### 3.4 401/403 Detection & Auto Re-authentication

```python
async def resume_workflow_with_session_recovery(
    context,
    execution_state: dict,
    credential_store: SecureCredentialStore,
    max_retries: int = 3
):
    """
    Resume workflow from checkpoint; detect session expiration and recover.
    
    Implements hybrid strategy:
    1. If checkpoint < 2 min ago: browser context kept alive, resume directly
    2. If checkpoint > 5 min ago or error: replay last N steps, detect 401/403, re-auth
    """
    page = await context.new_page()
    checkpoint_time = execution_state['checkpoint']['created_at']
    current_time = datetime.now(timezone.utc)
    elapsed = (current_time - checkpoint_time).total_seconds()
    
    SOFT_TIMEOUT = 120  # 2 minutes
    HARD_TIMEOUT = 300  # 5 minutes
    
    if elapsed < SOFT_TIMEOUT:
        # Quick resume: session still valid, continue from checkpoint
        logger.info(f"Soft timeout path: {elapsed}s elapsed, resuming with cached session")
        return page
    
    elif elapsed >= HARD_TIMEOUT:
        # Hard timeout: replay + re-auth required
        logger.info(f"Hard timeout path: {elapsed}s elapsed, replaying steps + re-auth")
        
        # Replay last N steps from checkpoint
        workflow_steps = execution_state['completed_steps'][max(0, len(execution_state['completed_steps']) - 3):]
        await replay_workflow_steps_with_csrf_refresh(page, workflow_steps)
        
        # Detect session expiration (401/403)
        try:
            test_page = await context.new_page()
            response = await test_page.goto(execution_state['last_url'])
            
            if response.status in [401, 403]:
                logger.warning(f"Session expired (status {response.status}); re-authenticating...")
                
                # Get stored credentials
                encrypted_creds = execution_state['encrypted_credentials']
                creds = credential_store.decrypt(encrypted_creds)
                
                # Navigate to login and re-authenticate
                await page.goto(execution_state['login_url'])
                await page.fill('input[name="username"]', creds['username'])
                await page.fill('input[name="password"]', creds['password'])
                await page.click('button[type="submit"]')
                await page.wait_for_load_state('networkidle')
                
                logger.info("Re-authentication successful")
            
            await test_page.close()
        except Exception as e:
            logger.error(f"Session recovery failed: {e}")
            raise
    
    return page
```

### Rationale

| Decision | Rationale | Alternatives Rejected |
|----------|-----------|----------------------|
| **AES-256-GCM** | Authenticated encryption (integrity + confidentiality) | AES-CBC (no integrity), plaintext (insecure) |
| **PBKDF2 (200K iters)** | Standard key derivation; high iteration count = slow brute-force attacks | SHA-256 direct (weak against GPU/ASIC attacks) |
| **Playwright storage_state** | Native support; preserves all session data (cookies, localStorage) | Manual cookie jar (incomplete state) |
| **CSRF token refresh** | Sites regenerate tokens per request; replay without refresh fails | Assume token valid (fails on new forms) |
| **Hybrid timeout strategy** | Balances quick recovery (soft) with security (hard + replay) | Single timeout (loses context or stale session) |

---

## 4. State Persistence with File Locking

### Decision

**Use `fcntl.flock` + atomic write-to-temp-rename pattern for process-safe JSON state**

### Implementation: LockedJSONState

```python
import json
import fcntl
import os
import tempfile
from pathlib import Path
from typing import Any, Dict

class LockedJSONState:
    """Thread-safe and process-safe JSON state manager."""
    
    def __init__(self, filepath: str):
        self.filepath = Path(filepath)
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        if not self.filepath.exists():
            self.filepath.write_text(json.dumps({}))
    
    def read(self) -> Dict[str, Any]:
        """Read state with exclusive lock."""
        with open(self.filepath, 'r') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                return json.load(f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    
    def write(self, data: Dict[str, Any]) -> None:
        """Write state atomically with exclusive lock."""
        dirpath = self.filepath.parent
        
        # Write to temp file in same directory (avoids cross-FS issues)
        with tempfile.NamedTemporaryFile(
            mode='w', dir=dirpath, delete=False
        ) as tf:
            json.dump(data, tf, indent=2)
            tf.flush()
            os.fsync(tf.fileno())  # Force to disk
            temp_name = tf.name
        
        # Atomic rename (POSIX guarantee)
        os.replace(temp_name, self.filepath)
        
        # Sync directory on POSIX (handle power loss)
        if hasattr(os, 'fsync'):
            try:
                dirfd = os.open(dirpath, os.O_DIRECTORY)
                os.fsync(dirfd)
                os.close(dirfd)
            except (OSError, AttributeError):
                pass  # Not supported on all systems
    
    def update(self, key: str, value: Any) -> None:
        """Read-modify-write with atomic guarantee."""
        data = self.read()
        data[key] = value
        self.write(data)
```

### File Locking Strategy Comparison

| Strategy | Use Case | Pros | Cons |
|----------|----------|------|------|
| **`fcntl.flock`** | Multi-process, Unix/Linux | OS-native, atomic, simple | Unix only; NFS issues |
| **`fcntl.fcntl`** | POSIX.1 advisory locks | More portable | Verbose; same OS limitations |
| **Explicit lock file** | Maximum portability | Works everywhere | Race conditions; cleanup needed |
| **Database lock** | Very high concurrency | Scalable to 1000+ | Adds external dependency |

**Selected: `fcntl.flock`** — simplest for MVP on single machine; upgradeable to SQLite for future scale.

### Atomic Write Pattern: Write-Temp-Rename

```python
def atomic_write(filepath: str, data: str) -> None:
    """Write file atomically; never leaves partial/corrupt writes."""
    dirpath = os.path.dirname(filepath) or '.'
    
    # Write to temporary file (same directory)
    with tempfile.NamedTemporaryFile(
        mode='w', dir=dirpath, delete=False
    ) as tf:
        tf.write(data)
        tf.flush()
        os.fsync(tf.fileno())  # Force to disk before rename
        temp_name = tf.name
    
    # Atomic rename (POSIX guarantee)
    os.replace(temp_name, filepath)
    
    # Optionally: sync directory (handles power loss)
    try:
        dirfd = os.open(dirpath, os.O_DIRECTORY)
        os.fsync(dirfd)
        os.close(dirfd)
    except (AttributeError, OSError):
        pass  # Not all systems support directory fsync
```

**Why This Works**:
- **Atomicity**: POSIX `rename` is atomic; OS doesn't split it into multiple operations
- **Crash-safe**: Readers never see partial or corrupt file (temp file is not visible)
- **No corruption**: Write fully completes to temp file before rename
- **Conflict-free**: Temp file in same directory avoids cross-filesystem issues

**Alternatives Rejected**:
- Direct `file.write()` then `close()` — can fail mid-write, leaving corrupt file
- `shutil.move()` — not atomic on all filesystems
- Lock-wait-then-write — doesn't prevent corruption between lock release and write

### JSON Schema Versioning for Future Migrations

```python
SCHEMA_VERSION = 1

class VersionedJSONState(LockedJSONState):
    """JSON state with versioning for schema migrations."""
    
    def read(self) -> Dict[str, Any]:
        data = super().read()
        
        # Auto-upgrade if schema version mismatch
        current_version = data.get('__version__', 0)
        if current_version < SCHEMA_VERSION:
            data = self._migrate(data, current_version, SCHEMA_VERSION)
            self.write(data)  # Persist upgraded schema
        
        return data
    
    def write(self, data: Dict[str, Any]) -> None:
        data['__version__'] = SCHEMA_VERSION
        super().write(data)
    
    def _migrate(self, data: Dict, from_ver: int, to_ver: int) -> Dict:
        """Handle schema migrations between versions."""
        if from_ver < 1:
            # Future migrations go here
            data['workflows'] = data.get('workflows', {})
            data['resources'] = data.get('resources', {})
        return data
```

### Rationale

- **File-based MVP**: No external database dependency; portable, inspectable
- **Process-safe**: `fcntl.flock` prevents concurrent write corruption
- **Crash-safe**: Atomic rename ensures no partial writes
- **Upgradeable**: Schema versioning enables transition to SQLite at scale ≥1000 concurrent

---

## Summary: Technology Decisions Locked

| Component | Decision | Rationale | Migration Path |
|-----------|----------|-----------|-----------------|
| **MCP SDK** | Anthropic `mcp` package | Official, bidirectional, best docs | N/A (stable) |
| **Concurrency** | asyncio.Semaphore + TaskGroup | Idiomatic Python, structured, scales | N/A (stable) |
| **Browser Pool** | Manual Semaphore (MVP) → `playwright-page-pool` (future) | Control + simplicity; upgrade if pooling needed | Add dependency, refactor executor |
| **Credential Storage** | AES-256-GCM + PBKDF2 + OS keyring (future) | Authenticated encryption + standard KDF | Use `keyring` library for OS keyring |
| **Session Recovery** | Hybrid (keep-alive ≤2min, replay+re-auth >5min) | Balances speed + security | N/A (specified in checkpoint logic) |
| **File Locking** | `fcntl.flock` + atomic writes | OS-native, simple for MVP | Migrate to SQLite when scale ≥1000 |
| **State Storage** | JSON + schema versioning | Portable, inspectable, upgradeable | SQLite with transaction support |

---

## Implementation Next Steps

1. **Phase 1 Design**: Use these decisions to generate `data-model.md`, `contracts/`, `quickstart.md`
2. **Phase 2 Tasks**: `/speckit-tasks` will generate implementation tasks prioritized by dependency
3. **Phase 3 Development**: Implement modules in order: framework core → checkpoint → execution → MCP server → workflows

---

**Research completed**: All NEEDS CLARIFICATION items resolved. Ready for Phase 1 design phase.
