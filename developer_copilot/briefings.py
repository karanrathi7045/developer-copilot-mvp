from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from lead_analytics.analytics import structured_summary

from developer_copilot.ai import reason_about_briefing
from developer_copilot.config import Settings
from developer_copilot.data_sources import ProjectData, load_project_data, select_developer_data
from developer_copilot.schemas import DailyBriefingResponse
from developer_copilot.voice import create_voice_note
from developer_copilot.whatsapp import send_whatsapp_briefing


def create_daily_briefing(settings: Settings, send_whatsapp: bool = False) -> DailyBriefingResponse:
    project_data = select_developer_data(
        load_project_data(settings),
        settings.target_developer_id,
    )
    deterministic = build_deterministic_briefing(project_data)
    ai_result = reason_about_briefing(settings, project_data, deterministic)
    fields = _normalize_briefing_fields(ai_result.payload)
    voice = create_voice_note(settings, fields["summary_text"])

    whatsapp_status = None
    if send_whatsapp:
        whatsapp_status = send_whatsapp_briefing(
            settings=settings,
            summary_text=fields["summary_text"],
            developer=project_data.developer,
            audio_path=voice.audio_path,
            audio_url=voice.audio_url,
            audio_mime_type=voice.mime_type,
        )

    response = DailyBriefingResponse(
        created_at=datetime.now(timezone.utc).isoformat(),
        data_source=project_data.source,
        developer=project_data.developer,
        top_objection=fields["top_objection"],
        conversion_trend=fields["conversion_trend"],
        inactive_cps=fields["inactive_cps"],
        inventory_opportunity=fields["inventory_opportunity"],
        recommendation=fields["recommendation"],
        summary_text=fields["summary_text"],
        audio_url=voice.audio_url,
        audio_path=str(voice.audio_path) if voice.audio_path else None,
        audio_mime_type=voice.mime_type,
        voice_status=voice.status,
        whatsapp_status=whatsapp_status,
        model=ai_result.model,
        used_mock=ai_result.used_mock,
    )
    save_latest_briefing(settings, response)
    return response


def load_latest_briefing(settings: Settings) -> dict[str, Any] | None:
    if not settings.latest_briefing_path.exists():
        return None
    try:
        return json.loads(settings.latest_briefing_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def save_latest_briefing(settings: Settings, briefing: DailyBriefingResponse) -> None:
    settings.latest_briefing_path.parent.mkdir(parents=True, exist_ok=True)
    payload = briefing.model_dump() if hasattr(briefing, "model_dump") else briefing.dict()
    settings.latest_briefing_path.write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )


def build_deterministic_briefing(project_data: ProjectData) -> dict[str, Any]:
    summary = structured_summary(project_data.analytics, inactive_days=30, period="month")
    top_objection = next(iter(summary["most_frequent_objections"]), None)
    inactive_cps = summary["inactive_channel_partners"][:5]
    conversion_trend = _conversion_trend(summary["conversion_trends"])
    inventory_opportunity = _inventory_opportunity(project_data.inventory)
    recommendation = _recommendation(top_objection, inactive_cps, inventory_opportunity)

    objection_text = (
        f"{top_objection['objection']} is the top objection with {top_objection['count']} mentions"
        if top_objection
        else "No dominant objection is visible yet"
    )
    inactive_text = (
        f"{len(inactive_cps)} inactive channel partners need follow-up"
        if inactive_cps
        else "No channel partners are inactive against the 30-day rule"
    )
    developer_name = (
        str(project_data.developer.get("developer_name"))
        if project_data.developer
        else "Developer"
    )
    summary_text = (
        f"Good morning {developer_name}. Anarock Buildr briefing. "
        f"{objection_text}. {conversion_trend}. {inactive_text}. "
        f"{inventory_opportunity}. Recommendation: {recommendation}"
    )

    return {
        "top_objection": top_objection,
        "conversion_trend": conversion_trend,
        "inactive_cps": inactive_cps,
        "inventory_opportunity": inventory_opportunity,
        "recommendation": recommendation,
        "summary_text": summary_text,
    }


def _normalize_briefing_fields(payload: dict[str, Any]) -> dict[str, Any]:
    top_objection = payload.get("top_objection")
    if top_objection is not None and not isinstance(top_objection, dict):
        top_objection = {"objection": str(top_objection), "count": None}

    inactive_cps = payload.get("inactive_cps")
    if not isinstance(inactive_cps, list):
        inactive_cps = []

    return {
        "top_objection": top_objection,
        "conversion_trend": str(payload.get("conversion_trend", "")).strip(),
        "inactive_cps": [item for item in inactive_cps if isinstance(item, dict)],
        "inventory_opportunity": str(payload.get("inventory_opportunity", "")).strip(),
        "recommendation": str(payload.get("recommendation", "")).strip(),
        "summary_text": str(payload.get("summary_text", "")).strip(),
    }


def _conversion_trend(trends: list[dict[str, Any]]) -> str:
    if not trends:
        return "Conversion trend is unavailable because dated leads are missing"
    if len(trends) == 1:
        latest = trends[-1]
        return f"Conversion is {latest['conversion_rate']:.0%} in {latest['period']}"

    previous = trends[-2]
    latest = trends[-1]
    delta = latest["conversion_rate"] - previous["conversion_rate"]
    direction = "up" if delta > 0 else "down" if delta < 0 else "flat"
    return (
        f"Conversion is {direction}: {previous['conversion_rate']:.0%} in {previous['period']} "
        f"to {latest['conversion_rate']:.0%} in {latest['period']}"
    )


def _inventory_opportunity(inventory: list[dict[str, Any]]) -> str:
    if not inventory:
        return "Inventory opportunity is unavailable until inventory data is connected"

    best = max(inventory, key=lambda row: _safe_int(row.get("available_units")))
    return (
        f"Prioritize {best.get('project', 'the project')} {best.get('configuration', best.get('unit_type', 'inventory'))}: "
        f"{best.get('available_units', 'available')} of {best.get('total_units', 'total')} units available, "
        f"{best.get('stage', 'active')} stage, aimed at {best.get('priority_segment', 'active buyers')}"
    )


def _recommendation(
    top_objection: dict[str, Any] | None,
    inactive_cps: list[dict[str, Any]],
    inventory_opportunity: str,
) -> str:
    objection = top_objection["objection"] if top_objection else "the leading objection"
    if inactive_cps:
        partner = inactive_cps[0]["channel_partner"]
        return (
            f"Send CPs a tight {objection} response, revive {partner}, "
            "and attach the priority inventory pocket to every warm lead today."
        )
    return (
        f"Package a sharper {objection} response and route new leads toward the inventory pocket with the clearest urgency."
    )


def _safe_int(value: Any) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0
