from __future__ import annotations

from dataclasses import dataclass

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
    if not settings.openai_api_key:
        return TranscriptionResult(
            text=None,
            ok=False,
            detail="OPENAI_API_KEY is required to transcribe WhatsApp voice notes",
        )
    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        return TranscriptionResult(
            text=None,
            ok=False,
            detail="Twilio credentials are required to download WhatsApp voice notes",
        )

    try:
        import httpx
        from openai import OpenAI
    except ImportError as exc:
        return TranscriptionResult(text=None, ok=False, detail=f"Missing dependency: {exc}")

    try:
        with httpx.Client(timeout=45, follow_redirects=True) as client:
            media_response = client.get(
                media_url,
                auth=(settings.twilio_account_sid, settings.twilio_auth_token),
            )
            media_response.raise_for_status()

        filename = _filename_for_content_type(content_type)
        openai_client = OpenAI(api_key=settings.openai_api_key)
        transcript = openai_client.audio.transcriptions.create(
            model=settings.openai_transcription_model,
            file=(filename, media_response.content, content_type or "audio/ogg"),
        )
        text = getattr(transcript, "text", None)
        if not text:
            return TranscriptionResult(text=None, ok=False, detail="Transcription returned no text")
        return TranscriptionResult(text=text.strip(), ok=True, detail="Voice note transcribed")
    except Exception as exc:
        return TranscriptionResult(text=None, ok=False, detail=str(exc))


def _filename_for_content_type(content_type: str | None) -> str:
    normalized = (content_type or "audio/ogg").split(";", 1)[0].lower()
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
