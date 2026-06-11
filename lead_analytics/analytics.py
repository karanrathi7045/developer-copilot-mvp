from __future__ import annotations

import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


DEFAULT_LEADS_PATH = Path("data/leads.csv")
DEFAULT_CONVERSATIONS_PATH = Path("data/conversations.csv")

CONVERTED_VALUES = {"converted", "won", "closed_won", "yes", "true", "1"}
OBJECTION_KEYWORDS = {
    "budget": ("budget", "price", "expensive", "cost", "discount"),
    "timing": ("timing", "later", "next quarter", "not now", "delay"),
    "authority": ("approval", "decision maker", "boss", "management", "committee"),
    "need": ("not needed", "no need", "already have", "current vendor"),
    "trust": ("trust", "case study", "reference", "security", "risk"),
    "competition": ("competitor", "alternative", "other vendor", "comparison"),
}


@dataclass(frozen=True)
class Dataset:
    leads: list[dict[str, Any]]
    conversations: list[dict[str, Any]]


def load_dataset(
    leads_path: str | Path = DEFAULT_LEADS_PATH,
    conversations_path: str | Path = DEFAULT_CONVERSATIONS_PATH,
) -> Dataset:
    return Dataset(
        leads=_read_csv(Path(leads_path)),
        conversations=_read_csv(Path(conversations_path)),
    )


def most_frequent_objections(
    dataset: Dataset,
    limit: int = 10,
) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()

    for row in dataset.conversations:
        explicit = _split_values(_first_value(row, "objection", "objections", "objection_type"))
        if explicit:
            counter.update(_normalize_label(value) for value in explicit)
            continue

        message = str(_first_value(row, "message", "notes", "transcript") or "").lower()
        for label, keywords in OBJECTION_KEYWORDS.items():
            if any(keyword in message for keyword in keywords):
                counter[label] += 1

    return [
        {"objection": objection, "count": count}
        for objection, count in counter.most_common(max(limit, 0))
    ]


def inactive_channel_partners(
    dataset: Dataset,
    inactive_days: int = 30,
    as_of: datetime | None = None,
) -> list[dict[str, Any]]:
    now = as_of or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=inactive_days)
    partners: dict[str, datetime | None] = {}

    for row in [*dataset.leads, *dataset.conversations]:
        partner = _normalize_partner(_first_value(row, "channel_partner", "partner", "partner_name"))
        if not partner:
            continue

        activity_at = _first_date(
            row,
            "last_activity_at",
            "conversation_at",
            "created_at",
            "updated_at",
            "date",
        )
        current = partners.get(partner)
        if current is None or (activity_at is not None and activity_at > current):
            partners[partner] = activity_at
        elif partner not in partners:
            partners[partner] = activity_at

    inactive = []
    for partner, last_activity_at in sorted(partners.items()):
        if last_activity_at is None or last_activity_at < cutoff:
            inactive.append(
                {
                    "channel_partner": partner,
                    "last_activity_at": _format_datetime(last_activity_at),
                    "inactive_days": None
                    if last_activity_at is None
                    else max((now.date() - last_activity_at.date()).days, 0),
                }
            )

    return inactive


def conversion_trends(dataset: Dataset, period: str = "month") -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, int]] = defaultdict(lambda: {"leads": 0, "converted": 0})

    for lead in dataset.leads:
        created_at = _first_date(lead, "created_at", "lead_created_at", "date")
        if created_at is None:
            continue

        bucket = _bucket(created_at, period)
        buckets[bucket]["leads"] += 1
        if _is_converted(lead):
            buckets[bucket]["converted"] += 1

    trends = []
    for bucket in sorted(buckets):
        leads = buckets[bucket]["leads"]
        converted = buckets[bucket]["converted"]
        trends.append(
            {
                "period": bucket,
                "leads": leads,
                "converted": converted,
                "conversion_rate": round(converted / leads, 4) if leads else 0,
            }
        )

    return trends


def structured_summary(
    dataset: Dataset,
    objection_limit: int = 10,
    inactive_days: int = 30,
    period: str = "month",
    as_of: datetime | None = None,
) -> dict[str, Any]:
    trends = conversion_trends(dataset, period=period)
    total_leads = sum(item["leads"] for item in trends)
    total_converted = sum(item["converted"] for item in trends)

    return {
        "metadata": {
            "lead_count": len(dataset.leads),
            "conversation_count": len(dataset.conversations),
            "period": period,
            "inactive_days": inactive_days,
            "generated_at": _format_datetime(as_of or datetime.now(timezone.utc)),
        },
        "metrics": {
            "total_leads_with_dates": total_leads,
            "total_converted": total_converted,
            "overall_conversion_rate": round(total_converted / total_leads, 4)
            if total_leads
            else 0,
        },
        "most_frequent_objections": most_frequent_objections(dataset, limit=objection_limit),
        "inactive_channel_partners": inactive_channel_partners(
            dataset,
            inactive_days=inactive_days,
            as_of=as_of,
        ),
        "conversion_trends": trends,
    }


def _read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")

    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [
            {str(key).strip(): value.strip() if isinstance(value, str) else value for key, value in row.items()}
            for row in csv.DictReader(handle)
        ]


def _first_value(row: dict[str, Any], *keys: str) -> Any:
    lowered = {key.lower(): value for key, value in row.items()}
    for key in keys:
        value = lowered.get(key.lower())
        if value not in (None, ""):
            return value
    return None


def _split_values(value: Any) -> list[str]:
    if value in (None, ""):
        return []

    values = [str(value)]
    for separator in (";", "|", ","):
        values = [part for item in values for part in item.split(separator)]

    return [item.strip() for item in values if item.strip()]


def _normalize_label(value: str) -> str:
    return " ".join(value.strip().lower().replace("_", " ").split())


def _normalize_partner(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return " ".join(str(value).strip().split())


def _first_date(row: dict[str, Any], *keys: str) -> datetime | None:
    for key in keys:
        parsed = _parse_datetime(_first_value(row, key))
        if parsed is not None:
            return parsed
    return None


def _parse_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None

    raw = str(value).strip()
    for suffix in ("Z", "z"):
        if raw.endswith(suffix):
            raw = f"{raw[:-1]}+00:00"

    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        for fmt in ("%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y"):
            try:
                parsed = datetime.combine(datetime.strptime(raw, fmt).date(), datetime.min.time())
                break
            except ValueError:
                parsed = None
        if parsed is None:
            return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _is_converted(lead: dict[str, Any]) -> bool:
    status = _first_value(lead, "status", "stage", "lead_status")
    converted = _first_value(lead, "converted", "is_converted")
    converted_at = _first_value(lead, "converted_at", "conversion_date", "closed_at")

    return (
        str(status or "").strip().lower() in CONVERTED_VALUES
        or str(converted or "").strip().lower() in CONVERTED_VALUES
        or converted_at not in (None, "")
    )


def _bucket(value: datetime, period: str) -> str:
    normalized = period.lower()
    if normalized == "day":
        return value.date().isoformat()
    if normalized == "week":
        year, week, _ = value.isocalendar()
        return f"{year}-W{week:02d}"
    if normalized == "month":
        return f"{value.year:04d}-{value.month:02d}"
    raise ValueError("period must be one of: day, week, month")


def _format_datetime(value: datetime | date | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return value.isoformat()
