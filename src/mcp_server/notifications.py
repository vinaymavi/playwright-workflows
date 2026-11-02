"""MCP Notifications Service

Sends notifications to MCP client when workflow events occur:
- checkpoint_requested: Workflow needs agent decision
- execution_completed: Workflow finished successfully
- execution_failed: Workflow failed with error
"""

import asyncio
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class NotificationService:
    """Manages MCP notifications to client.

    In a real implementation, this would be connected to the MCP server's
    notification system. For now, it queues notifications for the server
    to send to connected clients.
    """

    # Class variable to store notification queue (shared across instances)
    _notification_queue: asyncio.Queue = None
    _server_instance = None

    @classmethod
    def set_server(cls, server: Any) -> None:
        """Set the MCP server instance for sending notifications."""
        cls._server_instance = server

    @classmethod
    async def _get_queue(cls) -> asyncio.Queue:
        """Get or create the notification queue."""
        if cls._notification_queue is None:
            cls._notification_queue = asyncio.Queue()
        return cls._notification_queue

    async def send_notification(
        self, notification_type: str, payload: dict[str, Any]
    ) -> None:
        """Send a notification to the MCP client.

        Args:
            notification_type: Type of notification (checkpoint_requested, execution_completed, execution_failed)
            payload: Notification payload (JSON-serializable dict)
        """
        try:
            notification = {
                "type": notification_type,
                "timestamp": datetime.utcnow().isoformat(),
                "payload": payload,
            }

            logger.debug(
                f"Sending {notification_type} notification",
                extra={"event": notification_type, "context": payload})

            # If server is set, send directly
            if self._server_instance:
                # The server would have a method to send notifications
                # This is framework-specific to MCP implementation
                if hasattr(self._server_instance, "send_notification"):
                    await self._server_instance.send_notification(
                        notification_type, notification
                    )
            else:
                # Queue for later dispatch
                queue = await self._get_queue()
                await queue.put(notification)

        except Exception as e:
            logger.error(f"Error sending notification: {e}", exc_info=True)

    @classmethod
    async def checkpoint_requested(
        cls, execution_id: str, checkpoint_id: str, question: dict[str, Any]
    ) -> None:
        """Send checkpoint_requested notification.

        Args:
            execution_id: Execution identifier
            checkpoint_id: Checkpoint identifier
            question: Question/decision needed from agent
        """
        service = cls()
        await service.send_notification(
            "checkpoint_requested",
            {
                "execution_id": execution_id,
                "checkpoint_id": checkpoint_id,
                "question": question,
            })

    @classmethod
    async def execution_completed(cls, execution_id: str, result: dict[str, Any]) -> None:
        """Send execution_completed notification.

        Args:
            execution_id: Execution identifier
            result: Workflow execution result
        """
        service = cls()
        await service.send_notification(
            "execution_completed",
            {"execution_id": execution_id, "result": result})

    @classmethod
    async def execution_failed(cls, execution_id: str, error: str) -> None:
        """Send execution_failed notification.

        Args:
            execution_id: Execution identifier
            error: Error message
        """
        service = cls()
        await service.send_notification(
            "execution_failed", {"execution_id": execution_id, "error": error}
        )

    @classmethod
    async def get_pending_notifications(cls) -> list[dict[str, Any]]:
        """Get all pending notifications from the queue.

        Returns:
            List of pending notifications
        """
        queue = await cls._get_queue()
        notifications = []

        while not queue.empty():
            try:
                notification = queue.get_nowait()
                notifications.append(notification)
            except asyncio.QueueEmpty:
                break

        return notifications
