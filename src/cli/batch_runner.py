"""CLI for executing multiple workflows in parallel with concurrency control."""

import argparse
import json
import logging
import time
from pathlib import Path
from typing import Any, Optional
from dataclasses import asdict, dataclass

from src.framework import Workflow
from src.framework.concurrency_manager import ConcurrencyManager
from src.framework.errors import WorkflowError
from src.workflows.login_workflow import LoginWorkflow, LoginInput
from src.utils.logging import setup_logger


logger = logging.getLogger(__name__)


@dataclass
class BatchExecutionResult:
    """Result from batch execution."""

    total_workflows: int
    succeeded: int
    failed: int
    total_time_seconds: float
    results: list[dict[str, Any]]
    errors: list[dict[str, Any]]

    @property
    def success(self) -> bool:
        """True if all workflows succeeded."""
        return self.failed == 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_workflows": self.total_workflows,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "total_time_seconds": round(self.total_time_seconds, 2),
            "success": self.success,
            "summary": f"{self.succeeded} succeeded, {self.failed} failed",
            "results": self.results,
            "errors": self.errors if self.errors else None,
        }


class BatchRunner:
    """Runner for executing multiple workflows in parallel."""

    def __init__(
        self,
        max_concurrent: int = 5,
        output_format: str = "json"):
        """
        Initialize batch runner.

        Args:
            max_concurrent: Maximum number of concurrent workflows (default 5)
            output_format: Output format ("json" or "text")
        """
        self.max_concurrent = max_concurrent
        self.output_format = output_format
        self.concurrency_manager = ConcurrencyManager(max_concurrent=max_concurrent)

    def _get_workflow(self, workflow_type: str) -> Workflow:
        """Get workflow instance by type."""
        if workflow_type == "login":
            return LoginWorkflow()
        else:
            raise ValueError(f"Unknown workflow type: {workflow_type}")

    async def _run_single_workflow(
        self,
        execution_id: str,
        workflow_type: str,
        input_params: dict[str, Any],
        log_dir: Optional[str] = None) -> dict[str, Any]:
        """Run a single workflow with concurrency control.

        Args:
            execution_id: Unique ID for this execution
            workflow_type: Type of workflow to run
            input_params: Input parameters for the workflow
            log_dir: Directory to write logs to

        Returns:
            Result dictionary with execution details
        """
        try:
            # Acquire execution slot
            await self.concurrency_manager.acquire_execution_slot(execution_id)

            # Setup logging
            if log_dir:
                setup_logger(
                    name=__name__,
                    execution_id=execution_id,
                    log_file=Path(log_dir) / f"{execution_id}.log"
                )

            # Get workflow instance
            workflow = self._get_workflow(workflow_type)

            # Parse workflow-specific input
            if workflow_type == "login":
                input_obj = LoginInput(
                    url=input_params.get("url", "http://localhost:8000"),
                    username=input_params.get("username", ""),
                    password=input_params.get("password", ""))
            else:
                raise ValueError(f"Unknown workflow type: {workflow_type}")

            # Run workflow
            logger.info(f"[{execution_id}] Starting {workflow_type} workflow")
            start_time = time.time()
            result = await workflow.run(input_obj)
            elapsed = time.time() - start_time

            logger.info(f"[{execution_id}] Workflow completed in {elapsed:.2f}s")

            # Convert result to dict if needed
            if hasattr(result, "__dataclass_fields__"):
                result_data = asdict(result)
            else:
                result_data = result if isinstance(result, dict) else {"result": result}

            return {
                "execution_id": execution_id,
                "workflow_type": workflow_type,
                "status": "completed",
                "success": getattr(result, "success", True),
                "elapsed_seconds": round(elapsed, 2),
                "result": result_data,
            }

        except WorkflowError as e:
            logger.error(f"[{execution_id}] Workflow error: {e}")
            return {
                "execution_id": execution_id,
                "workflow_type": workflow_type,
                "status": "failed",
                "success": False,
                "error": str(e),
                "error_type": "WorkflowError",
            }

        except Exception as e:
            logger.error(f"[{execution_id}] Unexpected error: {type(e).__name__}: {e}")
            return {
                "execution_id": execution_id,
                "workflow_type": workflow_type,
                "status": "failed",
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
            }

        finally:
            # Release execution slot
            await self.concurrency_manager.release_execution_slot(execution_id)

    async def run_batch(
        self,
        workflow_specs: list[dict[str, Any]],
        log_dir: Optional[str] = None) -> BatchExecutionResult:
        """Run multiple workflows in parallel with concurrency control.

        Args:
            workflow_specs: List of workflow specifications, each with:
                - workflow_type: str (required)
                - input: Dict (required)
            log_dir: Directory to write logs to

        Returns:
            BatchExecutionResult with aggregated results
        """
        start_time = time.time()
        results = []
        errors = []

        # Create tasks for all workflows
        tasks = []
        for i, spec in enumerate(workflow_specs):
            execution_id = f"exec-{i:03d}"
            workflow_type = spec.get("workflow_type", "login")
            input_params = spec.get("input", {})

            task = self._run_single_workflow(
                execution_id=execution_id,
                workflow_type=workflow_type,
                input_params=input_params,
                log_dir=log_dir)
            tasks.append(task)

        # Run all workflows concurrently
        logger.info(f"Starting batch execution of {len(tasks)} workflows (max {self.max_concurrent} concurrent)")
        execution_results = await asyncio.gather(*tasks, return_exceptions=False)

        # Process results
        succeeded = 0
        failed = 0
        for result in execution_results:
            if result.get("success", False):
                succeeded += 1
                results.append(result)
            else:
                failed += 1
                errors.append(result)

        elapsed = time.time() - start_time

        return BatchExecutionResult(
            total_workflows=len(workflow_specs),
            succeeded=succeeded,
            failed=failed,
            total_time_seconds=elapsed,
            results=results,
            errors=errors)

    def _output_result(self, batch_result: BatchExecutionResult, exit_code: int) -> None:
        """Output result in specified format."""
        if self.output_format == "json":
            output_data = batch_result.to_dict()
            print(json.dumps(output_data, indent=2, default=str))

        elif self.output_format == "text":
            print(f"\n{'='*60}")
            print("Batch Execution Summary")
            print(f"{'='*60}")
            print(f"Total workflows: {batch_result.total_workflows}")
            print(f"Succeeded: {batch_result.succeeded}")
            print(f"Failed: {batch_result.failed}")
            print(f"Total time: {batch_result.total_time_seconds:.2f}s")
            print(f"Success rate: {batch_result.succeeded / batch_result.total_workflows * 100:.1f}%")
            print(f"{'='*60}\n")

            if batch_result.failed > 0:
                print(f"Failed Executions ({batch_result.failed}):")
                for error in batch_result.errors:
                    print(f"  - {error['execution_id']}: {error.get('error', 'Unknown error')}")
                print()

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
        description="Batch workflow executor with parallel execution and concurrency control",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run batch of 10 login workflows with JSON file
  python -m src.cli.batch_runner \\
    --input workflows.json \\
    --max-concurrent 5

  # Run with text output
  python -m src.cli.batch_runner \\
    --input workflows.json \\
    --max-concurrent 5 \\
    --output-format text

  # Run with custom log directory
  python -m src.cli.batch_runner \\
    --input workflows.json \\
    --max-concurrent 5 \\
    --log-dir data/batch_logs

