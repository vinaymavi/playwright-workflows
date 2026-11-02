"""Concurrency Management for Parallel Workflow Execution

Manages concurrent workflow instances with resource quotas, semaphore-based
concurrency limiting, and task group orchestration.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from ..utils.logging import setup_logger

logger = setup_logger(__name__)


class QuotaType(Enum):
    """Types of resource quotas per execution."""

    MAX_BROWSER_PAGES = "max_browser_pages"
    MAX_AGENT_CONCURRENCY = "agent_concurrency"
    MAX_MEMORY_MB = "max_memory_mb"
    MAX_TIMEOUT_SECONDS = "max_timeout_seconds"


@dataclass
class ResourceQuota:
    """Resource quota configuration for a single execution."""

    max_browser_pages: int = 10  # Max pages per execution
    max_agent_concurrency: int = 2  # Max concurrent agent calls per execution
    max_memory_mb: int = 512  # Max memory per execution in MB
    max_timeout_seconds: int = 3600  # Max execution timeout (1 hour)

    def to_dict(self) -> dict[str, int]:
        """Convert quota to dictionary."""
        return {
            QuotaType.MAX_BROWSER_PAGES.value: self.max_browser_pages,
            QuotaType.MAX_AGENT_CONCURRENCY.value: self.max_agent_concurrency,
            QuotaType.MAX_MEMORY_MB.value: self.max_memory_mb,
            QuotaType.MAX_TIMEOUT_SECONDS.value: self.max_timeout_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict[str, int]) -> "ResourceQuota":
        """Create quota from dictionary."""
        return cls(
            max_browser_pages=data.get(QuotaType.MAX_BROWSER_PAGES.value, 10),
            max_agent_concurrency=data.get(QuotaType.MAX_AGENT_CONCURRENCY.value, 2),
            max_memory_mb=data.get(QuotaType.MAX_MEMORY_MB.value, 512),
            max_timeout_seconds=data.get(QuotaType.MAX_TIMEOUT_SECONDS.value, 3600))


@dataclass
class ExecutionMetrics:
    """Resource usage metrics for a single execution."""

    execution_id: str
    current_browser_pages: int = 0
    current_agent_tasks: int = 0
    current_memory_mb: int = 0
    start_time: float = 0.0
    peak_memory_mb: int = 0

    @property
    def elapsed_seconds(self) -> float:
        """Time elapsed since execution start."""
        if self.start_time == 0:
            return 0.0
        return asyncio.get_event_loop().time() - self.start_time


class ConcurrencyManager:
    """Manages concurrent workflow execution with quotas and task orchestration."""

    def __init__(
        self,
        max_concurrent: int = 5,
        default_quota: Optional[ResourceQuota] = None):
        """Initialize concurrency manager.

        Args:
            max_concurrent: Maximum concurrent executions (default 5)
            default_quota: Default resource quota for all executions
        """
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.default_quota = default_quota or ResourceQuota()

        # Track active executions and their quotas
        self._active_executions: dict[str, dict[str, Any]] = {}
        self._execution_metrics: dict[str, ExecutionMetrics] = {}
        self._execution_quotas: dict[str, ResourceQuota] = {}  # Track quotas set before acquisition
        self._execution_lock = asyncio.Lock()

        logger.info(
            f"ConcurrencyManager initialized with max_concurrent={max_concurrent}",
            extra={"default_quota": self.default_quota.to_dict()})

    async def acquire_execution_slot(self, execution_id: str) -> None:
        """Acquire a concurrency slot for an execution.

        Args:
            execution_id: Unique execution ID

        Raises:
            RuntimeError: If execution already has a slot or is at quota limit
        """
        # Check if already exists (must be under lock)
        async with self._execution_lock:
            if execution_id in self._active_executions:
                raise RuntimeError(f"Execution {execution_id} already has a slot")

        # Acquire semaphore slot OUTSIDE the lock (it can block without holding the lock)
        await self.semaphore.acquire()

        # Now register under lock
        async with self._execution_lock:
            self._active_executions[execution_id] = {
                "slot_acquired_at": asyncio.get_event_loop().time(),
            }
            self._execution_metrics[execution_id] = ExecutionMetrics(
                execution_id=execution_id,
                start_time=asyncio.get_event_loop().time())

            logger.info(
                f"Execution slot acquired for: {execution_id}",
                extra={"total_active": len(self._active_executions)})

    async def release_execution_slot(self, execution_id: str) -> None:
        """Release concurrency slot for an execution.

        Args:
            execution_id: Unique execution ID
        """
        async with self._execution_lock:
            if execution_id not in self._active_executions:
                logger.warning(f"Attempt to release unknown execution: {execution_id}")
                return

            del self._active_executions[execution_id]
            self.semaphore.release()

            logger.info(
                f"Execution slot released for: {execution_id}",
                extra={"total_active": len(self._active_executions)})

    async def register_browser_page(
        self, execution_id: str, page_id: str
    ) -> None:
        """Register a new browser page for an execution.

        Args:
            execution_id: Unique execution ID
            page_id: Unique page ID

        Raises:
            RuntimeError: If execution exceeds max_browser_pages quota
        """
        async with self._execution_lock:
            if execution_id not in self._execution_metrics:
                raise RuntimeError(f"Unknown execution: {execution_id}")

            metrics = self._execution_metrics[execution_id]
            quota = self._get_execution_quota(execution_id)

            if metrics.current_browser_pages >= quota.max_browser_pages:
                raise RuntimeError(
                    f"Execution {execution_id} exceeded max_browser_pages "
                    f"({metrics.current_browser_pages} >= {quota.max_browser_pages})"
                )

            metrics.current_browser_pages += 1

            logger.debug(
                f"Browser page registered for execution: {execution_id}",
                extra={
                    "page_id": page_id,
                    "current_pages": metrics.current_browser_pages,
                    "max_pages": quota.max_browser_pages,
                })

    async def unregister_browser_page(
        self, execution_id: str, page_id: str
    ) -> None:
        """Unregister a browser page for an execution.

        Args:
            execution_id: Unique execution ID
            page_id: Unique page ID
        """
        async with self._execution_lock:
            if execution_id in self._execution_metrics:
                metrics = self._execution_metrics[execution_id]
                if metrics.current_browser_pages > 0:
                    metrics.current_browser_pages -= 1

                logger.debug(
                    f"Browser page unregistered for execution: {execution_id}",
                    extra={
                        "page_id": page_id,
                        "current_pages": metrics.current_browser_pages,
                    })

    async def acquire_agent_slot(self, execution_id: str) -> None:
        """Acquire a slot for an agent call.

        Args:
            execution_id: Unique execution ID

        Raises:
            RuntimeError: If execution exceeds max_agent_concurrency quota
        """
        async with self._execution_lock:
            if execution_id not in self._execution_metrics:
                raise RuntimeError(f"Unknown execution: {execution_id}")

            metrics = self._execution_metrics[execution_id]
            quota = self._get_execution_quota(execution_id)

            if metrics.current_agent_tasks >= quota.max_agent_concurrency:
                raise RuntimeError(
                    f"Execution {execution_id} exceeded max_agent_concurrency "
                    f"({metrics.current_agent_tasks} >= {quota.max_agent_concurrency})"
                )

            metrics.current_agent_tasks += 1

            logger.debug(
                f"Agent slot acquired for execution: {execution_id}",
                extra={
                    "current_tasks": metrics.current_agent_tasks,
                    "max_tasks": quota.max_agent_concurrency,
                })

    async def release_agent_slot(self, execution_id: str) -> None:
        """Release an agent slot.

        Args:
            execution_id: Unique execution ID
        """
        async with self._execution_lock:
            if execution_id in self._execution_metrics:
                metrics = self._execution_metrics[execution_id]
                if metrics.current_agent_tasks > 0:
                    metrics.current_agent_tasks -= 1

                logger.debug(
                    f"Agent slot released for execution: {execution_id}",
                    extra={"current_tasks": metrics.current_agent_tasks})

    async def set_execution_quota(
        self, execution_id: str, quota: ResourceQuota
    ) -> None:
        """Set custom resource quota for an execution.

        Args:
            execution_id: Unique execution ID
            quota: Resource quota configuration
        """
        async with self._execution_lock:
            # Store quota in both places: pre-acquisition tracker and active executions if it's already running
            self._execution_quotas[execution_id] = quota
            if execution_id in self._active_executions:
                self._active_executions[execution_id]["quota"] = quota

        logger.debug(
            f"Execution quota set for: {execution_id}",
            extra={"quota": quota.to_dict()})

    def _get_execution_quota(self, execution_id: str) -> ResourceQuota:
        """Get resource quota for an execution.

        Args:
            execution_id: Unique execution ID

        Returns:
            ResourceQuota for the execution, or default if not customized
        """
        # Check pre-acquisition quotas first
        if execution_id in self._execution_quotas:
            return self._execution_quotas[execution_id]

        # Then check active execution quotas
        if execution_id in self._active_executions:
            quota = self._active_executions[execution_id].get("quota")
            if quota:
                return quota

        return self.default_quota

    async def get_execution_metrics(self, execution_id: str) -> Optional[ExecutionMetrics]:
        """Get resource usage metrics for an execution.

        Args:
            execution_id: Unique execution ID

        Returns:
            ExecutionMetrics if execution is active, None otherwise
        """
        async with self._execution_lock:
            return self._execution_metrics.get(execution_id)

    async def get_all_metrics(self) -> dict[str, ExecutionMetrics]:
        """Get metrics for all active executions.

        Returns:
            Dictionary of execution_id -> ExecutionMetrics
        """
        async with self._execution_lock:
            return dict(self._execution_metrics)

    async def enforce_timeout(self, execution_id: str) -> bool:
        """Check if execution has exceeded timeout.

        Args:
            execution_id: Unique execution ID

        Returns:
            True if timeout exceeded, False otherwise
        """
        metrics = await self.get_execution_metrics(execution_id)
        if not metrics:
            return False

        quota = self._get_execution_quota(execution_id)
        if metrics.elapsed_seconds > quota.max_timeout_seconds:
            logger.warning(
                f"Execution {execution_id} exceeded max_timeout",
                extra={
                    "elapsed": metrics.elapsed_seconds,
                    "max_timeout": quota.max_timeout_seconds,
                })
            return True

        return False

    async def get_active_execution_count(self) -> int:
        """Get count of active executions.

        Returns:
            Number of active executions
        """
        async with self._execution_lock:
            return len(self._active_executions)

    async def get_available_slots(self) -> int:
        """Get count of available concurrency slots.

        Returns:
            Number of available slots
        """
        return self.max_concurrent - await self.get_active_execution_count()
