"""Reusable Form Interaction Actions

Provides common actions for form filling, validation, and submission.
These actions can be used across multiple workflows without modification.
"""

from typing import Any, Dict, List, Optional

from playwright.async_api import Page, TimeoutError

from ..framework.action import Action
from ..framework.errors import PermanentError, TransientError
from ..utils.logging import setup_logger

logger = setup_logger(__name__)


class FillFormAction(Action):
    """Fill form fields with provided data.

    Fills multiple form fields by selector and value pairs.
    Supports text inputs, textareas, selects, checkboxes, and radio buttons.

    Example:
        action = FillFormAction(workflow, name="fill_login_form")
        result = await action.run(fields={
            "input[name='username']": "user@example.com",
            "input[name='password']": "secret",
        })
    """

    async def execute(self, fields: Dict[str, str], wait_ms: int = 5000) -> Dict[str, Any]:
        """Fill form fields.

        Args:
            fields: Dictionary of {selector: value} pairs
            wait_ms: Wait time for elements in milliseconds

        Returns:
            Dictionary with keys filled and errors (if any)

        Raises:
            PermanentError: If selector doesn't exist
            TransientError: If field fill times out
        """
        if not fields:
            raise ValueError("fields parameter cannot be empty")

        page: Page = self.workflow_context.page
        filled = []
        errors = {}

        logger.debug(f"Filling {len(fields)} form fields")

        for selector, value in fields.items():
            try:
                # Wait for element and fill it
                await page.wait_for_selector(selector, timeout=wait_ms)
                await page.fill(selector, value)
                filled.append(selector)
                logger.debug(f"Filled field: {selector}")

            except TimeoutError as e:
                error_msg = f"Timeout waiting for selector '{selector}'"
                errors[selector] = error_msg
                logger.warning(error_msg)
                raise TransientError(self.name, error_msg, cause=e)

            except Exception as e:
                error_msg = f"Failed to fill field '{selector}': {str(e)}"
                errors[selector] = error_msg
                logger.warning(error_msg)
                raise PermanentError(self.name, error_msg, cause=e)

        return {
            "fields_filled": filled,
            "total_filled": len(filled),
            "errors": errors,
            "status": "success" if not errors else "partial",
        }


class SelectFromDropdownAction(Action):
    """Select an option from a dropdown/select element.

    Supports selecting by value, label, or index.

    Example:
        action = SelectFromDropdownAction(workflow, name="select_country")
        result = await action.run(
            selector="select[name='country']",
            label="United States"
        )
    """

    async def execute(
        self,
        selector: str,
        value: Optional[str] = None,
        label: Optional[str] = None,
        index: Optional[int] = None,
        wait_ms: int = 5000,
    ) -> Dict[str, Any]:
        """Select an option from a dropdown.

        Args:
            selector: CSS selector of the select element
            value: Value attribute to select (mutually exclusive with label/index)
            label: Label text to select (mutually exclusive with value/index)
            index: Index of option to select (mutually exclusive with value/label)
            wait_ms: Wait time in milliseconds

        Returns:
            Dictionary with selected_value and status

        Raises:
            ValueError: If none or multiple selection methods provided
            TransientError: If element not found or operation times out
            PermanentError: If selection fails
        """
        page: Page = self.workflow_context.page

        # Validate that exactly one selection method is provided
        selection_methods = sum([value is not None, label is not None, index is not None])
        if selection_methods != 1:
            raise ValueError(
                "Exactly one of value, label, or index must be provided"
            )

        try:
            await page.wait_for_selector(selector, timeout=wait_ms)

            if value is not None:
                await page.select_option(selector, value=value)
                selected = value
            elif label is not None:
                await page.select_option(selector, label=label)
                selected = label
            else:  # index is not None
                await page.select_option(selector, index=index)
                selected = str(index)

            logger.debug(f"Selected option '{selected}' from {selector}")

            return {
                "selector": selector,
                "selected": selected,
                "status": "success",
            }

        except TimeoutError as e:
            error_msg = f"Timeout waiting for selector '{selector}'"
            logger.warning(error_msg)
            raise TransientError(self.name, error_msg, cause=e)

        except Exception as e:
            error_msg = f"Failed to select option from '{selector}': {str(e)}"
            logger.warning(error_msg)
            raise PermanentError(self.name, error_msg, cause=e)


