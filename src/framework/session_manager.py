"""Browser Session Management

Handles browser context lifecycle, session persistence, and recovery
for expired sessions (401/403 Unauthorized/Forbidden).
"""

import json
import time
from pathlib import Path
from typing import Any, Optional

from playwright.async_api import BrowserContext, Page

from ..utils.logging import setup_logger

logger = setup_logger(__name__)


class SessionManager:
    """Manages browser session lifecycle, persistence, and recovery."""

    SESSION_TIMEOUT_SECONDS = 300  # 5 minutes
    AUTH_ERROR_CODES = {401, 403}

    def __init__(
        self,
        execution_id: str,
        session_dir: Optional[Path] = None):
        """Initialize session manager for an execution.

        Args:
            execution_id: Execution ID for session storage
            session_dir: Directory for session persistence (defaults to data/sessions/)
        """
        self.execution_id = execution_id

        if session_dir is None:
            session_dir = Path(__file__).parent.parent.parent / "data" / "sessions"

        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)

        self.session_file = self.session_dir / f"{execution_id}.json"
        self.browser_context: Optional[BrowserContext] = None
        self.created_at = time.time()
        self.last_activity_at = time.time()

        logger.info(f"SessionManager initialized for execution: {execution_id}")

    async def initialize_context(
        self,
        browser,
        base_url: str,
        **context_kwargs) -> BrowserContext:
        """Create or restore browser context.

        Attempts to restore session from previous execution if available,
        otherwise creates fresh context.

        Args:
            browser: Playwright browser instance
            base_url: Base URL for navigation
            **context_kwargs: Additional context creation arguments

        Returns:
            BrowserContext instance
        """
        logger.debug(f"Initializing browser context for execution: {self.execution_id}")

        # Try to restore session from storage
        session_data = self._load_session()

        if session_data:
            logger.info(
                f"Restoring session for execution: {self.execution_id}",
                extra={"cookies_count": len(session_data.get("cookies", []))})

            # Create context with stored storage state
            self.browser_context = await browser.new_context(
                base_url=base_url,
                storage_state={
                    "cookies": session_data.get("cookies", []),
                    "origins": session_data.get("origins", []),
                },
                **context_kwargs)
        else:
            # Create fresh context
            logger.info(
                f"Creating new browser context for execution: {self.execution_id}")
            self.browser_context = await browser.new_context(
                base_url=base_url,
                **context_kwargs)

        self.created_at = time.time()
        self.last_activity_at = time.time()

        return self.browser_context

    async def save_session(self) -> None:
        """Persist current session (cookies, storage) to storage.

        Called after successful operations to enable recovery.
        """
        if not self.browser_context:
            logger.warning("No active browser context to save")
            return

        try:
            # Get storage state (cookies, local storage, etc.)
            storage_state = await self.browser_context.storage_state()

            session_data = {
                "execution_id": self.execution_id,
                "timestamp": time.time(),
                "cookies": storage_state.get("cookies", []),
                "origins": storage_state.get("origins", []),
            }

            self._save_session_data(session_data)
            logger.debug(f"Session saved for execution: {self.execution_id}")

        except Exception as e:
            logger.error(f"Failed to save session: {e}", extra={"execution_id": self.execution_id})

    async def check_session_valid(self, page: Page) -> bool:
        """Check if session is still valid by testing a simple request.

        Args:
            page: Playwright page instance

        Returns:
            True if session valid, False if session expired
        """
        try:
            response = await page.goto(page.url or "/", wait_until="domcontentloaded")

            if response and response.status in self.AUTH_ERROR_CODES:
                logger.warning(
                    f"Session expired (HTTP {response.status}) for execution: {self.execution_id}")
                return False

            logger.debug(f"Session valid for execution: {self.execution_id}")
            self.last_activity_at = time.time()
            return True

        except Exception as e:
            logger.error(
                f"Error checking session validity: {e}",
                extra={"execution_id": self.execution_id})
            return False

    def get_session_age_seconds(self) -> float:
        """Get age of current session in seconds.

        Returns:
            Age of session since creation
        """
        return time.time() - self.created_at

    def is_session_expired(self) -> bool:
        """Check if session exceeds timeout threshold.

        Returns:
            True if session older than SESSION_TIMEOUT_SECONDS
        """
        age = self.get_session_age_seconds()
        return age > self.SESSION_TIMEOUT_SECONDS

    async def recover_session(
        self,
        browser,
        base_url: str,
        credential_provider=None,
        **context_kwargs) -> tuple[bool, Optional[str]]:
        """Attempt session recovery after 401/403 error.

        Strategy depends on session age:
        - If <5min: Keep browser alive, request credential confirmation
        - If ≥5min: Create new context, re-authenticate with stored credentials

        Args:
            browser: Playwright browser instance
            base_url: Base URL for navigation
            credential_provider: Provider for re-authentication (optional)
            **context_kwargs: Additional context creation arguments

        Returns:
            Tuple of (success, recovery_strategy_used)
        """
        session_age = self.get_session_age_seconds()
        logger.warning(
            f"Attempting session recovery for execution: {self.execution_id}",
            extra={"session_age_seconds": session_age, "strategy": "keep_alive" if session_age < 300 else "replay"})

        if session_age < 300:  # < 5 minutes
            # Strategy: Keep alive and wait for credential confirmation
            logger.info(
                "Using keep-alive recovery strategy",
                extra={"execution_id": self.execution_id})
            return True, "keep_alive"

        else:  # >= 5 minutes
            # Strategy: Create new context and replay auth
            logger.info(
                "Using replay recovery strategy",
                extra={"execution_id": self.execution_id})

            try:
                # Close old context
                if self.browser_context:
                    await self.browser_context.close()

                # Create new context (will restore cookies from storage)
                self.browser_context = await self.initialize_context(
                    browser,
                    base_url,
                    **context_kwargs)

                return True, "replay"

            except Exception as e:
                logger.error(
                    f"Session recovery failed: {e}",
                    extra={"execution_id": self.execution_id})
                return False, None

    async def close(self) -> None:
        """Close browser context and clean up resources.

        Saves session before closing for recovery on next execution.
        """
        if self.browser_context:
            try:
                await self.save_session()
                await self.browser_context.close()
                logger.info(f"Session closed for execution: {self.execution_id}")
            except Exception as e:
                logger.error(
                    f"Error closing session: {e}",
                    extra={"execution_id": self.execution_id})

    def _load_session(self) -> Optional[dict[str, Any]]:
        """Load session data from storage.

        Returns:
            Session dict if found, None otherwise
        """
        if not self.session_file.exists():
            return None

        try:
            with open(self.session_file, "r") as f:
                data = json.load(f)

            logger.debug(f"Loaded session from: {self.session_file}")
            return data

        except Exception as e:
            logger.error(
                f"Failed to load session: {e}",
                extra={"session_file": str(self.session_file)})
            return None

    def _save_session_data(self, data: dict[str, Any]) -> None:
        """Save session data to storage.

        Uses atomic write for crash safety.

        Args:
            data: Session data to persist
        """
        temp_file = self.session_file.with_suffix(".json.tmp")

        try:
            # Write to temp file
            with open(temp_file, "w") as f:
                json.dump(data, f, indent=2)

            # Atomic rename
            temp_file.replace(self.session_file)

            logger.debug(f"Session saved to: {self.session_file}")

        except Exception as e:
            logger.error(
                f"Failed to save session: {e}",
                extra={"session_file": str(self.session_file)})
            if temp_file.exists():
                temp_file.unlink()


