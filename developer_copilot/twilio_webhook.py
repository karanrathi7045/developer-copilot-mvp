from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any

from developer_copilot.ai import answer_question
from developer_copilot.charts import chart_payload, create_question_chart
from developer_copilot.config import Settings
from developer_copilot.data_sources import ProjectData, select_developer_data_by_phone
from developer_copilot.transcription import transcribe_twilio_media
from developer_copilot.transcripts import (
    TRANSCRIPT_BUTTON_LABEL,
    format_transcript_for_whatsapp,
    load_latest_voice_transcript,
    load_voice_transcript,
    save_voice_transcript,
    transcript_button_payload,
    transcript_id_from_button_payload,
)
from developer_copilot.voice import VoiceResult, create_voice_note


def send_whatsapp_followup_response(
    settings: Settings,
    project_data: ProjectData,
    whatsapp_from: str,
    question: str,
    media_url: str | None = None,
    media_content_type: str | None = None,
) -> dict[str, Any]:
    result = answer_whatsapp_question(
        settings=settings,
        project_data=project_data,
        whatsapp_from=whatsapp_from,
        question=question,
        media_url=media_url,
        media_content_type=media_content_type,
    )
    statuses: list[dict[str, Any]] = []

    if result.get("reply_mode") == "voice" and result.get("reply_media_url"):
        statuses.append(
            _send_twilio_reply(
                settings=settings,
                to=whatsapp_from,
                body=None,
                media_url=result["reply_media_url"],
            )
        )
        if result.get("chart_media_url"):
            statuses.append(
                _send_twilio_reply(
                    settings=settings,
                    to=whatsapp_from,
                    body=None,
                    media_url=result["chart_media_url"],
                )
            )
        if result.get("reply"):
            transcript = save_voice_transcript(
                settings=settings,
                transcript=result["reply"],
                developer=result.get("developer"),
                whatsapp_from=whatsapp_from,
                source="copilot_voice_reply",
            )
            statuses.append(
                _send_twilio_transcript_button(
                    settings=settings,
                    to=whatsapp_from,
                    transcript_id=transcript["id"],
                )
            )
    else:
        statuses.append(
            _send_twilio_reply(
                settings=settings,
                to=whatsapp_from,
                body=result["reply"],
                media_url=result.get("chart_media_url"),
            )
        )

    return {
        "reply_mode": result.get("reply_mode"),
        "chart_attached": bool(result.get("chart_media_url")),
        "transcript_button_sent": bool(result.get("reply") and result.get("reply_mode") == "voice"),
        "statuses": statuses,
    }


def answer_transcript_button(
    settings: Settings,
    whatsapp_from: str,
    button_payload: str | None = None,
    button_text: str | None = None,
) -> str | None:
    transcript_id = transcript_id_from_button_payload(button_payload)
    if transcript_id:
        record = load_voice_transcript(settings, transcript_id)
        if record is None:
            return "I could not find that transcript anymore. Please send the voice note again."
        return format_transcript_for_whatsapp(record)

    if (button_text or "").strip().lower() == TRANSCRIPT_BUTTON_LABEL.lower():
        record = load_latest_voice_transcript(settings, whatsapp_from)
        if record is None:
            return "I could not find a recent transcript for this chat. Please send the voice note again."
        return format_transcript_for_whatsapp(record)

    return None


