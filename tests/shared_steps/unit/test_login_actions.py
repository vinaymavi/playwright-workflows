"""Unit tests for login actions."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from src.shared_steps.login_actions import (
    EnterCredentialsAction,
    SubmitLoginFormAction,
    VerifyLoginSuccessAction,
    HandleLoginErrorAction,
)
from src.framework.errors import PermanentError, TransientError


@pytest.fixture
def mock_workflow():
    """Create a mock workflow with page."""
    workflow = MagicMock()
    workflow.page = MagicMock()
    # Make async methods return awaitables
    workflow.page.wait_for_selector = AsyncMock()
    workflow.page.fill = AsyncMock()
    workflow.page.click = AsyncMock()
    workflow.page.url = "https://example.com/login"
    workflow.page.title = AsyncMock(return_value="Login Page")
    workflow.page.is_visible = AsyncMock()
    workflow.page.inner_text = AsyncMock()
    workflow.page.locator = MagicMock()
    return workflow


@pytest.mark.asyncio
class TestEnterCredentialsAction:
    """Tests for EnterCredentialsAction."""

    async def test_enter_credentials_success(self, mock_workflow):
        """Test successfully entering username and password."""
        action = EnterCredentialsAction(mock_workflow)

        result = await action.run(
            username_selector="input[name='username']",
            password_selector="input[name='password']",
            username="testuser@example.com",
            password="securepass123",
        )

        # Verify wait_for_selector called for both fields
        assert mock_workflow.page.wait_for_selector.call_count == 2
        mock_workflow.page.wait_for_selector.assert_any_call(
            "input[name='username']", timeout=5000
        )
        mock_workflow.page.wait_for_selector.assert_any_call(
            "input[name='password']", timeout=5000
        )

        # Verify fill called with correct values
        assert mock_workflow.page.fill.call_count == 2
        mock_workflow.page.fill.assert_any_call(
            "input[name='username']", "testuser@example.com"
        )
        mock_workflow.page.fill.assert_any_call(
            "input[name='password']", "securepass123"
        )

        # Verify result
        assert result["status"] == "success"
        assert result["username_field"] == "input[name='username']"
        assert result["password_field"] == "input[name='password']"

    async def test_enter_credentials_with_custom_timeout(self, mock_workflow):
        """Test entering credentials with custom timeout."""
        action = EnterCredentialsAction(mock_workflow)

        result = await action.run(
            username_selector="input#user",
            password_selector="input#pass",
            username="user123",
            password="pass456",
            wait_ms=10000,
        )

        # Verify custom timeout used
        calls = mock_workflow.page.wait_for_selector.call_args_list
        assert calls[0][1]["timeout"] == 10000
        assert calls[1][1]["timeout"] == 10000

        assert result["status"] == "success"

    async def test_enter_credentials_selector_not_found(self, mock_workflow):
        """Test handling when selector not found."""
        mock_workflow.page.wait_for_selector.side_effect = PlaywrightTimeoutError(
            "Timeout"
        )
        action = EnterCredentialsAction(mock_workflow)

        with pytest.raises(TransientError):
            await action.run(
                username_selector="input[name='username']",
                password_selector="input[name='password']",
                username="user",
                password="pass",
            )

    async def test_enter_credentials_fill_fails(self, mock_workflow):
        """Test handling when fill operation fails."""
        mock_workflow.page.fill.side_effect = Exception("Fill failed")
        action = EnterCredentialsAction(mock_workflow)

        with pytest.raises(PermanentError):
            await action.run(
                username_selector="input[name='username']",
                password_selector="input[name='password']",
                username="user",
                password="pass",
            )


@pytest.mark.asyncio
class TestSubmitLoginFormAction:
    """Tests for SubmitLoginFormAction."""

    async def test_submit_login_with_navigation_wait(self, mock_workflow):
        """Test submitting login form and waiting for navigation."""
        action = SubmitLoginFormAction(mock_workflow)

        result = await action.run(
            button_selector="button[type='submit']",
            wait_for_navigation=True,
        )

        mock_workflow.page.wait_for_selector.assert_called_once_with(
            "button[type='submit']", timeout=10000
        )
        mock_workflow.page.click.assert_called_once_with("button[type='submit']")
        assert result["status"] == "success"
        assert result["button_clicked"] == "button[type='submit']"

    async def test_submit_login_with_element_wait(self, mock_workflow):
        """Test submitting login form and waiting for element."""
        action = SubmitLoginFormAction(mock_workflow)

        result = await action.run(
            button_selector="button#login",
            wait_for_element=".dashboard",
            wait_for_navigation=False,
        )

        mock_workflow.page.wait_for_selector.assert_any_call(
            "button#login", timeout=10000
        )
        mock_workflow.page.wait_for_selector.assert_any_call(
            ".dashboard", timeout=10000
        )
        mock_workflow.page.click.assert_called_once_with("button#login")
        assert result["status"] == "success"

    async def test_submit_login_button_not_found(self, mock_workflow):
        """Test handling when login button not found."""
        mock_workflow.page.wait_for_selector.side_effect = PlaywrightTimeoutError(
            "Timeout"
        )
        action = SubmitLoginFormAction(mock_workflow)

        with pytest.raises(TransientError):
            await action.run(button_selector="button[type='submit']")

    async def test_submit_login_click_fails(self, mock_workflow):
        """Test handling when click operation fails."""
        mock_workflow.page.click.side_effect = Exception("Click failed")
        action = SubmitLoginFormAction(mock_workflow)

        with pytest.raises(PermanentError):
            await action.run(button_selector="button[type='submit']")

    async def test_submit_login_with_custom_timeout(self, mock_workflow):
        """Test submitting with custom timeout."""
        action = SubmitLoginFormAction(mock_workflow)

        result = await action.run(
            button_selector="button#submit",
            wait_ms=15000,
        )

        mock_workflow.page.wait_for_selector.assert_called_once_with(
            "button#submit", timeout=15000
        )
        assert result["status"] == "success"


@pytest.mark.asyncio
class TestVerifyLoginSuccessAction:
    """Tests for VerifyLoginSuccessAction."""

    async def test_verify_login_by_url(self, mock_workflow):
        """Test verifying login by URL check."""
        mock_workflow.page.url = "https://example.com/dashboard"
        action = VerifyLoginSuccessAction(mock_workflow)

        result = await action.run(
            url_contains="dashboard",
        )

        assert result["status"] == "success"
        assert result["verification_results"]["url_verified"] is True

    async def test_verify_login_by_element(self, mock_workflow):
        """Test verifying login by checking element exists."""
        mock_workflow.page.wait_for_selector = AsyncMock()
        action = VerifyLoginSuccessAction(mock_workflow)

        result = await action.run(
            element_selector=".user-profile",
        )

        mock_workflow.page.wait_for_selector.assert_called_once_with(
            ".user-profile", timeout=10000
        )
        assert result["status"] == "success"
        assert result["verification_results"]["element_verified"] is True

    async def test_verify_login_by_page_title(self, mock_workflow):
        """Test verifying login by page title."""
        mock_workflow.page.title = AsyncMock(return_value="Dashboard - MyApp")
        action = VerifyLoginSuccessAction(mock_workflow)

        result = await action.run(
            page_title_contains="Dashboard",
        )

        assert result["status"] == "success"
        assert result["verification_results"]["title_verified"] is True

    async def test_verify_login_url_mismatch(self, mock_workflow):
        """Test verification fails when URL doesn't match."""
        mock_workflow.page.url = "https://example.com/login"
        action = VerifyLoginSuccessAction(mock_workflow)

        with pytest.raises(PermanentError, match="URL doesn't contain"):
            await action.run(
                url_contains="dashboard",
            )

    async def test_verify_login_element_not_found(self, mock_workflow):
        """Test verification fails when element not found."""
        mock_workflow.page.wait_for_selector.side_effect = PlaywrightTimeoutError(
            "Timeout"
        )
        action = VerifyLoginSuccessAction(mock_workflow)

        with pytest.raises(TransientError, match="Timeout during login verification"):
            await action.run(
                element_selector=".user-profile",
            )

    async def test_verify_login_page_title_mismatch(self, mock_workflow):
        """Test verification fails when page title doesn't match."""
        mock_workflow.page.title = AsyncMock(return_value="Login Error")
        action = VerifyLoginSuccessAction(mock_workflow)

        with pytest.raises(PermanentError, match="Title doesn't contain"):
            await action.run(
                page_title_contains="Dashboard",
            )

    async def test_verify_login_with_custom_timeout(self, mock_workflow):
        """Test verification with custom timeout."""
        mock_workflow.page.url = "https://example.com/dashboard"
        action = VerifyLoginSuccessAction(mock_workflow)

        result = await action.run(
            url_contains="dashboard",
            wait_ms=20000,
        )

        assert result["status"] == "success"


