from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from lead_analytics.analytics import Dataset

from developer_copilot.config import Settings


class DataSourceError(RuntimeError):
    """Raised when project data cannot be loaded."""


@dataclass(frozen=True)
class ProjectData:
    analytics: Dataset
    developers: list[dict[str, Any]]
    leads: list[dict[str, Any]]
    projects: list[dict[str, Any]]
    inventory: list[dict[str, Any]]
    bookings: list[dict[str, Any]]
    channel_partners: list[dict[str, Any]]
    developer: dict[str, Any] | None
    source: str
    status: str


def load_project_data(settings: Settings) -> ProjectData:
    wants_snowflake = settings.snowflake_enabled or settings.data_source == "snowflake"
    if wants_snowflake:
        try:
            return _load_snowflake_data(settings)
        except Exception as exc:
            if not settings.fallback_to_mock:
                raise DataSourceError(str(exc)) from exc

    tables = {
        "developers": _read_csv(settings.developers_csv_path),
        "leads": _read_csv(settings.leads_csv_path),
        "projects": _read_csv(settings.projects_csv_path),
        "inventory": _read_csv(settings.inventory_csv_path),
        "bookings": _read_csv(settings.bookings_csv_path),
        "channel_partners": _read_csv(settings.channel_partner_csv_path),
    }
    _assert_mock_tables(tables)
    return _build_project_data(
        source="mock_csv",
        status="mock normalized CSV fallback",
        **tables,
    )


def _load_snowflake_data(settings: Settings) -> ProjectData:
    missing = [
        name
        for name, value in {
            "SNOWFLAKE_ACCOUNT": settings.snowflake_account,
            "SNOWFLAKE_USER": settings.snowflake_user,
            "SNOWFLAKE_PASSWORD": settings.snowflake_password,
            "SNOWFLAKE_WAREHOUSE": settings.snowflake_warehouse,
            "SNOWFLAKE_DATABASE": settings.snowflake_database,
            "SNOWFLAKE_SCHEMA": settings.snowflake_schema,
        }.items()
        if not value
    ]
    if missing:
        raise DataSourceError(f"Snowflake is enabled but missing: {', '.join(missing)}")

    try:
        import snowflake.connector
    except ImportError as exc:
        raise DataSourceError("snowflake-connector-python is not installed") from exc

    connection = snowflake.connector.connect(
        account=settings.snowflake_account,
        user=settings.snowflake_user,
        password=settings.snowflake_password,
        role=settings.snowflake_role,
        warehouse=settings.snowflake_warehouse,
        database=settings.snowflake_database,
        schema=settings.snowflake_schema,
    )

    try:
        developers = _fetch_table(connection, settings.snowflake_developers_table)
        leads = _fetch_table(connection, settings.snowflake_leads_table)
        projects = _fetch_table(connection, settings.snowflake_projects_table)
        inventory = _fetch_table(connection, settings.snowflake_inventory_table)
        bookings = _fetch_table(connection, settings.snowflake_bookings_table)
        channel_partners = _fetch_table(connection, settings.snowflake_channel_partner_table)
    finally:
        connection.close()

    return _build_project_data(
        developers=developers,
        leads=leads,
        projects=projects,
        inventory=inventory,
        bookings=bookings,
        channel_partners=channel_partners,
        source="snowflake",
        status="live Snowflake",
    )