def answer_whatsapp_question(
    settings: Settings,
    project_data: ProjectData,
    whatsapp_from: str,
    question: str,
    media_url: str | None = None,
    media_content_type: str | None = None,
) -> dict[str, Any]:
    developer_data = select_developer_data_by_phone(project_data, whatsapp_from)
    is_voice_input = _is_voice_note(media_url, media_content_type, question)
    if developer_data.developer is None:
        return _with_optional_voice_reply(
            settings,
            {
                "reply": (
                    "I could not find your WhatsApp number in the Anarock PropPilot developer table. "
                    "Please ask the team to add your developer record first."
                ),
                "developer": None,
                "model": "none",
                "used_mock": True,
            },
            is_voice_input,
        )

    cleaned_question = question.strip()
    if not cleaned_question and media_url:
        transcription = transcribe_twilio_media(settings, media_url, media_content_type)
        if not transcription.ok or not transcription.text:
            return _with_optional_voice_reply(
                settings,
                {
                    "reply": (
                        "I received your voice note, but I could not understand it yet. "
                        "Please send it again, or type the question once so I can help."
                    ),
                    "developer": developer_data.developer,
                    "model": "transcription-unavailable",
                    "used_mock": True,
                    "transcription_status": transcription.detail,
                },
                is_voice_input,
            )
        cleaned_question = transcription.text

    if not cleaned_question:
        return _with_optional_voice_reply(
            settings,
            {
                "reply": "Send me a project question, for example: What is the top objection today?",
                "developer": developer_data.developer,
                "model": "none",
                "used_mock": True,
            },
            is_voice_input,
        )

    result = answer_question(settings, developer_data, cleaned_question)
    reply = result.payload["answer"]

    response = {
        "reply": reply[:1500],
        "developer": developer_data.developer,
        "model": result.model,
        "used_mock": result.used_mock,
    }
    chart = create_question_chart(settings, developer_data, cleaned_question)
    if chart:
        response["chart"] = chart_payload(chart)
        response["chart_media_url"] = _public_media_url(settings, chart.chart_url, chart.chart_path, chart.mime_type)
    if is_voice_input:
        response["transcribed_question"] = cleaned_question
    return _with_optional_voice_reply(settings, response, is_voice_input)


def twiml_message(
    body: str,
    media_url: str | None = None,
    media_urls: list[str] | None = None,
    include_body: bool | None = None,
) -> str:
    media_items = [item for item in [media_url, *(media_urls or [])] if item]
    if media_items:
        should_include_body = include_body if include_body is not None else False
        if not should_include_body and len(media_items) > 1:
            messages_xml = "".join(
                f"<Message><Media>{escape(item)}</Media></Message>"
                for item in media_items
            )
            return '<?xml version="1.0" encoding="UTF-8"?>' f"<Response>{messages_xml}</Response>"
        body_xml = escape(body) if should_include_body else ""
        media_xml = "".join(f"<Media>{escape(item)}</Media>" for item in media_items)
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f"<Response><Message>{body_xml}{media_xml}</Message></Response>"
        )
    return '<?xml version="1.0" encoding="UTF-8"?>' f"<Response><Message>{escape(body)}</Message></Response>"


def twiml_empty() -> str:
    return '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'


def _is_voice_note(media_url: str | None, media_content_type: str | None, body: str) -> bool:
    if not media_url:
        return False
    content_type = (media_content_type or "").strip().lower()
    return content_type.startswith("audio/") or not body.strip()


def _with_optional_voice_reply(
    settings: Settings,
    response: dict[str, Any],
    is_voice_input: bool,
) -> dict[str, Any]:
    response["reply_mode"] = "text"
    if not is_voice_input:
        return response

    voice = create_voice_note(settings, response["reply"])
    media_url = _public_audio_url(settings, voice)
    response.update(
        {
            "reply_mode": "voice" if media_url else "text",
            "reply_media_url": media_url,
            "reply_media_mime_type": voice.mime_type,
            "voice_status": voice.status,
        }
    )
    return response


def _public_audio_url(settings: Settings, voice: VoiceResult) -> str | None:
    return _public_media_url(settings, voice.audio_url, voice.audio_path, voice.mime_type)


def _public_media_url(
    settings: Settings,
    media_url: str | None,
    media_path: Path | None,
    mime_type: str | None,
) -> str | None:
    if not media_url or not media_path or not media_path.exists():
        return None
    if not mime_type:
        return None
    if settings.base_url.startswith(("http://localhost", "http://127.0.0.1")):
        return None
    return media_url if media_url.startswith("http") else f"{settings.base_url}{media_url}"


