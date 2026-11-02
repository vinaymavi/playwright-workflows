"""Unit tests for ActionRegistry."""

import pytest
from unittest.mock import MagicMock, patch
from typing import Any, Dict

from src.framework.action import Action
from src.framework.action_registry import (
    ActionRegistry,
    get_registry,
    register_action,
    get_action,
)


class DummyAction(Action):
    """Dummy action for testing."""

    async def execute(self, **kwargs) -> Dict[str, str]:
        return {"result": "success"}


class AnotherAction(Action):
    """Another dummy action."""

    async def execute(self, **kwargs) -> Dict[str, str]:
        return {"result": "another"}


class NotAnAction:
    """Not an Action subclass."""

    pass


class TestActionRegistry:
    """Tests for ActionRegistry class."""

    def test_init(self):
        """Test ActionRegistry initialization."""
        registry = ActionRegistry()

        assert registry._actions == {}
        assert registry._metadata == {}

    def test_register_action(self):
        """Test registering an action."""
        registry = ActionRegistry()
        registry.register(DummyAction)

        assert "DummyAction" in registry._actions
        assert registry._actions["DummyAction"] is DummyAction

    def test_register_with_custom_name(self):
        """Test registering with custom name."""
        registry = ActionRegistry()
        registry.register(DummyAction, name="custom_action")

        assert "custom_action" in registry._actions
        assert "DummyAction" not in registry._actions

    def test_register_with_metadata(self):
        """Test registering with metadata."""
        registry = ActionRegistry()
        registry.register(DummyAction, custom_field="custom_value")

        metadata = registry.get_metadata("DummyAction")
        assert metadata["custom_field"] == "custom_value"

    def test_register_stores_metadata(self):
        """Test that registration stores action metadata."""
        registry = ActionRegistry()
        registry.register(DummyAction)

        metadata = registry.get_metadata("DummyAction")
        assert metadata["class"] == "DummyAction"
        assert metadata["module"] == DummyAction.__module__
        assert "Dummy" in metadata["description"]  # from docstring

    def test_register_fails_with_non_class(self):
        """Test that registration fails with non-class."""
        registry = ActionRegistry()

        with pytest.raises(ValueError, match="must be a class"):
            registry.register("not_a_class")

    def test_register_fails_with_non_action(self):
        """Test that registration fails with non-Action class."""
        registry = ActionRegistry()

        with pytest.raises(ValueError, match="must be a subclass of Action"):
            registry.register(NotAnAction)

    def test_get_action(self):
        """Test getting a registered action."""
        registry = ActionRegistry()
        registry.register(DummyAction)

        action = registry.get("DummyAction")

        assert action is DummyAction

    def test_get_nonexistent_action(self):
        """Test getting a non-existent action returns None."""
        registry = ActionRegistry()

        action = registry.get("NonExistent")

        assert action is None

    def test_has_action_true(self):
        """Test has() with registered action."""
        registry = ActionRegistry()
        registry.register(DummyAction)

        assert registry.has("DummyAction")

    def test_has_action_false(self):
        """Test has() with non-existent action."""
        registry = ActionRegistry()

        assert not registry.has("NonExistent")

    def test_list_actions(self):
        """Test listing all actions."""
        registry = ActionRegistry()
        registry.register(DummyAction)
        registry.register(AnotherAction)

        actions = registry.list()

        assert "DummyAction" in actions
        assert "AnotherAction" in actions
        assert len(actions) == 2

    def test_list_actions_sorted(self):
        """Test that list() returns sorted action names."""
        registry = ActionRegistry()
        registry.register(DummyAction)
        registry.register(AnotherAction)

        actions = registry.list()

        assert actions == sorted(actions)

    def test_list_actions_empty(self):
        """Test listing actions with empty registry."""
        registry = ActionRegistry()

        actions = registry.list()

        assert actions == []

    def test_get_metadata_exists(self):
        """Test getting metadata for registered action."""
        registry = ActionRegistry()
        registry.register(DummyAction, version="1.0")

        metadata = registry.get_metadata("DummyAction")

        assert metadata is not None
        assert metadata["version"] == "1.0"

    def test_get_metadata_nonexistent(self):
        """Test getting metadata for non-existent action."""
        registry = ActionRegistry()

        metadata = registry.get_metadata("NonExistent")

        assert metadata is None

    def test_instantiate_action(self):
        """Test instantiating an action."""
        registry = ActionRegistry()
        registry.register(DummyAction)

        workflow = MagicMock()
        action = registry.instantiate("DummyAction", workflow)

        assert isinstance(action, DummyAction)
        assert action.workflow_context is workflow

    def test_instantiate_with_kwargs(self):
        """Test instantiating with kwargs."""
        registry = ActionRegistry()
        registry.register(DummyAction)

        workflow = MagicMock()
        action = registry.instantiate(
            "DummyAction",
            workflow,
            name="custom",
            max_retries=5,
        )

        assert action.name == "custom"
        assert action.max_retries == 5

    def test_instantiate_nonexistent_fails(self):
        """Test instantiating non-existent action fails."""
        registry = ActionRegistry()

        workflow = MagicMock()

        with pytest.raises(ValueError, match="Action not found"):
            registry.instantiate("NonExistent", workflow)

    def test_clear_registry(self):
        """Test clearing the registry."""
        registry = ActionRegistry()
        registry.register(DummyAction)
        registry.register(AnotherAction)

        assert len(registry.list()) == 2

        registry.clear()

        assert len(registry.list()) == 0
        assert registry.get("DummyAction") is None

    def test_discover_entry_points_integration(self):
        """Test entry point discovery (with mock)."""
        registry = ActionRegistry()

        # Mock entry point
        mock_ep = MagicMock()
        mock_ep.name = "dummy"
        mock_ep.load.return_value = DummyAction

        with patch("importlib.metadata.entry_points") as mock_eps:
            # Handle both dict and SelectableGroups interface
            mock_eps.return_value = {"playwright_actions": [mock_ep]}

            registry.discover_entry_points()

            assert registry.has("dummy")


