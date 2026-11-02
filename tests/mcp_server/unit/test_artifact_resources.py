"""Unit tests for MCP Artifact Resources

Tests artifact serving functionality:
- get_artifact_resource(): Retrieve screenshot/PDF by ID and name
- list_artifact_resources(): List all artifacts for an execution
- get_execution_artifacts_from_state(): Query artifacts from execution state
- Content type detection for various image/PDF formats
- File path validation and security
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.mcp_server.resources import (
    get_artifact_resource,
    list_artifact_resources,
    get_execution_artifacts_from_state,
)


@pytest.fixture
def temp_artifacts_dir(tmp_path, monkeypatch):
    """Create temporary artifacts directory and set working directory."""
    artifacts_dir = tmp_path / "data" / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    
    # Change to temp directory so relative paths work
    monkeypatch.chdir(tmp_path)
    return artifacts_dir


@pytest.fixture
def temp_executions_dir(tmp_path):
    """Create temporary executions directory."""
    executions_dir = tmp_path / "data" / "executions"
    executions_dir.mkdir(parents=True, exist_ok=True)
    return executions_dir


class TestGetArtifactResource:
    """Test get_artifact_resource() function."""

    def test_get_png_artifact(self, temp_artifacts_dir):
        """Test retrieving a PNG screenshot artifact."""
        execution_id = "exec-001"
        artifact_name = "screenshot_001.png"
        
        # Create test artifact directory and file
        exec_dir = temp_artifacts_dir / execution_id
        exec_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = exec_dir / artifact_name
        
        # Write test PNG data (minimal PNG header)
        png_data = b'\x89PNG\r\n\x1a\n' + b'test_png_content'
        artifact_path.write_bytes(png_data)
        
        # Retrieve artifact
        result = get_artifact_resource(execution_id, artifact_name)
        
        assert result is not None
        content, content_type = result
        assert content == png_data
        assert content_type == "image/png"

    def test_get_pdf_artifact(self, temp_artifacts_dir):
        """Test retrieving a PDF artifact."""
        execution_id = "exec-002"
        artifact_name = "export_2024.pdf"
        
        # Create test artifact directory and file
        exec_dir = temp_artifacts_dir / execution_id
        exec_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = exec_dir / artifact_name
        
        # Write test PDF data (minimal PDF header)
        pdf_data = b'%PDF-1.4\ntest_pdf_content'
        artifact_path.write_bytes(pdf_data)
        
        # Retrieve artifact
        result = get_artifact_resource(execution_id, artifact_name)
        
        assert result is not None
        content, content_type = result
        assert content == pdf_data
        assert content_type == "application/pdf"

    def test_get_jpeg_artifact(self, temp_artifacts_dir):
        """Test retrieving a JPEG artifact."""
        execution_id = "exec-003"
        artifact_name = "screenshot.jpg"
        
        # Create test artifact directory and file
        exec_dir = temp_artifacts_dir / execution_id
        exec_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = exec_dir / artifact_name
        
        # Write test JPEG data
        jpeg_data = b'\xff\xd8\xff\xe0' + b'test_jpeg_content'
        artifact_path.write_bytes(jpeg_data)
        
        # Retrieve artifact
        result = get_artifact_resource(execution_id, artifact_name)
        
        assert result is not None
        content, content_type = result
        assert content == jpeg_data
        assert content_type == "image/jpeg"

    def test_get_artifact_not_found(self, temp_artifacts_dir):
        """Test retrieving non-existent artifact returns None."""
        result = get_artifact_resource("nonexistent-exec", "missing.png")
        assert result is None

    def test_get_artifact_invalid_path(self, temp_artifacts_dir):
        """Test that directory paths are rejected."""
        execution_id = "exec-004"
        
        # Create test directory (not a file)
        exec_dir = temp_artifacts_dir / execution_id
        exec_dir.mkdir(parents=True, exist_ok=True)
        
        # Try to get directory as artifact
        result = get_artifact_resource(execution_id, execution_id)
        assert result is None

    def test_get_artifact_unknown_extension(self, temp_artifacts_dir):
        """Test artifact with unknown extension gets generic content type."""
        execution_id = "exec-005"
        artifact_name = "data.xyz"
        
        # Create test artifact
        exec_dir = temp_artifacts_dir / execution_id
        exec_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = exec_dir / artifact_name
        artifact_path.write_bytes(b'unknown_data')
        
        # Retrieve artifact
        result = get_artifact_resource(execution_id, artifact_name)
        
        assert result is not None
        content, content_type = result
        assert content == b'unknown_data'
        assert content_type == "application/octet-stream"


class TestListArtifactResources:
    """Test list_artifact_resources() function."""

    def test_list_empty_artifacts(self, temp_artifacts_dir):
        """Test listing artifacts for execution with no artifacts."""
        result = list_artifact_resources("exec-empty")
        assert result == []

    def test_list_multiple_artifacts(self, temp_artifacts_dir):
        """Test listing multiple artifacts for an execution."""
        execution_id = "exec-multi"
        
        # Create multiple artifacts
        exec_dir = temp_artifacts_dir / execution_id
        exec_dir.mkdir(parents=True, exist_ok=True)
        
        artifacts_created = {
            "screenshot_001.png": b'png_data_1',
            "screenshot_002.png": b'png_data_2',
            "export.pdf": b'pdf_data',
        }
        
        for name, data in artifacts_created.items():
            (exec_dir / name).write_bytes(data)
        
        # List artifacts
        result = list_artifact_resources(execution_id)
        
        assert len(result) == 3
        assert all("name" in art for art in result)
        assert all("size_bytes" in art for art in result)
        assert all("type" in art for art in result)
        assert all("url" in art for art in result)
        
        # Verify specific artifacts
        names = {art["name"] for art in result}
        assert names == set(artifacts_created.keys())
        
        # Verify content types
        artifact_dict = {art["name"]: art for art in result}
        assert artifact_dict["screenshot_001.png"]["type"] == "image/png"
        assert artifact_dict["screenshot_002.png"]["type"] == "image/png"
        assert artifact_dict["export.pdf"]["type"] == "application/pdf"

    def test_list_artifacts_with_size(self, temp_artifacts_dir):
        """Test that artifact sizes are correctly reported."""
        execution_id = "exec-size"
        
        # Create artifacts with known sizes
        exec_dir = temp_artifacts_dir / execution_id
        exec_dir.mkdir(parents=True, exist_ok=True)
        
        artifact_path = exec_dir / "large.png"
        test_data = b'x' * 10240  # 10KB
        artifact_path.write_bytes(test_data)
        
        # List artifacts
        result = list_artifact_resources(execution_id)
        
        assert len(result) == 1
        assert result[0]["size_bytes"] == 10240

    def test_list_artifacts_ignores_directories(self, temp_artifacts_dir):
        """Test that subdirectories are not listed as artifacts."""
        execution_id = "exec-dirs"
        
        # Create artifact and subdirectory
        exec_dir = temp_artifacts_dir / execution_id
        exec_dir.mkdir(parents=True, exist_ok=True)
        
        (exec_dir / "screenshot.png").write_bytes(b'png_data')
        (exec_dir / "subdir").mkdir()
        
        # List artifacts
        result = list_artifact_resources(execution_id)
        
        # Should only include file, not directory
        assert len(result) == 1
        assert result[0]["name"] == "screenshot.png"

    def test_list_artifacts_url_format(self, temp_artifacts_dir):
        """Test that artifact URLs are correctly formatted."""
        execution_id = "exec-url-test"
        artifact_name = "screenshot.png"
        
        # Create artifact
        exec_dir = temp_artifacts_dir / execution_id
        exec_dir.mkdir(parents=True, exist_ok=True)
        (exec_dir / artifact_name).write_bytes(b'data')
        
        # List artifacts
        result = list_artifact_resources(execution_id)
        
        assert len(result) == 1
        expected_url = f"/artifact/{execution_id}/{artifact_name}"
        assert result[0]["url"] == expected_url


class TestGetExecutionArtifactsFromState:
    """Test get_execution_artifacts_from_state() function."""

    def test_get_artifacts_from_state(self, tmp_path, monkeypatch):
        """Test retrieving artifacts from execution state JSON."""
        monkeypatch.chdir(tmp_path)
        
        # Create data directory
        data_dir = tmp_path / "data" / "executions"
        data_dir.mkdir(parents=True, exist_ok=True)
        
        # Create execution state with artifacts
        execution_id = "exec-state-001"
        resources = [
            {
                "resource_id": "res-001",
                "execution_id": execution_id,
                "name": "screenshot.png",
                "file_path": f"data/artifacts/{execution_id}/screenshot.png",
                "resource_type": "screenshot",
                "file_size_bytes": 4096,
                "created_at": "2024-01-01T10:00:00Z",
            },
            {
                "resource_id": "res-002",
                "execution_id": execution_id,
                "name": "export.pdf",
                "file_path": f"data/artifacts/{execution_id}/export.pdf",
                "resource_type": "pdf_export",
                "file_size_bytes": 8192,
                "created_at": "2024-01-01T10:05:00Z",
            },
        ]
        
        state = {
            "execution_id": execution_id,
            "status": "completed",
            "resources": resources,
        }
        
        execution_file = data_dir / f"{execution_id}.json"
        execution_file.write_text(json.dumps(state))
        
        # Get artifacts from state
        result = get_execution_artifacts_from_state(execution_id)
        
        assert result is not None
        assert len(result) == 2
        assert result[0]["name"] == "screenshot.png"
        assert result[0]["resource_type"] == "screenshot"
        assert result[1]["name"] == "export.pdf"
        assert result[1]["resource_type"] == "pdf_export"

    def test_get_artifacts_state_not_found(self):
        """Test retrieving artifacts from non-existent execution state."""
        result = get_execution_artifacts_from_state("nonexistent-exec")
        assert result is None

    def test_get_artifacts_empty_state(self, tmp_path, monkeypatch):
        """Test retrieving artifacts from state with no resources."""
        monkeypatch.chdir(tmp_path)
        
        # Create data directory
        data_dir = tmp_path / "data" / "executions"
        data_dir.mkdir(parents=True, exist_ok=True)
        
        # Create execution state without resources
        execution_id = "exec-empty-state"
        state = {
            "execution_id": execution_id,
            "status": "completed",
        }
        
        execution_file = data_dir / f"{execution_id}.json"
        execution_file.write_text(json.dumps(state))
        
        # Get artifacts from state
        result = get_execution_artifacts_from_state(execution_id)
        
        assert result == []
