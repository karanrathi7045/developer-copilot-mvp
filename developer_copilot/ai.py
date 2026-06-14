from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from lead_analytics.analytics import structured_summary

from developer_copilot.config import Settings
from developer_copilot.data_sources import ProjectData


@dataclass(frozen=True)
class AITextResult:
    payload: dict[str, Any]
    model: str
    used_mock: bool


def reason_about_briefing(
    settings: Settings,
    project_data: ProjectData,
    deterministic_fields: dict[str, Any],
) -> AITextResult:
    if not settings.openai_api_key:
        return AITextResult(payload=deterministic_fields, model="mock-reasoner", used_mock=True)

    prompt = (
        "You are a revenue co-pilot for a real-estate developer. Use the analytics JSON "
        "to produce a concise daily WhatsApp voice briefing. Return only JSON with keys: "
        "top_objection, conversion_trend, inactive_cps, inventory_opportunity, recommendation, summary_text."
    )
    context = _project_context(project_data, deterministic_fields)
    payload = _call_openai_json(settings, prompt, context)
    if not payload:
        return AITextResult(payload=deterministic_fields, model="mock-reasoner", used_mock=True)

    merged = {**deterministic_fields, **payload}
    return AITextResult(payload=merged, model=settings.openai_model, used_mock=False)


def answer_question(settings: Settings, project_data: ProjectData, question: str) -> AITextResult:
    fallback = _fallback_answer(project_data, question)
    force_bullets = _wants_structured_answer(question)
    fallback["answer"] = _format_long_answer(fallback.get("answer", ""), force_bullets=force_bullets)
    if not settings.openai_api_key:
        return AITextResult(payload=fallback, model="mock-reasoner", used_mock=True)

    prompt = (
        "Answer the developer's question using only the provided project analytics. "
        "Use computed_metrics for all arithmetic instead of recalculating from sample rows. "
        "Keep the answer business-friendly and concise unless the developer explicitly asks for deep analysis. "
        "When the answer has more than two distinct points, format the answer as short bullet points using '- '. "
        "For analysis, highlights, summaries, trends, comparisons, and last-week questions, always use bullet points. "
        "Return JSON with keys: answer and evidence."
    )
    payload = _call_openai_json(settings, prompt, {"question": question, **_project_context(project_data)})
    if not payload:
        return AITextResult(payload=fallback, model="mock-reasoner", used_mock=True)

    return AITextResult(
        payload=_normalize_answer(payload, force_bullets=force_bullets),
        model=settings.openai_model,
        used_mock=False,
    )


def generate_action(settings: Settings, project_data: ProjectData, request: dict[str, Any]) -> AITextResult:
    fallback = _fallback_action(project_data, request)
    if not settings.openai_api_key:
        return AITextResult(payload=fallback, model="mock-reasoner", used_mock=True)

    prompt = (
        "Generate developer sales enablement copy from project analytics. Return only JSON with keys: "
        "cp_message, sales_talking_points, objection_handlers, next_steps."
    )
    payload = _call_openai_json(settings, prompt, {"request": request, **_project_context(project_data)})
    if not payload:
        return AITextResult(payload=fallback, model="mock-reasoner", used_mock=True)

    return AITextResult(payload=_normalize_action(payload), model=settings.openai_model, used_mock=False)


