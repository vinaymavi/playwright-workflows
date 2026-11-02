"""Unit tests for ResourceManager (T094)

Tests resource lifecycle management:
- Track resources (screenshots, PDFs)
- Query resources by name and type
- Cleanup resources per execution
- Export/import resource state for recovery
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest

from src.framework.resource_manager import Resource, ResourceManager


class TestResource:
    """Unit tests for Resource model."""

    def test_resource_creation(self):
        """Test Resource instantiation with all fields."""
        resource_id = str(uuid4())
        execution_id = str(uuid4())
        file_path = "/tmp/screenshot.png"
        now = datetime.utcnow().isoformat()

        resource = Resource(
            resource_id=resource_id,
            execution_id=execution_id,
            name="screenshot.png",
            resource_type="screenshot",
            file_path=file_path,
            file_size_bytes=1024,
            created_at=now,
        )

        assert resource.resource_id == resource_id
        assert resource.execution_id == execution_id
        assert resource.name == "screenshot.png"
        assert resource.resource_type == "screenshot"
        assert resource.file_path == file_path
        assert resource.file_size_bytes == 1024
        assert resource.created_at == now

    def test_resource_model_dump(self):
        """Test Resource serialization to dict."""
        resource = Resource(
            resource_id="id123",
            execution_id="exec123",
            name="export.pdf",
            resource_type="pdf",
            file_path="/data/export.pdf",
            file_size_bytes=2048,
            created_at="2024-01-01T12:00:00",
        )

        data = resource.model_dump()
        assert data["resource_id"] == "id123"
        assert data["execution_id"] == "exec123"
        assert data["name"] == "export.pdf"
        assert data["resource_type"] == "pdf"
        assert data["file_path"] == "/data/export.pdf"
        assert data["file_size_bytes"] == 2048

    def test_resource_get_url(self):
        """Test Resource URL generation for MCP server."""
        resource = Resource(
            resource_id="id123",
            execution_id="exec456",
            name="screenshot.png",
            resource_type="screenshot",
            file_path="/data/artifacts/screenshot.png",
            file_size_bytes=1024,
        )

        url = resource.get_url()
        assert url == "/artifacts/exec456/screenshot.png"

        url_custom = resource.get_url("/files")
        assert url_custom == "/files/exec456/screenshot.png"


class TestResourceManager:
    """Unit tests for ResourceManager class."""

    @pytest.fixture
    def manager(self):
        """Create fresh ResourceManager for each test."""
        return ResourceManager()

    def test_track_resource(self, manager):
        """Test tracking a single resource."""
        execution_id = str(uuid4())

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a temporary file
            file_path = Path(tmpdir) / "screenshot.png"
            file_path.write_bytes(b"screenshot data")

            # Track the resource
            resource = manager.track_resource(
                execution_id, file_path, resource_type="screenshot"
            )

            assert resource.name == "screenshot.png"
            assert resource.resource_type == "screenshot"
            assert resource.file_size_bytes == 15
            assert resource.execution_id == execution_id

            # Verify tracked
            resources = manager.get_resources(execution_id)
            assert len(resources) == 1
            assert resources[0].name == "screenshot.png"

    def test_track_multiple_resources(self, manager):
        """Test tracking multiple resources for same execution."""
        execution_id = str(uuid4())

        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = Path(tmpdir) / "screenshot1.png"
            file2 = Path(tmpdir) / "export.pdf"
            file1.write_bytes(b"screenshot data")
            file2.write_bytes(b"pdf data content")

            manager.track_resource(execution_id, file1, resource_type="screenshot")
            manager.track_resource(execution_id, file2, resource_type="pdf")

            resources = manager.get_resources(execution_id)
            assert len(resources) == 2
            assert resources[0].name == "screenshot1.png"
            assert resources[1].name == "export.pdf"

    def test_get_resources_empty(self, manager):
        """Test getting resources for execution with no resources."""
        execution_id = str(uuid4())
        resources = manager.get_resources(execution_id)
        assert resources == []

    def test_get_resource_by_name(self, manager):
        """Test querying resource by name."""
        execution_id = str(uuid4())

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "screenshot1.png"
            file_path.write_bytes(b"screenshot data")

            manager.track_resource(execution_id, file_path, resource_type="screenshot")
            found = manager.get_resource_by_name(execution_id, "screenshot1.png")

            assert found is not None
            assert found.name == "screenshot1.png"
            assert found.resource_type == "screenshot"

    def test_get_resource_by_name_not_found(self, manager):
        """Test querying resource by name when not found."""
        execution_id = str(uuid4())
        found = manager.get_resource_by_name(execution_id, "nonexistent.png")
        assert found is None

    def test_query_resources_by_type(self, manager):
        """Test querying resources by type."""
        execution_id = str(uuid4())

        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = Path(tmpdir) / "screenshot1.png"
            file2 = Path(tmpdir) / "export.pdf"
            file1.write_bytes(b"screenshot data")
            file2.write_bytes(b"pdf data")

            manager.track_resource(execution_id, file1, resource_type="screenshot")
            manager.track_resource(execution_id, file2, resource_type="pdf")

            # Manually filter by type
            all_resources = manager.get_resources(execution_id)
            screenshots = [r for r in all_resources if r.resource_type == "screenshot"]
            pdfs = [r for r in all_resources if r.resource_type == "pdf"]

            assert len(screenshots) == 1
            assert screenshots[0].name == "screenshot1.png"
            assert len(pdfs) == 1
            assert pdfs[0].name == "export.pdf"

    def test_cleanup_execution_artifacts(self, manager):
        """Test cleanup removes all resources for execution."""
        execution_id = str(uuid4())

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create temporary files
            file1 = Path(tmpdir) / "screenshot1.png"
            file2 = Path(tmpdir) / "export.pdf"
            file1.write_bytes(b"screenshot data")
            file2.write_bytes(b"pdf data")

            manager.track_resource(execution_id, file1, resource_type="screenshot")
            manager.track_resource(execution_id, file2, resource_type="pdf")

            # Verify files exist
            assert file1.exists()
            assert file2.exists()

            # Cleanup
            manager.cleanup_execution_artifacts(execution_id)

            # Verify files deleted
            assert not file1.exists()
            assert not file2.exists()

            # Verify resources cleared
            resources = manager.get_resources(execution_id)
            assert len(resources) == 0

    def test_cleanup_all_artifacts(self, manager):
        """Test cleanup_all removes resources across all executions."""
        exec1 = str(uuid4())
        exec2 = str(uuid4())

        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = Path(tmpdir) / "screenshot1.png"
            file2 = Path(tmpdir) / "screenshot2.png"
            file1.write_bytes(b"data1")
            file2.write_bytes(b"data2")

            manager.track_resource(exec1, file1, resource_type="screenshot")
            manager.track_resource(exec2, file2, resource_type="screenshot")

            assert len(manager.get_resources(exec1)) == 1
            assert len(manager.get_resources(exec2)) == 1

            manager.cleanup_all()

            assert len(manager.get_resources(exec1)) == 0
            assert len(manager.get_resources(exec2)) == 0
            assert not file1.exists()
            assert not file2.exists()

    def test_export_resources_json(self, manager):
        """Test exporting resources to JSON for persistence."""
        execution_id = str(uuid4())

        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = Path(tmpdir) / "screenshot1.png"
            file2 = Path(tmpdir) / "export.pdf"
            file1.write_bytes(b"screenshot data")
            file2.write_bytes(b"pdf data")

            manager.track_resource(execution_id, file1, resource_type="screenshot")
            manager.track_resource(execution_id, file2, resource_type="pdf")

            data = manager.export_resources_json(execution_id)

            assert len(data) == 2
            assert data[0]["name"] == "screenshot1.png"
            assert data[1]["name"] == "export.pdf"

    def test_import_resources_json(self, manager):
        """Test importing resources from JSON."""
        execution_id = str(uuid4())

        json_data = [
            {
                "resource_id": "res1",
                "execution_id": execution_id,
                "name": "screenshot1.png",
                "resource_type": "screenshot",
                "file_path": "/data/artifacts/screenshot1.png",
                "file_size_bytes": 512,
                "created_at": "2024-01-01T12:00:00",
            },
            {
                "resource_id": "res2",
                "execution_id": execution_id,
                "name": "export.pdf",
                "resource_type": "pdf",
                "file_path": "/data/artifacts/export.pdf",
                "file_size_bytes": 2048,
                "created_at": "2024-01-01T12:01:00",
            },
        ]

        manager.import_resources_json(execution_id, json_data)

        resources = manager.get_resources(execution_id)
        assert len(resources) == 2
        assert resources[0].name == "screenshot1.png"
        assert resources[1].name == "export.pdf"

    def test_export_import_round_trip(self, manager):
        """Test export -> import preserves all data."""
        execution_id = str(uuid4())

        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = Path(tmpdir) / "screenshot1.png"
            file2 = Path(tmpdir) / "export.pdf"
            file1.write_bytes(b"screenshot data")
            file2.write_bytes(b"pdf data")

            manager.track_resource(execution_id, file1, resource_type="screenshot")
            manager.track_resource(execution_id, file2, resource_type="pdf")

            # Export and clear
            exported = manager.export_resources_json(execution_id)
            manager.cleanup_execution_artifacts(execution_id)
            assert len(manager.get_resources(execution_id)) == 0

            # Import
            manager.import_resources_json(execution_id, exported)

            # Verify all data preserved
            imported = manager.get_resources(execution_id)
            assert len(imported) == 2
            assert imported[0].name == "screenshot1.png"
            assert imported[1].name == "export.pdf"