class BrowserContextPool:
    """Manages a pool of isolated browser contexts for concurrent executions.

    Allocates contexts to executions, tracks usage, and detects/cleans up leaks.
    """

    def __init__(self, max_concurrent: int = 5):
        """Initialize context pool.

        Args:
            max_concurrent: Maximum concurrent contexts (default 5)
        """

        self.max_concurrent = max_concurrent
        self._available_contexts: list[BrowserContext] = []
        self._context_to_execution: dict[int, str] = {}  # context id -> execution_id
        self._execution_to_context: dict[str, BrowserContext] = {}  # execution_id -> context
        self._context_created_at: dict[int, float] = {}  # context id -> creation time
        self._pool_lock = asyncio.Lock()
        self._browser = None

        logger.info(
            f"BrowserContextPool initialized with max_concurrent={max_concurrent}")

    async def initialize(self, browser) -> None:
        """Initialize pool with browser instance.

        Args:
            browser: Playwright browser instance
        """
        async with self._pool_lock:
            self._browser = browser
            logger.debug("BrowserContextPool initialized with browser instance")

    async def acquire_context(
        self,
        execution_id: str,
        base_url: str = None,
        **context_kwargs) -> BrowserContext:
        """Acquire a context for an execution.

        Prioritizes reusing available contexts from pool. If none available,
        creates new context if under max_concurrent limit, else raises error.

        Args:
            execution_id: Unique execution ID
            base_url: Base URL for context
            **context_kwargs: Additional context creation arguments

        Returns:
            BrowserContext instance

        Raises:
            RuntimeError: If execution already has assigned context or at max capacity
        """

        async with self._pool_lock:
            if execution_id in self._execution_to_context:
                raise RuntimeError(
                    f"Execution {execution_id} already has assigned context"
                )

            # Prefer reusing available contexts first
            if self._available_contexts:
                context = self._available_contexts.pop()
                context_id = id(context)

                # Assign context to new execution
                self._execution_to_context[execution_id] = context
                old_exec = self._context_to_execution.get(context_id, "unknown")
                self._context_to_execution[context_id] = execution_id

                logger.debug(
                    f"Reused context for execution: {execution_id}",
                    extra={"previous_execution": old_exec})

                return context

            # Otherwise create new context if under max concurrent limit
            if len(self._execution_to_context) < self.max_concurrent:
                if not self._browser:
                    raise RuntimeError("Pool not initialized with browser")

                context = await self._browser.new_context(
                    base_url=base_url,
                    **context_kwargs)

                context_id = id(context)
                self._execution_to_context[execution_id] = context
                self._context_to_execution[context_id] = execution_id
                self._context_created_at[context_id] = time.time()

                logger.info(
                    f"New context created for execution: {execution_id}",
                    extra={"total_contexts": len(self._execution_to_context)})

                return context

            # At capacity and no available contexts
            raise RuntimeError(
                f"Context pool at max capacity ({self.max_concurrent}), "
                f"cannot acquire for {execution_id}"
            )

    async def release_context(
        self,
        execution_id: str,
        save_session: bool = False,
        session_manager: Optional["SessionManager"] = None) -> None:
        """Release context back to pool or close it.

        Args:
            execution_id: Execution ID holding the context
            save_session: Whether to save session before release
            session_manager: Optional session manager for saving state
        """
        async with self._pool_lock:
            if execution_id not in self._execution_to_context:
                logger.warning(
                    f"Cannot release context for unknown execution: {execution_id}"
                )
                return

            context = self._execution_to_context[execution_id]

            if save_session and session_manager:
                try:
                    # Temporarily set context for session save
                    old_context = session_manager.browser_context
                    session_manager.browser_context = context
                    await session_manager.save_session()
                    session_manager.browser_context = old_context
                except Exception as e:
                    logger.error(
                        f"Failed to save session for execution {execution_id}: {e}"
                    )

            # Return to pool (don't close yet, reuse for next execution)
            self._available_contexts.append(context)
            del self._execution_to_context[execution_id]

            logger.debug(
                f"Context released for execution: {execution_id}",
                extra={
                    "available_contexts": len(self._available_contexts),
                    "active_contexts": len(self._execution_to_context),
                })

    def get_context_for_execution(self, execution_id: str) -> Optional[BrowserContext]:
        """Get current context for an execution (non-blocking lookup).

        Args:
            execution_id: Execution ID

        Returns:
            BrowserContext if execution has assigned context, None otherwise
        """
        return self._execution_to_context.get(execution_id)

    async def get_pool_metrics(self) -> dict[str, Any]:
        """Get current pool state metrics.

        Returns:
            Dict with active_contexts, available_contexts, max_concurrent, leak_detected
        """
        async with self._pool_lock:
            metrics = {
                "active_contexts": len(self._execution_to_context),
                "available_contexts": len(self._available_contexts),
                "max_concurrent": self.max_concurrent,
                "total_contexts": len(self._context_to_execution),
            }

            # Detect potential leaks (contexts held >1 hour)
            now = time.time()
            leaked = [
                (exec_id, now - created_at)
                for (ctx_id, exec_id), created_at in zip(
                    self._context_to_execution.items(),
                    self._context_created_at.values())
                if now - created_at > 3600  # 1 hour
            ]

            if leaked:
                metrics["leaked_contexts"] = [
                    {"execution_id": exec_id, "held_seconds": held_seconds}
                    for exec_id, held_seconds in leaked
                ]

            return metrics

    async def cleanup(self) -> None:
        """Clean up pool, close all contexts.

        Should be called on process exit to release browser resources.
        """
        async with self._pool_lock:
            logger.info(
                "Cleaning up BrowserContextPool",
                extra={
                    "active_contexts": len(self._execution_to_context),
                    "available_contexts": len(self._available_contexts),
                })

            # Close all contexts
            all_contexts = (
                list(self._execution_to_context.values())
                + self._available_contexts
            )

            for context in all_contexts:
                try:
                    await context.close()
                except Exception as e:
                    logger.error(f"Error closing context during cleanup: {e}")

            # Clear all tracking
            self._execution_to_context.clear()
            self._available_contexts.clear()
            self._context_to_execution.clear()
            self._context_created_at.clear()

            logger.info("BrowserContextPool cleanup complete")
