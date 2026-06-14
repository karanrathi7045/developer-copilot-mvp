from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from developer_copilot.config import Settings

MAX_HISTORY_ITEMS = 200


def load_chat_history(settings: Settings, limit: int = 50) -> list[dict[str, Any]]:
    items = _read_history(settings)
    limit = max(1, min(limit, MAX_HISTORY_ITEMS))
    return items[-limit:]


def append_chat_messages(settings: Settings, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    existing = _read_history(settings)
    normalized = [_normalize_message(message) for message in messages]
    normalized = [message for message in normalized if message]
    if not normalized:
        return existing

    combined = _dedupe_messages([*existing, *normalized])[-MAX_HISTORY_ITEMS:]
    settings.chat_history_path.parent.mkdir(parents=True, exist_ok=True)
    settings.chat_history_path.write_text(
        json.dumps(combined, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return combined


def _read_history(settings: Settings) -> list[dict[str, Any]]:
    if not settings.chat_history_path.exists():
        return []
    try:
        payload = json.loads(settings.chat_history_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    return [message for message in (_normalize_message(item) for item in payload) if message]


def _normalize_message(message: Any) -> dict[str, Any] | None:
    if not isinstance(message, dict):
        return None
    role = str(message.get("role") or "").strip().lower()
    if role not in {"assistant", "user"}:
        return None
    content = str(message.get("content") or "").strip()
    if not content:
        return None

    normalized: dict[str, Any] = {
        "role": role,
        "content": content[:3000],
        "created_at": str(message.get("created_at") or datetime.now(timezone.utc).isoformat()),
    }
    for key in ("chart_url", "chart_title"):
        value = message.get(key)
        if value:
            normalized[key] = str(value)
    return normalized


def _dedupe_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str | None]] = set()
    deduped: list[dict[str, Any]] = []
    for message in messages:
        key = (message["role"], message["content"], message.get("chart_url"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(message)
    return deduped
