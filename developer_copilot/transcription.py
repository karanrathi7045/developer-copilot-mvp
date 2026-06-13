from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from developer_copilot.config import Settings


@dataclass(frozen=True)
class TranscriptionResult:
    text: str | None
    ok: bool
    detail: str


def transcribe_twilio_media(
    settings: Settings,
    media_url: str | None,
    content_type: str | None,
) -> TranscriptionResult:
    if not media_url:
        return TranscriptionResult(text=None, ok=False, detail="No media URL provided")
    if content_type and not content_type.lower().startswith("audio/"):
        return TranscriptionResult(text=None, ok=False, detail=f"Unsupported media type: {content_type}")
    if not settings.openai_api_key and not settings.elevenlabs_api_key:
        return TranscriptionResult(
            text=None,
            ok=False,
            detail="OPENAI_API_KEY or ELEVENLABS_API_KEY is required to transcribe WhatsApp voice notes",
        )
    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        return TranscriptionResult(
            text=None,
            ok=False,
            detail="Twilio credentials are required to download WhatsApp voice notes",
        )

    try:
        import httpx
    except ImportError as exc:
        return TranscriptionResult(text=None, ok=False, detail=f"Missing dependency: {exc}")

    try:
        with httpx.Client(timeout=45, follow_redirects=True) as client:
            media_response = client.get(
                media_url,
                auth=(settings.twilio_account_sid, settings.twilio_auth_token),
            )
            media_response.raise_for_status()

        normalized_content_type = _normalized_content_type(content_type)
        filename = _filename_for_content_type(normalized_content_type)
        failures: list[str] = []

        if settings.openai_api_key:
            result = _transcribe_with_openai(
                settings=settings,
                filename=filename,
                content=media_response.content,
                content_type=normalized_content_type,
            )
            if result.ok:
                return result
            failures.append(f"OpenAI: {result.detail}")

        if settings.elevenlabs_api_key:
            result = _transcribe_with_elevenlabs(
                settings=settings,
                filename=filename,
                content=media_response.content,
                content_type=normalized_content_type,
            )
            if result.ok:
                return result
            failures.append(f"ElevenLabs: {result.detail}")

        return TranscriptionResult(
            text=None,
            ok=False,
            detail="; ".join(failures) or "No transcription provider was available",
        )
    except Exception as exc:
        return TranscriptionResult(text=None, ok=False, detail=str(exc))


def _transcribe_with_openai(
    settings: Settings,
    filename: str,
    content: bytes,
    content_type: str,
) -> TranscriptionResult:
    try:
        from openai import OpenAI
    except ImportError as exc:
        return TranscriptionResult(text=None, ok=False, detail=f"Missing dependency: {exc}")

    try:
        openai_client = OpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.openai_timeout_seconds,
            max_retries=0,
        )
        transcript = openai_client.audio.transcriptions.create(
            model=settings.openai_transcription_model,
            file=(filename, content, content_type),
        )
        text = getattr(transcript, "text", None)
        if not text:
            return TranscriptionResult(text=None, ok=False, detail="Transcription returned no text")
        return TranscriptionResult(text=text.strip(), ok=True, detail="Voice note transcribed by OpenAI")
    except Exception as exc:
        return TranscriptionResult(text=None, ok=False, detail=str(exc))


def _transcribe_with_elevenlabs(
    settings: Settings,
    filename: str,
    content: bytes,
    content_type: str,
) -> TranscriptionResult:
    try:
        import httpx
    except ImportError as exc:
        return TranscriptionResult(text=None, ok=False, detail=f"Missing dependency: {exc}")

    try:
        with httpx.Client(timeout=60) as client:
            response = client.post(
                "https://api.elevenlabs.io/v1/speech-to-text",
                headers={"xi-api-key": settings.elevenlabs_api_key or ""},
                data={
                    "model_id": settings.elevenlabs_stt_model_id,
                    "tag_audio_events": "false",
                },
                files={"file": (filename, content, content_type)},
            )
        if response.is_error:
            return TranscriptionResult(text=None, ok=False, detail=_http_error_detail(response))
        payload = response.json()
        text = payload.get("text") if isinstance(payload, dict) else None
        if not text:
            return TranscriptionResult(text=None, ok=False, detail="Transcription returned no text")
        return TranscriptionResult(text=str(text).strip(), ok=True, detail="Voice note transcribed by ElevenLabs")
    except Exception as exc:
        return TranscriptionResult(text=None, ok=False, detail=str(exc))


def _filename_for_content_type(content_type: str | None) -> str:
    normalized = _normalized_content_type(content_type)
    extension = {
        "audio/ogg": "ogg",
        "audio/opus": "ogg",
        "audio/mpeg": "mp3",
        "audio/mp3": "mp3",
        "audio/mp4": "m4a",
        "audio/x-m4a": "m4a",
        "audio/wav": "wav",
        "audio/wave": "wav",
        "audio/webm": "webm",
    }.get(normalized, "ogg")
    return f"whatsapp-voice-note.{extension}"


def _normalized_content_type(content_type: str | None) -> str:
    return (content_type or "audio/ogg").split(";", 1)[0].strip().lower()


def _http_error_detail(response: Any) -> str:
    try:
        payload = response.json()
    except Exception:
        payload = None
    if isinstance(payload, dict):
        detail = payload.get("detail") or payload.get("message") or payload.get("error")
        return str(detail) if detail else str(payload)
    return f"HTTP {response.status_code}: {response.text[:300]}"
