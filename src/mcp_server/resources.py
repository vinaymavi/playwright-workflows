"""MCP Resources for Workflow Orchestration

Provides access to workflow metadata and execution state via MCP resources.

Resources:
- workflow://{workflow_type}: Metadata for a workflow type
- execution/{execution_id}: Complete execution state snapshot
- artifact/{execution_id}/{name}: Screenshot or PDF artifact
"""

import json
from pathlib import Path
from typing import Any, Optional, Tuple


# Registry of available workflows with metadata
_workflow_metadata: dict[str, dict[str, Any]] = {}


def register_workflow_metadata(
    workflow_type: str,
    description: str,
    input_schema: dict[str, Any],
    output_schema: dict[str, Any]) -> None:
    """Register workflow metadata.

    Args:
        workflow_type: Workflow type/name
        description: Human-readable description
        input_schema: JSON schema for workflow inputs
        output_schema: JSON schema for workflow outputs
    """
    _workflow_metadata[workflow_type] = {
        "type": workflow_type,
        "description": description,
        "input_schema": input_schema,
        "output_schema": output_schema,
    }


def get_workflow_resource(workflow_type: str) -> Optional[dict[str, Any]]:
    """Get workflow metadata resource.

    Args:
        workflow_type: Type of workflow

    Returns:
        Workflow metadata or None if not found
    """
    return _workflow_metadata.get(workflow_type)


def get_execution_resource(execution_id: str) -> Optional[dict[str, Any]]:
    """Get execution state resource.

    Args:
        execution_id: Execution ID

    Returns:
        Complete execution state or None if not found
    """
    data_dir = Path(__file__).parent.parent.parent / "data" / "executions"
    execution_file = data_dir / f"{execution_id}.json"

    if not execution_file.exists():
        return None

    with open(execution_file, "r") as f:
        return json.load(f)


def list_workflow_resources() -> list[dict[str, Any]]:
    """List all available workflow resources.

    Returns:
        List of workflow metadata resources
    """
    return list(_workflow_metadata.values())


def list_execution_resources() -> list[dict[str, str]]:
    """List all execution resources (execution IDs and summary).

    Returns:
        List of execution summaries
    """
    data_dir = Path(__file__).parent.parent.parent / "data" / "executions"
    data_dir.mkdir(parents=True, exist_ok=True)

    executions = []
    for execution_file in data_dir.glob("*.json"):
        with open(execution_file, "r") as f:
            state = json.load(f)
            executions.append({
                "execution_id": state["execution_id"],
                "workflow_type": state.get("workflow_type"),
                "status": state.get("status"),
                "created_at": state.get("created_at"),
            })

    return executions


def get_artifact_resource(execution_id: str, name: str) -> Optional[Tuple[bytes, str]]:
    """Get artifact resource (screenshot or PDF).

    Args:
        execution_id: Execution ID
        name: Artifact name (e.g., 'screenshot_001.png' or 'export_2024.pdf')

    Returns:
        Tuple of (file_content, content_type) or None if not found
    """
    artifacts_dir = Path("data/artifacts") / execution_id
    artifact_path = artifacts_dir / name

    if not artifact_path.exists() or not artifact_path.is_file():
        return None

    with open(artifact_path, "rb") as f:
        content = f.read()

    # Determine content type based on file extension
    if name.lower().endswith(".png"):
        content_type = "image/png"
    elif name.lower().endswith(".jpg") or name.lower().endswith(".jpeg"):
        content_type = "image/jpeg"
    elif name.lower().endswith(".pdf"):
        content_type = "application/pdf"
    else:
        content_type = "application/octet-stream"

    return content, content_type


def list_artifact_resources(execution_id: str) -> list[dict[str, Any]]:
    """List all artifacts for an execution.

    Args:
        execution_id: Execution ID

    Returns:
        List of artifact metadata
    """
    artifacts_dir = Path("data/artifacts") / execution_id
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    artifacts = []
    for artifact_path in artifacts_dir.glob("*"):
        if artifact_path.is_file():
            file_size = artifact_path.stat().st_size
            artifacts.append({
                "name": artifact_path.name,
                "size_bytes": file_size,
                "type": "image/png" if artifact_path.suffix.lower() == ".png" else
                        "application/pdf" if artifact_path.suffix.lower() == ".pdf" else
                        "application/octet-stream",
                "url": f"/artifact/{execution_id}/{artifact_path.name}",
            })

    return artifacts


def get_execution_artifacts_from_state(execution_id: str) -> Optional[list[dict[str, Any]]]:
    """Get artifacts recorded in execution state.

    Args:
        execution_id: Execution ID

    Returns:
        List of Resource objects from execution state or None
    """
    data_dir = Path("data/executions")
    execution_file = data_dir / f"{execution_id}.json"

    if not execution_file.exists():
        return None

    with open(execution_file, "r") as f:
        state = json.load(f)
        return state.get("resources", [])
