from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3)
    user_role: str = "developer"
    context: dict[str, Any] | None = None


class AskResponse(BaseModel):
    answer: str
    evidence: list[str]
    data_source: str
    model: str
    used_mock: bool
    chart_url: str | None = None
    chart_title: str | None = None
    chart_type: str | None = None
    chart_mime_type: str | None = None


class GenerateActionRequest(BaseModel):
    target: str = Field("channel partner", min_length=2)
    action_type: str = Field("cp_message", description="cp_message, sales_talking_points, or objection_handler")
    tone: str = "confident"
    context: str | None = None


class GenerateActionResponse(BaseModel):
    cp_message: str
    sales_talking_points: list[str]
    objection_handlers: list[str]
    next_steps: list[str]
    data_source: str
    model: str
    used_mock: bool


class BriefingRequest(BaseModel):
    send_whatsapp: bool = False


class DailyBriefingResponse(BaseModel):
    created_at: str
    data_source: str
    developer: dict[str, Any] | None = None
    top_objection: dict[str, Any] | None
    conversion_trend: str
    inactive_cps: list[dict[str, Any]]
    inventory_opportunity: str
    recommendation: str
    summary_text: str
    audio_url: str | None = None
    audio_path: str | None = None
    audio_mime_type: str | None = None
    voice_status: dict[str, Any]
    whatsapp_status: dict[str, Any] | None = None
    model: str
    used_mock: bool