class ClickElementAction(Action):
    """Click an element on the page.

    Supports clicking by selector, waiting for navigation, and double-clicking.

    Example:
        action = ClickElementAction(workflow, name="submit_form")
        result = await action.run(selector="button[type='submit']")
    """

    async def execute(
        self,
        selector: str,
        double_click: bool = False,
        wait_for_navigation: bool = False,
        wait_ms: int = 5000,
    ) -> Dict[str, Any]:
        """Click an element.

        Args:
            selector: CSS selector of element to click
            double_click: If True, double-click instead of single click
            wait_for_navigation: If True, wait for navigation after click
            wait_ms: Wait time in milliseconds

        Returns:
            Dictionary with clicked_selector and status

        Raises:
            TransientError: If element not found or operation times out
            PermanentError: If click fails
        """
        page: Page = self.workflow_context.page

        try:
            await page.wait_for_selector(selector, timeout=wait_ms)

            if double_click:
                await page.dblclick(selector)
                logger.debug(f"Double-clicked element: {selector}")
            else:
                if wait_for_navigation:
                    async with page.expect_navigation():
                        await page.click(selector)
                    logger.debug(f"Clicked and navigated: {selector}")
                else:
                    await page.click(selector)
                    logger.debug(f"Clicked element: {selector}")

            return {
                "selector": selector,
                "double_click": double_click,
                "status": "success",
            }

        except TimeoutError as e:
            error_msg = f"Timeout waiting for selector '{selector}'"
            logger.warning(error_msg)
            raise TransientError(self.name, error_msg, cause=e)

        except Exception as e:
            error_msg = f"Failed to click element '{selector}': {str(e)}"
            logger.warning(error_msg)
            raise PermanentError(self.name, error_msg, cause=e)


class ValidateFormFieldAction(Action):
    """Validate that form fields exist and have expected values.

    Checks that elements exist and optionally match expected values.

    Example:
        action = ValidateFormFieldAction(workflow, name="validate_fields")
        result = await action.run(fields={"input[name='email']": ""})
    """

    async def execute(
        self,
        fields: Dict[str, Optional[str]],
        wait_ms: int = 5000,
    ) -> Dict[str, Any]:
        """Validate form fields.

        Args:
            fields: Dictionary of {selector: expected_value} pairs
                   None value means field should exist but any value is OK
            wait_ms: Wait time in milliseconds

        Returns:
            Dictionary with validation results

        Raises:
            TransientError: If element not found
            PermanentError: If validation fails
        """
        page: Page = self.workflow_context.page
        validated = []
        errors = {}

        logger.debug(f"Validating {len(fields)} form fields")

        for selector, expected_value in fields.items():
            try:
                await page.wait_for_selector(selector, timeout=wait_ms)

                if expected_value is not None:
                    # Get actual value and compare
                    actual_value = await page.input_value(selector)
                    if actual_value != expected_value:
                        error_msg = (
                            f"Field '{selector}' has value '{actual_value}', "
                            f"expected '{expected_value}'"
                        )
                        errors[selector] = error_msg
                        logger.warning(error_msg)
                        raise PermanentError(self.name, error_msg)

                validated.append(selector)
                logger.debug(f"Validated field: {selector}")

            except TimeoutError as e:
                error_msg = f"Timeout waiting for selector '{selector}'"
                errors[selector] = error_msg
                logger.warning(error_msg)
                raise TransientError(self.name, error_msg, cause=e)

        return {
            "fields_validated": validated,
            "total_validated": len(validated),
            "errors": errors,
            "status": "success",
        }


class CheckCheckboxAction(Action):
    """Check or uncheck checkboxes.

    Example:
        action = CheckCheckboxAction(workflow, name="agree_terms")
        result = await action.run(
            selector="input[type='checkbox'][name='terms']",
            checked=True
        )
    """

    async def execute(
        self,
        selector: str,
        checked: bool = True,
        wait_ms: int = 5000,
    ) -> Dict[str, Any]:
        """Check or uncheck a checkbox.

        Args:
            selector: CSS selector of checkbox
            checked: True to check, False to uncheck
            wait_ms: Wait time in milliseconds

        Returns:
            Dictionary with selector and checked status

        Raises:
            TransientError: If checkbox not found
            PermanentError: If check/uncheck fails
        """
        page: Page = self.workflow_context.page

        try:
            await page.wait_for_selector(selector, timeout=wait_ms)

            if checked:
                await page.check(selector)
                logger.debug(f"Checked checkbox: {selector}")
            else:
                await page.uncheck(selector)
                logger.debug(f"Unchecked checkbox: {selector}")

            return {
                "selector": selector,
                "checked": checked,
                "status": "success",
            }

        except TimeoutError as e:
            error_msg = f"Timeout waiting for selector '{selector}'"
            logger.warning(error_msg)
            raise TransientError(self.name, error_msg, cause=e)

        except Exception as e:
            error_msg = (
                f"Failed to {'check' if checked else 'uncheck'} "
                f"checkbox '{selector}': {str(e)}"
            )
            logger.warning(error_msg)
            raise PermanentError(self.name, error_msg, cause=e)
