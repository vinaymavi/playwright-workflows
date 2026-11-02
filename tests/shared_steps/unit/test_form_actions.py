"""Unit tests for form actions."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from src.shared_steps.form_actions import (
    FillFormAction,
    SelectFromDropdownAction,
    ClickElementAction,
    ValidateFormFieldAction,
    CheckCheckboxAction,
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
    workflow.page.dblclick = AsyncMock()
    workflow.page.select_option = AsyncMock()
    workflow.page.check = AsyncMock()
    workflow.page.uncheck = AsyncMock()
    workflow.page.inner_text = AsyncMock()
    workflow.page.get_attribute = AsyncMock()
    workflow.page.input_value = AsyncMock()
    return workflow


@pytest.mark.asyncio
class TestFillFormAction:
    """Tests for FillFormAction."""

    async def test_fill_single_field(self, mock_workflow):
        """Test filling a single form field."""
        action = FillFormAction(mock_workflow)

        result = await action.run(fields={"input[name='username']": "testuser"})

        mock_workflow.page.wait_for_selector.assert_called_once()
        mock_workflow.page.fill.assert_called_once_with("input[name='username']", "testuser")
        assert result["status"] == "success"
        assert result["total_filled"] == 1

    async def test_fill_multiple_fields(self, mock_workflow):
        """Test filling multiple form fields."""
        fields = {
            "input[name='username']": "user",
            "input[name='password']": "pass",
            "input[name='email']": "test@example.com",
        }

        action = FillFormAction(mock_workflow)
        result = await action.run(fields=fields)

        assert mock_workflow.page.fill.call_count == 3
        assert result["total_filled"] == 3
        assert result["status"] == "success"

    async def test_fill_empty_fields_fails(self, mock_workflow):
        """Test that empty fields dict raises error."""
        action = FillFormAction(mock_workflow)

        with pytest.raises(PermanentError, match="cannot be empty"):
            await action.run(fields={})

    async def test_fill_field_timeout(self, mock_workflow):
        """Test timeout when waiting for field."""
        mock_workflow.page.wait_for_selector.side_effect = PlaywrightTimeoutError("timeout")

        action = FillFormAction(mock_workflow)

        with pytest.raises(TransientError):
            await action.run(fields={"#nonexistent": "value"})

    async def test_fill_field_error(self, mock_workflow):
        """Test error when filling field."""
        mock_workflow.page.wait_for_selector.return_value = None
        mock_workflow.page.fill.side_effect = Exception("Fill failed")

        action = FillFormAction(mock_workflow)

        with pytest.raises(PermanentError):
            await action.run(fields={"input[name='username']": "user"})


@pytest.mark.asyncio
class TestSelectFromDropdownAction:
    """Tests for SelectFromDropdownAction."""

    async def test_select_by_value(self, mock_workflow):
        """Test selecting option by value."""
        action = SelectFromDropdownAction(mock_workflow)

        result = await action.run(
            selector="select[name='country']",
            value="US",
        )

        mock_workflow.page.select_option.assert_called_once_with("select[name='country']", value="US")
        assert result["selected"] == "US"
        assert result["status"] == "success"

    async def test_select_by_label(self, mock_workflow):
        """Test selecting option by label."""
        action = SelectFromDropdownAction(mock_workflow)

        result = await action.run(
            selector="select[name='country']",
            label="United States",
        )

        mock_workflow.page.select_option.assert_called_once_with(
            "select[name='country']", label="United States"
        )
        assert result["selected"] == "United States"

    async def test_select_by_index(self, mock_workflow):
        """Test selecting option by index."""
        action = SelectFromDropdownAction(mock_workflow)

        result = await action.run(
            selector="select[name='country']",
            index=2,
        )

        mock_workflow.page.select_option.assert_called_once_with(
            "select[name='country']", index=2
        )
        assert result["selected"] == "2"

    async def test_select_no_method_fails(self, mock_workflow):
        """Test that providing no selection method fails."""
        action = SelectFromDropdownAction(mock_workflow)

        with pytest.raises(PermanentError, match="Exactly one"):
            await action.run(selector="select[name='country']")

    async def test_select_multiple_methods_fails(self, mock_workflow):
        """Test that providing multiple selection methods fails."""
        action = SelectFromDropdownAction(mock_workflow)

        with pytest.raises(PermanentError, match="Exactly one"):
            await action.run(
                selector="select[name='country']",
                value="US",
                label="United States",
            )

    async def test_select_timeout(self, mock_workflow):
        """Test timeout when waiting for dropdown."""
        mock_workflow.page.wait_for_selector.side_effect = PlaywrightTimeoutError("timeout")

        action = SelectFromDropdownAction(mock_workflow)

        with pytest.raises(TransientError):
            await action.run(
                selector="select[name='nonexistent']",
                value="US",
            )


@pytest.mark.asyncio
class TestClickElementAction:
    """Tests for ClickElementAction."""

    async def test_single_click(self, mock_workflow):
        """Test single clicking an element."""
        action = ClickElementAction(mock_workflow)

        result = await action.run(selector="button[type='submit']")

        mock_workflow.page.click.assert_called_once_with("button[type='submit']")
        assert result["status"] == "success"

    async def test_double_click(self, mock_workflow):
        """Test double clicking an element."""
        action = ClickElementAction(mock_workflow)

        result = await action.run(selector="button", double_click=True)

        mock_workflow.page.dblclick.assert_called_once_with("button")
        assert result["double_click"] is True

    async def test_click_with_navigation(self, mock_workflow):
        """Test clicking and waiting for navigation."""
        # Create mock context manager for expect_navigation
        nav_context = MagicMock()
        nav_context.__aenter__ = AsyncMock(return_value=None)
        nav_context.__aexit__ = AsyncMock(return_value=None)
        mock_workflow.page.expect_navigation.return_value = nav_context

        action = ClickElementAction(mock_workflow)

        result = await action.run(
            selector="a.link",
            wait_for_navigation=True,
        )

        mock_workflow.page.expect_navigation.assert_called_once()
        assert result["status"] == "success"

    async def test_click_timeout(self, mock_workflow):
        """Test timeout when waiting for element."""
        mock_workflow.page.wait_for_selector.side_effect = PlaywrightTimeoutError("timeout")

        action = ClickElementAction(mock_workflow)

        with pytest.raises(TransientError):
            await action.run(selector="button[disabled]")


@pytest.mark.asyncio
class TestValidateFormFieldAction:
    """Tests for ValidateFormFieldAction."""

    async def test_validate_field_exists(self, mock_workflow):
        """Test validating that field exists."""
        action = ValidateFormFieldAction(mock_workflow)

        result = await action.run(fields={"input[name='email']": None})

        mock_workflow.page.wait_for_selector.assert_called_once()
        assert result["status"] == "success"

    async def test_validate_field_value(self, mock_workflow):
        """Test validating field has expected value."""
        mock_workflow.page.input_value.return_value = "expected_value"

        action = ValidateFormFieldAction(mock_workflow)

        result = await action.run(fields={"input[name='email']": "expected_value"})

        mock_workflow.page.input_value.assert_called_once()
        assert result["status"] == "success"

    async def test_validate_field_wrong_value(self, mock_workflow):
        """Test validation fails with wrong value."""
        mock_workflow.page.input_value.return_value = "wrong_value"

        action = ValidateFormFieldAction(mock_workflow)

        with pytest.raises(PermanentError):
            await action.run(fields={"input[name='email']": "expected_value"})

    async def test_validate_multiple_fields(self, mock_workflow):
        """Test validating multiple fields."""
        mock_workflow.page.input_value.side_effect = ["user", "test@example.com"]

        action = ValidateFormFieldAction(mock_workflow)

        result = await action.run(
            fields={
                "input[name='username']": "user",
                "input[name='email']": "test@example.com",
            }
        )

        assert result["total_validated"] == 2
        assert result["status"] == "success"

    async def test_validate_field_timeout(self, mock_workflow):
        """Test timeout when validating field."""
        mock_workflow.page.wait_for_selector.side_effect = PlaywrightTimeoutError("timeout")

        action = ValidateFormFieldAction(mock_workflow)

        with pytest.raises(TransientError):
            await action.run(fields={"#nonexistent": None})


@pytest.mark.asyncio
class TestCheckCheckboxAction:
    """Tests for CheckCheckboxAction."""

    async def test_check_checkbox(self, mock_workflow):
        """Test checking a checkbox."""
        action = CheckCheckboxAction(mock_workflow)

        result = await action.run(
            selector="input[type='checkbox'][name='terms']",
            checked=True,
        )

        mock_workflow.page.check.assert_called_once()
        assert result["checked"] is True
        assert result["status"] == "success"

    async def test_uncheck_checkbox(self, mock_workflow):
        """Test unchecking a checkbox."""
        action = CheckCheckboxAction(mock_workflow)

        result = await action.run(
            selector="input[type='checkbox'][name='terms']",
            checked=False,
        )

        mock_workflow.page.uncheck.assert_called_once()
        assert result["checked"] is False

    async def test_checkbox_timeout(self, mock_workflow):
        """Test timeout when waiting for checkbox."""
        mock_workflow.page.wait_for_selector.side_effect = PlaywrightTimeoutError("timeout")

        action = CheckCheckboxAction(mock_workflow)

        with pytest.raises(TransientError):
            await action.run(
                selector="input[type='checkbox'][name='nonexistent']",
                checked=True,
            )


@pytest.mark.asyncio
class TestFormActionsIntegration:
    """Integration tests for form actions."""

    async def test_fill_and_validate(self, mock_workflow):
        """Test filling and validating fields."""
        mock_workflow.page.input_value.return_value = "test_user"

        fill_action = FillFormAction(mock_workflow, name="fill")
        await fill_action.run(fields={"input[name='username']": "test_user"})

        validate_action = ValidateFormFieldAction(mock_workflow, name="validate")
        result = await validate_action.run(fields={"input[name='username']": "test_user"})

        assert result["status"] == "success"

    async def test_action_dependencies(self, mock_workflow):
        """Test action dependency tracking."""
        action = FillFormAction(
            mock_workflow,
            name="fill_form",
            requires=["enter_credentials"],
        )

        assert action.has_dependency("enter_credentials")
        assert not action.has_dependency("other_action")
        assert action.get_dependencies() == ["enter_credentials"]