def _send_twilio_reply(
    settings: Settings,
    to: str,
    body: str | None,
    media_url: str | None,
    content_sid: str | None = None,
    content_variables: dict[str, str] | None = None,
) -> dict[str, Any]:
    missing = [
        name
        for name, value in {
            "TWILIO_ACCOUNT_SID": settings.twilio_account_sid,
            "TWILIO_AUTH_TOKEN": settings.twilio_auth_token,
            "TWILIO_WHATSAPP_FROM or TWILIO_MESSAGING_SERVICE_SID": (
                settings.twilio_whatsapp_from or settings.twilio_messaging_service_sid
            ),
            "recipient": to,
        }.items()
        if not value
    ]
    if not settings.twilio_enabled or missing:
        return {
            "provider": "twilio-mock",
            "sent": False,
            "missing": missing,
            "media_url": media_url,
            "content_sid": content_sid,
            "text_preview": (body or "")[:160],
        }

    try:
        import httpx
    except ImportError:
        return {"provider": "twilio", "sent": False, "detail": "httpx is not installed"}

    form = {"To": _normalize_whatsapp(to)}
    if settings.twilio_messaging_service_sid:
        form["MessagingServiceSid"] = settings.twilio_messaging_service_sid
    else:
        form["From"] = _normalize_whatsapp(settings.twilio_whatsapp_from or "")
    if content_sid:
        form["ContentSid"] = content_sid
        if content_variables:
            form["ContentVariables"] = json.dumps(content_variables)
    elif body:
        form["Body"] = body[:1500]
    if media_url:
        form["MediaUrl"] = media_url

    url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json"
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
            "message_sid": payload.get("sid"),
            "status": payload.get("status"),
            "media_attached": bool(media_url),
            "content_attached": bool(content_sid),
        }
    except Exception as exc:
        return {
            "provider": "twilio",
            "sent": False,
            "detail": str(exc),
            "media_url": media_url,
            "content_sid": content_sid,
            "text_preview": (body or "")[:160],
        }


def _send_twilio_transcript_button(
    settings: Settings,
    to: str,
    transcript_id: str,
) -> dict[str, Any]:
    content_sid = settings.twilio_transcript_button_content_sid or _get_or_create_transcript_button_content_sid(settings)
    if not content_sid:
        return {
            "provider": "twilio",
            "sent": False,
            "detail": "Could not create or find the Twilio transcript button content SID",
        }

    return _send_twilio_reply(
        settings=settings,
        to=to,
        body=None,
        media_url=None,
        content_sid=content_sid,
        content_variables={"1": transcript_button_payload(transcript_id)},
    )


def _get_or_create_transcript_button_content_sid(settings: Settings) -> str | None:
    cache_path = settings.generated_transcript_dir / "_twilio_transcript_button_content.json"
    if cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            if cached.get("sid"):
                return cached["sid"]
        except json.JSONDecodeError:
            pass

    if not settings.twilio_enabled or not settings.twilio_account_sid or not settings.twilio_auth_token:
        return None

    try:
        import httpx
    except ImportError:
        return None

    payload = {
        "friendly_name": "anarock_propilot_show_transcript",
        "language": "en",
        "variables": {"1": "show_transcript:transcript_id"},
        "types": {
            "twilio/quick-reply": {
                "body": "Transcript is ready.",
                "actions": [
                    {
                        "title": TRANSCRIPT_BUTTON_LABEL,
                        "id": "{{1}}",
                    }
                ],
            }
        },
    }
    try:
        with httpx.Client(timeout=45) as client:
            response = client.post(
                "https://content.twilio.com/v1/Content",
                json=payload,
                auth=(settings.twilio_account_sid, settings.twilio_auth_token),
            )
            response.raise_for_status()
        sid = response.json().get("sid")
        if not sid:
            return None
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps({"sid": sid}, indent=2), encoding="utf-8")
        return sid
    except Exception:
        return None


def _normalize_whatsapp(value: str) -> str:
    raw = value.strip()
    if raw.startswith("whatsapp:+"):
        return raw
    return f"whatsapp:+{''.join(char for char in raw if char.isdigit())}"
