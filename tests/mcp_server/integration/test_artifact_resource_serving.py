"""Integration tests for MCP Artifact Resource Serving

Tests artifact serving via MCP resources protocol:
- HTTP-like resource serving for artifacts
- Artifact retrieval with proper headers
- Error handling for missing artifacts
- MIME type detection and correctness
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

from src.mcp_server.resources import (
    get_artifact_resource,
    list_artifact_resources,
    get_execution_artifacts_from_state,
)


@pytest.fixture
def temp_workspace(tmp_path, monkeypatch):
    """Create temporary workspace with proper directory structure."""
    monkeypatch.chdir(tmp_path)
    
    # Create all necessary directories
    (tmp_path / "data" / "artifacts").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "executions").mkdir(parents=True, exist_ok=True)
    
    return tmp_path


@pytest.fixture
def sample_execution_with_artifacts(temp_workspace):
    """Create a sample execution with artifacts."""
    execution_id = "integration-exec-001"
    
    # Create artifacts
    artifacts_dir = temp_workspace / "data" / "artifacts" / execution_id
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    
    artifacts = {
        "screenshot_initial.png": b'\x89PNG\r\n\x1a\ntest_png_1',
        "screenshot_after_login.png": b'\x89PNG\r\n\x1a\ntest_png_2',
        "form_filled.pdf": b'%PDF-1.4\ntest_pdf_content',
    }
    
    for name, content in artifacts.items():
        (artifacts_dir / name).write_bytes(content)
    
    # Create execution state
    resources = [
        {
            "resource_id": f"res-{i:03d}",
            "execution_id": execution_id,
            "name": name,
            "file_path": f"data/artifacts/{execution_id}/{name}",
            "resource_type": "screenshot" if name.endswith(".png") else "pdf_export",
            "file_size_bytes": len(content),
            "created_at": f"2024-01-01T10:{i:02d}:00Z",
        }
        for i, (name, content) in enumerate(artifacts.items(), 1)
    ]
    
    state = {
        "execution_id": execution_id,
        "workflow_type": "form_filler",
        "status": "completed",
        "resources": resources,
    }
    
    executions_dir = temp_workspace / "data" / "executions"
    (executions_dir / f"{execution_id}.json").write_text(json.dumps(state))
    
    return {
        "execution_id": execution_id,
        "artifacts": artifacts,
        "resources": resources,
    }


class TestArtifactResourceServing:
    """Test artifact serving functionality."""

    def test_serve_screenshot_artifact(self, sample_execution_with_artifacts):
        """Test serving a screenshot artifact."""
        execution_id = sample_execution_with_artifacts["execution_id"]
        artifact_name = "screenshot_initial.png"
        expected_content = sample_execution_with_artifacts["artifacts"][artifact_name]
        
        # Get artifact
        result = get_artifact_resource(execution_id, artifact_name)
        
        assert result is not None
        content, content_type = result
        assert content == expected_content
        assert content_type == "image/png"

    def test_serve_pdf_artifact(self, sample_execution_with_artifacts):
        """Test serving a PDF artifact."""
        execution_id = sample_execution_with_artifacts["execution_id"]
        artifact_name = "form_filled.pdf"
        expected_content = sample_execution_with_artifacts["artifacts"][artifact_name]
        
        # Get artifact
        result = get_artifact_resource(execution_id, artifact_name)
        
        assert result is not None
        content, content_type = result
        assert content == expected_content
        assert content_type == "application/pdf"

    def test_list_execution_artifacts(self, sample_execution_with_artifacts):
        """Test listing all artifacts for an execution."""
        execution_id = sample_execution_with_artifacts["execution_id"]
        
        # List artifacts
        result = list_artifact_resources(execution_id)
        
        assert len(result) == 3
        
        # Verify names
        names = {art["name"] for art in result}
        expected_names = {"screenshot_initial.png", "screenshot_after_login.png", "form_filled.pdf"}
        assert names == expected_names
        
        # Verify types
        for art in result:
            if art["name"].endswith(".png"):
                assert art["type"] == "image/png"
            elif art["name"].endswith(".pdf"):
                assert art["type"] == "application/pdf"

    def test_query_artifacts_from_execution_state(self, sample_execution_with_artifacts):
        """Test querying artifacts from execution state."""
        execution_id = sample_execution_with_artifacts["execution_id"]
        
        # Query execution state
        resources = get_execution_artifacts_from_state(execution_id)
        
        assert resources is not None
        assert len(resources) == 3
        
        # Verify resource structure
        for resource in resources:
            assert "resource_id" in resource
            assert "execution_id" in resource
            assert "name" in resource
            assert "file_path" in resource
            assert "resource_type" in resource
            assert "file_size_bytes" in resource
            assert "created_at" in resource
            
            # Verify execution ID matches
            assert resource["execution_id"] == execution_id

    def test_artifact_resource_urls(self, sample_execution_with_artifacts):
        """Test that artifact URLs are properly formatted for MCP resources."""
        execution_id = sample_execution_with_artifacts["execution_id"]
        
        # List artifacts
        result = list_artifact_resources(execution_id)
        
        # Verify URL format for each artifact
        for art in result:
            expected_url = f"/artifact/{execution_id}/{art['name']}"
            assert art["url"] == expected_url

    def test_serve_multiple_artifacts_sequentially(self, sample_execution_with_artifacts):
        """Test serving multiple artifacts in sequence."""
        execution_id = sample_execution_with_artifacts["execution_id"]
        
        # List all artifacts
        artifacts = list_artifact_resources(execution_id)
        assert len(artifacts) == 3
        
        # Serve each artifact
        served_count = 0
        for art in artifacts:
            result = get_artifact_resource(execution_id, art["name"])
            assert result is not None
            content, content_type = result
            assert len(content) > 0
            assert content_type == art["type"]
            served_count += 1
        
        assert served_count == 3

    def test_artifact_with_special_characters_in_name(self, temp_workspace):
        """Test artifact serving with special characters in filename."""
        execution_id = "exec-special-001"
        artifact_name = "screenshot_2024-01-15_14-30-45.png"
        
        # Create artifact with special chars in name
        artifacts_dir = temp_workspace / "data" / "artifacts" / execution_id
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = artifacts_dir / artifact_name
        artifact_path.write_bytes(b'test_data')
        
        # Serve artifact
        result = get_artifact_resource(execution_id, artifact_name)
        assert result is not None
        content, content_type = result
        assert content == b'test_data'

    def test_artifact_size_tracking(self, sample_execution_with_artifacts):
        """Test that artifact sizes are correctly tracked."""
        execution_id = sample_execution_with_artifacts["execution_id"]
        
        # Get artifacts
        artifacts = list_artifact_resources(execution_id)
        
        # Verify sizes match
        for art in artifacts:
            # Get actual file size
            artifact_path = Path(f"data/artifacts/{execution_id}/{art['name']}")
            actual_size = artifact_path.stat().st_size
            
            assert art["size_bytes"] == actual_size

    def test_artifact_not_found_returns_none(self):
        """Test that requesting non-existent artifact returns None."""
        result = get_artifact_resource("nonexistent", "missing.png")
        assert result is None

    def test_multiple_executions_artifact_isolation(self, temp_workspace):
        """Test that artifacts from different executions are isolated."""
        # Create artifacts for two different executions
        exec1_id = "exec-001"
        exec2_id = "exec-002"
        
        # Create artifacts for execution 1
        exec1_dir = temp_workspace / "data" / "artifacts" / exec1_id
        exec1_dir.mkdir(parents=True, exist_ok=True)
        (exec1_dir / "screenshot.png").write_bytes(b'exec1_data')
        
        # Create artifacts for execution 2
        exec2_dir = temp_workspace / "data" / "artifacts" / exec2_id
        exec2_dir.mkdir(parents=True, exist_ok=True)
        (exec2_dir / "screenshot.png").write_bytes(b'exec2_data')
        
        # List artifacts for each execution
        exec1_artifacts = list_artifact_resources(exec1_id)
        exec2_artifacts = list_artifact_resources(exec2_id)
        
        assert len(exec1_artifacts) == 1
        assert len(exec2_artifacts) == 1
        
        # Serve artifacts and verify isolation
        exec1_content, _ = get_artifact_resource(exec1_id, "screenshot.png")
        exec2_content, _ = get_artifact_resource(exec2_id, "screenshot.png")
        
        assert exec1_content == b'exec1_data'
        assert exec2_content == b'exec2_data'
        assert exec1_content != exec2_content


class TestArtifactResourceErrorHandling:
    """Test error handling in artifact resource serving."""

    def test_missing_artifact_returns_none(self, temp_workspace):
        """Test handling of missing artifact file."""
        # Try to get non-existent artifact
        result = get_artifact_resource("exec-001", "missing.png")
        assert result is None

    def test_missing_execution_dir(self, temp_workspace):
        """Test handling of missing execution directory."""
        # Try to get artifact from non-existent execution
        result = get_artifact_resource("exec-missing", "screenshot.png")
        assert result is None

    def test_list_empty_execution_directory(self, temp_workspace):
        """Test listing artifacts from execution with no artifacts."""
        # List artifacts from execution with no files
        result = list_artifact_resources("empty-exec")
        assert result == []

    def test_artifact_query_missing_execution_state(self, temp_workspace):
        """Test querying artifacts from non-existent execution state."""
        # Query missing execution state
        result = get_execution_artifacts_from_state("missing-exec")
        assert result is None
