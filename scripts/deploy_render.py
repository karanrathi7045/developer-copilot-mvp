from __future__ import annotations

import os
import time
from typing import Any

import requests

try:
    from dotenv import load_dotenv

    load_dotenv(".env", override=True)
except ImportError:
    pass


API_BASE = "https://api.render.com/v1"
REPO_URL = "https://github.com/karanrathi7045/developer-copilot-mvp"
API_NAME = "developer-copilot-api"
DASHBOARD_NAME = "developer-copilot-dashboard"


def main() -> None:
    api_key = os.getenv("RENDER_API_KEY")
    if not api_key:
        raise SystemExit("Missing RENDER_API_KEY. Add it to .env and rerun.")

    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
    )
    owner_id = os.getenv("RENDER_OWNER_ID") or select_owner(session)

    api_service = ensure_service(session, owner_id, API_NAME, backend_payload(owner_id))
    api_url = service_url(api_service)
    if not api_url:
        raise SystemExit("Backend service was created but Render did not return a public URL yet.")

    for item in backend_env_vars():
        set_env_var(session, api_service["id"], item["key"], item["value"])
    set_env_var(session, api_service["id"], "BASE_URL", api_url)
    trigger_deploy(session, api_service["id"])

    dashboard_service = ensure_service(
        session,
        owner_id,
        DASHBOARD_NAME,
        dashboard_payload(owner_id, api_url),
    )
    set_env_var(session, dashboard_service["id"], "API_BASE_URL", api_url)
    trigger_deploy(session, dashboard_service["id"])

    print("Render services ready")
    print(f"Backend: {api_url}")
    print(f"Dashboard: {service_url(dashboard_service)}")
    print(f"Twilio webhook: {api_url}/twilio/whatsapp/webhook")


def select_owner(session: requests.Session) -> str:
    owners = request_json(session, "GET", f"{API_BASE}/owners")
    items = [item.get("owner", item) for item in owners]
    if not items:
        raise SystemExit("No Render workspace found for this API key.")
    if len(items) > 1:
        print("Multiple Render workspaces found:")
        for item in items:
            print(f"- {item.get('name')} ({item.get('type')}): {item.get('id')}")
        raise SystemExit("Set RENDER_OWNER_ID in .env to the workspace ID you want to use.")
    return items[0]["id"]


