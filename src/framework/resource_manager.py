"""Manage execution artifacts (screenshots, PDFs, etc.)."""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from pydantic import BaseModel, Field


class Resource(BaseModel):
    """Represents an artifact (screenshot, PDF, etc.) tracked by an execution."""

    resource_id: str = Field(description="Unique ID for this resource")
    execution_id: str = Field(description="ID of execution that created this resource")
    name: str = Field(description="User-friendly name (e.g., 'login_form.png')")
    file_path: str = Field(description="Absolute path to file on disk")
    resource_type: str = Field(description="Type: 'screenshot', 'pdf', etc.")
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    file_size_bytes: int = Field(default=0, description="Size of file in bytes")

    def get_url(self, base_path: str = "/artifacts") -> str:
        """Get URL path for this resource (for MCP server)."""
        return f"{base_path}/{self.execution_id}/{self.name}"


class ResourceManager:
    """Manage artifacts (screenshots, PDFs) per execution."""

    def __init__(self, artifacts_base_dir: str = "data/artifacts"):
        self.artifacts_base_dir = Path(artifacts_base_dir)
        self.resources: dict[str, list[Resource]] = {}

    def track_resource(
        self,
        execution_id: str,
        file_path: Path,
        resource_type: str = "screenshot",
        name: Optional[str] = None) -> Resource:
        """
        Track a newly created artifact.

        Args:
            execution_id: Execution ID that created this resource
            file_path: Path to the artifact file
            resource_type: Type of resource ('screenshot', 'pdf', etc.)
            name: Optional user-friendly name (defaults to file name)

        Returns:
            Resource object representing the tracked artifact
        """

        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Artifact file not found: {file_path}")

        name = name or file_path.name
        file_size = file_path.stat().st_size

        resource = Resource(
            resource_id=str(uuid.uuid4()),
            execution_id=execution_id,
            name=name,
            file_path=str(file_path.absolute()),
            resource_type=resource_type,
            file_size_bytes=file_size)

        if execution_id not in self.resources:
            self.resources[execution_id] = []
        self.resources[execution_id].append(resource)

        return resource

    def get_resources(self, execution_id: str) -> list[Resource]:
        """Get all resources for an execution."""
        return self.resources.get(execution_id, [])

    def get_resource_by_name(self, execution_id: str, name: str) -> Optional[Resource]:
        """Get specific resource by name."""
        for resource in self.get_resources(execution_id):
            if resource.name == name:
                return resource
        return None

    def cleanup_execution_artifacts(self, execution_id: str) -> int:
        """
        Delete all artifacts for an execution.

        Args:
            execution_id: Execution to clean up

        Returns:
            Number of files deleted
        """
        resources = self.resources.get(execution_id, [])
        deleted_count = 0

        for resource in resources:
            try:
                file_path = Path(resource.file_path)
                if file_path.exists():
                    file_path.unlink()
                    deleted_count += 1
            except Exception as e:
                print(f"Failed to delete {resource.file_path}: {e}")

        # Remove execution directory if empty
        exec_dir = self.artifacts_base_dir / execution_id
        if exec_dir.exists():
            try:
                if not any(exec_dir.iterdir()):  # Check if directory is empty
                    exec_dir.rmdir()
            except Exception as e:
                print(f"Failed to remove directory {exec_dir}: {e}")

        # Clear from tracking
        if execution_id in self.resources:
            del self.resources[execution_id]

        return deleted_count

    def cleanup_all(self) -> int:
        """Delete all tracked artifacts."""
        total_deleted = 0
        for execution_id in list(self.resources.keys()):
            total_deleted += self.cleanup_execution_artifacts(execution_id)
        return total_deleted

    def export_resources_json(self, execution_id: str) -> list[Dict]:
        """Export resources as JSON-serializable dicts."""
        return [r.model_dump() for r in self.get_resources(execution_id)]

    def import_resources_json(self, execution_id: str, resources_data: list[Dict]) -> None:
        """Import resources from JSON (for recovery/resume)."""
        for data in resources_data:
            resource = Resource(**data)
            if execution_id not in self.resources:
                self.resources[execution_id] = []
            self.resources[execution_id].append(resource)
