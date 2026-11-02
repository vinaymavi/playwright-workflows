"""CLI entry point for executing workflows."""

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Optional
from dataclasses import asdict

from playwright.async_api import async_playwright

from src.framework import Workflow
from src.framework.errors import WorkflowError
from src.framework.execution import Execution
from src.framework.session_manager import SessionManager
from src.workflows.login_workflow import LoginWorkflow, LoginInput
from src.utils.logging import setup_logger


logger = logging.getLogger(__name__)


class WorkflowRunner:
    """Runner for executing workflows via CLI."""

    def __init__(self, workflow_type: str, output_format: str = "json"):
        """
        Initialize workflow runner.

        Args:
            workflow_type: Type of workflow to run (e.g., "login")
            output_format: Output format ("json" or "text")
        """
        self.workflow_type = workflow_type
        self.output_format = output_format
        self.workflow: Workflow | None = None

    def _get_workflow(self) -> Workflow:
        """Get workflow instance by type."""
        if self.workflow_type == "login":
            return LoginWorkflow()
        else:
            raise ValueError(f"Unknown workflow type: {self.workflow_type}")

    async def run(
        self, input_params: dict[str, Any], log_dir: Optional[str] = None
    ) -> int:
        """
        Run the workflow.

        Args:
            input_params: Input parameters for the workflow
            log_dir: Directory to write logs to

        Returns:
            Exit code (0 for success, non-zero for failure)
        """
        # Setup logging
        if log_dir:
            setup_logger(
                name=__name__, log_file=Path(log_dir) / f"{self.workflow_type}.log"
            )

        # Get workflow instance
        self.workflow = self._get_workflow()

        # Parse workflow-specific input
        if self.workflow_type == "login":
            input_obj = LoginInput(
                url=input_params.get("url", "http://localhost:8000"),
                username=input_params.get("username", ""),
                password=input_params.get("password", ""))
        else:
            raise ValueError(f"Unknown workflow type: {self.workflow_type}")

        # Initialize Playwright and execute workflow
        async with async_playwright() as playwright:
            try:
                # Launch browser
                browser = await playwright.chromium.launch(headless=True)
                logger.info("Browser launched")

                # Initialize session manager
                session_manager = SessionManager(self.workflow.execution_id)

                # Create browser context (with session restoration if available)
                context = await session_manager.initialize_context(
                    browser,
                    self.workflow.base_url)
                logger.info("Browser context created")

                # Create page
                page = await context.new_page()
                logger.info("Page created")

                # Set page in workflow
                self.workflow.set_page(page)
                self.workflow.set_browser_context(context)
                self.workflow.set_browser(browser)

                # Initialize execution tracker
                execution = Execution(
                    execution_id=self.workflow.execution_id,
                    base_url=self.workflow.base_url)
                self.workflow.set_execution(execution)

                # Run workflow
                logger.info(f"Starting {self.workflow_type} workflow")
                result = await self.workflow.run(input_obj)

                # Output result
                self._output_result(result, 0)
                return 0

            except WorkflowError as e:
                logger.error(f"Workflow error: {e}")
                if self.workflow and hasattr(self.workflow, "output"):
                    self._output_result(self.workflow.output, 1)
                else:
                    self._output_error(str(e), 1)
                return 1

            except Exception as e:
                logger.error(f"Unexpected error: {type(e).__name__}: {e}")
                self._output_error(str(e), 1)
                return 1

    def _output_result(self, result: Any, exit_code: int) -> None:
        """Output result in specified format."""
        if self.output_format == "json":
            # Convert dataclass to dict if needed
            if hasattr(result, "__dataclass_fields__"):
                output_data = asdict(result)
            else:
                output_data = result

            print(json.dumps(output_data, indent=2, default=str))

        elif self.output_format == "text":
            if hasattr(result, "success"):
                status = "✓ SUCCESS" if result.success else "✗ FAILED"
                print(f"{status}: {result.message}")
                if result.success and hasattr(result, "dashboard_url"):
                    print(f"Dashboard URL: {result.dashboard_url}")
            else:
                print(f"Result: {result}")

        sys.exit(exit_code)

    def _output_error(self, message: str, exit_code: int) -> None:
        """Output error message."""
        if self.output_format == "json":
            error_data = {
                "success": False,
                "message": message,
                "error": True,
            }
            print(json.dumps(error_data, indent=2))
        else:
            print(f"Error: {message}", file=sys.stderr)

        sys.exit(exit_code)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Playwright workflow automation runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run login workflow with JSON parameters
  python -m src.cli.workflow_runner login \\
    --input '{"url":"http://localhost:8000","username":"test","password":"pass"}'

  # Run with text output
  python -m src.cli.workflow_runner login \\
    --input '{"url":"http://localhost:8000","username":"test","password":"pass"}' \\
    --output-format text

  # Run with log file
  python -m src.cli.workflow_runner login \\
    --input '{"url":"http://localhost:8000","username":"test","password":"pass"}' \\
    --log-dir data/logs
        """)

    parser.add_argument(
        "workflow_type",
        help="Type of workflow to run (e.g., 'login')")

    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="JSON input parameters for the workflow")

    parser.add_argument(
        "--output-format",
        "-f",
        choices=["json", "text"],
        default="json",
        help="Output format (default: json)")

    parser.add_argument(
        "--log-dir",
        "-l",
        default="data/logs",
        help="Directory to write logs to (default: data/logs)")

    args = parser.parse_args()

    try:
        # Parse input parameters
        input_params = json.loads(args.input)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON input: {e}", file=sys.stderr)
        sys.exit(1)

    # Create runner and run workflow
    runner = WorkflowRunner(args.workflow_type, args.output_format)

    # Ensure log directory exists
    if args.log_dir:
        Path(args.log_dir).mkdir(parents=True, exist_ok=True)

    # Run workflow
    exit_code = asyncio.run(runner.run(input_params, args.log_dir))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
