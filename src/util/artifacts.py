import re
from pathlib import Path
from uuid import uuid4

from prefect.runtime import flow_run


def new_artifact_path(slug: str, extension: str = "png") -> Path:
    """Create a unique local artifact path for the current Prefect flow run."""
    if flow_run.id is None:
        raise RuntimeError("Artifact paths require a Prefect flow run")
    run_name = re.sub(r"[^a-zA-Z0-9_.-]+", "-", flow_run.name or "flow").strip(".-") or "flow"
    safe_slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", slug).strip("-") or "artifact"
    safe_extension = extension.lstrip(".")
    if not re.fullmatch(r"[a-zA-Z0-9]+", safe_extension):
        raise ValueError("Artifact extension must contain only letters and numbers")
    directory = Path("data/artifacts")
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{run_name}-{flow_run.id}-{safe_slug}-{uuid4().hex}.{safe_extension}"
