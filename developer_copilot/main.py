from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import BackgroundTasks, FastAPI, Form, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from lead_analytics.analytics import structured_summary

from developer_copilot.ai import answer_question, generate_action
from developer_copilot.briefings import create_daily_briefing, load_latest_briefing
from developer_copilot.charts import create_question_chart
from developer_copilot.config import get_settings
from developer_copilot.data_sources import DataSourceError, load_project_data, select_developer_data
from developer_copilot.scheduler import start_scheduler, stop_scheduler
from developer_copilot.transcripts import load_voice_transcript, voice_transcript_html
from developer_copilot.schemas import (
    AskRequest,
    AskResponse,
    BriefingRequest,
    DailyBriefingResponse,
    GenerateActionRequest,
    GenerateActionResponse,
)
from developer_copilot.twilio_webhook import (
    answer_transcript_button,
    answer_whatsapp_question,
    send_whatsapp_followup_response,
    twiml_empty,
    twiml_message,
)

settings = get_settings()
settings.generated_audio_dir.mkdir(parents=True, exist_ok=True)
settings.generated_chart_dir.mkdir(parents=True, exist_ok=True)
settings.generated_transcript_dir.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(_: FastAPI):
    scheduler = start_scheduler(settings)
    try:
        yield
    finally:
        stop_scheduler(scheduler)


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Daily WhatsApp voice briefings, project Q&A, and sales action generation.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/audio", StaticFiles(directory=str(settings.generated_audio_dir)), name="audio")
app.mount("/charts", StaticFiles(directory=str(settings.generated_chart_dir)), name="charts")


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "app": settings.app_name,
        "data_source": settings.data_source,
        "snowflake_configured": settings.snowflake_enabled,
        "openai_configured": bool(settings.openai_api_key),
        "elevenlabs_configured": bool(settings.elevenlabs_api_key),
        "twilio_configured": settings.twilio_enabled and bool(settings.twilio_account_sid),
        "target_developer_id": settings.target_developer_id,
        "scheduler": {
            "enabled": settings.scheduler_enabled,
            "time": f"{settings.scheduler_hour:02d}:{settings.scheduler_minute:02d}",
            "timezone": settings.scheduler_timezone,
        },
    }


@app.get("/summary")
def get_summary() -> dict[str, Any]:
    project_data = _load_project_or_502()
    return {
        "data_source": project_data.source,
        "source_status": project_data.status,
        "developer": project_data.developer,
        "analytics": structured_summary(project_data.analytics, inactive_days=30, period="month"),
        "developers": project_data.developers,
        "leads": project_data.leads,
        "projects": project_data.projects,
        "inventory": project_data.inventory,
        "bookings": project_data.bookings,
        "channel_partners": project_data.channel_partners,
    }


@app.get("/developers")
def get_developers() -> dict[str, Any]:
    project_data = _load_all_project_data_or_502()
    return {
        "items": project_data.developers,
        "target_developer_id": settings.target_developer_id,
    }


@app.post("/briefing/daily", response_model=DailyBriefingResponse)
def daily_briefing(request: BriefingRequest) -> DailyBriefingResponse:
    try:
        return create_daily_briefing(settings, send_whatsapp=request.send_whatsapp)
    except DataSourceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/briefing/latest")
def latest_briefing() -> dict[str, Any]:
    briefing = load_latest_briefing(settings)
    if briefing is None:
        raise HTTPException(status_code=404, detail="No briefing has been generated yet")
    return briefing


@app.get("/transcripts/{transcript_id}", response_class=HTMLResponse)
def get_voice_transcript(transcript_id: str) -> HTMLResponse:
    record = load_voice_transcript(settings, transcript_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Transcript not found")
    return HTMLResponse(voice_transcript_html(record, settings.app_name))


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse:
    project_data = _load_project_or_502()
    result = answer_question(settings, project_data, request.question)
    chart = create_question_chart(settings, project_data, request.question)
    return AskResponse(
        answer=result.payload["answer"],
        evidence=result.payload["evidence"],
        data_source=project_data.source,
        model=result.model,
        used_mock=result.used_mock,
        chart_url=chart.chart_url if chart else None,
        chart_title=chart.title if chart else None,
        chart_type=chart.chart_type if chart else None,
        chart_mime_type=chart.mime_type if chart else None,
    )


@app.post("/generate-action", response_model=GenerateActionResponse)
def action(request: GenerateActionRequest) -> GenerateActionResponse:
    project_data = _load_project_or_502()
    request_payload = request.model_dump() if hasattr(request, "model_dump") else request.dict()
    result = generate_action(settings, project_data, request_payload)
    return GenerateActionResponse(
        cp_message=result.payload["cp_message"],
        sales_talking_points=result.payload["sales_talking_points"],
        objection_handlers=result.payload["objection_handlers"],
        next_steps=result.payload["next_steps"],
        data_source=project_data.source,
        model=result.model,
        used_mock=result.used_mock,
    )


@app.post("/twilio/whatsapp/webhook")
def twilio_whatsapp_webhook(
    background_tasks: BackgroundTasks,
    From: str = Form(...),  # noqa: N803 - Twilio sends title-case form fields.
    Body: str = Form(""),  # noqa: N803
    MessageSid: str | None = Form(None),  # noqa: N803
    NumMedia: str = Form("0"),  # noqa: N803
    MediaUrl0: str | None = Form(None),  # noqa: N803
    MediaContentType0: str | None = Form(None),  # noqa: N803
    ButtonText: str | None = Form(None),  # noqa: N803
    ButtonPayload: str | None = Form(None),  # noqa: N803
) -> Response:
    transcript_reply = answer_transcript_button(
        settings=settings,
        whatsapp_from=From,
        button_payload=ButtonPayload or Body,
        button_text=ButtonText or Body,
    )
    if transcript_reply:
        return Response(content=twiml_message(transcript_reply), media_type="application/xml")

    project_data = _load_all_project_data_or_502()
    inbound_media_url = MediaUrl0 if NumMedia != "0" else None
    is_voice_input = bool(inbound_media_url) and (
        not MediaContentType0
        or MediaContentType0.lower().startswith("audio/")
        or not Body.strip()
    )
    if is_voice_input:
        background_tasks.add_task(
            send_whatsapp_followup_response,
            settings,
            project_data,
            From,
            Body,
            inbound_media_url,
            MediaContentType0,
        )
        return Response(content=twiml_empty(), media_type="application/xml")

    result = answer_whatsapp_question(
        settings=settings,
        project_data=project_data,
        whatsapp_from=From,
        question=Body,
        media_url=inbound_media_url,
        media_content_type=MediaContentType0,
    )
    media_urls = [
        media_url
        for media_url in (result.get("reply_media_url"), result.get("chart_media_url"))
        if media_url
    ]
    return Response(
        content=twiml_message(
            result["reply"],
            media_urls=media_urls,
            include_body=result.get("reply_mode") != "voice",
        ),
        media_type="application/xml",
    )


def _load_project_or_502():
    project_data = _load_all_project_data_or_502()
    return select_developer_data(project_data, settings.target_developer_id)


def _load_all_project_data_or_502():
    try:
        return load_project_data(settings)
    except DataSourceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
