from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _optional_int(name: str, default: int | None = None) -> int | None:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    app_name: str = "Anarock PropPilot"
    environment: str = "local"
    base_url: str = "http://localhost:8000"

    data_source: str = "mock"
    fallback_to_mock: bool = True
    target_developer_id: int | None = 101
    developers_csv_path: Path = Path("data/developers.csv")
    leads_csv_path: Path = Path("data/leads.csv")
    projects_csv_path: Path = Path("data/projects.csv")
    inventory_csv_path: Path = Path("data/inventory.csv")
    bookings_csv_path: Path = Path("data/bookings.csv")
    channel_partner_csv_path: Path = Path("data/channel_partner.csv")
    generated_audio_dir: Path = Path("storage/voice_notes")
    generated_chart_dir: Path = Path("storage/charts")
    generated_transcript_dir: Path = Path("storage/transcripts")
    latest_briefing_path: Path = Path("storage/latest_briefing.json")

    snowflake_enabled: bool = False
    snowflake_account: str | None = None
    snowflake_user: str | None = None
    snowflake_password: str | None = None
    snowflake_role: str | None = None
    snowflake_warehouse: str | None = None
    snowflake_database: str | None = None
    snowflake_schema: str | None = None
    snowflake_developers_table: str = "DEVELOPERS"
    snowflake_leads_table: str = "LEADS"
    snowflake_projects_table: str = "PROJECTS"
    snowflake_inventory_table: str = "INVENTORY"
    snowflake_bookings_table: str = "BOOKINGS"
    snowflake_channel_partner_table: str = "CHANNEL_PARTNER"

    openai_api_key: str | None = None
    openai_model: str = "gpt-5.4-mini"
    openai_transcription_model: str = "whisper-1"
    openai_temperature: float = 0.2
    openai_timeout_seconds: float = 8.0

    elevenlabs_api_key: str | None = None
    elevenlabs_voice_id: str | None = None
    elevenlabs_model_id: str = "eleven_multilingual_v2"
    elevenlabs_stt_model_id: str = "scribe_v2"

    twilio_enabled: bool = False
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_whatsapp_from: str | None = None
    twilio_messaging_service_sid: str | None = None
    twilio_content_sid: str | None = None
    twilio_transcript_button_content_sid: str | None = None
    twilio_status_callback: str | None = None
    twilio_send_audio: bool = False

    scheduler_enabled: bool = True
    scheduler_timezone: str = "Asia/Kolkata"
    scheduler_hour: int = 8
    scheduler_minute: int = 0


def get_settings() -> Settings:
    return Settings(
        app_name=os.getenv("APP_NAME", "Anarock PropPilot"),
        environment=os.getenv("ENVIRONMENT", "local"),
        base_url=os.getenv("BASE_URL", "http://localhost:8000").rstrip("/"),
        data_source=os.getenv("DATA_SOURCE", "mock").strip().lower(),
        fallback_to_mock=_bool("FALLBACK_TO_MOCK", True),
        target_developer_id=_optional_int("TARGET_DEVELOPER_ID", 101),
        developers_csv_path=Path(os.getenv("DEVELOPERS_CSV_PATH", "data/developers.csv")),
        leads_csv_path=Path(os.getenv("LEADS_CSV_PATH", "data/leads.csv")),
        projects_csv_path=Path(os.getenv("PROJECTS_CSV_PATH", "data/projects.csv")),
        inventory_csv_path=Path(os.getenv("INVENTORY_CSV_PATH", "data/inventory.csv")),
        bookings_csv_path=Path(os.getenv("BOOKINGS_CSV_PATH", "data/bookings.csv")),
        channel_partner_csv_path=Path(os.getenv("CHANNEL_PARTNER_CSV_PATH", "data/channel_partner.csv")),
        generated_audio_dir=Path(os.getenv("GENERATED_AUDIO_DIR", "storage/voice_notes")),
        generated_chart_dir=Path(os.getenv("GENERATED_CHART_DIR", "storage/charts")),
        generated_transcript_dir=Path(os.getenv("GENERATED_TRANSCRIPT_DIR", "storage/transcripts")),
        latest_briefing_path=Path(os.getenv("LATEST_BRIEFING_PATH", "storage/latest_briefing.json")),
        snowflake_enabled=_bool("SNOWFLAKE_ENABLED", False),
        snowflake_account=os.getenv("SNOWFLAKE_ACCOUNT"),
        snowflake_user=os.getenv("SNOWFLAKE_USER"),
        snowflake_password=os.getenv("SNOWFLAKE_PASSWORD"),
        snowflake_role=os.getenv("SNOWFLAKE_ROLE"),
        snowflake_warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
        snowflake_database=os.getenv("SNOWFLAKE_DATABASE"),
        snowflake_schema=os.getenv("SNOWFLAKE_SCHEMA"),
        snowflake_developers_table=os.getenv("SNOWFLAKE_DEVELOPERS_TABLE", "DEVELOPERS"),
        snowflake_leads_table=os.getenv("SNOWFLAKE_LEADS_TABLE", "LEADS"),
        snowflake_projects_table=os.getenv("SNOWFLAKE_PROJECTS_TABLE", "PROJECTS"),
        snowflake_inventory_table=os.getenv("SNOWFLAKE_INVENTORY_TABLE", "INVENTORY"),
        snowflake_bookings_table=os.getenv("SNOWFLAKE_BOOKINGS_TABLE", "BOOKINGS"),
        snowflake_channel_partner_table=os.getenv("SNOWFLAKE_CHANNEL_PARTNER_TABLE", "CHANNEL_PARTNER"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5.4-mini"),
        openai_transcription_model=os.getenv("OPENAI_TRANSCRIPTION_MODEL", "whisper-1"),
        openai_temperature=float(os.getenv("OPENAI_TEMPERATURE", "0.2")),
        openai_timeout_seconds=float(os.getenv("OPENAI_TIMEOUT_SECONDS", "8.0")),
        elevenlabs_api_key=os.getenv("ELEVENLABS_API_KEY"),
        elevenlabs_voice_id=os.getenv("ELEVENLABS_VOICE_ID") or None,
        elevenlabs_model_id=os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2"),
        elevenlabs_stt_model_id=os.getenv("ELEVENLABS_STT_MODEL_ID", "scribe_v2"),
        twilio_enabled=_bool("TWILIO_ENABLED", False),
        twilio_account_sid=os.getenv("TWILIO_ACCOUNT_SID"),
        twilio_auth_token=os.getenv("TWILIO_AUTH_TOKEN"),
        twilio_whatsapp_from=os.getenv("TWILIO_WHATSAPP_FROM"),
        twilio_messaging_service_sid=os.getenv("TWILIO_MESSAGING_SERVICE_SID"),
        twilio_content_sid=os.getenv("TWILIO_CONTENT_SID"),
        twilio_transcript_button_content_sid=os.getenv("TWILIO_TRANSCRIPT_BUTTON_CONTENT_SID") or None,
        twilio_status_callback=os.getenv("TWILIO_STATUS_CALLBACK"),
        twilio_send_audio=_bool("TWILIO_SEND_AUDIO", False),
        scheduler_enabled=_bool("SCHEDULER_ENABLED", True),
        scheduler_timezone=os.getenv("SCHEDULER_TIMEZONE", "Asia/Kolkata"),
        scheduler_hour=_int("SCHEDULER_HOUR", 8),
        scheduler_minute=_int("SCHEDULER_MINUTE", 0),
    )
