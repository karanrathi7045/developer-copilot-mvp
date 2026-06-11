from __future__ import annotations

import math
import shutil
import subprocess
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from developer_copilot.config import Settings


@dataclass(frozen=True)
class VoiceResult:
    audio_path: Path | None
    audio_url: str | None
    mime_type: str | None
    status: dict[str, Any]


def create_voice_note(settings: Settings, text: str) -> VoiceResult:
    settings.generated_audio_dir.mkdir(parents=True, exist_ok=True)
    timestamp = int(time.time())
    provider_failures: list[dict[str, Any]] = []

    if settings.elevenlabs_api_key:
        filename = f"daily-briefing-{timestamp}.mp3"
        audio_path = settings.generated_audio_dir / filename
        status = _create_elevenlabs_mp3(settings, text, audio_path)
        if status.get("ok"):
            return VoiceResult(
                audio_path=audio_path,
                audio_url=f"/audio/{filename}",
                mime_type="audio/mpeg",
                status=status,
            )
        provider_failures.append(status)

    if settings.openai_api_key:
        filename = f"openai-briefing-{timestamp}.mp3"
        audio_path = settings.generated_audio_dir / filename
        status = _create_openai_speech_mp3(settings, text, audio_path)
        if status.get("ok"):
            return VoiceResult(
                audio_path=audio_path,
                audio_url=f"/audio/{filename}",
                mime_type="audio/mpeg",
                status=status,
            )
        provider_failures.append(status)

    filename = f"spoken-briefing-{timestamp}.m4a"
    audio_path = settings.generated_audio_dir / filename
    status = _create_macos_spoken_audio(text, audio_path, provider_failures)
    if status.get("ok"):
        return VoiceResult(
            audio_path=audio_path,
            audio_url=f"/audio/{filename}",
            mime_type="audio/mp4",
            status=status,
        )

    filename = f"mock-briefing-{timestamp}.wav"
    audio_path = settings.generated_audio_dir / filename
    _write_mock_wav(audio_path)
    return VoiceResult(
        audio_path=audio_path,
        audio_url=f"/audio/{filename}",
        mime_type="audio/wav",
        status={
            "provider": "mock",
            "ok": True,
            "detail": "Generated local demo tone because speech providers were unavailable.",
            "provider_failures": provider_failures,
        },
    )


def _create_elevenlabs_mp3(settings: Settings, text: str, audio_path: Path) -> dict[str, Any]:
    try:
        import httpx
    except ImportError:
        return {"provider": "elevenlabs", "ok": False, "detail": "httpx is not installed"}

    url = (
        "https://api.elevenlabs.io/v1/text-to-speech/"
        f"{settings.elevenlabs_voice_id}?output_format=mp3_44100_128"
    )
    payload = {
        "text": text,
        "model_id": settings.elevenlabs_model_id,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }
    headers = {
        "xi-api-key": settings.elevenlabs_api_key or "",
        "accept": "audio/mpeg",
        "content-type": "application/json",
    }

    try:
        with httpx.Client(timeout=45) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
        audio_path.write_bytes(response.content)
        return {"provider": "elevenlabs", "ok": True, "detail": "MP3 voice note generated"}
    except Exception as exc:
        return {"provider": "elevenlabs", "ok": False, "detail": str(exc)}


def _create_openai_speech_mp3(settings: Settings, text: str, audio_path: Path) -> dict[str, Any]:
    try:
        from openai import OpenAI
    except ImportError:
        return {"provider": "openai-tts", "ok": False, "detail": "openai is not installed"}

    try:
        client = OpenAI(api_key=settings.openai_api_key)
        response = client.audio.speech.create(
            model="gpt-4o-mini-tts",
            voice="alloy",
            input=text,
        )
        content = getattr(response, "content", None)
        if not content:
            return {"provider": "openai-tts", "ok": False, "detail": "OpenAI TTS returned no audio"}
        audio_path.write_bytes(content)
        return {"provider": "openai-tts", "ok": True, "detail": "MP3 voice note generated"}
    except Exception as exc:
        return {"provider": "openai-tts", "ok": False, "detail": str(exc)}


def _create_macos_spoken_audio(
    text: str,
    audio_path: Path,
    provider_failures: list[dict[str, Any]],
) -> dict[str, Any]:
    say_path = shutil.which("say")
    afconvert_path = shutil.which("afconvert")
    if not say_path or not afconvert_path:
        return {
            "provider": "macos-say",
            "ok": False,
            "detail": "macOS speech tools are not available",
            "provider_failures": provider_failures,
        }

    aiff_path = audio_path.with_suffix(".aiff")
    try:
        subprocess.run(
            [say_path, "-v", "Samantha", "-r", "175", "-o", str(aiff_path), text],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            [afconvert_path, "-f", "m4af", "-d", "aac", str(aiff_path), str(audio_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        return {
            "provider": "macos-say",
            "ok": True,
            "detail": "Generated narrated audio with macOS speech fallback",
            "provider_failures": provider_failures,
        }
    except Exception as exc:
        return {
            "provider": "macos-say",
            "ok": False,
            "detail": str(exc),
            "provider_failures": provider_failures,
        }
    finally:
        if aiff_path.exists():
            aiff_path.unlink()


def _write_mock_wav(path: Path) -> None:
    sample_rate = 16000
    duration_seconds = 1.5
    amplitude = 5000
    total_samples = int(sample_rate * duration_seconds)

    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        for index in range(total_samples):
            tone = math.sin(2 * math.pi * 440 * (index / sample_rate))
            value = int(amplitude * tone)
            handle.writeframesraw(value.to_bytes(2, byteorder="little", signed=True))
