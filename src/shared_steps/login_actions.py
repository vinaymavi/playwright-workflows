"""Reusable Login and Credential Actions

Provides common actions for authentication workflows including
credential entry, two-factor authentication, and session verification.
"""

from typing import Any, Optional

from playwright.async_api import Page, TimeoutError

from ..framework.action import Action
from ..framework.errors import PermanentError, TransientError
from ..utils.logging import setup_logger

logger = setup_logger(__name__)


class EnterCredentialsAction(Action):
    """Enter username and password into login form fields.

    Fills username and password fields and returns status.

    Example:
        action = EnterCredentialsAction(workflow, name="login_step")
        result = await action.run(
            username_selector="input[name='username']",
            password_selector="input[name='password']",
            username="user@example.com",
            password="secret123"
        )
    """

    async def execute(
        self,
        username_selector: str,
        password_selector: str,
        username: str,
        password: str,
        wait_ms: int = 5000) -> dict[str, Any]:
        """Enter credentials into form.

        Args:
            username_selector: CSS selector for username/email field
            password_selector: CSS selector for password field
            username: Username or email value
            password: Password value
            wait_ms: Wait time in milliseconds

        Returns:
            Dictionary with entered_fields and status

        Raises:
            ValueError: If selectors or credentials are empty
            TransientError: If fields not found
            PermanentError: If field fill fails
        """
        if not username_selector or not password_selector:
            raise ValueError("Selectors cannot be empty")

        if not username or not password:
            raise ValueError("Credentials cannot be empty")

        page: Page = self.workflow_context.page

        try:
            # Fill username
            await page.wait_for_selector(username_selector, timeout=wait_ms)
            await page.fill(username_selector, username)
            logger.debug(f"Entered username into {username_selector}")

            # Fill password
            await page.wait_for_selector(password_selector, timeout=wait_ms)
            await page.fill(password_selector, password)
            logger.debug(f"Entered password into {password_selector}")

            return {
                "username_field": username_selector,
                "password_field": password_selector,
                "status": "success",
            }

        except TimeoutError as e:
            error_msg = "Timeout waiting for credential fields"
            logger.warning(error_msg)
            raise TransientError(self.name, error_msg, cause=e)

        except Exception as e:
            error_msg = f"Failed to enter credentials: {str(e)}"
            logger.warning(error_msg)
            raise PermanentError(self.name, error_msg, cause=e)


class SubmitLoginFormAction(Action):
    """Submit login form and wait for navigation.

    Clicks the login button and waits for page navigation or element appearance.

    Example:
        action = SubmitLoginFormAction(workflow, name="submit_login")
        result = await action.run(
            button_selector="button[type='submit']",
            wait_for_element="div.dashboard"
        )
    """

    async def execute(
        self,
        button_selector: str,
        wait_for_element: Optional[str] = None,
        wait_for_navigation: bool = True,
        wait_ms: int = 10000) -> dict[str, Any]:
        """Submit login form.

        Args:
            button_selector: CSS selector for submit button
            wait_for_element: Optional selector to wait for after submission
            wait_for_navigation: If True, wait for page navigation
            wait_ms: Wait time in milliseconds

        Returns:
            Dictionary with submission status

        Raises:
            TransientError: If button not found or timeout occurs
            PermanentError: If submission fails
        """
        page: Page = self.workflow_context.page

        try:
            await page.wait_for_selector(button_selector, timeout=wait_ms)

            # Click button, optionally waiting for navigation
            if wait_for_navigation:
                async with page.expect_navigation(timeout=wait_ms):
                    await page.click(button_selector)
                logger.debug("Clicked login button and waited for navigation")
            else:
                await page.click(button_selector)
                logger.debug("Clicked login button")

            # If specific element should appear, wait for it
            if wait_for_element:
                await page.wait_for_selector(wait_for_element, timeout=wait_ms)
                logger.debug(
                    f"Login succeeded, element appeared: {wait_for_element}"
                )

            return {
                "button_clicked": button_selector,
                "navigation_waited": wait_for_navigation,
                "status": "success",
            }

        except TimeoutError as e:
            error_msg = f"Timeout during login submission (waited {wait_ms}ms)"
            logger.warning(error_msg)
            raise TransientError(self.name, error_msg, cause=e)

        except Exception as e:
            error_msg = f"Failed to submit login form: {str(e)}"
            logger.warning(error_msg)
            raise PermanentError(self.name, error_msg, cause=e)