def _project_context(project_data: ProjectData, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    summary = structured_summary(project_data.analytics, inactive_days=30, period="month")
    return {
        "analytics": summary,
        "developer": project_data.developer,
        "leads": project_data.leads[:30],
        "projects": project_data.projects[:30],
        "inventory": project_data.inventory[:20],
        "bookings": project_data.bookings[:30],
        "channel_partners": project_data.channel_partners[:30],
        "computed_metrics": _computed_metrics(project_data),
        "data_source": project_data.source,
        "draft": extra or {},
    }


def _computed_metrics(project_data: ProjectData) -> dict[str, Any]:
    inventory_by_configuration: dict[str, dict[str, float]] = {}
    for row in project_data.inventory:
        configuration = str(row.get("configuration") or row.get("unit_type") or "Unknown").strip() or "Unknown"
        current = inventory_by_configuration.setdefault(configuration, {"total_units": 0, "available_units": 0})
        current["total_units"] += _safe_float(row.get("total_units"))
        current["available_units"] += _safe_float(row.get("available_units"))

    booking_by_configuration: dict[str, dict[str, float]] = {}
    for row in project_data.bookings:
        configuration = str(row.get("configuration") or "Unknown").strip() or "Unknown"
        current = booking_by_configuration.setdefault(
            configuration,
            {"bookings": 0, "agreement_value": 0, "brokerage_amount": 0},
        )
        current["bookings"] += 1
        current["agreement_value"] += _safe_float(row.get("agreement_value"))
        current["brokerage_amount"] += _safe_float(row.get("brokerage_amount"))

    lead_statuses: dict[str, int] = {}
    for row in project_data.leads:
        status = str(row.get("status") or "Unknown").strip() or "Unknown"
        lead_statuses[status] = lead_statuses.get(status, 0) + 1

    project_stages: dict[str, int] = {}
    for row in project_data.projects:
        stage = str(row.get("stage") or "Unknown").strip() or "Unknown"
        project_stages[stage] = project_stages.get(stage, 0) + 1

    return {
        "inventory": {
            "rows": len(project_data.inventory),
            "total_units": sum(_safe_float(row.get("total_units")) for row in project_data.inventory),
            "available_units": sum(_safe_float(row.get("available_units")) for row in project_data.inventory),
            "by_configuration": inventory_by_configuration,
        },
        "bookings": {
            "count": len(project_data.bookings),
            "agreement_value": sum(_safe_float(row.get("agreement_value")) for row in project_data.bookings),
            "brokerage_amount": sum(_safe_float(row.get("brokerage_amount")) for row in project_data.bookings),
            "by_configuration": booking_by_configuration,
        },
        "leads_by_status": lead_statuses,
        "projects_by_stage": project_stages,
    }


def _call_openai_json(settings: Settings, system_prompt: str, context: dict[str, Any]) -> dict[str, Any] | None:
    try:
        from openai import OpenAI
    except ImportError:
        return None

    try:
        client = OpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.openai_timeout_seconds,
            max_retries=0,
        )
        response = client.responses.create(
            model=settings.openai_model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(context, indent=2, sort_keys=True)},
            ],
            temperature=settings.openai_temperature,
        )
        text = getattr(response, "output_text", "") or ""
        return _parse_json(text)
    except Exception:
        return None


def _parse_json(text: str) -> dict[str, Any] | None:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```").strip()
        cleaned = cleaned.removesuffix("```").strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end <= start:
            return None
        try:
            parsed = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError:
            return None

    return parsed if isinstance(parsed, dict) else None


