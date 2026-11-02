"""Action Registry for Managing Reusable Workflow Actions

Provides registration, discovery, and management of Action classes.
Supports both explicit registration and auto-discovery via entry points.
"""

import importlib
import inspect
from typing import Any, Dict, List, Optional, Type

from ..utils.logging import setup_logger
from .action import Action

logger = setup_logger(__name__)


class ActionRegistry:
    """Registry for managing Action classes.

    Provides:
    - Central registration of custom actions
    - Action discovery and retrieval
    - Validation of action interface compliance
    - Listing available actions with metadata

    Example:
        registry = ActionRegistry()
        registry.register(FillFormAction)
        action = registry.get("FillFormAction")
        actions = registry.list()
    """

    def __init__(self):
        """Initialize the action registry."""
        self._actions: Dict[str, Type[Action]] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}
        logger.debug("Initialized ActionRegistry")

    def register(
        self, action_class: Type[Action], name: Optional[str] = None, **metadata
    ) -> None:
        """Register an action class in the registry.

        Args:
            action_class: The Action subclass to register
            name: Custom name for the action (defaults to class name)
            **metadata: Additional metadata for the action

        Raises:
            ValueError: If action_class is not a subclass of Action
            ValueError: If action_class doesn't implement execute()
        """
        if not inspect.isclass(action_class):
            raise ValueError(f"action_class must be a class, got {type(action_class)}")

        if not issubclass(action_class, Action):
            raise ValueError(
                f"{action_class.__name__} must be a subclass of Action"
            )

        if not hasattr(action_class, "execute"):
            raise ValueError(
                f"{action_class.__name__} must implement execute() method"
            )

        action_name = name or action_class.__name__
        self._actions[action_name] = action_class
        self._metadata[action_name] = {
            "class": action_class.__name__,
            "module": action_class.__module__,
            "description": action_class.__doc__,
            **metadata,
        }

        logger.debug(f"Registered action: {action_name}")

    def get(self, name: str) -> Optional[Type[Action]]:
        """Retrieve an action class by name.

        Args:
            name: Name of the action

        Returns:
            The Action class if found, None otherwise
        """
        return self._actions.get(name)

    def has(self, name: str) -> bool:
        """Check if an action is registered.

        Args:
            name: Name of the action

        Returns:
            True if the action is registered
        """
        return name in self._actions

    def list(self) -> List[str]:
        """List all registered action names.

        Returns:
            List of action names
        """
        return sorted(self._actions.keys())

    def get_metadata(self, name: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a registered action.

        Args:
            name: Name of the action

        Returns:
            Metadata dictionary if action is registered, None otherwise
        """
        return self._metadata.get(name)

    def instantiate(
        self, action_name: str, workflow_context: Any, **kwargs
    ) -> Action:
        """Instantiate an action by name.

        Args:
            action_name: Name/type of the action class to instantiate
            workflow_context: Reference to parent workflow
            **kwargs: Arguments to pass to action constructor (including 'name' for instance name)

        Returns:
            An instance of the requested Action

        Raises:
            ValueError: If action is not registered
        """
        action_class = self.get(action_name)
        if not action_class:
            raise ValueError(f"Action not found: {action_name}")

        try:
            return action_class(workflow_context, **kwargs)
        except Exception as e:
            logger.error(f"Failed to instantiate action '{action_name}': {e}")
            raise

    def discover_entry_points(self, entry_point_group: str = "playwright_actions") -> None:
        """Auto-discover and register actions from entry points.

        Entry points should be defined in pyproject.toml:

        [project.entry-points."playwright_actions"]
        fill_form = "shared_steps.form_actions:FillFormAction"
        enter_credentials = "shared_steps.login_actions:EnterCredentialsAction"

        Args:
            entry_point_group: Name of the entry point group to scan
        """
        try:
            import importlib.metadata as metadata
        except ImportError:
            # Python < 3.8
            import importlib_metadata as metadata

        logger.debug(f"Discovering entry points for group: {entry_point_group}")

        try:
            entry_points = metadata.entry_points()

            # Handle both dict and SelectableGroups interface (different Python versions)
            if hasattr(entry_points, "select"):
                # Python 3.10+ SelectableGroups interface
                eps = entry_points.select(group=entry_point_group)
            elif isinstance(entry_points, dict):
                # Python 3.9 dict interface
                eps = entry_points.get(entry_point_group, [])
            else:
                # Fallback
                eps = entry_points.get(entry_point_group, [])

            for ep in eps:
                try:
                    action_class = ep.load()
                    self.register(action_class, name=ep.name)
                    logger.debug(
                        f"Auto-discovered action from entry point: {ep.name}"
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to load entry point '{ep.name}': {e}"
                    )

        except Exception as e:
            logger.warning(f"Failed to discover entry points: {e}")

    def clear(self) -> None:
        """Clear all registered actions.

        Useful for testing and resetting registry state.
        """
        self._actions.clear()
        self._metadata.clear()
        logger.debug("Cleared ActionRegistry")


# Global registry instance
_global_registry: Optional[ActionRegistry] = None


def get_registry() -> ActionRegistry:
    """Get the global action registry instance.

    Returns:
        The global ActionRegistry
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = ActionRegistry()
    return _global_registry


def register_action(
    action_class: Type[Action], name: Optional[str] = None, **metadata
) -> None:
    """Register an action class in the global registry.

    Convenience function for module-level registration.

    Args:
        action_class: The Action subclass to register
        name: Custom name for the action
        **metadata: Additional metadata
    """
    get_registry().register(action_class, name, **metadata)


def get_action(name: str) -> Optional[Type[Action]]:
    """Get an action class from the global registry.

    Args:
        name: Name of the action

    Returns:
        The Action class if found
    """
    return get_registry().get(name)