class VerifyLoginSuccessAction(Action):
    """Verify that login was successful.

    Checks for expected elements/URL/text that indicate successful login.

    Example:
        action = VerifyLoginSuccessAction(workflow, name="verify_login")
        result = await action.run(
            url_contains="dashboard",
            element_selector=".user-profile"
        )
    """

    async def execute(
        self,
        url_contains: Optional[str] = None,
        element_selector: Optional[str] = None,
        page_title_contains: Optional[str] = None,
        wait_ms: int = 10000) -> dict[str, Any]:
        """Verify login success.

        Args:
            url_contains: URL substring to verify (e.g., '/dashboard')
            element_selector: Selector of element that should be visible
            page_title_contains: Substring of page title to verify
            wait_ms: Wait time in milliseconds

        Returns:
            Dictionary with verification results

        Raises:
            ValueError: If no verification criteria provided
            TransientError: If verification times out
            PermanentError: If verification fails
        """
        page: Page = self.workflow_context.page

        # Verify at least one criterion is provided
        verification_criteria = sum([
            url_contains is not None,
            element_selector is not None,
            page_title_contains is not None,
        ])

        if verification_criteria == 0:
            raise ValueError(
                "At least one verification criterion must be provided"
            )

        verification_results = {}

        try:
            # Check URL
            if url_contains:
                current_url = page.url
                if url_contains in current_url:
                    verification_results["url_verified"] = True
                    logger.debug(f"URL verification passed: {current_url}")
                else:
                    error_msg = (
                        f"URL doesn't contain '{url_contains}', "
                        f"got '{current_url}'"
                    )
                    logger.warning(error_msg)
                    raise PermanentError(self.name, error_msg)

            # Check element visibility
            if element_selector:
                await page.wait_for_selector(element_selector, timeout=wait_ms)
                verification_results["element_verified"] = True
                logger.debug(f"Element verification passed: {element_selector}")

            # Check page title
            if page_title_contains:
                title = await page.title()
                if page_title_contains in title:
                    verification_results["title_verified"] = True
                    logger.debug(f"Title verification passed: {title}")
                else:
                    error_msg = (
                        f"Title doesn't contain '{page_title_contains}', "
                        f"got '{title}'"
                    )
                    logger.warning(error_msg)
                    raise PermanentError(self.name, error_msg)

            return {
                "verification_results": verification_results,
                "status": "success",
            }

        except TimeoutError as e:
            error_msg = f"Timeout during login verification (waited {wait_ms}ms)"
            logger.warning(error_msg)
            raise TransientError(self.name, error_msg, cause=e)

        except Exception as e:
            if isinstance(e, PermanentError):
                raise
            error_msg = f"Login verification failed: {str(e)}"
            logger.warning(error_msg)
            raise PermanentError(self.name, error_msg, cause=e)


class HandleLoginErrorAction(Action):
    """Handle login errors such as invalid credentials or account locked.

    Detects error messages and categorizes the error type.

    Example:
        action = HandleLoginErrorAction(workflow, name="handle_login_error")
        result = await action.run(
            error_selector=".error-message",
            error_messages={
                "invalid_creds": ["Invalid username or password", "Incorrect login"],
                "account_locked": ["Account locked", "Too many attempts"],
            }
        )
    """

    async def execute(
        self,
        error_selector: str,
        error_messages: dict[str, list] = None,
        wait_ms: int = 5000) -> dict[str, Any]:
        """Check for and handle login errors.

        Args:
            error_selector: Selector for error message element
            error_messages: Dictionary mapping error types to message patterns
            wait_ms: Wait time in milliseconds

        Returns:
            Dictionary with error_found, error_type, and error_text

        Raises:
            TransientError: If error message times out (soft failure)
            PermanentError: If permanent error detected
        """
        if error_messages is None:
            error_messages = {
                "invalid_credentials": [
                    "invalid",
                    "incorrect",
                    "wrong",
                ],
                "account_locked": [
                    "locked",
                    "attempts",
                    "too many",
                ],
                "unknown": [],
            }

        page: Page = self.workflow_context.page

        try:
            # Try to find error element
            await page.wait_for_selector(error_selector, timeout=wait_ms)

            # Get error text
            error_element = page.locator(error_selector).first
            error_text = await error_element.text_content()
            error_text = error_text.lower() if error_text else ""

            logger.warning(f"Login error detected: {error_text}")

            # Categorize error
            error_type = "unknown"
            for category, patterns in error_messages.items():
                for pattern in patterns:
                    if pattern.lower() in error_text:
                        error_type = category
                        break
                if error_type != "unknown":
                    break

            # Permanent errors that shouldn't be retried
            if error_type == "invalid_credentials":
                raise PermanentError(
                    self.name,
                    f"Login failed with invalid credentials: {error_text}")
            elif error_type == "account_locked":
                raise PermanentError(
                    self.name,
                    f"Account is locked: {error_text}")

            return {
                "error_found": True,
                "error_type": error_type,
                "error_text": error_text,
                "status": "error_detected",
            }

        except TimeoutError:
            # No error element found - login might have succeeded
            logger.debug("No error message found, login may have succeeded")
            return {
                "error_found": False,
                "status": "success",
            }

        except Exception as e:
            if isinstance(e, PermanentError):
                raise
            error_msg = f"Failed to check for login errors: {str(e)}"
            logger.warning(error_msg)
            raise TransientError(self.name, error_msg, cause=e)
