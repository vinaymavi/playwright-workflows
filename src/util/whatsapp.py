"""Send WhatsApp Cloud API text and local image messages."""

import mimetypes
import re
from pathlib import Path
from typing import Any

import httpx
from prefect.blocks.system import Secret
from prefect.variables import Variable


def _check_response(response: httpx.Response, operation: str, token: str) -> None:
    """Include Meta's error details without exposing the access token."""
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError:
        try:
            error = response.json().get("error", {})
            if not isinstance(error, dict):
                error = {}
        except (ValueError, AttributeError):
            error = {}
        details = ", ".join(
            f"{key}={str(error[key]).replace(token, '[redacted]')}"
            for key in ("code", "error_subcode", "type", "message", "fbtrace_id")
            if key in error
        )
        raise RuntimeError(
            f"WhatsApp {operation} failed (HTTP {response.status_code})"
            + (f": {details}" if details else "")
        ) from None


def send_message(
    recipient: str,
    *,
    text: str | None = None,
    image_path: str | Path | None = None,
    template_name: str | None = None,
    template_language: str = "en_US",
    template_body_parameters: list[str] | None = None,
) -> dict[str, Any]:
    """Send text, an image, or an image with a text caption via Meta Cloud API.

    The sender ID and Graph API version come from Prefect Variables.
    The recipient is a phone number in international format.
    """
    if not template_name and not text and image_path is None:
        raise ValueError("Provide text, an image, or both")
    if template_name and text is not None:
        raise ValueError("For templates, provide dynamic body values as template_body_parameters")
    if not template_name and template_body_parameters is not None:
        raise ValueError("template_body_parameters requires template_name")
    phone_number_id = Variable.get("whatsapp_phone_number_id")
    api_version = Variable.get("whatsapp_api_version")
    if not isinstance(phone_number_id, str) or not isinstance(api_version, str):
        raise ValueError("Prefect variables whatsapp_phone_number_id and whatsapp_api_version must be strings")
    if not re.fullmatch(r"v\d+\.\d+", api_version):
        raise ValueError("api_version must look like v25.0")
    if not phone_number_id.isdigit():
        raise ValueError("phone_number_id must contain only digits")
    if not re.fullmatch(r"\+?\d+", recipient):
        raise ValueError("recipient must be a phone number in international format")

    token = Secret.load("whatsapp-token").get()
    if not isinstance(token, str) or not token:
        raise ValueError("whatsapp-token must contain a non-empty string")
    base_url = f"https://graph.facebook.com/{api_version}/{phone_number_id}"
    headers = {"Authorization": f"Bearer {token}"}
    payload: dict[str, Any] = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient.lstrip("+"),
    }

    with httpx.Client(timeout=30.0, follow_redirects=False) as client:
        media_id = None
        if image_path is not None:
            path = Path(image_path).expanduser().resolve(strict=True)
            mime_type, _ = mimetypes.guess_type(path.name)
            if not path.is_file() or mime_type not in {"image/jpeg", "image/png"}:
                raise ValueError("image_path must be a PNG or JPEG file")
            with path.open("rb") as image_file:
                response = client.post(
                    f"{base_url}/media",
                    headers=headers,
                    data={"messaging_product": "whatsapp", "type": mime_type},
                    files={"file": (path.name, image_file, mime_type)},
                )
            _check_response(response, "media upload", token)
            media_id = response.json()["id"]
        if template_name:
            components: list[dict[str, Any]] = []
            if media_id:
                components.append({"type": "header", "parameters": [{"type": "image", "image": {"id": media_id}}]})
            if template_body_parameters:
                components.append({"type": "body", "parameters": [{"type": "text", "text": value} for value in template_body_parameters]})
            template: dict[str, Any] = {"name": template_name, "language": {"code": template_language}}
            if components:
                template["components"] = components
            payload.update(type="template", template=template)
        elif media_id is not None:
            image = {"id": media_id}
            if text:
                image["caption"] = text
            payload.update(type="image", image=image)
        else:
            payload.update(type="text", text={"body": text})

        response = client.post(f"{base_url}/messages", headers=headers, json=payload)
        _check_response(response, "message send", token)
        return response.json()
