from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from lead_analytics.analytics import (
    DEFAULT_CONVERSATIONS_PATH,
    DEFAULT_LEADS_PATH,
    conversion_trends,
    inactive_channel_partners,
    load_dataset,
    most_frequent_objections,
    structured_summary,
)
from lead_analytics.bedrock_insights import (
    BedrockInsightConfig,
    BedrockInsightError,
    DEFAULT_AWS_REGION,
    DEFAULT_BEDROCK_MODEL_ID,
    generate_project_insights,
)

app = FastAPI(
    title="Lead Analytics Service",
    version="1.0.0",
    description="Reads lead and conversation CSVs and exposes sales-channel analytics.",
)


class ProjectInsightsRequest(BaseModel):
    project_analytics: dict[str, Any] = Field(
        ...,
        description="Project analytics JSON to analyze with Claude on AWS Bedrock.",
    )
    model_id: str | None = Field(
        None,
        description="Optional Bedrock model ID. Defaults to BEDROCK_MODEL_ID or Claude 3 Haiku.",
    )
    aws_region: str | None = Field(
        None,
        description="Optional AWS region. Defaults to AWS_REGION or us-east-1.",
    )
    max_tokens: int = Field(1200, ge=256, le=4096)
    temperature: float = Field(0.2, ge=0, le=1)


class ProjectInsightsResponse(BaseModel):
    executive_summary: str
    risks: list[str]
    opportunities: list[str]
    recommended_actions: list[str]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/analytics/objections")
def get_objections(
    leads_path: Path = Query(DEFAULT_LEADS_PATH),
    conversations_path: Path = Query(DEFAULT_CONVERSATIONS_PATH),
    limit: int = Query(10, ge=1, le=100),
) -> dict[str, object]:
    dataset = _load_or_404(leads_path, conversations_path)
    return {"items": most_frequent_objections(dataset, limit=limit)}


@app.get("/analytics/inactive-partners")
def get_inactive_partners(
    leads_path: Path = Query(DEFAULT_LEADS_PATH),
    conversations_path: Path = Query(DEFAULT_CONVERSATIONS_PATH),
    inactive_days: int = Query(30, ge=1, le=3650),
) -> dict[str, object]:
    dataset = _load_or_404(leads_path, conversations_path)
    return {"items": inactive_channel_partners(dataset, inactive_days=inactive_days)}


@app.get("/analytics/conversion-trends")
def get_conversion_trends(
    leads_path: Path = Query(DEFAULT_LEADS_PATH),
    conversations_path: Path = Query(DEFAULT_CONVERSATIONS_PATH),
    period: str = Query("month", pattern="^(day|week|month)$"),
) -> dict[str, object]:
    dataset = _load_or_404(leads_path, conversations_path)
    return {"items": conversion_trends(dataset, period=period)}


@app.get("/analytics/summary")
def get_summary(
    leads_path: Path = Query(DEFAULT_LEADS_PATH),
    conversations_path: Path = Query(DEFAULT_CONVERSATIONS_PATH),
    objection_limit: int = Query(10, ge=1, le=100),
    inactive_days: int = Query(30, ge=1, le=3650),
    period: str = Query("month", pattern="^(day|week|month)$"),
) -> dict[str, object]:
    dataset = _load_or_404(leads_path, conversations_path)
    return structured_summary(
        dataset,
        objection_limit=objection_limit,
        inactive_days=inactive_days,
        period=period,
    )


@app.post("/analytics/project-insights", response_model=ProjectInsightsResponse)
def create_project_insights(request: dict[str, Any] = Body(...)) -> dict[str, Any]:
    parsed_request = ProjectInsightsRequest(**request) if "project_analytics" in request else None
    project_analytics = (
        parsed_request.project_analytics
        if parsed_request is not None
        else request
    )
    config = BedrockInsightConfig(
        model_id=(parsed_request.model_id if parsed_request else None)
        or os.getenv("BEDROCK_MODEL_ID", DEFAULT_BEDROCK_MODEL_ID),
        region_name=(parsed_request.aws_region if parsed_request else None)
        or os.getenv("AWS_REGION", DEFAULT_AWS_REGION),
        max_tokens=parsed_request.max_tokens if parsed_request else 1200,
        temperature=parsed_request.temperature if parsed_request else 0.2,
    )

    try:
        return generate_project_insights(project_analytics, config=config)
    except BedrockInsightError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def _load_or_404(leads_path: Path, conversations_path: Path):
    try:
        return load_dataset(leads_path=leads_path, conversations_path=conversations_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
