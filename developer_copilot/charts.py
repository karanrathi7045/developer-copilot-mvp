from __future__ import annotations

import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from PIL import Image, ImageDraw, ImageFont

from lead_analytics.analytics import structured_summary

from developer_copilot.config import Settings
from developer_copilot.data_sources import ProjectData


BRAND = "#4447b8"
INK = "#171923"
MUTED = "#748094"
LINE = "#e4e8f0"
PANEL = "#ffffff"
GREEN = "#57b96c"
ORANGE = "#ed845d"
PINK = "#e9587f"
PURPLE = "#9b7cf4"


@dataclass(frozen=True)
class ChartResult:
    chart_path: Path
    chart_url: str
    mime_type: str
    title: str
    chart_type: str


def create_question_chart(
    settings: Settings,
    project_data: ProjectData,
    question: str,
) -> ChartResult | None:
    spec = _chart_spec(question)
    if spec is None:
        return None

    rows = _chart_rows(project_data, question, spec)
    if not rows:
        return None

    settings.generated_chart_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{spec['kind']}-{int(time.time())}-{uuid4().hex[:8]}.png"
    chart_path = settings.generated_chart_dir / filename

    if spec["kind"] == "conversion-trend":
        _draw_line_chart(chart_path, spec["title"], rows)
    else:
        _draw_bar_chart(chart_path, spec["title"], spec["subtitle"], rows, spec["value_format"])

    return ChartResult(
        chart_path=chart_path,
        chart_url=f"/charts/{filename}",
        mime_type="image/png",
        title=spec["title"],
        chart_type=spec["kind"],
    )


def chart_payload(chart: ChartResult | None) -> dict[str, Any] | None:
    if chart is None:
        return None
    return {
        "url": chart.chart_url,
        "title": chart.title,
        "type": chart.chart_type,
        "mime_type": chart.mime_type,
    }


def _chart_spec(question: str) -> dict[str, Any] | None:
    text = " ".join(question.lower().split())
    wants_visual = _has_any(
        text,
        "analysis",
        "analyze",
        "deep",
        "chart",
        "graph",
        "visual",
        "plot",
        "trend",
        "breakdown",
        "compare",
        "show",
    )

    if _has_any(text, "conversion", "trend", "convert"):
        return {
            "kind": "conversion-trend",
            "title": "Conversion Trend",
            "subtitle": "Monthly lead-to-booking conversion",
            "value_format": "percent",
        }
    if _has_any(text, "inventory", "unit", "stock", "available", "push"):
        return {
            "kind": "inventory",
            "title": "Inventory Opportunity",
            "subtitle": "Available units by project and configuration",
            "value_format": "count",
        }
    if _has_any(text, "booking", "booked", "agreement", "revenue", "brokerage", "sales value", "gmv"):
        value_format = "money"
        title = "Agreement Value by Configuration"
        if _has_any(text, "brokerage", "commission"):
            title = "Brokerage by Configuration"
        return {
            "kind": "bookings",
            "title": title,
            "subtitle": "Booked value from matched leads",
            "value_format": value_format,
        }
    if _has_any(text, "inactive", "partner", "channel partner", "cp", "broker"):
        return {
            "kind": "inactive-cps",
            "title": "Inactive Channel Partners",
            "subtitle": "Longest inactivity among matched CPs",
            "value_format": "days",
        }
    if _has_any(text, "objection", "concern", "lost reason", "budget", "why are leads"):
        return {
            "kind": "objections",
            "title": "Top Buyer Objections",
            "subtitle": "Objection mentions from project activity",
            "value_format": "count",
        }
    if wants_visual or _has_any(text, "lead", "pipeline", "status"):
        return {
            "kind": "lead-status",
            "title": "Lead Pipeline Status",
            "subtitle": "Matched leads by current status",
            "value_format": "count",
        }
    return None


def _chart_rows(
    project_data: ProjectData,
    question: str,
    spec: dict[str, Any],
) -> list[dict[str, Any]]:
    kind = spec["kind"]
    if kind == "conversion-trend":
        summary = structured_summary(project_data.analytics, inactive_days=30, period="month")
        return [
            {
                "label": row["period"],
                "value": float(row["conversion_rate"]) * 100,
                "detail": f"{row['converted']}/{row['leads']} converted",
            }
            for row in summary["conversion_trends"]
        ]

    if kind == "inventory":
        rows = [
            {
                "label": f"{row.get('project', 'Project')} {row.get('configuration', row.get('unit_type', 'Units'))}",
                "value": _safe_float(row.get("available_units")),
                "detail": f"{row.get('available_units', 0)}/{row.get('total_units', 'total')} available",
            }
            for row in project_data.inventory
        ]
        return sorted(rows, key=lambda item: item["value"], reverse=True)[:8]

    if kind == "bookings":
        wants_brokerage = _has_any(question.lower(), "brokerage", "commission")
        grouped: dict[str, float] = defaultdict(float)
        for row in project_data.bookings:
            label = str(row.get("configuration") or "Unknown").strip() or "Unknown"
            field = "brokerage_amount" if wants_brokerage else "agreement_value"
            grouped[label] += _safe_float(row.get(field))
        return [
            {"label": label, "value": value, "detail": _money(value)}
            for label, value in sorted(grouped.items(), key=lambda item: item[1], reverse=True)
        ]

    if kind == "inactive-cps":
        summary = structured_summary(project_data.analytics, inactive_days=30, period="month")
        rows = [
            {
                "label": str(item.get("channel_partner", "Channel partner")),
                "value": _safe_float(item.get("inactive_days")),
                "detail": f"{item.get('inactive_days') or 0} days",
            }
            for item in summary["inactive_channel_partners"]
        ]
        return sorted(rows, key=lambda item: item["value"], reverse=True)[:8]

    if kind == "objections":
        summary = structured_summary(project_data.analytics, inactive_days=30, period="month")
        return [
            {
                "label": str(item.get("objection", "Objection")).title(),
                "value": _safe_float(item.get("count")),
                "detail": f"{item.get('count', 0)} mentions",
            }
            for item in summary["most_frequent_objections"][:8]
        ]

    statuses = Counter(str(row.get("status") or "Unknown").strip() or "Unknown" for row in project_data.leads)
    return [
        {"label": label, "value": value, "detail": f"{value} leads"}
        for label, value in statuses.most_common(8)
    ]