Input JSON format:
  [
    {
      "workflow_type": "login",
      "input": {
        "url": "http://localhost:8000",
        "username": "user1",
        "password": "pass1"
      }
    },
    {
      "workflow_type": "login",
      "input": {
        "url": "http://localhost:8000",
        "username": "user2",
        "password": "pass2"
      }
    }
  ]
        """)

    parser.add_argument(
        "--input",
        "-i",
        required=True,
        type=str,
        help="JSON file with array of workflow specifications")

    parser.add_argument(
        "--max-concurrent",
        "-c",
        type=int,
        default=5,
        help="Maximum concurrent workflows (default: 5)")

    parser.add_argument(
        "--output-format",
        "-f",
        choices=["json", "text"],
        default="json",
        help="Output format (default: json)")

    parser.add_argument(
        "--log-dir",
        "-l",
        default="data/batch_logs",
        help="Directory to write logs to (default: data/batch_logs)")

    args = parser.parse_args()

    try:
        # Read workflow specs from file
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"Error: Input file not found: {args.input}", file=sys.stderr)
            sys.exit(1)

        with open(input_path) as f:
            workflow_specs = json.load(f)

        if not isinstance(workflow_specs, list):
            print("Error: Input JSON must be an array of workflow specifications", file=sys.stderr)
            sys.exit(1)

    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in input file: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: Failed to read input file: {e}", file=sys.stderr)
        sys.exit(1)

    # Create runner and run batch
    runner = BatchRunner(
        max_concurrent=args.max_concurrent,
        output_format=args.output_format)

    # Ensure log directory exists
    if args.log_dir:
        Path(args.log_dir).mkdir(parents=True, exist_ok=True)

    # Setup logging
    setup_logger(
        name=__name__,
        log_file=Path(args.log_dir) / "batch.log"
    )

    logger.info(f"Starting batch execution of {len(workflow_specs)} workflows")

    # Run batch
    batch_result = asyncio.run(
        runner.run_batch(workflow_specs, args.log_dir)
    )

    # Output results and exit
    exit_code = 0 if batch_result.success else 1
    runner._output_result(batch_result, exit_code)


if __name__ == "__main__":
    main()
