"""Send transactional emails using the Resend API."""

import base64
from pathlib import Path
from typing import Any

import httpx
from prefect.blocks.system import Secret


def send_email(
    recipient: str,
    sender: str,
    subject: str,
    *,
    text: str | None = None,
    html: str | None = None,
    attachments: list[str | Path] | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Send text or HTML email, optionally with local file attachments.

    The Resend API key is read from the ``resend-api-key`` Prefect Secret.
    """
    if not recipient.strip() or not sender.strip() or not subject.strip():
        raise ValueError("recipient, sender, and subject must be non-empty")
    if not text and not html:
        raise ValueError("Provide text or html email content")

    payload: dict[str, Any] = {"from": sender, "to": [recipient], "subject": subject}
    if text is not None:
        payload["text"] = text
    if html is not None:
        payload["html"] = html
    if attachments:
        payload["attachments"] = []
        for attachment in attachments:
            path = Path(attachment).expanduser().resolve(strict=True)
            if not path.is_file():
                raise ValueError(f"Not a file: {path}")
            payload["attachments"].append(
                {"filename": path.name, "content": base64.b64encode(path.read_bytes()).decode("ascii")}
            )

    token = Secret.load("resend-api-key").get()
    if not isinstance(token, str) or not token:
        raise ValueError("resend-api-key must contain a non-empty string")
    headers = {"Authorization": f"Bearer {token}"}
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key

    with httpx.Client(timeout=30.0, follow_redirects=False) as client:
        response = client.post("https://api.resend.com/emails", headers=headers, json=payload)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError:
            try:
                error = response.json()
                message = str(error.get("message", "")) if isinstance(error, dict) else ""
            except ValueError:
                message = ""
            message = message.replace(token, "[redacted]")
            raise RuntimeError(
                f"Resend email request failed (HTTP {response.status_code})"
                + (f": {message}" if message else "")
            ) from None
        return response.json()