def ensure_service(
    session: requests.Session,
    owner_id: str,
    name: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    existing = find_service(session, owner_id, name)
    if existing:
        print(f"Using existing Render service: {name}")
        return existing
    response = request_json(session, "POST", f"{API_BASE}/services", json=payload)
    service = response.get("service", response)
    print(f"Created Render service: {name}")
    return service


def find_service(session: requests.Session, owner_id: str, name: str) -> dict[str, Any] | None:
    response = request_json(
        session,
        "GET",
        f"{API_BASE}/services",
        params={"ownerId": owner_id, "name": name, "limit": 20},
    )
    for item in response:
        service = item.get("service", item)
        if service.get("name") == name:
            return service
    return None


def backend_payload(owner_id: str) -> dict[str, Any]:
    return {
        "type": "web_service",
        "name": API_NAME,
        "ownerId": owner_id,
        "repo": REPO_URL,
        "branch": "main",
        "autoDeploy": "yes",
        "envVars": backend_env_vars(),
        "serviceDetails": {
            "runtime": "python",
            "plan": "free",
            "healthCheckPath": "/health",
            "envSpecificDetails": {
                "buildCommand": "pip install -r requirements.txt",
                "startCommand": "python -m uvicorn developer_copilot.main:app --host 0.0.0.0 --port $PORT",
            },
        },
    }


def dashboard_payload(owner_id: str, api_url: str) -> dict[str, Any]:
    return {
        "type": "web_service",
        "name": DASHBOARD_NAME,
        "ownerId": owner_id,
        "repo": REPO_URL,
        "branch": "main",
        "autoDeploy": "yes",
        "envVars": [{"key": "API_BASE_URL", "value": api_url}],
        "serviceDetails": {
            "runtime": "python",
            "plan": "free",
            "envSpecificDetails": {
                "buildCommand": "pip install -r requirements.txt",
                "startCommand": (
                    "streamlit run frontend/streamlit_app.py "
                    "--server.address 0.0.0.0 --server.port $PORT "
                    "--server.headless true --browser.gatherUsageStats false"
                ),
            },
        },
    }


def backend_env_vars() -> list[dict[str, str]]:
    values = {
        "ENVIRONMENT": "production",
        "DATA_SOURCE": os.getenv("DATA_SOURCE", "mock"),
        "FALLBACK_TO_MOCK": os.getenv("FALLBACK_TO_MOCK", "true"),
        "TARGET_DEVELOPER_ID": os.getenv("TARGET_DEVELOPER_ID", "101"),
        "SCHEDULER_ENABLED": os.getenv("SCHEDULER_ENABLED", "true"),
        "SCHEDULER_TIMEZONE": os.getenv("SCHEDULER_TIMEZONE", "Asia/Kolkata"),
        "SCHEDULER_HOUR": os.getenv("SCHEDULER_HOUR", "8"),
        "SCHEDULER_MINUTE": os.getenv("SCHEDULER_MINUTE", "0"),
        "TWILIO_SEND_AUDIO": os.getenv("TWILIO_SEND_AUDIO", "true"),
        "OPENAI_MODEL": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        "OPENAI_TEMPERATURE": os.getenv("OPENAI_TEMPERATURE", "0.2"),
        "OPENAI_TIMEOUT_SECONDS": os.getenv("OPENAI_TIMEOUT_SECONDS", "8.0"),
        "OPENAI_TRANSCRIPTION_MODEL": os.getenv("OPENAI_TRANSCRIPTION_MODEL", "whisper-1"),
        "TWILIO_ENABLED": os.getenv("TWILIO_ENABLED", "false"),
        "TWILIO_ACCOUNT_SID": os.getenv("TWILIO_ACCOUNT_SID", ""),
        "TWILIO_AUTH_TOKEN": os.getenv("TWILIO_AUTH_TOKEN", ""),
        "TWILIO_WHATSAPP_FROM": os.getenv("TWILIO_WHATSAPP_FROM", ""),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", ""),
        "ELEVENLABS_API_KEY": os.getenv("ELEVENLABS_API_KEY", ""),
        "ELEVENLABS_VOICE_ID": os.getenv("ELEVENLABS_VOICE_ID", ""),
        "ELEVENLABS_MODEL_ID": os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2"),
        "ELEVENLABS_STT_MODEL_ID": os.getenv("ELEVENLABS_STT_MODEL_ID", "scribe_v2"),
        "SNOWFLAKE_ENABLED": os.getenv("SNOWFLAKE_ENABLED", "false"),
        "SNOWFLAKE_ACCOUNT": os.getenv("SNOWFLAKE_ACCOUNT", ""),
        "SNOWFLAKE_USER": os.getenv("SNOWFLAKE_USER", ""),
        "SNOWFLAKE_PASSWORD": os.getenv("SNOWFLAKE_PASSWORD", ""),
        "SNOWFLAKE_ROLE": os.getenv("SNOWFLAKE_ROLE", ""),
        "SNOWFLAKE_WAREHOUSE": os.getenv("SNOWFLAKE_WAREHOUSE", ""),
        "SNOWFLAKE_DATABASE": os.getenv("SNOWFLAKE_DATABASE", ""),
        "SNOWFLAKE_SCHEMA": os.getenv("SNOWFLAKE_SCHEMA", ""),
    }
    return [{"key": key, "value": value} for key, value in values.items()]


def set_env_var(session: requests.Session, service_id: str, key: str, value: str) -> None:
    request_json(
        session,
        "PUT",
        f"{API_BASE}/services/{service_id}/env-vars/{key}",
        json={"value": value},
    )


def trigger_deploy(session: requests.Session, service_id: str) -> None:
    request_json(
        session,
        "POST",
        f"{API_BASE}/services/{service_id}/deploys",
        json={"clearCache": "do_not_clear"},
        allow_statuses={202},
    )
    time.sleep(1)


def service_url(service: dict[str, Any]) -> str | None:
    details = service.get("serviceDetails") or {}
    return details.get("url") or (f"https://{service.get('slug')}.onrender.com" if service.get("slug") else None)


def request_json(
    session: requests.Session,
    method: str,
    url: str,
    allow_statuses: set[int] | None = None,
    **kwargs: Any,
) -> Any:
    response = session.request(method, url, timeout=60, **kwargs)
    if allow_statuses and response.status_code in allow_statuses:
        return {}
    if not response.ok:
        raise SystemExit(f"Render API failed: {response.status_code} {response.text[:500]}")
    if response.status_code == 204:
        return {}
    return response.json()


if __name__ == "__main__":
    main()