def _fallback_answer(project_data: ProjectData, question: str) -> dict[str, Any]:
    summary = structured_summary(project_data.analytics, inactive_days=30, period="month")
    question_lower = " ".join(question.lower().strip().split())
    top_objection = next(iter(summary["most_frequent_objections"]), None)
    inactive = summary["inactive_channel_partners"]
    trends = summary["conversion_trends"]
    inventory = _best_inventory(project_data.inventory)
    developer_name = (
        str(project_data.developer.get("developer_name", "there")).split()[0]
        if project_data.developer
        else "there"
    )

    if question_lower in {"hi", "hello", "hey", "good morning", "gm", "namaste"}:
        return _normalize_answer(
            {
                "answer": (
                    f"Hi {developer_name}. Ask me about top objections, conversion, inventory, "
                    "bookings, brokerage, inactive CPs, or what action to take today."
                ),
                "evidence": [f"I am looking at {len(project_data.projects)} projects and {len(project_data.leads)} leads for your account."],
            }
        )

    if _has_any(question_lower, "help", "what can you do", "commands"):
        return _normalize_answer(
            {
                "answer": (
                    "You can ask: top objection, conversion trend, inventory to push, inactive CPs, "
                    "bookings, brokerage, project stages, or what should I tell CPs today."
                ),
                "evidence": ["WhatsApp questions are matched to your developer record before analysis."],
            }
        )

    if _has_any(question_lower, "objection", "concern", "lost reason", "budget", "why are leads"):
        if top_objection:
            return _normalize_answer(
                {
                    "answer": f"The top objection is {top_objection['objection']} with {top_objection['count']} mentions.",
                    "evidence": [f"{top_objection['count']} conversation records mention {top_objection['objection']}."],
                }
            )
        return _normalize_answer(
            {
                "answer": "I do not see a dominant objection in your current lead slice.",
                "evidence": [f"{summary['metadata']['conversation_count']} activity records analyzed."],
            }
        )

    if _has_any(question_lower, "booking", "booked", "agreement", "revenue", "brokerage", "sales value", "gmv"):
        booking_count = len(project_data.bookings)
        agreement_value = sum(_safe_float(row.get("agreement_value")) for row in project_data.bookings)
        brokerage_amount = sum(_safe_float(row.get("brokerage_amount")) for row in project_data.bookings)
        if _has_any(question_lower, "brokerage", "commission"):
            answer = f"Brokerage booked is {_money(brokerage_amount)} across {booking_count} bookings."
        else:
            answer = f"You have {booking_count} bookings worth {_money(agreement_value)} agreement value."
        return _normalize_answer(
            {
                "answer": answer,
                "evidence": [f"Bookings table rows linked to your projects: {booking_count}."],
            }
        )

    if _has_any(question_lower, "inventory", "unit", "stock", "available", "push"):
        if inventory:
            top_rows = _top_inventory(project_data.inventory, limit=3)
            answer = "Inventory to push: " + "; ".join(
                f"{row.get('project', 'Project')} {row.get('configuration', row.get('unit_type', 'units'))} "
                f"({row.get('available_units', 0)}/{row.get('total_units', 'total')} available)"
                for row in top_rows
            )
            return _normalize_answer(
                {
                    "answer": answer,
                    "evidence": [f"{len(project_data.inventory)} inventory rows reviewed for availability."],
                }
            )
        return _normalize_answer(
            {
                "answer": "I do not see inventory rows for your projects yet.",
                "evidence": ["Inventory table returned zero matched rows."],
            }
        )

    if _has_any(question_lower, "action", "recommend", "next step", "what should", "what do i tell", "tell cp", "talking point", "message"):
        action = _fallback_action(project_data, {"target": "your channel partners"})
        return _normalize_answer(
            {
                "answer": (
                    f"{action['cp_message']} "
                    f"Talking point: {action['sales_talking_points'][0] if action['sales_talking_points'] else 'Push the clearest inventory opportunity today.'}"
                ),
                "evidence": [f"Generated from {len(project_data.leads)} leads and {len(project_data.inventory)} inventory rows."],
            }
        )

    if _has_any(question_lower, "inactive", "partner", "channel partner", "cp", "broker"):
        partners = ", ".join(item["channel_partner"] for item in inactive[:5]) or "no channel partners"
        return _normalize_answer(
            {
                "answer": f"{partners} need attention based on recent activity.",
                "evidence": [f"{len(inactive)} partners crossed the inactive threshold."],
            }
        )

    if _has_any(question_lower, "conversion", "trend", "convert"):
        if trends:
            latest = trends[-1]
            return _normalize_answer(
                {
                    "answer": f"Latest monthly conversion is {latest['conversion_rate']:.0%} from {latest['leads']} dated leads.",
                    "evidence": [f"{latest['converted']} converted out of {latest['leads']} leads in {latest['period']}."],
                }
            )
        return _normalize_answer(
            {
                "answer": "Conversion trend is not available because dated lead activity is missing.",
                "evidence": ["No conversion trend buckets were generated."],
            }
        )

    if _has_any(question_lower, "lead", "pipeline", "status"):
        statuses: dict[str, int] = {}
        for lead in project_data.leads:
            status = str(lead.get("status", "Unknown") or "Unknown")
            statuses[status] = statuses.get(status, 0) + 1
        top_statuses = sorted(statuses.items(), key=lambda item: item[1], reverse=True)[:4]
        return _normalize_answer(
            {
                "answer": (
                    f"You have {len(project_data.leads)} matched leads. "
                    + ", ".join(f"{status}: {count}" for status, count in top_statuses)
                ),
                "evidence": [f"Lead table filtered to developer {project_data.developer.get('developer_name') if project_data.developer else 'account'}."],
            }
        )

    if _has_any(question_lower, "project", "stage"):
        stages: dict[str, int] = {}
        for project in project_data.projects:
            stage = str(project.get("stage", "Unknown") or "Unknown")
            stages[stage] = stages.get(stage, 0) + 1
        return _normalize_answer(
            {
                "answer": (
                    f"You have {len(project_data.projects)} active projects: "
                    + ", ".join(f"{stage}: {count}" for stage, count in sorted(stages.items()))
                ),
                "evidence": [", ".join(str(project.get("name")) for project in project_data.projects[:3])],
            }
        )

    if top_objection and inventory:
        return _normalize_answer(
            {
                "answer": (
                    f"Today I would address {top_objection['objection']} first and push "
                    f"{inventory.get('project', 'the strongest project')} {inventory.get('configuration', inventory.get('unit_type', 'inventory'))}."
                ),
                "evidence": [
                    f"{len(project_data.leads)} leads, {len(project_data.inventory)} inventory rows, and {len(project_data.bookings)} bookings analyzed.",
                ],
            }
        )

    rate = summary["metrics"]["overall_conversion_rate"]
    return _normalize_answer(
        {
            "answer": f"Overall conversion is {rate:.0%}. Ask me about objections, inventory, CPs, bookings, or next action.",
            "evidence": [
                f"{summary['metadata']['lead_count']} leads and {summary['metadata']['conversation_count']} activity records analyzed.",
            ],
        }
    )