class TestGlobalRegistry:
    """Tests for global registry functions."""

    def test_get_registry_returns_singleton(self):
        """Test that get_registry() returns singleton."""
        registry1 = get_registry()
        registry2 = get_registry()

        assert registry1 is registry2

    def test_register_action_global(self):
        """Test global register_action() function."""
        # Get a fresh registry for testing
        registry = ActionRegistry()
        old_registry = globals().get("_global_registry")

        try:
            # Mock the global registry
            with patch("src.framework.action_registry._global_registry", registry):
                register_action(DummyAction)

                assert registry.has("DummyAction")
        finally:
            # Restore
            pass

    def test_get_action_global(self):
        """Test global get_action() function."""
        registry = ActionRegistry()
        registry.register(DummyAction)

        with patch("src.framework.action_registry._global_registry", registry):
            action = get_action("DummyAction")

            assert action is DummyAction


class TestActionRegistryMultipleRegistration:
    """Tests for handling multiple actions and edge cases."""

    def test_register_same_action_twice(self):
        """Test registering same action twice (overwrites)."""
        registry = ActionRegistry()
        registry.register(DummyAction, custom="first")
        registry.register(DummyAction, custom="second")

        metadata = registry.get_metadata("DummyAction")
        assert metadata["custom"] == "second"

    def test_register_many_actions(self):
        """Test registering many actions."""
        registry = ActionRegistry()

        classes = [DummyAction, AnotherAction]
        for cls in classes:
            registry.register(cls)

        assert len(registry.list()) == 2

    def test_registry_isolation(self):
        """Test that registries are isolated."""
        registry1 = ActionRegistry()
        registry2 = ActionRegistry()

        registry1.register(DummyAction)

        assert registry1.has("DummyAction")
        assert not registry2.has("DummyAction")
