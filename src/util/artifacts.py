import re
from pathlib import Path
from uuid import uuid4
from uuid import UUID
from typing import Literal
from urllib.parse import quote

from prefect.artifacts import create_link_artifact
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


def publish_file_link(
    path: str | Path,
    storage: Literal["local", "gcs"] = "local",
    *,
    key: str | None = None,
    description: str | None = None,
) -> UUID:
    """Publish a Prefect link to a local file or a placeholder GCS object."""
    if storage == "local":
        file_path = Path(path).expanduser().resolve(strict=True)
        if not file_path.is_file():
            raise ValueError(f"Not a file: {file_path}")
        link = file_path.as_uri()
        link_text = file_path.name
    elif storage == "gcs":
        # TODO: Upload the file and create an authenticated GCS link.
        link_text = f"GCS placeholder: {Path(path).name}"
        link = f"https://example.invalid/gcs-placeholder/{quote(Path(path).name)}"
        description = f"Placeholder only; no file was uploaded. {description or ''}".strip()
    else:
        raise ValueError(f"Unsupported artifact storage: {storage}")

    return create_link_artifact(
        link=link, link_text=link_text, key=key, description=description
    )