def _has_any(text: str, *needles: str) -> bool:
    return any(needle in text for needle in needles)


def _top_inventory(inventory: list[dict[str, Any]], limit: int = 3) -> list[dict[str, Any]]:
    return sorted(
        inventory,
        key=lambda row: _safe_int(row.get("available_units")),
        reverse=True,
    )[:limit]


def _money(value: float) -> str:
    if value >= 10_000_000:
        return f"INR {value / 10_000_000:.2f} Cr"
    if value >= 100_000:
        return f"INR {value / 100_000:.2f} L"
    return f"INR {value:,.0f}"


def _safe_float(value: Any) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return 0.0


def _fallback_action(project_data: ProjectData, request: dict[str, Any]) -> dict[str, Any]:
    summary = structured_summary(project_data.analytics, inactive_days=30, period="month")
    top_objection = next(iter(summary["most_frequent_objections"]), {"objection": "budget", "count": 0})
    inventory = _best_inventory(project_data.inventory)
    target = request.get("target") or "channel partner"
    tone = request.get("tone") or "confident"
    project = inventory.get("project", "the priority project") if inventory else "the priority project"
    unit_type = inventory.get("unit_type", "available units") if inventory else "available units"

    return _normalize_action(
        {
            "cp_message": (
                f"Hi {target}, quick update from the developer team. We have a strong push on {project} "
                f"with {unit_type} inventory ready for qualified buyers. The main buyer concern is "
                f"{top_objection['objection']}, so lead with proof points, urgency, and a clear next visit slot."
            ),
            "sales_talking_points": [
                f"Open with the {project} inventory pocket and match it to the buyer's budget band.",
                f"Address {top_objection['objection']} early with ROI, availability, and comparison proof.",
                "Ask the CP to revive warm leads that have not moved in the last 30 days.",
            ],
            "objection_handlers": [
                f"If the buyer raises {top_objection['objection']}, anchor the response in total value and next-step clarity.",
                "Offer a short site visit window instead of an open-ended follow-up.",
            ],
            "next_steps": [
                "Send the CP message today.",
                "Call the top inactive CPs.",
                "Review conversion movement after the next batch of visits.",
            ],
            "tone": tone,
        }
    )