def _draw_bar_chart(
    path: Path,
    title: str,
    subtitle: str,
    rows: list[dict[str, Any]],
    value_format: str,
) -> None:
    image = Image.new("RGB", (1040, 640), PANEL)
    draw = ImageDraw.Draw(image)
    _draw_header(draw, title, subtitle)

    rows = [row for row in rows if row["value"] > 0][:8]
    if not rows:
        _draw_no_data(draw)
        image.save(path, "PNG")
        return

    max_value = max(row["value"] for row in rows) or 1
    plot_left = 330
    plot_right = 930
    top = 150
    row_height = 52
    gap = 13
    colors = [BRAND, GREEN, ORANGE, PURPLE, PINK]

    for index, row in enumerate(rows):
        y = top + index * (row_height + gap)
        label = _truncate(str(row["label"]), 32)
        value = float(row["value"])
        bar_width = max(int((plot_right - plot_left) * (value / max_value)), 8)
        color = colors[index % len(colors)]

        draw.text((72, y + 9), label, fill=INK, font=_font(24, bold=True))
        draw.rounded_rectangle(
            (plot_left, y + 8, plot_right, y + 36),
            radius=12,
            fill="#eef1f6",
        )
        draw.rounded_rectangle(
            (plot_left, y + 8, plot_left + bar_width, y + 36),
            radius=12,
            fill=color,
        )
        draw.text(
            (plot_left + bar_width + 14, y + 7),
            _format_value(value, value_format, row.get("detail")),
            fill=INK,
            font=_font(22, bold=True),
        )

    _draw_footer(draw)
    image.save(path, "PNG")


def _draw_line_chart(path: Path, title: str, rows: list[dict[str, Any]]) -> None:
    image = Image.new("RGB", (1040, 640), PANEL)
    draw = ImageDraw.Draw(image)
    _draw_header(draw, title, "Monthly lead-to-booking conversion rate")

    rows = rows[-8:]
    if not rows:
        _draw_no_data(draw)
        image.save(path, "PNG")
        return

    x0, y0, x1, y1 = 92, 150, 960, 500
    for step in range(6):
        y = y1 - int((y1 - y0) * step / 5)
        draw.line((x0, y, x1, y), fill=LINE, width=1)
        draw.text((42, y - 10), f"{step * 20}%", fill=MUTED, font=_font(17))

    values = [float(row["value"]) for row in rows]
    max_axis = max(100.0, max(values) * 1.2)
    points = []
    for index, row in enumerate(rows):
        x = x0 + int((x1 - x0) * index / max(len(rows) - 1, 1))
        y = y1 - int((y1 - y0) * (float(row["value"]) / max_axis))
        points.append((x, y))
        draw.text((x - 42, y1 + 18), str(row["label"])[-7:], fill=MUTED, font=_font(17))
        draw.text((x - 36, y - 34), f"{row['value']:.0f}%", fill=INK, font=_font(18, bold=True))
        draw.ellipse((x - 7, y - 7, x + 7, y + 7), fill=BRAND)

    if len(points) > 1:
        draw.line(points, fill=BRAND, width=5, joint="curve")

    _draw_footer(draw)
    image.save(path, "PNG")


def _draw_header(draw: ImageDraw.ImageDraw, title: str, subtitle: str) -> None:
    draw.rectangle((0, 0, 1040, 95), fill="#f7f8fc")
    draw.text((56, 28), title, fill=INK, font=_font(34, bold=True))
    draw.text((56, 72), subtitle, fill=MUTED, font=_font(18))
    draw.rounded_rectangle((835, 28, 984, 62), radius=16, fill="#eef0ff")
    draw.text((858, 36), "PropPilot chart", fill=BRAND, font=_font(17, bold=True))


def _draw_footer(draw: ImageDraw.ImageDraw) -> None:
    draw.text((56, 592), "Source: developer project data", fill=MUTED, font=_font(16))


def _draw_no_data(draw: ImageDraw.ImageDraw) -> None:
    draw.text((360, 300), "No matching data found", fill=MUTED, font=_font(28, bold=True))


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Helvetica Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Helvetica.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def _format_value(value: float, value_format: str, detail: Any = None) -> str:
    if detail:
        return str(detail)
    if value_format == "money":
        return _money(value)
    if value_format == "percent":
        return f"{value:.0f}%"
    if value_format == "days":
        return f"{value:.0f} days"
    return f"{value:.0f}"


def _money(value: float) -> str:
    if value >= 10_000_000:
        return f"INR {value / 10_000_000:.2f} Cr"
    if value >= 100_000:
        return f"INR {value / 100_000:.2f} L"
    return f"INR {value:,.0f}"


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else f"{text[: limit - 1]}..."


def _safe_float(value: Any) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return 0.0


def _has_any(text: str, *needles: str) -> bool:
    return any(needle in text for needle in needles)
