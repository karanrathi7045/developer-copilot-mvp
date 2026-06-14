from __future__ import annotations

import os
from html import escape
from typing import Any

import requests
import streamlit as st


API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")


st.set_page_config(
    page_title="Anarock PropPilot",
    page_icon="AP",
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
            st.warning(f"Anarock PropPilot data is not reachable yet: {exc}")
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


def media_url(path: str | None) -> str | None:
    if not path:
        return None
    if path.startswith(("http://", "https://")):
        return path
    return f"{API_BASE_URL}{path}"


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
            max-width: none;
            margin: 0 auto;
            padding: 16px 28px 0;
        }
        .dashboard-title {
            font-size: 22px;
            font-weight: 800;
            color: var(--ink);
            margin: 0 0 18px;
        }
        .target-card {
            background: var(--panel);
            border-radius: 0 0 16px 16px;
            min-height: 118px;
            padding: 8px 32px 24px;
            box-shadow: 0 1px 2px rgba(21, 28, 51, 0.03);
            margin-bottom: 16px;
        }
        .target-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 18px;
        }
        .target-label {
            color: #5f6878;
            font-size: 12px;
            font-weight: 850;
            letter-spacing: 0;
            text-transform: uppercase;
            margin-bottom: 8px;
        }
        .target-track {
            width: min(565px, 62vw);
            height: 8px;
            display: grid;
            grid-template-columns: 30% 23% 23% 24%;
            overflow: hidden;
        }
        .target-track span { border-right: 2px solid rgba(255,255,255,0.75); }
        .target-track span:nth-child(1) { background: #63af75; }
        .target-track span:nth-child(2) { background: #b9bd66; }
        .target-track span:nth-child(3) { background: #f6c35b; }
        .target-track span:nth-child(4) { background: #ef5448; border-right: 0; }
        .target-scale {
            width: min(565px, 62vw);
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            color: #6f7784;
            font-size: 12px;
            font-weight: 750;
            margin-top: 8px;
        }
        .city-pager {
            display: flex;
            align-items: center;
            gap: 8px;
            color: #2f3340;
            font-size: 13px;
            font-weight: 800;
            white-space: nowrap;
            margin-left: auto;
        }
        .pager-btn {
            width: 34px;
            height: 34px;
            border-radius: 5px;
            border: 1px solid #d9dee8;
            display: grid;
            place-items: center;
            color: #313743;
            font-size: 22px;
            background: #ffffff;
        }
        .analytics-grid {
            display: grid;
            grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
            gap: 16px;
        }
        .analytics-card {
            background: var(--panel);
            border-radius: 14px;
            min-height: 365px;
            padding: 30px;
            box-shadow: 0 1px 2px rgba(21, 28, 51, 0.04);
            position: relative;
            overflow: hidden;
        }
        .analytics-card.large { min-height: 430px; }
        .card-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
            margin-bottom: 34px;
        }
        .card-title {
            display: flex;
            align-items: center;
            gap: 11px;
            color: #2b2f38;
            font-size: 15px;
            font-weight: 850;
        }
        .card-icon {
            width: 18px;
            height: 18px;
            border: 2px solid #8d949d;
            border-radius: 50%;
            display: inline-grid;
            place-items: center;
            color: #8d949d;
            font-size: 11px;
            line-height: 1;
        }
        .info-dot {
            width: 16px;
            height: 16px;
            border: 2px solid #9299a3;
            border-radius: 50%;
            display: grid;
            place-items: center;
            color: #7c8490;
            font-size: 11px;
            font-weight: 850;
        }
        .contribution {
            position: absolute;
            right: 30px;
            top: 30px;
            text-align: right;
        }
        .contribution span {
            display: block;
            color: #8c929c;
            font-size: 12px;
            font-weight: 750;
        }
        .contribution strong {
            color: #63b782;
            font-size: 22px;
            line-height: 1.2;
        }
        .mandate-chart {
            display: grid;
            grid-template-columns: 170px 170px 170px;
            gap: 0;
            align-items: end;
            min-height: 190px;
            margin-top: 10px;
        }
        .mandate-bar {
            height: 155px;
            border-left: 1px solid #edf0f4;
            display: flex;
            flex-direction: column;
            justify-content: flex-end;
        }
        .mandate-bar:last-child { border-right: 1px solid #edf0f4; }
        .mandate-value {
            color: #383d47;
            font-size: 24px;
            font-weight: 850;
            margin: 0 0 18px 8px;
            white-space: nowrap;
        }
        .mandate-value small {
            color: #383d47;
            font-size: 13px;
            font-weight: 850;
            margin-right: 2px;
        }
        .mandate-value em {
            color: #ef5448;
            font-size: 12px;
            font-style: normal;
            margin-left: 4px;
        }
        .mandate-value em.green { color: #61b77d; }
        .stack {
            width: 100%;
            display: flex;
            flex-direction: column;
            justify-content: flex-end;
        }
        .stack.grey { background: #c8c8c8; }
        .stack.orange { background: #ce7c42; }
        .stack.green { background: #5cb27a; }
        .stack.olive { background: #9ba15d; }
        .mandate-label {
            color: #818891;
            font-size: 12px;
            font-weight: 750;
            text-align: center;
            margin-top: 10px;
            white-space: nowrap;
        }
        .agents-list {
            margin-top: 18px;
        }
        .agent-row {
            display: grid;
            grid-template-columns: 1fr auto;
            gap: 18px;
            align-items: center;
            min-height: 90px;
            border-bottom: 1px dashed #bfc5cf;
        }
        .agent-row:last-child { border-bottom: 0; }
        .agent-label {
            display: flex;
            align-items: center;
            gap: 13px;
            color: #2d323b;
            font-size: 15px;
            font-weight: 850;
        }
        .metric-icon {
            width: 18px;
            height: 18px;
            border: 2px solid #8c949e;
            border-radius: 5px;
            color: #8c949e;
            display: grid;
            place-items: center;
            font-size: 10px;
        }
        .agent-total {
            text-align: right;
            color: #2d323b;
        }
        .agent-total span {
            display: block;
            color: #8c929c;
            font-size: 12px;
            font-weight: 750;
        }
        .agent-total strong {
            font-size: 23px;
            font-weight: 900;
        }
        .donut-layout {
            display: grid;
            grid-template-columns: 1fr 220px;
            gap: 34px;
            align-items: center;
            min-height: 300px;
        }
        .donut-wrap {
            display: grid;
            place-items: center;
        }
        .donut {
            width: 270px;
            height: 270px;
            border-radius: 50%;
            display: grid;
            place-items: center;
            position: relative;
        }
        .donut::after {
            content: "";
            width: 158px;
            height: 158px;
            border-radius: 50%;
            background: #ffffff;
            position: absolute;
        }
        .donut-center {
            position: relative;
            z-index: 1;
            text-align: center;
            color: #2b3039;
        }
        .donut-center span {
            display: block;
            color: #8c929c;
            font-size: 12px;
            font-weight: 750;
        }
        .donut-center strong {
            display: block;
            font-size: 16px;
            margin-top: 7px;
            font-weight: 900;
        }
        .legend {
            display: grid;
            gap: 14px;
            align-content: center;
        }
        .legend-item {
            display: flex;
            align-items: center;
            gap: 10px;
            color: #7b828c;
            font-size: 12px;
            font-weight: 700;
        }
        .legend-dot {
            width: 17px;
            height: 17px;
            border-radius: 50%;
            flex: 0 0 auto;
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
        @keyframes prop-ring {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        @keyframes prop-ring-centered {
            0% { transform: translateY(-50%) rotate(0deg); }
            100% { transform: translateY(-50%) rotate(360deg); }
        }
        @keyframes prop-glow {
            0%, 100% { box-shadow: 0 16px 40px rgba(68, 71, 184, 0.28), 0 0 0 0 rgba(87, 185, 108, 0.26); }
            50% { box-shadow: 0 18px 48px rgba(68, 71, 184, 0.36), 0 0 0 9px rgba(87, 185, 108, 0.08); }
        }
        @keyframes prop-bar {
            0%, 100% { transform: scaleY(0.42); opacity: 0.72; }
            50% { transform: scaleY(1); opacity: 1; }
        }
        @keyframes prop-bar-centered {
            0%, 100% { transform: translateY(-50%) scaleY(0.42); opacity: 0.72; }
            50% { transform: translateY(-50%) scaleY(1); opacity: 1; }
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
            background:
                linear-gradient(135deg, rgba(18, 23, 42, 0.94), rgba(48, 52, 126, 0.96)) padding-box,
                conic-gradient(from 120deg, #58d6ff, #8d74ff, #ff6aa3, #f6c65b, #58d6ff) border-box !important;
            color: #ffffff !important;
            border: 2px solid transparent !important;
            box-shadow: 0 18px 44px rgba(27, 32, 88, 0.34) !important;
            min-height: 58px !important;
            width: auto !important;
            min-width: 190px !important;
            padding: 0 20px 0 66px !important;
            font-weight: 800 !important;
            white-space: nowrap !important;
            position: relative !important;
            overflow: hidden !important;
            animation: prop-glow 3.2s ease-in-out infinite !important;
        }
        div[data-testid="stPopover"] > button::before,
        div[data-testid="stPopover"] button[kind="secondary"]::before {
            content: "";
            position: absolute;
            left: 12px;
            top: 50%;
            width: 38px;
            height: 38px;
            transform: translateY(-50%);
            border-radius: 50%;
            background:
                radial-gradient(circle at 50% 50%, #ffffff 0 18%, transparent 19%),
                conic-gradient(from 45deg, #58d6ff, #8d74ff, #ff6aa3, #f6c65b, #58d6ff);
            box-shadow: 0 0 22px rgba(88, 214, 255, 0.38);
            animation: prop-ring-centered 4.5s linear infinite;
        }
        div[data-testid="stPopover"] > button::after,
        div[data-testid="stPopover"] button[kind="secondary"]::after {
            content: "";
            position: absolute;
            left: 28px;
            top: 50%;
            width: 6px;
            height: 16px;
            border-radius: 99px;
            background: #1d2451;
            transform: translateY(-50%);
            box-shadow: -9px 0 0 #4447b8, 9px 0 0 #57b96c;
            animation: prop-bar-centered 1.05s ease-in-out infinite;
        }
        div[data-testid="stPopover"] > button:hover,
        div[data-testid="stPopover"] button[kind="secondary"]:hover {
            background:
                linear-gradient(135deg, rgba(22, 28, 55, 0.98), rgba(58, 62, 150, 0.98)) padding-box,
                conic-gradient(from 200deg, #58d6ff, #8d74ff, #ff6aa3, #f6c65b, #58d6ff) border-box !important;
            color: #ffffff !important;
            transform: translateY(-1px);
        }
        div[data-testid="stPopover"] p {
            font-size: 14px;
        }
        .chat-header {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 14px;
            border: 1px solid rgba(228, 232, 240, 0.95);
            border-radius: 16px;
            margin-bottom: 12px;
            background: linear-gradient(135deg, #ffffff 0%, #f7f9ff 52%, #eef2ff 100%);
        }
        .chat-dot {
            width: 48px;
            height: 48px;
            border-radius: 50%;
            background:
                radial-gradient(circle at 50% 50%, #ffffff 0 20%, transparent 21%),
                conic-gradient(from 45deg, #58d6ff, #8d74ff, #ff6aa3, #f6c65b, #58d6ff);
            color: #ffffff;
            display: grid;
            place-items: center;
            position: relative;
            box-shadow: 0 12px 30px rgba(68, 71, 184, 0.22);
            animation: prop-ring 6s linear infinite;
        }
        .chat-dot::before,
        .chat-dot::after {
            content: "";
            position: absolute;
            top: 16px;
            width: 5px;
            height: 16px;
            border-radius: 99px;
            background: #4447b8;
            animation: prop-bar 1.1s ease-in-out infinite;
        }
        .chat-dot::before {
            left: 16px;
            box-shadow: 9px 0 0 #1d2451, 18px 0 0 #57b96c;
        }
        .chat-dot::after {
            display: none;
        }
        .chat-title {
            color: var(--ink);
            font-size: 17px;
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
            .analytics-grid { grid-template-columns: 1fr; }
            .donut-layout { grid-template-columns: 1fr; }
            .legend { justify-content: center; }
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
            .target-card { padding: 12px 18px 20px; }
            .target-row { align-items: flex-start; flex-direction: column; }
            .target-track, .target-scale { width: 100%; }
            .analytics-card { padding: 22px; min-height: auto; }
            .mandate-chart { grid-template-columns: 1fr; gap: 18px; }
            .mandate-bar { border-right: 1px solid #edf0f4; }
            .donut { width: 230px; height: 230px; }
            .donut::after { width: 136px; height: 136px; }
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
            </div>
            <div class="developer-chip">
                <div class="developer-avatar">{escape(initials)}</div>
                <div>{escape(developer_name)} | Category {escape(category)}</div>
            </div>
        </div>
        <main class="dashboard-shell">
            <section class="target-card">
                <div class="target-row">
                    <div>
                        <div class="target-label">Target Achieved</div>
                        <div class="target-track" aria-hidden="true">
                            <span></span><span></span><span></span><span></span>
                        </div>
                        <div class="target-scale">
                            <span>&gt;100%</span>
                            <span>100-76%</span>
                            <span>75-51%</span>
                            <span>50-26%</span>
                        </div>
                    </div>
                    <div class="city-pager">
                        <span>9 of 55 cities</span>
                        <span class="pager-btn">&lsaquo;</span>
                        <span class="pager-btn">&rsaquo;</span>
                    </div>
                </div>
            </section>
            <section class="analytics-grid">
                <div class="analytics-card">
                    <div class="card-header">
                        <div class="card-title"><span class="card-icon">M</span>Top 3 sales value contributing mandates</div>
                    </div>
                    <div class="contribution">
                        <span>Total Contribution</span>
                        <strong>27.53%</strong>
                    </div>
                    <div class="mandate-chart">
                        <div>
                            <div class="mandate-value"><small>Rs.</small>256 Cr<em>15%</em></div>
                            <div class="mandate-bar">
                                <div class="stack grey" style="height:84px"></div>
                                <div class="stack orange" style="height:16px"></div>
                            </div>
                            <div class="mandate-label">Embassy Citadel</div>
                        </div>
                        <div>
                            <div class="mandate-value"><small>Rs.</small>108 Cr<em class="green">100%</em></div>
                            <div class="mandate-bar">
                                <div class="stack green" style="height:8px"></div>
                            </div>
                            <div class="mandate-label">Raheja District - World Re...</div>
                        </div>
                        <div>
                            <div class="mandate-value"><small>Rs.</small>97 Cr<em class="green">55%</em></div>
                            <div class="mandate-bar">
                                <div class="stack grey" style="height:5px"></div>
                                <div class="stack olive" style="height:5px"></div>
                            </div>
                            <div class="mandate-label">Godrej Avenue 11</div>
                        </div>
                    </div>
                </div>
                <div class="analytics-card">
                    <div class="card-header">
                        <div class="card-title"><span class="card-icon">A</span>Agents Insights</div>
                        <span class="info-dot">i</span>
                    </div>
                    <div class="agents-list">
                        <div class="agent-row">
                            <div class="agent-label"><span class="metric-icon">SV</span>Sales Value per agent</div>
                            <div class="agent-total"><span>Total</span><strong><small>Rs.</small> 2.6 Cr</strong></div>
                        </div>
                        <div class="agent-row">
                            <div class="agent-label"><span class="metric-icon">B</span>Bookings per agent</div>
                            <div class="agent-total"><span>Total</span><strong>1.9</strong></div>
                        </div>
                        <div class="agent-row">
                            <div class="agent-label"><span class="metric-icon">SD</span>SV Done per agent</div>
                            <div class="agent-total"><span>Total</span><strong>24.8</strong></div>
                        </div>
                    </div>
                </div>
                <div class="analytics-card large">
                    <div class="card-header">
                        <div class="card-title"><span class="card-icon">S</span>Source Group Wise Sales Contribution</div>
                        <span class="info-dot">i</span>
                    </div>
                    <div class="donut-layout">
                        <div class="donut-wrap">
                            <div class="donut" style="background: conic-gradient(#61b782 0 45%, #bfc168 45% 78%, #f7c65d 78% 94%, #f7964d 94% 99%, #ef5448 99% 100%);">
                                <div class="donut-center"><span>Total Sales</span><strong>Rs.1,675 Cr</strong></div>
                            </div>
                        </div>
                        <div class="legend">
                            {legend_item("#61b782", "Channel Partner - 45%")}
                            {legend_item("#bfc168", "Offline - 33%")}
                            {legend_item("#f7c65d", "Digital - 16%")}
                            {legend_item("#f7964d", "Referral - 6%")}
                            {legend_item("#ef5448", "Others - 1%")}
                        </div>
                    </div>
                </div>
                <div class="analytics-card large">
                    <div class="card-header">
                        <div class="card-title"><span class="card-icon">U</span>Source Group Wise Unit Contribution</div>
                        <span class="info-dot">i</span>
                    </div>
                    <div class="donut-layout">
                        <div class="donut-wrap">
                            <div class="donut" style="background: conic-gradient(#61b782 0 49%, #bfc168 49% 73%, #f7c65d 73% 91%, #f7964d 91% 98%, #ef5448 98% 100%);">
                                <div class="donut-center"><span>Total Units</span><strong>1,199</strong></div>
                            </div>
                        </div>
                        <div class="legend">
                            {legend_item("#61b782", "Channel Partner - 49%")}
                            {legend_item("#bfc168", "Offline - 24%")}
                            {legend_item("#f7c65d", "Digital - 18%")}
                            {legend_item("#f7964d", "Referral - 6%")}
                            {legend_item("#ef5448", "Others - 2%")}
                        </div>
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


def legend_item(color: str, label: str) -> str:
    return f"""
    <div class="legend-item">
        <span class="legend-dot" style="background:{escape(color)}"></span>
        <span>{escape(label)}</span>
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
                "content": "Hi Karan. Anarock PropPilot is ready. Ask me about bookings, conversion, inventory, CPs, or the next action for today.",
            }
        ]

    with st.popover("Ask PropPilot", use_container_width=False):
        st.html(
            """
            <div class="chat-header">
                <div class="chat-dot" aria-hidden="true"></div>
                <div>
                    <div class="chat-title">Anarock PropPilot</div>
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
            chart_url = media_url(message.get("chart_url"))
            if chart_url:
                st.image(
                    chart_url,
                    caption=message.get("chart_title") or "PropPilot chart",
                    use_container_width=True,
                )
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
        answer = "I am not able to reach Anarock PropPilot right now. Please try again in a moment."
        chart_url = None
        chart_title = None
    else:
        answer = clean_answer(str(result.get("answer") or "I do not have a clear answer for that yet."))
        chart_url = result.get("chart_url")
        chart_title = result.get("chart_title")
    st.session_state.copilot_messages.append(
        {
            "role": "assistant",
            "content": answer,
            "chart_url": chart_url,
            "chart_title": chart_title,
        }
    )


render_global_styles()
summary_data = api_get("/summary")
render_dashboard(summary_data)
render_copilot_widget()