def _normalize_answer(payload: dict[str, Any], force_bullets: bool = False) -> dict[str, Any]:
    answer = str(payload.get("answer", "")).strip()
    return {
        "answer": _format_long_answer(answer, force_bullets=force_bullets),
        "evidence": _as_strings(payload.get("evidence")),
    }


def _format_long_answer(answer: str, force_bullets: bool = False) -> str:
    if not answer or "\n- " in answer or answer.startswith("- "):
        return answer
    sentences = _split_sentences(answer)
    if force_bullets:
        bullet_items = _bullet_items(answer, sentences)
        if len(bullet_items) >= 2:
            return "Here are the key points:\n" + "\n".join(f"- {item}" for item in bullet_items[:6])

    if len(answer) < 180 and len(sentences) < 4:
        return answer
    if len(sentences) < 3:
        return answer

    intro = sentences[0]
    bullet_sentences = sentences[1:7]
    if len(intro) > 150:
        bullet_sentences = sentences[:6]
        intro = "Here are the key highlights:"
    return intro + "\n" + "\n".join(f"- {sentence}" for sentence in bullet_sentences)


def _wants_structured_answer(question: str) -> bool:
    question_lower = " ".join(question.lower().strip().split())
    return _has_any(
        question_lower,
        "analysis",
        "analyze",
        "breakdown",
        "deep",
        "detail",
        "detailed",
        "highlights",
        "last week",
        "summary",
        "summarize",
        "performance",
        "compare",
        "comparison",
        "trend",
        "why",
        "what changed",
    )


def _bullet_items(answer: str, sentences: list[str]) -> list[str]:
    if len(sentences) >= 2:
        return [_trim_bullet_item(sentence) for sentence in sentences if _trim_bullet_item(sentence)]

    separators = ["; ", ". ", " and ", ", while ", ", with ", ", but "]
    parts = [answer]
    for separator in separators:
        next_parts: list[str] = []
        for part in parts:
            next_parts.extend(part.split(separator))
        parts = next_parts
        if len([part for part in parts if part.strip()]) >= 2:
            break

    return [_trim_bullet_item(part) for part in parts if _trim_bullet_item(part)]


def _trim_bullet_item(text: str) -> str:
    cleaned = " ".join(text.strip(" -•\n\t").split())
    if not cleaned:
        return ""
    return cleaned[:1].upper() + cleaned[1:]


def _split_sentences(text: str) -> list[str]:
    protected = text.replace("e.g.", "eg").replace("i.e.", "ie")
    parts: list[str] = []
    current = []
    for char in protected:
        current.append(char)
        if char in ".!?":
            sentence = "".join(current).strip()
            if sentence:
                parts.append(sentence)
            current = []
    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return [part.replace("eg", "e.g.").replace("ie", "i.e.") for part in parts]


def _normalize_action(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "cp_message": str(payload.get("cp_message", "")).strip(),
        "sales_talking_points": _as_strings(payload.get("sales_talking_points")),
        "objection_handlers": _as_strings(payload.get("objection_handlers")),
        "next_steps": _as_strings(payload.get("next_steps")),
    }


def _as_strings(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _best_inventory(inventory: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not inventory:
        return None

    def score(row: dict[str, Any]) -> int:
        units = _safe_int(row.get("available_units"))
        age_days = _safe_int(row.get("age_days"))
        return units * 3 + age_days

    return max(inventory, key=score)


def _inventory_sentence(inventory: dict[str, Any]) -> str:
    return (
        f"Prioritize {inventory.get('project', 'the project')} "
        f"{inventory.get('unit_type', 'inventory')} with "
        f"{inventory.get('available_units', 'available')} available units."
    )


def _safe_int(value: Any) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0
