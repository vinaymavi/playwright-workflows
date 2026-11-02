# Artifacts Guide

This guide explains how to capture screenshots and export PDF files during workflow execution, and how to query and serve artifacts.

## Overview

The workflow framework provides two methods for creating artifacts during execution:

1. **Screenshots** - Capture the current state of the browser page
2. **PDF Exports** - Export the page as a PDF document using the print-to-PDF feature

All artifacts are automatically tracked in the execution state and can be queried or served via the MCP resources protocol.

## Taking Screenshots

### Method: `take_screenshot()`

Capture the current page as a PNG screenshot.

#### Signature

```python
async def take_screenshot(self, name: str = None) -> Path:
    """Capture a screenshot of the current page.
    
    Args:
        name: Optional custom name for the screenshot (without extension).
              If not provided, a timestamped name is generated.
    
    Returns:
        Path object pointing to the saved screenshot file.
    
    Raises:
        WorkflowError: If screenshot capture fails or no page is active.
    """
```

#### Usage Example

```python
from src.framework.workflow import Workflow

class MyWorkflow(Workflow):
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        # Navigate to a page
        await self.goto("https://example.com")
        
        # Capture a screenshot with default name (timestamp-based)
        screenshot_path = await self.take_screenshot()
        # Saved as: data/artifacts/{execution_id}/screenshot_20240115_143045.png
        
        # Capture with custom name
        screenshot_path = await self.take_screenshot("login_page")
        # Saved as: data/artifacts/{execution_id}/login_page.png
        
        return {"screenshot": str(screenshot_path)}
```

#### Screenshot Storage

Screenshots are automatically saved to:

```
data/artifacts/{execution_id}/{name}.png
```

Where:
- `{execution_id}` - Unique identifier of the workflow execution
- `{name}` - Custom name or auto-generated timestamp-based name

#### Artifact Tracking

Each screenshot is automatically tracked as a `Resource` entity in the execution state with the following metadata:

- `resource_id`: Unique identifier (UUID)
- `execution_id`: Associated execution ID
- `name`: Screenshot filename
- `file_path`: Full path to the saved file
- `resource_type`: "screenshot"
- `file_size_bytes`: Size of the PNG file
- `created_at`: ISO 8601 timestamp

## Exporting to PDF

### Method: `export_to_pdf()`

Export the current page as a PDF document using the browser's print-to-PDF feature.

#### Signature

```python
async def export_to_pdf(self, name: str = None) -> Path:
    """Export the current page as a PDF document.
    
    Args:
        name: Optional custom name for the PDF (without extension).
              If not provided, a timestamped name is generated.
    
    Returns:
        Path object pointing to the saved PDF file.
    
    Raises:
        WorkflowError: If PDF export fails or no page is active.
    """
```

#### Usage Example

```python
from src.framework.workflow import Workflow

class MyWorkflow(Workflow):
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        # Fill a form and submit
        await self.fill("input[name='email']", "user@example.com")
        await self.fill("input[name='password']", "password123")
        await self.click("button[type='submit']")
        
        # Wait for confirmation page
        await self.wait_for_navigation()
        
        # Export confirmation as PDF
        pdf_path = await self.export_to_pdf("confirmation")
        # Saved as: data/artifacts/{execution_id}/confirmation.pdf
        
        return {"pdf": str(pdf_path)}
```

#### PDF Export Features

- **Print Media Type**: Uses the browser's print media type for rendering
- **Background Colors**: Includes background colors and images in the PDF
- **Full Page**: Captures the entire page content
- **Pagination**: Automatically handles page breaks

#### PDF Storage

PDFs are automatically saved to:

```
data/artifacts/{execution_id}/{name}.pdf
```

#### Artifact Tracking

Each PDF export is tracked as a `Resource` entity with:

- `resource_id`: Unique identifier (UUID)
- `execution_id`: Associated execution ID
- `name`: PDF filename
- `file_path`: Full path to the saved file
- `resource_type`: "pdf_export"
- `file_size_bytes`: Size of the PDF file
- `created_at`: ISO 8601 timestamp

