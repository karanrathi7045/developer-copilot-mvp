from __future__ import annotations

import json
import re
import secrets
from datetime import datetime, timezone
from html import escape
from typing import Any

from developer_copilot.config import Settings

_TRANSCRIPT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{12,80}$")
TRANSCRIPT_BUTTON_LABEL = "Show Transcript"
TRANSCRIPT_BUTTON_PAYLOAD_PREFIX = "show_transcript:"


def save_voice_transcript(
    settings: Settings,
    transcript: str,
    developer: dict[str, Any] | None,
    whatsapp_from: str | None = None,
    source: str = "whatsapp_voice_note",
) -> dict[str, Any]:
    settings.generated_transcript_dir.mkdir(parents=True, exist_ok=True)
    transcript_id = secrets.token_urlsafe(18)
    payload = {
        "id": transcript_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "developer": {
            "id": developer.get("id") or developer.get("ID") if developer else None,
            "name": developer.get("developer_name") or developer.get("DEVELOPER_NAME") if developer else None,
        },
        "whatsapp_from": _contact_key(whatsapp_from),
        "transcript": transcript.strip(),
    }
    _transcript_path(settings, transcript_id).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "id": transcript_id,
        "url": f"{settings.base_url}/transcripts/{transcript_id}",
        "created_at": payload["created_at"],
    }


def load_voice_transcript(settings: Settings, transcript_id: str) -> dict[str, Any] | None:
    if not _TRANSCRIPT_ID_RE.fullmatch(transcript_id):
        return None
    path = _transcript_path(settings, transcript_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def load_latest_voice_transcript(settings: Settings, whatsapp_from: str) -> dict[str, Any] | None:
    contact_key = _contact_key(whatsapp_from)
    if not contact_key or not settings.generated_transcript_dir.exists():
        return None

    latest: dict[str, Any] | None = None
    for path in settings.generated_transcript_dir.glob("*.json"):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if record.get("whatsapp_from") != contact_key:
            continue
        if latest is None or record.get("created_at", "") > latest.get("created_at", ""):
            latest = record
    return latest


def transcript_button_payload(transcript_id: str) -> str:
    return f"{TRANSCRIPT_BUTTON_PAYLOAD_PREFIX}{transcript_id}"


def transcript_id_from_button_payload(payload: str | None) -> str | None:
    if not payload:
        return None
    raw = payload.strip()
    if raw.startswith(TRANSCRIPT_BUTTON_PAYLOAD_PREFIX):
        transcript_id = raw.removeprefix(TRANSCRIPT_BUTTON_PAYLOAD_PREFIX)
        if _TRANSCRIPT_ID_RE.fullmatch(transcript_id):
            return transcript_id
    if _TRANSCRIPT_ID_RE.fullmatch(raw):
        return raw
    return None


def format_transcript_for_whatsapp(record: dict[str, Any]) -> str:
    transcript = (record.get("transcript") or "").strip()
    if not transcript:
        return "I could not find the transcript text for that voice note."
    return f"Transcript:\n{transcript}"[:1500]


def voice_transcript_html(record: dict[str, Any], app_name: str) -> str:
    developer = record.get("developer") or {}
    developer_name = developer.get("name") or "Developer"
    created_at = record.get("created_at", "")
    transcript = record.get("transcript", "")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex, nofollow">
  <meta property="og:title" content="Show Transcript">
  <meta property="og:description" content="{escape(app_name)} voice note transcript">
  <title>Show Transcript</title>
  <style>
    :root {{
      color-scheme: light;
      font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f4f6fb;
      color: #202231;
    }}
    body {{
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      padding: 28px;
    }}
    main {{
      width: min(720px, 100%);
      background: #fff;
      border: 1px solid #e2e6f0;
      border-radius: 18px;
      box-shadow: 0 18px 50px rgba(33, 37, 71, 0.10);
      padding: 28px;
    }}
    .eyebrow {{
      margin: 0 0 8px;
      color: #4b46b9;
      font-size: 13px;
      font-weight: 800;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    h1 {{
      margin: 0;
      font-size: 28px;
      line-height: 1.18;
    }}
    .meta {{
      margin: 10px 0 24px;
      color: #687083;
      font-size: 14px;
    }}
    .transcript {{
      white-space: pre-wrap;
      font-size: 19px;
      line-height: 1.55;
      padding: 22px;
      border-radius: 14px;
      background: #f7f8fc;
      border: 1px solid #e7eaf3;
    }}
  </style>
</head>
<body>
  <main>
    <p class="eyebrow">{escape(app_name)}</p>
    <h1>Voice note transcript</h1>
    <p class="meta">{escape(developer_name)} · {escape(created_at)}</p>
    <div class="transcript">{escape(transcript)}</div>
  </main>
</body>
</html>"""


def _transcript_path(settings: Settings, transcript_id: str):
    return settings.generated_transcript_dir / f"{transcript_id}.json"


def _contact_key(value: str | None) -> str | None:
    if not value:
        return None
    digits = "".join(char for char in value if char.isdigit())
    return digits or value.strip().lower()
