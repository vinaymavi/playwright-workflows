"""CLI command to resume paused or failed workflows.

Supports both quick (<5 min) and slow (>5 min) resumption strategies.
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional

import click

from ..api.workflow_controller import WorkflowController
from ..framework.resumption_manager import ResumptionManager, ResumptionStrategy
from ..utils.logging import setup_logger

logger = setup_logger(__name__)


class ResumeWorkflowCommand:
    """CLI command for resuming workflows."""
    
    def __init__(
        self,
        execution_id: str,
        resumption_manager: Optional[ResumptionManager] = None,
        controller: Optional[WorkflowController] = None,
    ):
        """Initialize resume command.
        
        Args:
            execution_id: Execution ID to resume
            resumption_manager: ResumptionManager instance (optional)
            controller: WorkflowController instance (optional)
        """
        self.execution_id = execution_id
        self.resumption_manager = resumption_manager or ResumptionManager()
        self.controller = controller or WorkflowController()
    
    def get_resumption_info(self) -> Optional[dict]:
        """Get resumption information for the execution.
        
        Returns:
            Resumption info dict or None if not found
        """
        return self.resumption_manager.get_resumption_info(self.execution_id)
    
    async def execute(self) -> tuple[bool, Optional[str]]:
        """Execute the resumption workflow.
        
        Returns:
            Tuple of (success, message)
        """
        logger.info(f"Starting resume workflow for execution: {self.execution_id}")
        
        # Load execution state
        state = self.resumption_manager.load_execution_state(self.execution_id)
        if not state:
            return False, f"Execution not found: {self.execution_id}"
        
        # Determine resume strategy
        strategy = ResumptionStrategy.determine_strategy(state)
        logger.info(f"Resume strategy: {strategy}")
        
        # Prepare for resumption
        if strategy == "quick":
            success, message = self.resumption_manager.prepare_for_quick_resume(
                self.execution_id
            )
        else:
            success, message = self.resumption_manager.prepare_for_slow_resume(
                self.execution_id
            )
        
        if not success:
            return False, f"Failed to prepare resumption: {message}"
        
        logger.info(f"Resumption prepared: {message}")
        
        # Record recovery event
        self.resumption_manager.record_recovery_event(
            self.execution_id,
            "session_recovered",
            {
                "strategy": strategy,
                "execution_id": self.execution_id,
            }
        )
        
        # Mark resumption complete
        self.resumption_manager.mark_resumption_complete(self.execution_id)
        
        logger.info(f"Resumption workflow complete for execution: {self.execution_id}")
        return True, f"Resumption initiated with {strategy} strategy"


@click.command()
@click.argument("execution_id", required=True)
@click.option(
    "--execution-dir",
    type=click.Path(exists=False),
    default=None,
    help="Directory for execution state storage (defaults to data/executions/)",
)
@click.option(
    "--verbose",
    is_flag=True,
    default=False,
    help="Enable verbose logging",
)
def resume_workflow(execution_id: str, execution_dir: Optional[str], verbose: bool):
    """Resume a paused or failed workflow execution.
    
    EXECUTION_ID: The ID of the execution to resume
    
    Examples:
    
        Resume a workflow with automatic strategy selection:
        
            python -m src.cli.resume_workflow exec-123
        
        Resume with custom execution directory:
        
            python -m src.cli.resume_workflow exec-123 --execution-dir /path/to/executions
    """
    if verbose:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # Initialize resumption manager
        exec_dir = Path(execution_dir) if execution_dir else None
        resumption_manager = ResumptionManager(execution_dir=exec_dir)
        
        # Get resumption info
        info = resumption_manager.get_resumption_info(execution_id)
        if not info:
            click.secho(f"✗ Execution not found: {execution_id}", fg="red")
            sys.exit(1)
        
        # Display resumption info
        click.echo("\n" + "=" * 60)
        click.echo("RESUMPTION INFO")
        click.echo("=" * 60)
        click.echo(f"Execution ID:    {info['execution_id']}")
        click.echo(f"Status:          {info['status']}")
        click.echo(f"Workflow Type:   {info['workflow_type']}")
        click.echo(f"Strategy:        {info['strategy'].upper()}")
        click.echo(f"Session Age:     {info['session_age_seconds']:.0f}s")
        click.echo(f"Progress:        {info['completed_steps']}/{info['total_steps']} steps")
        
        if info['last_checkpoint']:
            click.echo(f"Last Checkpoint: {info['last_checkpoint'].get('id', 'N/A')}")
        
        click.echo("=" * 60 + "\n")
        
        # Show strategy details
        if info['strategy'] == 'quick':
            click.secho(
                "ℹ  QUICK RESUME (< 5 min)",
                fg="blue",
                bold=True
            )
            click.echo("Strategy: Keep browser context alive, continue from checkpoint")
        else:
            click.secho(
                "ℹ  SLOW RESUME (> 5 min)",
                fg="yellow",
                bold=True
            )
            click.echo("Strategy: Replay steps, detect auth failures, re-auth if needed")
        
        click.echo()
        
        # Confirm before proceeding
        if not click.confirm("Proceed with resumption?", default=True):
            click.secho("✗ Resumption cancelled", fg="red")
            sys.exit(0)
        
        # Execute resumption
        click.echo("\nInitiating resumption workflow...")
        click.echo()
        
        command = ResumeWorkflowCommand(execution_id, resumption_manager)
        success, message = asyncio.run(command.execute())
        
        if success:
            click.secho(f"✓ {message}", fg="green", bold=True)
            click.echo()
            click.echo("Next steps:")
            click.echo("1. The execution will be marked as resuming")
            click.echo("2. Execution engine will continue from the checkpoint")
            click.echo("3. Monitor execution with: get-execution-status <execution_id>")
            sys.exit(0)
        else:
            click.secho(f"✗ {message}", fg="red")
            sys.exit(1)
    
    except Exception as e:
        click.secho(f"✗ Error: {e}", fg="red")
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    resume_workflow()
