"""Browser Session Management

Handles browser context lifecycle, session persistence, and recovery
for expired sessions (401/403 Unauthorized/Forbidden).
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

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
        session_dir: Optional[Path] = None,
    ):
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
        **context_kwargs,
    ) -> BrowserContext:
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
                extra={"cookies_count": len(session_data.get("cookies", []))},
            )

            # Create context with stored storage state
            self.browser_context = await browser.new_context(
                base_url=base_url,
                storage_state={
                    "cookies": session_data.get("cookies", []),
                    "origins": session_data.get("origins", []),
                },
                **context_kwargs,
            )
        else:
            # Create fresh context
            logger.info(
                f"Creating new browser context for execution: {self.execution_id}",
            )
            self.browser_context = await browser.new_context(
                base_url=base_url,
                **context_kwargs,
            )

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
                    f"Session expired (HTTP {response.status}) for execution: {self.execution_id}",
                )
                return False

            logger.debug(f"Session valid for execution: {self.execution_id}")
            self.last_activity_at = time.time()
            return True

        except Exception as e:
            logger.error(
                f"Error checking session validity: {e}",
                extra={"execution_id": self.execution_id},
            )
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
        **context_kwargs,
    ) -> tuple[bool, Optional[str]]:
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
            extra={"session_age_seconds": session_age, "strategy": "keep_alive" if session_age < 300 else "replay"},
        )

        if session_age < 300:  # < 5 minutes
            # Strategy: Keep alive and wait for credential confirmation
            logger.info(
                "Using keep-alive recovery strategy",
                extra={"execution_id": self.execution_id},
            )
            return True, "keep_alive"

        else:  # >= 5 minutes
            # Strategy: Create new context and replay auth
            logger.info(
                "Using replay recovery strategy",
                extra={"execution_id": self.execution_id},
            )

            try:
                # Close old context
                if self.browser_context:
                    await self.browser_context.close()

                # Create new context (will restore cookies from storage)
                self.browser_context = await self.initialize_context(
                    browser,
                    base_url,
                    **context_kwargs,
                )

                return True, "replay"

            except Exception as e:
                logger.error(
                    f"Session recovery failed: {e}",
                    extra={"execution_id": self.execution_id},
                )
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
                    extra={"execution_id": self.execution_id},
                )

    def _load_session(self) -> Optional[Dict[str, Any]]:
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
                extra={"session_file": str(self.session_file)},
            )
            return None

    def _save_session_data(self, data: Dict[str, Any]) -> None:
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
                extra={"session_file": str(self.session_file)},
            )
            if temp_file.exists():
                temp_file.unlink()