def _build_project_data(
    developers: list[dict[str, Any]],
    leads: list[dict[str, Any]],
    projects: list[dict[str, Any]],
    inventory: list[dict[str, Any]],
    bookings: list[dict[str, Any]],
    channel_partners: list[dict[str, Any]],
    source: str,
    status: str,
) -> ProjectData:
    normalized_leads = [_lower_keys(row) for row in leads]
    normalized_developers = [_lower_keys(row) for row in developers]
    normalized_projects = [_lower_keys(row) for row in projects]
    normalized_inventory = [_lower_keys(row) for row in inventory]
    normalized_bookings = [_lower_keys(row) for row in bookings]
    normalized_channel_partners = [_lower_keys(row) for row in channel_partners]

    project_by_id = {_as_key(row.get("id")): row for row in normalized_projects}
    project_id_by_name = {
        str(row.get("name", "")).strip(): _as_key(row.get("id"))
        for row in normalized_projects
        if str(row.get("name", "")).strip()
    }
    bookings_by_lead: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for booking in normalized_bookings:
        bookings_by_lead[_as_key(booking.get("lead_id"))].append(booking)

    enriched_inventory = [
        _enrich_inventory_row(row, project_by_id)
        for row in normalized_inventory
    ]
    partner_activity = _partner_activity(
        normalized_channel_partners,
        project_id_by_name,
        normalized_leads,
        normalized_bookings,
    )
    analytics = Dataset(
        leads=_analytics_leads(normalized_leads, project_by_id, bookings_by_lead),
        conversations=_analytics_conversations(
            normalized_leads,
            normalized_channel_partners,
            project_by_id,
            bookings_by_lead,
            partner_activity,
        ),
    )

    return ProjectData(
        analytics=analytics,
        developers=normalized_developers,
        leads=normalized_leads,
        projects=normalized_projects,
        inventory=enriched_inventory,
        bookings=normalized_bookings,
        channel_partners=normalized_channel_partners,
        developer=None,
        source=source,
        status=status,
    )


def select_developer_data(project_data: ProjectData, developer_id: int | None) -> ProjectData:
    if developer_id is None:
        return project_data

    developer_key = _as_key(developer_id)
    developer = next(
        (row for row in project_data.developers if _as_key(row.get("id")) == developer_key),
        None,
    )
    if developer is None:
        return project_data

    projects = [
        row for row in project_data.projects
        if _as_key(row.get("developer_id")) == developer_key
    ]
    project_ids = {_as_key(row.get("id")) for row in projects}
    project_names = {str(row.get("name", "")).strip() for row in projects}
    leads = [
        row for row in project_data.leads
        if _as_key(row.get("project_id")) in project_ids
    ]
    lead_ids = {_as_key(row.get("id")) for row in leads}
    bookings = [
        row for row in project_data.bookings
        if _as_key(row.get("lead_id")) in lead_ids
    ]
    inventory = [
        row for row in project_data.inventory
        if _as_key(row.get("project_id")) in project_ids
    ]
    channel_partners = [
        row for row in project_data.channel_partners
        if project_names.intersection(set(_as_list(row.get("projects_working_on"))))
    ]
    filtered = _build_project_data(
        developers=project_data.developers,
        leads=leads,
        projects=projects,
        inventory=inventory,
        bookings=bookings,
        channel_partners=channel_partners,
        source=project_data.source,
        status=f"{project_data.status}; filtered to developer {developer.get('developer_name')}",
    )
    return ProjectData(
        analytics=filtered.analytics,
        developers=filtered.developers,
        leads=filtered.leads,
        projects=filtered.projects,
        inventory=filtered.inventory,
        bookings=filtered.bookings,
        channel_partners=filtered.channel_partners,
        developer=developer,
        source=filtered.source,
        status=filtered.status,
    )


def select_developer_data_by_phone(project_data: ProjectData, whatsapp_from: str) -> ProjectData:
    sender_digits = _digits(whatsapp_from)
    developer = next(
        (
            row for row in project_data.developers
            if sender_digits.endswith(
                f"{_digits(row.get('country_code'))}{_digits(row.get('developer_phone'))}"
            )
        ),
        None,
    )
    if developer is None:
        return project_data
    return select_developer_data(project_data, int(_as_key(developer.get("id"))))