@pytest.mark.asyncio
class TestHandleLoginErrorAction:
    """Tests for HandleLoginErrorAction."""

    async def test_handle_login_error_found_invalid_credentials(self, mock_workflow):
        """Test handling invalid credentials error when error message found."""
        # Mock locator to return text_content async
        mock_locator = MagicMock()
        mock_locator.first = MagicMock()
        mock_locator.first.text_content = AsyncMock(return_value="Invalid username or password")
        mock_workflow.page.locator.return_value = mock_locator
        
        action = HandleLoginErrorAction(mock_workflow)

        with pytest.raises(PermanentError, match="Login failed with invalid credentials"):
            await action.run(
                error_selector=".error-message",
                error_messages={
                    "invalid_credentials": ["invalid", "incorrect"],
                }
            )

    async def test_handle_login_error_found_account_locked(self, mock_workflow):
        """Test handling account locked error."""
        mock_locator = MagicMock()
        mock_locator.first = MagicMock()
        mock_locator.first.text_content = AsyncMock(return_value="Account locked")
        mock_workflow.page.locator.return_value = mock_locator
        
        action = HandleLoginErrorAction(mock_workflow)

        with pytest.raises(PermanentError, match="Account is locked"):
            await action.run(
                error_selector=".error-message",
                error_messages={
                    "account_locked": ["locked", "attempts"],
                }
            )

    async def test_handle_login_error_not_found(self, mock_workflow):
        """Test when no error message found (login may have succeeded)."""
        mock_workflow.page.wait_for_selector.side_effect = PlaywrightTimeoutError("Timeout")
        action = HandleLoginErrorAction(mock_workflow)

        result = await action.run(
            error_selector=".error-message",
        )

        assert result["error_found"] is False
        assert result["status"] == "success"

    async def test_handle_login_error_unknown_type(self, mock_workflow):
        """Test handling unknown error type (transient)."""
        mock_locator = MagicMock()
        mock_locator.first = MagicMock()
        mock_locator.first.text_content = AsyncMock(return_value="Some unknown error")
        mock_workflow.page.locator.return_value = mock_locator
        
        action = HandleLoginErrorAction(mock_workflow)

        result = await action.run(
            error_selector=".error-message",
        )

        assert result["error_found"] is True
        assert result["error_type"] == "unknown"
        assert result["status"] == "error_detected"

    async def test_handle_login_error_with_custom_timeout(self, mock_workflow):
        """Test error handling with custom timeout."""
        mock_workflow.page.wait_for_selector.side_effect = PlaywrightTimeoutError("Timeout")
        action = HandleLoginErrorAction(mock_workflow)

        result = await action.run(
            error_selector=".error-message",
            wait_ms=3000,
        )

        mock_workflow.page.wait_for_selector.assert_called_once_with(
            ".error-message", timeout=3000
        )
        assert result["error_found"] is False


