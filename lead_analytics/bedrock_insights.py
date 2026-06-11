from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any


DEFAULT_BEDROCK_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"
DEFAULT_AWS_REGION = "us-east-1"


class BedrockInsightError(RuntimeError):
    """Raised when Bedrock insight generation fails."""


@dataclass(frozen=True)
class BedrockInsightConfig:
    model_id: str = DEFAULT_BEDROCK_MODEL_ID
    region_name: str = DEFAULT_AWS_REGION
    max_tokens: int = 1200
    temperature: float = 0.2


def generate_project_insights(
    project_analytics: dict[str, Any],
    config: BedrockInsightConfig | None = None,
    client: Any | None = None,
) -> dict[str, Any]:
    active_config = config or BedrockInsightConfig(
        model_id=os.getenv("BEDROCK_MODEL_ID", DEFAULT_BEDROCK_MODEL_ID),
        region_name=os.getenv("AWS_REGION", DEFAULT_AWS_REGION),
    )
    bedrock_client = client or _create_bedrock_client(active_config.region_name)
    prompt = _build_prompt(project_analytics)
    payload = _build_bedrock_payload(prompt, active_config)

    try:
        response = bedrock_client.invoke_model(
            modelId=active_config.model_id,
            body=json.dumps(payload),
            contentType="application/json",
            accept="application/json",
        )
    except Exception as exc:
        raise BedrockInsightError(f"Bedrock invocation failed: {exc}") from exc

    try:
        raw_response = response["body"].read()
        model_response = json.loads(raw_response)
        text = model_response["content"][0]["text"]
        parsed = _parse_json_response(text)
    except Exception as exc:
        raise BedrockInsightError(f"Could not parse Bedrock response: {exc}") from exc

    return _normalize_insights(parsed)


def _create_bedrock_client(region_name: str):
    try:
        import boto3
    except ImportError as exc:
        raise BedrockInsightError(
            "boto3 is required for Bedrock calls. Install dependencies with `pip install -r requirements.txt`."
        ) from exc

    return boto3.client("bedrock-runtime", region_name=region_name)


def _build_prompt(project_analytics: dict[str, Any]) -> str:
    analytics_json = json.dumps(project_analytics, indent=2, sort_keys=True)
    return (
        "You are a senior revenue operations analyst. Review the project analytics JSON below "
        "and produce concise business-facing guidance.\n\n"
        "Return only valid JSON with this exact shape:\n"
        "{\n"
        '  "executive_summary": "string",\n'
        '  "risks": ["string"],\n'
        '  "opportunities": ["string"],\n'
        '  "recommended_actions": ["string"]\n'
        "}\n\n"
        "Project analytics JSON:\n"
        f"{analytics_json}"
    )


def _build_bedrock_payload(prompt: str, config: BedrockInsightConfig) -> dict[str, Any]:
    return {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": config.max_tokens,
        "temperature": config.temperature,
        "messages": [
            {
                "role": "user",
                "content": [{"type": "text", "text": prompt}],
            }
        ],
    }


def _parse_json_response(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```").strip()
        cleaned = cleaned.removesuffix("```").strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        parsed = json.loads(cleaned[start : end + 1])

    if not isinstance(parsed, dict):
        raise ValueError("Claude response must be a JSON object")
    return parsed


def _normalize_insights(parsed: dict[str, Any]) -> dict[str, Any]:
    return {
        "executive_summary": str(parsed.get("executive_summary", "")).strip(),
        "risks": _as_string_list(parsed.get("risks")),
        "opportunities": _as_string_list(parsed.get("opportunities")),
        "recommended_actions": _as_string_list(parsed.get("recommended_actions")),
    }


def _as_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []
