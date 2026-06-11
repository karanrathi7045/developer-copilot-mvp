from __future__ import annotations

from html import escape
from typing import Any

from developer_copilot.ai import answer_question
from developer_copilot.config import Settings
from developer_copilot.data_sources import ProjectData, select_developer_data_by_phone
from developer_copilot.transcription import transcribe_twilio_media


def answer_whatsapp_question(
    settings: Settings,
    project_data: ProjectData,
    whatsapp_from: str,
    question: str,
    media_url: str | None = None,
    media_content_type: str | None = None,
) -> dict[str, Any]:
    developer_data = select_developer_data_by_phone(project_data, whatsapp_from)
    if developer_data.developer is None:
        return {
            "reply": (
                "I could not find your WhatsApp number in the Developer Co-pilot developer table. "
                "Please ask the team to add your developer record first."
            ),
            "developer": None,
            "model": "none",
            "used_mock": True,
        }

    cleaned_question = question.strip()
    if not cleaned_question and media_url:
        transcription = transcribe_twilio_media(settings, media_url, media_content_type)
        if not transcription.ok or not transcription.text:
            return {
                "reply": (
                    "I received your voice note, but I could not transcribe it yet. "
                    "Please send the question as text, or configure OpenAI transcription."
                ),
                "developer": developer_data.developer,
                "model": "transcription-unavailable",
                "used_mock": True,
                "transcription_status": transcription.detail,
            }
        cleaned_question = transcription.text

    if not cleaned_question:
        return {
            "reply": "Send me a project question, for example: What is the top objection today?",
            "developer": developer_data.developer,
            "model": "none",
            "used_mock": True,
        }

    result = answer_question(settings, developer_data, cleaned_question)
    reply = result.payload["answer"]

    return {
        "reply": reply[:1500],
        "developer": developer_data.developer,
        "model": result.model,
        "used_mock": result.used_mock,
    }


def twiml_message(body: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f"<Response><Message>{escape(body)}</Message></Response>"
    )
