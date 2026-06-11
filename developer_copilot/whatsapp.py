from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from developer_copilot.config import Settings


def send_whatsapp_briefing(
    settings: Settings,
    summary_text: str,
    developer: dict[str, Any] | None,
    audio_path: Path | None,
    audio_url: str | None,
    audio_mime_type: str | None,
) -> dict[str, Any]:
    recipient = _developer_whatsapp_to(developer)
    missing = [
        name
        for name, value in {
            "TWILIO_ACCOUNT_SID": settings.twilio_account_sid,
            "TWILIO_AUTH_TOKEN": settings.twilio_auth_token,
            "TWILIO_WHATSAPP_FROM or TWILIO_MESSAGING_SERVICE_SID": (
                settings.twilio_whatsapp_from or settings.twilio_messaging_service_sid
            ),
            "developer phone": recipient,
        }.items()
        if not value
    ]
    if not settings.twilio_enabled or missing:
        return {
            "provider": "twilio-mock",
            "sent": False,
            "recipient": recipient,
            "developer": _developer_name(developer),
            "detail": "Twilio disabled or missing configuration",
            "missing": missing,
            "text_preview": summary_text[:320],
        }

    try:
        import httpx
    except ImportError:
        return {"provider": "twilio", "sent": False, "detail": "httpx is not installed"}

    url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json"
    form = _twilio_form(settings, summary_text, recipient, audio_url, audio_path, audio_mime_type)
    audio_attached = "MediaUrl" in form

    try:
        with httpx.Client(timeout=45) as client:
            response = client.post(
                url,
                data=form,
                auth=(settings.twilio_account_sid or "", settings.twilio_auth_token or ""),
            )
            response.raise_for_status()
        payload = response.json()
        return {
            "provider": "twilio",
            "sent": True,
            "recipient": recipient,
            "developer": _developer_name(developer),
            "message_sid": payload.get("sid"),
            "status": payload.get("status"),
            "audio_attached": audio_attached,
            "detail": "WhatsApp briefing sent through Twilio",
        }
    except Exception as exc:
        return {
            "provider": "twilio",
            "sent": False,
            "recipient": recipient,
            "developer": _developer_name(developer),
            "detail": str(exc),
        }


def _twilio_form(
    settings: Settings,
    summary_text: str,
    recipient: str,
    audio_url: str | None,
    audio_path: Path | None,
    audio_mime_type: str | None,
) -> dict[str, str]:
    form: dict[str, str] = {"To": recipient}
    if settings.twilio_messaging_service_sid:
        form["MessagingServiceSid"] = settings.twilio_messaging_service_sid
    else:
        form["From"] = _normalize_whatsapp(settings.twilio_whatsapp_from or "")

    if settings.twilio_content_sid:
        form["ContentSid"] = settings.twilio_content_sid
        form["ContentVariables"] = json.dumps({"1": summary_text[:1500]})
    else:
        form["Body"] = summary_text[:1500]

    if settings.twilio_status_callback:
        form["StatusCallback"] = settings.twilio_status_callback

    public_media_url = _public_media_url(settings, audio_url, audio_path, audio_mime_type)
    if public_media_url:
        form["MediaUrl"] = public_media_url

    return form


def _public_media_url(
    settings: Settings,
    audio_url: str | None,
    audio_path: Path | None,
    audio_mime_type: str | None,
) -> str | None:
    if not settings.twilio_send_audio or not audio_url or not audio_path or not audio_path.exists():
        return None
    if not audio_mime_type:
        return None
    if settings.base_url.startswith(("http://localhost", "http://127.0.0.1")):
        return None
    return audio_url if audio_url.startswith("http") else f"{settings.base_url}{audio_url}"


def _developer_whatsapp_to(developer: dict[str, Any] | None) -> str | None:
    if not developer:
        return None
    country_code = _digits(developer.get("country_code"))
    phone = _digits(developer.get("developer_phone"))
    if not country_code or not phone:
        return None
    return f"whatsapp:+{country_code}{phone}"


def _normalize_whatsapp(value: str) -> str:
    raw = value.strip()
    if raw.startswith("whatsapp:+"):
        return raw
    return f"whatsapp:+{_digits(raw)}"


def _digits(value: Any) -> str:
    return "".join(char for char in str(value or "") if char.isdigit())


def _developer_name(developer: dict[str, Any] | None) -> str | None:
    if not developer:
        return None
    return str(developer.get("developer_name", "")).strip() or None