def _analytics_leads(
    leads: list[dict[str, Any]],
    project_by_id: dict[str, dict[str, Any]],
    bookings_by_lead: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    rows = []
    for index, lead in enumerate(leads):
        lead_id = _as_key(lead.get("id"))
        bookings = bookings_by_lead.get(lead_id, [])
        project = project_by_id.get(_as_key(lead.get("project_id")), {})
        booking_dates = [_as_date(booking.get("booking_date")) for booking in bookings]
        converted_at = max([item for item in booking_dates if item], default=None)
        rows.append(
            {
                "lead_id": lead_id,
                "name": lead.get("name"),
                "project_id": lead.get("project_id"),
                "project": project.get("name"),
                "created_at": _synthetic_lead_date(index).isoformat(),
                "status": "converted" if converted_at else lead.get("status", ""),
                "converted_at": converted_at.isoformat() if converted_at else "",
            }
        )
    return rows


def _analytics_conversations(
    leads: list[dict[str, Any]],
    channel_partners: list[dict[str, Any]],
    project_by_id: dict[str, dict[str, Any]],
    bookings_by_lead: dict[str, list[dict[str, Any]]],
    partner_activity: dict[str, str],
) -> list[dict[str, Any]]:
    project_to_partner = _project_to_partner(channel_partners)
    rows: list[dict[str, Any]] = []

    for index, lead in enumerate(leads):
        lead_id = _as_key(lead.get("id"))
        project = project_by_id.get(_as_key(lead.get("project_id")), {})
        project_name = str(project.get("name", "")).strip()
        partner = project_to_partner.get(project_name, "Unassigned Channel")
        objection = _objection_from_status(str(lead.get("status", "")))
        bookings = bookings_by_lead.get(lead_id, [])
        booking_dates = [_as_date(booking.get("booking_date")) for booking in bookings]
        last_activity = max([item for item in booking_dates if item], default=None)
        if last_activity is None:
            last_activity = _synthetic_activity_date(index, lead.get("status", ""))

        rows.append(
            {
                "conversation_id": f"L-{lead_id}",
                "lead_id": lead_id,
                "channel_partner": partner,
                "created_at": _synthetic_lead_date(index).isoformat(),
                "last_activity_at": last_activity.isoformat(),
                "objection": objection,
                "message": _message_from_status(lead.get("status", ""), objection),
            }
        )

    for partner in channel_partners:
        cp_name = str(partner.get("cp_name", "")).strip()
        if not cp_name:
            continue
        rows.append(
            {
                "conversation_id": f"CP-{partner.get('id')}",
                "lead_id": "",
                "channel_partner": cp_name,
                "created_at": partner_activity.get(cp_name, "2026-01-15"),
                "last_activity_at": partner_activity.get(cp_name, "2026-01-15"),
                "objection": "",
                "message": "Channel partner portfolio activity snapshot.",
            }
        )

    return rows


def _partner_activity(
    channel_partners: list[dict[str, Any]],
    project_id_by_name: dict[str, str],
    leads: list[dict[str, Any]],
    bookings: list[dict[str, Any]],
) -> dict[str, str]:
    project_ids_by_lead = {
        _as_key(lead.get("id")): _as_key(lead.get("project_id"))
        for lead in leads
    }
    booking_dates_by_project: dict[str, list[date]] = defaultdict(list)
    for booking in bookings:
        lead_project_id = project_ids_by_lead.get(_as_key(booking.get("lead_id")))
        booking_date = _as_date(booking.get("booking_date"))
        if lead_project_id and booking_date:
            booking_dates_by_project[lead_project_id].append(booking_date)

    activity = {}
    for index, partner in enumerate(channel_partners):
        cp_name = str(partner.get("cp_name", "")).strip()
        project_dates = []
        for project_name in _as_list(partner.get("projects_working_on")):
            project_id = project_id_by_name.get(project_name)
            project_dates.extend(booking_dates_by_project.get(project_id, []))
        fallback = date(2026, 1, 10) + timedelta(days=index % 60)
        last_activity = max(project_dates, default=fallback)
        activity[cp_name] = last_activity.isoformat()
    return activity


def _project_to_partner(channel_partners: list[dict[str, Any]]) -> dict[str, str]:
    mapping = {}
    for partner in channel_partners:
        cp_name = str(partner.get("cp_name", "")).strip()
        for project_name in _as_list(partner.get("projects_working_on")):
            mapping.setdefault(project_name, cp_name)
    return mapping


def _enrich_inventory_row(
    row: dict[str, Any],
    project_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    project = project_by_id.get(_as_key(row.get("project_id")), {})
    configuration = row.get("configuration", "")
    return {
        **row,
        "project": project.get("name", "Unknown Project"),
        "developer_id": project.get("developer_id", ""),
        "stage": project.get("stage", ""),
        "unit_type": configuration,
        "priority_segment": _segment_for_configuration(str(configuration)),
    }


def _fetch_table(connection: Any, table_name: str) -> list[dict[str, Any]]:
    identifier = _validate_identifier(table_name)
    cursor = connection.cursor()
    try:
        cursor.execute(f"SELECT * FROM {identifier}")
        columns = [item[0].lower() for item in cursor.description]
        return [
            {column: _stringify(value) for column, value in zip(columns, row)}
            for row in cursor.fetchall()
        ]
    finally:
        cursor.close()


def _validate_identifier(identifier: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_.$\"]+", identifier):
        raise DataSourceError(f"Unsafe Snowflake table identifier: {identifier}")
    return identifier


def _assert_mock_tables(tables: dict[str, list[dict[str, Any]]]) -> None:
    missing = [name for name, rows in tables.items() if not rows]
    if missing:
        raise DataSourceError(f"Mock table files are missing or empty: {', '.join(missing)}")


def _read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [
            {str(key).strip().lower(): _decode_csv_value(value) for key, value in row.items()}
            for row in csv.DictReader(handle)
        ]


def _decode_csv_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    cleaned = value.strip()
    if cleaned.startswith("[") and cleaned.endswith("]"):
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return cleaned
    return cleaned


def _lower_keys(row: dict[str, Any]) -> dict[str, Any]:
    return {str(key).lower(): value for key, value in row.items()}


def _as_list(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    raw = str(value).strip()
    if raw.startswith("[") and raw.endswith("]"):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except json.JSONDecodeError:
            pass
    return [part.strip() for part in raw.split(",") if part.strip()]


def _as_key(value: Any) -> str:
    if value in (None, ""):
        return ""
    try:
        return str(int(float(str(value))))
    except ValueError:
        return str(value).strip()


def _digits(value: Any) -> str:
    return "".join(char for char in str(value or "") if char.isdigit())


def _as_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _synthetic_lead_date(index: int) -> date:
    return date(2026, 1, 1) + timedelta(days=index % 120)


def _synthetic_activity_date(index: int, status: Any) -> date:
    status_text = str(status).lower()
    if "inactive" in status_text or "lost" in status_text:
        return date(2026, 2, 1) + timedelta(days=index % 55)
    return date(2026, 5, 1) + timedelta(days=index % 25)


def _objection_from_status(status: str) -> str:
    normalized = status.lower()
    if "budget" in normalized:
        return "budget"
    if "timing" in normalized:
        return "timing"
    if "authority" in normalized:
        return "authority"
    if "competition" in normalized:
        return "competition"
    return ""


def _message_from_status(status: Any, objection: str) -> str:
    if objection == "budget":
        return "Buyer is interested but wants sharper pricing or payment-plan proof."
    if objection == "timing":
        return "Buyer asked to revisit later and needs a reason to move now."
    if objection == "authority":
        return "Buyer needs family or management approval before moving forward."
    if objection == "competition":
        return "Buyer is comparing this project against another option."
    return f"Lead status is {status}."


def _segment_for_configuration(configuration: str) -> str:
    normalized = configuration.lower()
    if "1 bhk" in normalized or "studio" in normalized:
        return "first-time buyers"
    if "2 bhk" in normalized:
        return "budget-qualified families"
    if "3 bhk" in normalized or "4 bhk" in normalized:
        return "upgrade buyers"
    if "retail" in normalized:
        return "investors"
    return "active buyers"


def _stringify(value: Any) -> Any:
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value