## Artifact Storage Structure

All artifacts are organized in a predictable directory structure:

```
data/
├── artifacts/
│   ├── {execution_id_1}/
│   │   ├── screenshot_20240115_143045.png
│   │   ├── login_page.png
│   │   └── confirmation.pdf
│   └── {execution_id_2}/
│       ├── screenshot_initial.png
│       └── export_2024.pdf
└── executions/
    ├── {execution_id_1}.json
    └── {execution_id_2}.json
```

## Querying Artifacts from Execution State

### Getting Execution State

Artifacts are persisted in the execution state JSON file at `data/executions/{execution_id}.json`:

```python
import json
from pathlib import Path

def get_execution_artifacts(execution_id: str):
    """Load artifacts from execution state."""
    state_file = Path(f"data/executions/{execution_id}.json")
    
    with open(state_file, "r") as f:
        state = json.load(f)
    
    return state.get("resources", [])

# Usage
artifacts = get_execution_artifacts("exec-12345")
for resource in artifacts:
    if resource["resource_type"] in ["screenshot", "pdf_export"]:
        print(f"{resource['name']}: {resource['file_path']}")
```

### Execution State Schema

The `resources` field in execution state contains an array of `Resource` objects:

```json
{
  "execution_id": "exec-12345",
  "workflow_type": "form_filler",
  "status": "completed",
  "resources": [
    {
      "resource_id": "res-001",
      "execution_id": "exec-12345",
      "name": "screenshot_20240115_143045.png",
      "file_path": "data/artifacts/exec-12345/screenshot_20240115_143045.png",
      "resource_type": "screenshot",
      "file_size_bytes": 45678,
      "created_at": "2024-01-15T14:30:45Z"
    },
    {
      "resource_id": "res-002",
      "execution_id": "exec-12345",
      "name": "confirmation.pdf",
      "file_path": "data/artifacts/exec-12345/confirmation.pdf",
      "resource_type": "pdf_export",
      "file_size_bytes": 123456,
      "created_at": "2024-01-15T14:35:22Z"
    }
  ]
}
```

## Serving Artifacts via MCP Resources

The MCP server provides resource endpoints for accessing artifacts:

### Resource Functions

#### `get_artifact_resource(execution_id, name)`

Retrieve a specific artifact file content and content type.

```python
from src.mcp_server.resources import get_artifact_resource

# Retrieve a screenshot
result = get_artifact_resource("exec-12345", "screenshot_001.png")
if result:
    content, content_type = result
    # content: bytes of the file
    # content_type: "image/png", "image/jpeg", "application/pdf", etc.
```

#### `list_artifact_resources(execution_id)`

List all artifacts for an execution with metadata.

```python
from src.mcp_server.resources import list_artifact_resources

# List all artifacts for an execution
artifacts = list_artifact_resources("exec-12345")
# Returns:
# [
#     {
#         "name": "screenshot_001.png",
#         "size_bytes": 45678,
#         "type": "image/png",
#         "url": "/artifact/exec-12345/screenshot_001.png"
#     },
#     ...
# ]
```

#### `get_execution_artifacts_from_state(execution_id)`

Query artifacts from the execution state JSON.

```python
from src.mcp_server.resources import get_execution_artifacts_from_state

# Get Resource objects from execution state
resources = get_execution_artifacts_from_state("exec-12345")
# Returns Resource array from execution state
```

## Content Type Mapping

Artifacts are served with the appropriate content type:

| Extension | Content Type |
|-----------|--------------|
| `.png` | `image/png` |
| `.jpg` / `.jpeg` | `image/jpeg` |
| `.pdf` | `application/pdf` |
| Other | `application/octet-stream` |

## Best Practices

### 1. Use Descriptive Names

```python
# Good: descriptive names
await self.take_screenshot("login_successful")
await self.take_screenshot("form_filled")
await self.export_to_pdf("invoice_2024")

# Avoid: generic or unclear names
await self.take_screenshot("img1")
await self.take_screenshot("screenshot")
```

### 2. Capture at Key Checkpoints

Capture artifacts at important workflow checkpoints:

```python
async def execute(self, inputs):
    # Initial state
    await self.goto(url)
    await self.take_screenshot("initial_page")
    
    # After login
    await self.login(username, password)
    await self.take_screenshot("after_login")
    
    # After form filling
    await self.fill_form(form_data)
    await self.take_screenshot("form_filled")
    
    # After submission
    await self.click("button[type='submit']")
    await self.wait_for_navigation()
    await self.export_to_pdf("confirmation")
```

### 3. Error Handling

Handle errors gracefully:

```python
try:
    screenshot = await self.take_screenshot("debug_image")
    await self.checkpoint(f"Screenshot saved: {screenshot}")
except WorkflowError as e:
    await self.checkpoint(f"Screenshot failed: {str(e)}")
```

### 4. Managing Storage

Be mindful of storage usage:

- Screenshots can be large (typically 50-200 KB each)
- PDFs vary in size depending on page complexity
- Consider retention policies for old executions
- Clean up artifacts when execution is deleted (automatic via ResourceManager)

## Resource Cleanup

When an execution is deleted, all associated artifacts are automatically cleaned up:

```python
# All files in data/artifacts/{execution_id}/ are deleted
# All Resource entries in execution state are removed
```

This is handled automatically by the `ResourceManager.cleanup_execution()` method.

## Common Workflows

### Screenshot Series for Debugging

```python
async def execute(self, inputs):
    step_count = 0
    
    for step_data in inputs["steps"]:
        step_count += 1
        
        # Execute step
        await self.navigate_and_interact(step_data)
        
        # Capture for debugging
        await self.take_screenshot(f"step_{step_count:03d}")
        
        await self.checkpoint(f"Completed step {step_count}")
```

### Form Submission with Confirmation

```python
async def execute(self, inputs):
    # Fill and submit form
    await self.fill_form(inputs["form_data"])
    await self.take_screenshot("form_before_submit")
    
    await self.click("button[type='submit']")
    await self.wait_for_navigation()
    
    # Capture confirmation and export
    await self.take_screenshot("confirmation_page")
    confirmation_pdf = await self.export_to_pdf("form_submission_" + str(date.today()))
    
    return {
        "success": True,
        "confirmation_pdf": str(confirmation_pdf)
    }
```

### Automated Report Generation

```python
async def execute(self, inputs):
    # Navigate to report page
    await self.goto(inputs["report_url"])
    await self.wait_for_selector(".report-data")
    
    # Export report as PDF
    report_pdf = await self.export_to_pdf(f"report_{inputs['report_id']}")
    
    # Also capture screenshot for preview
    await self.take_screenshot(f"report_{inputs['report_id']}_preview")
    
    return {"report_pdf": str(report_pdf)}
```

## Troubleshooting

### Artifacts Not Being Saved

**Problem**: Screenshots or PDFs are not appearing in the data/artifacts/ directory.

**Solutions**:
1. Verify the page is active before calling the methods
2. Check that the workflow has proper async/await setup
3. Ensure data/ directory exists and is writable
4. Check execution logs for any WorkflowError exceptions

### Large PDF Files

**Problem**: PDF files are larger than expected.

**Solution**: This is normal when `print_background=True` is used (which captures background colors and images). The PDF export uses browser's print-to-PDF feature which includes full styling.

### Missing Artifacts in Execution State

**Problem**: `execution.state.resources` is empty even after calling take_screenshot().

**Solution**:
1. Verify you called `execution.save()` after capturing artifacts
2. Check that ResourceManager is properly initialized
3. Ensure execution_id is correctly set in the workflow

### File Path Issues

**Problem**: Cannot access artifact files using the returned Path objects.

**Solution**:
1. Use `str(path)` to convert Path to string when needed
2. Verify the working directory hasn't changed
3. Use absolute paths if available: `path.absolute()`

## See Also

- [Workflow Documentation](../docs/workflow-guide.md) - Complete workflow execution guide
- [Execution State Guide](../docs/execution-state-guide.md) - Understanding execution state
- [MCP Server Guide](../docs/mcp-server-guide.md) - MCP resource serving
