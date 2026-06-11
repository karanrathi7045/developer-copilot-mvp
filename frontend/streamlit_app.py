from __future__ import annotations

import os
from html import escape
from typing import Any

import requests
import streamlit as st


API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")


st.set_page_config(
    page_title="Developer Dashboard",
    page_icon="DC",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def api_get(path: str, show_error: bool = False) -> dict[str, Any] | None:
    try:
        response = requests.get(f"{API_BASE_URL}{path}", timeout=15)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        if show_error:
            st.warning(f"Co-pilot data is not reachable yet: {exc}")
        return None


def api_post(path: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    try:
        response = requests.post(f"{API_BASE_URL}{path}", json=payload, timeout=60)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return None


def clean_answer(text: str) -> str:
    for marker in ("\nEvidence:", "Evidence:", "\nSources:", "Sources:"):
        if marker in text:
            text = text.split(marker, 1)[0]
    return text.strip()


def render_global_styles() -> None:
    st.html(
        """
        <style>
        :root {
            --brand: #4447b8;
            --brand-dark: #363897;
            --ink: #171923;
            --muted: #748094;
            --line: #e4e8f0;
            --page: #eef1f6;
            --panel: #ffffff;
            --green: #57b96c;
            --purple: #9b7cf4;
            --orange: #ed845d;
            --pink: #e9587f;
            --amber: #f3b249;
        }
        .stApp { background: var(--page); }
        [data-testid="stHeader"], [data-testid="stSidebar"], footer { display: none; }
        .block-container {
            max-width: none;
            padding: 0 0 5.8rem 0;
        }
        div[data-testid="stToolbar"] { display: none; }
        .dev-topbar {
            height: 58px;
            background: var(--brand);
            color: #ffffff;
            display: flex;
            align-items: stretch;
            gap: 28px;
            padding: 0 28px;
            box-shadow: 0 1px 0 rgba(20, 24, 44, 0.12);
        }
        .app-switcher {
            width: 28px;
            display: grid;
            grid-template-columns: repeat(3, 6px);
            grid-auto-rows: 6px;
            gap: 4px;
            align-content: center;
            flex: 0 0 auto;
        }
        .app-switcher span {
            width: 6px;
            height: 6px;
            border-radius: 2px;
            background: #ffffff;
            display: block;
        }
        .brand-block {
            min-width: 220px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            line-height: 1.15;
        }
        .brand-title {
            font-size: 18px;
            font-weight: 700;
        }
        .brand-subtitle {
            color: rgba(255,255,255,0.86);
            font-size: 13px;
            margin-top: 4px;
        }
        .nav-items {
            display: flex;
            align-items: stretch;
            gap: 2px;
            min-width: 0;
        }
        .nav-item {
            display: flex;
            align-items: center;
            padding: 0 16px;
            color: rgba(255,255,255,0.6);
            font-weight: 650;
            font-size: 14px;
            border-bottom: 3px solid transparent;
        }
        .nav-item.active {
            color: #ffffff;
            border-bottom-color: #ffffff;
            background: rgba(255,255,255,0.04);
        }
        .beta {
            color: var(--brand);
            background: #ffffff;
            border-radius: 4px;
            padding: 1px 6px;
            margin-left: 5px;
            font-size: 11px;
            font-weight: 800;
        }
        .developer-chip {
            margin-left: auto;
            display: flex;
            align-items: center;
            gap: 10px;
            color: rgba(255,255,255,0.9);
            font-size: 13px;
            white-space: nowrap;
        }
        .developer-avatar {
            width: 32px;
            height: 32px;
            border-radius: 50%;
            background: rgba(255,255,255,0.18);
            display: grid;
            place-items: center;
            font-weight: 800;
        }
        .dashboard-shell {
            max-width: 1480px;
            margin: 0 auto;
            padding: 38px 32px 0;
        }
        .dashboard-title {
            font-size: 22px;
            font-weight: 800;
            color: var(--ink);
            margin: 0 0 18px;
        }
        .lead-table {
            display: grid;
            gap: 12px;
        }
        .lead-row {
            display: grid;
            grid-template-columns: 260px 145px 40px 150px 40px 230px 160px 170px;
            gap: 24px;
            align-items: center;
            min-height: 84px;
            background: var(--panel);
            border-radius: 5px;
            padding: 0 24px;
            box-shadow: 0 1px 2px rgba(21, 28, 51, 0.04);
        }
        .source-cell {
            display: flex;
            align-items: center;
            gap: 18px;
            min-width: 0;
        }
        .source-icon {
            width: 52px;
            height: 52px;
            border-radius: 50%;
            display: grid;
            place-items: center;
            font-size: 13px;
            font-weight: 850;
            flex: 0 0 auto;
        }
        .icon-purple { color: var(--purple); background: #f1ecfb; }
        .icon-green { color: var(--green); background: #eaf7eb; }
        .icon-orange { color: var(--orange); background: #fff0e9; }
        .source-name {
            color: #242936;
            font-size: 17px;
            font-weight: 760;
        }
        .source-note {
            color: var(--muted);
            margin-top: 5px;
            font-size: 13px;
        }
        .metric strong {
            display: block;
            color: var(--ink);
            font-size: 17px;
            line-height: 1.15;
        }
        .metric span {
            display: block;
            color: var(--muted);
            font-size: 13px;
            margin-top: 7px;
            line-height: 1.25;
        }
        .arrow {
            color: #778396;
            font-size: 24px;
            font-weight: 700;
            text-align: center;
        }
        .lower-grid {
            display: grid;
            grid-template-columns: 1fr 1.08fr 1.36fr;
            gap: 32px;
            margin-top: 48px;
            align-items: start;
        }
        .panel-title {
            color: #242936;
            font-size: 21px;
            font-weight: 800;
            margin: 0 0 16px;
        }
        .panel-title .accent {
            color: #6875ff;
            font-weight: 800;
        }
        .panel {
            background: var(--panel);
            border-radius: 6px;
            min-height: 126px;
            padding: 24px;
            box-shadow: 0 1px 2px rgba(21, 28, 51, 0.04);
        }
        .fresh-grid {
            display: grid;
            grid-template-columns: 0.8fr 1.3fr;
            gap: 22px;
            align-items: start;
        }
        .big-number {
            display: block;
            color: var(--ink);
            font-size: 27px;
            font-weight: 850;
            line-height: 1;
        }
        .small-label {
            color: var(--muted);
            display: block;
            margin-top: 20px;
            font-size: 13px;
            line-height: 1.25;
        }
        .ignored {
            color: #d94a38;
            font-size: 15px;
            font-weight: 800;
            margin-left: 6px;
        }
        .activity-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 24px;
        }
        .lead-today-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 22px 38px;
        }
        .today-item {
            display: flex;
            align-items: center;
            gap: 14px;
            min-width: 0;
        }
        .today-icon {
            width: 42px;
            height: 42px;
            border-radius: 50%;
            display: grid;
            place-items: center;
            font-size: 12px;
            font-weight: 850;
        }
        .today-value {
            color: var(--ink);
            font-size: 28px;
            font-weight: 850;
            line-height: 1;
            margin-right: 4px;
        }
        .today-label {
            color: var(--muted);
            font-size: 14px;
            font-weight: 650;
        }
        div[data-testid="stPopover"] {
            position: fixed !important;
            left: auto !important;
            right: 26px !important;
            bottom: 24px !important;
            z-index: 999999 !important;
            width: auto !important;
            max-width: calc(100vw - 32px) !important;
        }
        div[data-testid="stPopover"] > button,
        div[data-testid="stPopover"] button[kind="secondary"] {
            border-radius: 999px !important;
            background: var(--brand) !important;
            color: #ffffff !important;
            border: 1px solid rgba(255,255,255,0.28) !important;
            box-shadow: 0 18px 38px rgba(38, 43, 132, 0.32) !important;
            min-height: 48px !important;
            width: auto !important;
            min-width: 154px !important;
            padding: 0 18px !important;
            font-weight: 800 !important;
            white-space: nowrap !important;
        }
        div[data-testid="stPopover"] > button:hover,
        div[data-testid="stPopover"] button[kind="secondary"]:hover {
            background: var(--brand-dark) !important;
            color: #ffffff !important;
        }
        div[data-testid="stPopover"] p {
            font-size: 14px;
        }
        .chat-header {
            display: flex;
            align-items: center;
            gap: 10px;
            padding-bottom: 12px;
            border-bottom: 1px solid var(--line);
            margin-bottom: 12px;
        }
        .chat-dot {
            width: 34px;
            height: 34px;
            border-radius: 50%;
            background: var(--brand);
            color: #ffffff;
            display: grid;
            place-items: center;
            font-weight: 850;
        }
        .chat-title {
            color: var(--ink);
            font-size: 16px;
            font-weight: 850;
            line-height: 1.15;
        }
        .chat-subtitle {
            color: var(--muted);
            font-size: 12px;
            margin-top: 3px;
        }
        .chat-log {
            display: flex;
            flex-direction: column;
            gap: 10px;
            max-height: 330px;
            overflow-y: auto;
            padding: 2px 2px 10px;
        }
        .chat-bubble {
            border-radius: 14px;
            padding: 10px 12px;
            font-size: 13px;
            line-height: 1.45;
            max-width: 92%;
            border: 1px solid transparent;
        }
        .chat-bubble.assistant {
            align-self: flex-start;
            background: #f5f7fb;
            color: #202635;
            border-color: #e7ebf3;
        }
        .chat-bubble.user {
            align-self: flex-end;
            background: var(--brand);
            color: #ffffff;
        }
        .stForm {
            border: 0 !important;
            padding: 0 !important;
            margin-top: 8px;
        }
        @media (max-width: 1100px) {
            .developer-chip { display: none; }
            .lead-row {
                grid-template-columns: 1fr 1fr;
                gap: 16px;
                padding: 18px;
            }
            .arrow { display: none; }
            .lower-grid { grid-template-columns: 1fr; }
            .nav-item:nth-last-child(-n+2) { display: none; }
        }
        @media (max-width: 700px) {
            .dev-topbar { padding: 0 16px; gap: 14px; }
            .brand-block { min-width: 170px; }
            .nav-items { display: none; }
            .dashboard-shell { padding: 28px 16px 0; }
            .lead-row { grid-template-columns: 1fr; }
            .lead-today-grid, .activity-grid, .fresh-grid { grid-template-columns: 1fr; }
            div[data-testid="stPopover"] {
                right: 16px !important;
                bottom: 16px !important;
            }
        }
        </style>
        """,
    )


def render_dashboard(summary: dict[str, Any] | None) -> None:
    developer = (summary or {}).get("developer") or {}
    developer_name = str(developer.get("developer_name") or "Karan Rathi")
    category = str(developer.get("category") or "A")
    initials = "".join(part[:1] for part in developer_name.split()[:2]).upper() or "KR"

    rows = [
        {
            "icon": "DL",
            "icon_class": "icon-purple",
            "source": "Digital Leads",
            "note": "",
            "received": "57054",
            "visit_rate": "3.01%",
            "visits": "1719 Visits Done",
            "booking_rate": "9.02%",
            "bookings": "155 Booking Done Leads",
            "failed": "54.2%",
            "failed_count": "30921 Leads Failed",
            "junk": "22.96%",
            "junk_count": "13098 Junk Leads",
        },
        {
            "icon": "PH",
            "icon_class": "icon-green",
            "source": "Offline",
            "note": "",
            "received": "38687",
            "visit_rate": "10.79%",
            "visits": "4174 Visits Done",
            "booking_rate": "5.7%",
            "bookings": "238 Booking Done Leads",
            "failed": "62.12%",
            "failed_count": "24031 Leads Failed",
            "junk": "20.25%",
            "junk_count": "7834 Junk Leads",
        },
        {
            "icon": "CP",
            "icon_class": "icon-green",
            "source": "Channel Partners",
            "note": "",
            "received": "39792",
            "visit_rate": "19.01%",
            "visits": "7565 Visits Done",
            "booking_rate": "7.8%",
            "bookings": "590 Booking Done Leads",
            "failed": "49.71%",
            "failed_count": "19781 Leads Failed",
            "junk": "13.21%",
            "junk_count": "5258 Junk Leads",
        },
        {
            "icon": "RF",
            "icon_class": "icon-green",
            "source": "Referral",
            "note": "",
            "received": "558",
            "visit_rate": "71.33%",
            "visits": "398 Visits Done",
            "booking_rate": "22.11%",
            "bookings": "88 Booking Done Leads",
            "failed": "40.86%",
            "failed_count": "228 Leads Failed",
            "junk": "2.69%",
            "junk_count": "15 Junk Leads",
        },
        {
            "icon": "...",
            "icon_class": "icon-orange",
            "source": "Others",
            "note": "Added by agents",
            "received": "18649",
            "visit_rate": "0.7%",
            "visits": "131 Visits Done",
            "booking_rate": "15.27%",
            "bookings": "20 Booking Done Leads",
            "failed": "61.15%",
            "failed_count": "11403 Leads Failed",
            "junk": "19.21%",
            "junk_count": "3583 Junk Leads",
        },
    ]

    row_html = "\n".join(render_lead_row(row) for row in rows)
    st.html(
        f"""
        <div class="dev-topbar">
            <div class="app-switcher" aria-hidden="true">
                <span></span><span></span><span></span>
                <span></span><span></span><span></span>
                <span></span><span></span><span></span>
            </div>
            <div class="brand-block">
                <div class="brand-title">Ambrosia by Adani</div>
                <div class="brand-subtitle">1045 Mandate, 2095 Proj</div>
            </div>
            <div class="nav-items">
                <div class="nav-item active">Home</div>
                <div class="nav-item">Leads</div>
                <div class="nav-item">Reports</div>
                <div class="nav-item">Genie Activity <span class="beta">Beta</span></div>
                <div class="nav-item">QuickSight</div>
            </div>
            <div class="developer-chip">
                <div class="developer-avatar">{escape(initials)}</div>
                <div>{escape(developer_name)} | Category {escape(category)}</div>
            </div>
        </div>
        <main class="dashboard-shell">
            <h1 class="dashboard-title">1091 Leads In Booking Done, 7.8% Visit to Booking Conversion</h1>
            <section class="lead-table">
                {row_html}
            </section>
            <section class="lower-grid">
                <div>
                    <h2 class="panel-title">Fresh/WIP Leads</h2>
                    <div class="panel fresh-grid">
                        <div>
                            <span class="big-number">421103</span>
                            <span class="small-label">Fresh<br/>Leads</span>
                        </div>
                        <div>
                            <span class="big-number">2.5L <span class="ignored">(2.3L Ignored)</span></span>
                            <span class="small-label">WIP<br/>Leads</span>
                        </div>
                    </div>
                </div>
                <div>
                    <h2 class="panel-title">Lead Activity <span class="accent">Today</span></h2>
                    <div class="panel activity-grid">
                        <div><span class="big-number">119/146</span><span class="small-label">Site Visits<br/>Done</span></div>
                        <div><span class="big-number">17/20</span><span class="small-label">Revisits<br/>Done</span></div>
                        <div><span class="big-number">1.5K/4.0K</span><span class="small-label">Followups<br/>Done</span></div>
                    </div>
                </div>
                <div>
                    <h2 class="panel-title">Lead <span class="accent">Today</span></h2>
                    <div class="panel lead-today-grid">
                        {render_today_item("WL", "icon-pink", "60", "Direct Walkins")}
                        {render_today_item("PC", "icon-amber", "80", "Patchout Given")}
                        {render_today_item("PH", "icon-green", "292", "Offline")}
                        {render_today_item("DL", "icon-purple", "462", "Digital Leads")}
                    </div>
                </div>
            </section>
        </main>
        """,
    )


def render_lead_row(row: dict[str, str]) -> str:
    note = f'<div class="source-note">{escape(row["note"])}</div>' if row["note"] else ""
    return f"""
    <div class="lead-row">
        <div class="source-cell">
            <div class="source-icon {escape(row["icon_class"])}">{escape(row["icon"])}</div>
            <div><div class="source-name">{escape(row["source"])}</div>{note}</div>
        </div>
        {metric(row["received"], "Leads Received")}
        <div class="arrow">&rarr;</div>
        {metric(row["visit_rate"], row["visits"])}
        <div class="arrow">&rarr;</div>
        {metric(row["booking_rate"], row["bookings"])}
        {metric(row["failed"], row["failed_count"])}
        {metric(row["junk"], row["junk_count"])}
    </div>
    """


def metric(value: str, label: str) -> str:
    return f'<div class="metric"><strong>{escape(value)}</strong><span>{escape(label)}</span></div>'


def render_today_item(icon: str, icon_class: str, value: str, label: str) -> str:
    class_map = {
        "icon-pink": "color: var(--pink); background: #fdebf0;",
        "icon-amber": "color: var(--amber); background: #fff5df;",
        "icon-green": "color: var(--green); background: #eaf7eb;",
        "icon-purple": "color: var(--purple); background: #f1ecfb;",
    }
    style = class_map.get(icon_class, "")
    return f"""
    <div class="today-item">
        <div class="today-icon" style="{style}">{escape(icon)}</div>
        <div><span class="today-value">{escape(value)}</span><span class="today-label">{escape(label)}</span></div>
    </div>
    """


def render_copilot_widget() -> None:
    if "copilot_messages" not in st.session_state:
        st.session_state.copilot_messages = [
            {
                "role": "assistant",
                "content": "Hi Karan. Ask me about bookings, conversion, inventory, CPs, or the next action for today.",
            }
        ]

    with st.popover("Ask Co-pilot", use_container_width=False):
        st.html(
            """
            <div class="chat-header">
                <div class="chat-dot">DC</div>
                <div>
                    <div class="chat-title">Developer Co-pilot</div>
                    <div class="chat-subtitle">Live project assistant</div>
                </div>
            </div>
            """,
        )

        if "queued_copilot_question" in st.session_state:
            question = st.session_state.pop("queued_copilot_question")
            send_copilot_message(question)

        st.html('<div class="chat-log">')
        for message in st.session_state.copilot_messages[-8:]:
            role = "user" if message["role"] == "user" else "assistant"
            content = escape(message["content"]).replace("\n", "<br/>")
            st.html(f'<div class="chat-bubble {role}">{content}</div>')
        st.html("</div>")

        col_a, col_b, col_c = st.columns(3)
        if col_a.button("Objection", use_container_width=True):
            st.session_state.queued_copilot_question = "What is the top objection today?"
            st.rerun()
        if col_b.button("Inventory", use_container_width=True):
            st.session_state.queued_copilot_question = "Which inventory should I push today?"
            st.rerun()
        if col_c.button("CPs", use_container_width=True):
            st.session_state.queued_copilot_question = "Which channel partners need attention?"
            st.rerun()

        with st.form("copilot_chat_form", clear_on_submit=True):
            question = st.text_input(
                "Message",
                placeholder="Ask about bookings, leads, CPs...",
                label_visibility="collapsed",
            )
            submitted = st.form_submit_button("Send", type="primary", use_container_width=True)

        if submitted and question.strip():
            send_copilot_message(question.strip())
            st.rerun()


def send_copilot_message(question: str) -> None:
    st.session_state.copilot_messages.append({"role": "user", "content": question})
    result = api_post("/ask", {"question": question})
    if not result:
        answer = "I am not able to reach the co-pilot service right now. Please try again in a moment."
    else:
        answer = clean_answer(str(result.get("answer") or "I do not have a clear answer for that yet."))
    st.session_state.copilot_messages.append({"role": "assistant", "content": answer})


render_global_styles()
summary_data = api_get("/summary")
render_dashboard(summary_data)
render_copilot_widget()
