"""
============================================
📊 LIVE MONITORING DASHBOARD
Web-based real-time dashboard showing
agent statuses and signals
============================================
"""

import threading
import time
import json
from enum import Enum
from datetime import datetime, date
from decimal import Decimal  # <-- fix missing import for Decimal
import sqlite3
import os
from flask import Flask, render_template_string, jsonify, Response
from flask_socketio import SocketIO, emit
from utils.logger import get_logger
from typing import Optional

logger = get_logger("dashboard")


class _SafeEncoder(json.JSONEncoder):
    """
    Handles all types that are commonly NOT JSON-serialisable:
    - datetime / date   → ISO string
    - Enum              → .value
    - Decimal / float   → rounded float
    - Everything else   → str() fallback (never crashes)
    """
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Enum):
            return obj.value
        if isinstance(obj, Decimal):
            return float(obj)
        try:
            return super().default(obj)
        except TypeError:
            return str(obj)   # absolute last resort — never crash


def _safe_jsonify(data: dict, status: int = 200) -> Response:
    """jsonify() replacement that never raises TypeError."""
    payload = json.dumps(data, cls=_SafeEncoder)
    return Response(payload, status=status, mimetype="application/json")


# ─────────────────────────────────────────────────────────────
# MODERN DASHBOARD TEMPLATE — Institutional Operations Console v3.0
# Design: glassmorphism, bento grid, micro-interactions, a11y
# ─────────────────────────────────────────────────────────────
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nifty AI — Operations Console</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.4/socket.io.min.js"></script>
    <style>
        :root {
            --bg: #060a12;
            --bg-glow-1: rgba(56, 189, 248, 0.08);
            --bg-glow-2: rgba(139, 92, 246, 0.07);
            --surface: rgba(255, 255, 255, 0.03);
            --surface-solid: #0c1220;
            --surface-hover: rgba(255, 255, 255, 0.06);
            --border: rgba(255, 255, 255, 0.08);
            --border-strong: rgba(255, 255, 255, 0.16);
            --text-primary: #eef2f8;
            --text-secondary: #94a3b8;
            --text-tertiary: #64748b;
            --green: #10b981;
            --green-soft: rgba(16, 185, 129, 0.12);
            --red: #f43f5e;
            --red-soft: rgba(244, 63, 94, 0.12);
            --amber: #f59e0b;
            --amber-soft: rgba(245, 158, 11, 0.12);
            --blue: #38bdf8;
            --blue-soft: rgba(56, 189, 248, 0.12);
            --violet: #8b5cf6;
            --violet-soft: rgba(139, 92, 246, 0.12);
            --radius-lg: 18px;
            --radius-md: 12px;
            --radius-sm: 8px;
            --shadow: 0 12px 40px rgba(0, 0, 0, 0.35);
            --shadow-hover: 0 16px 48px rgba(0, 0, 0, 0.45);
            --transition: 0.22s cubic-bezier(0.4, 0, 0.2, 1);
            --font-sans: 'Inter', system-ui, -apple-system, sans-serif;
            --font-mono: 'JetBrains Mono', 'SFMono-Regular', Consolas, monospace;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }

        html {
            scroll-behavior: smooth;
            -webkit-text-size-adjust: 100%;
        }

        body {
            font-family: var(--font-sans);
            background:
                radial-gradient(1100px 700px at 15% -5%, var(--bg-glow-1), transparent 60%),
                radial-gradient(900px 600px at 95% 5%, var(--bg-glow-2), transparent 60%),
                var(--bg);
            color: var(--text-primary);
            min-height: 100vh;
            font-size: 13px;
            line-height: 1.5;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }

        /* ── App Loader ── */
        .app-loader {
            position: fixed;
            inset: 0;
            z-index: 1000;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 16px;
            background: var(--bg);
            color: var(--text-secondary);
            transition: opacity 0.4s ease, visibility 0.4s ease;
        }
        body.loaded .app-loader {
            opacity: 0;
            visibility: hidden;
            pointer-events: none;
        }
        .loader-ring {
            width: 44px;
            height: 44px;
            border-radius: 50%;
            border: 3px solid rgba(255,255,255,0.08);
            border-top-color: var(--blue);
            animation: spin 0.8s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }

        /* ── Topbar ── */
        .topbar {
            position: sticky;
            top: 0;
            z-index: 100;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
            padding: 12px 24px;
            background: rgba(6, 10, 18, 0.78);
            -webkit-backdrop-filter: blur(20px);
            backdrop-filter: blur(20px);
            border-bottom: 1px solid var(--border);
        }
        .brand {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .brand-mark {
            width: 38px;
            height: 38px;
            border-radius: 10px;
            display: grid;
            place-items: center;
            font-size: 18px;
            font-weight: 700;
            background: linear-gradient(135deg, var(--blue-soft), var(--violet-soft));
            border: 1px solid var(--border-strong);
            color: var(--blue);
        }
        .brand-copy {
            display: flex;
            flex-direction: column;
            gap: 2px;
        }
        .brand-title {
            font-family: var(--font-mono);
            font-size: 14px;
            font-weight: 700;
            letter-spacing: 0.6px;
            color: var(--text-primary);
        }
        .brand-subtitle {
            font-size: 10px;
            letter-spacing: 1.4px;
            text-transform: uppercase;
            color: var(--text-tertiary);
        }
        .topbar-meta {
            display: flex;
            align-items: center;
            gap: 20px;
            flex-wrap: wrap;
            font-family: var(--font-mono);
            font-size: 11px;
            color: var(--text-secondary);
        }
        .meta-item {
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .meta-item .label {
            color: var(--text-tertiary);
            font-size: 9px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .pill {
            padding: 4px 10px;
            border-radius: 999px;
            font-weight: 600;
            font-size: 10px;
            letter-spacing: 0.8px;
        }
        .pill.sim {
            background: var(--amber-soft);
            color: var(--amber);
            border: 1px solid rgba(245, 158, 11, 0.3);
        }
        .pill.live {
            background: var(--green-soft);
            color: var(--green);
            border: 1px solid rgba(16, 185, 129, 0.3);
        }
        .freeze-badge {
            padding: 4px 10px;
            border-radius: 999px;
            background: var(--violet-soft);
            color: var(--violet);
            border: 1px solid rgba(139, 92, 246, 0.3);
            font-size: 10px;
            font-weight: 600;
            letter-spacing: 0.8px;
            white-space: nowrap;
        }
        .sync-status {
            display: flex;
            align-items: center;
            gap: 6px;
            font-family: var(--font-mono);
            font-size: 11px;
            color: var(--text-tertiary);
            white-space: nowrap;
        }
        .sync-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--text-tertiary);
            transition: background 0.3s;
        }
        .sync-dot.live {
            background: var(--green);
            box-shadow: 0 0 10px var(--green);
            animation: pulse-dot 2s infinite;
        }
        .sync-dot.offline {
            background: var(--red);
            box-shadow: 0 0 10px var(--red);
        }
        @keyframes pulse-dot {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        /* ── Main Layout ── */
        .main-wrap {
            padding: 20px 24px 32px;
            display: flex;
            flex-direction: column;
            gap: 18px;
            max-width: 1800px;
            margin: 0 auto;
        }

        .panel {
            background: var(--surface);
            -webkit-backdrop-filter: blur(14px);
            backdrop-filter: blur(14px);
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            box-shadow: var(--shadow);
            overflow: hidden;
            transition: border-color var(--transition), transform var(--transition), box-shadow var(--transition);
        }
        .panel:hover {
            border-color: var(--border-strong);
            box-shadow: var(--shadow-hover);
            transform: translateY(-1px);
        }
        .panel-header {
            padding: 14px 18px;
            border-bottom: 1px solid var(--border);
            font-size: 10px;
            font-weight: 600;
            letter-spacing: 1.5px;
            text-transform: uppercase;
            color: var(--text-secondary);
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 12px;
        }
        .panel-body { padding: 16px 18px; }

        /* ── Stats Grid ── */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 12px;
            padding: 16px;
        }
        .stat-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            padding: 14px 16px;
            display: flex;
            flex-direction: column;
            gap: 6px;
            transition: border-color var(--transition), background var(--transition);
        }
        .stat-card:hover {
            border-color: var(--border-strong);
            background: var(--surface-hover);
        }
        .stat-head {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 8px;
        }
        .stat-icon {
            width: 26px;
            height: 26px;
            border-radius: 7px;
            display: grid;
            place-items: center;
            font-size: 13px;
            flex-shrink: 0;
        }
        .stat-head .s-label {
            font-size: 9px;
            font-weight: 600;
            letter-spacing: 1.3px;
            text-transform: uppercase;
            color: var(--text-tertiary);
        }
        .stat-card .s-value {
            font-family: var(--font-mono);
            font-size: 24px;
            font-weight: 700;
            line-height: 1.1;
            color: var(--text-primary);
        }
        .stat-card .s-sub {
            font-size: 10px;
            color: var(--text-secondary);
            letter-spacing: 0.2px;
        }
        .stat-card.green .s-value { color: var(--green); }
        .stat-card.red .s-value { color: var(--red); }
        .stat-card.blue .s-value { color: var(--blue); }
        .stat-card.amber .s-value { color: var(--amber); }

        /* ── Two/Three Column Grids ── */
        .grid-main {
            display: grid;
            grid-template-columns: 1.5fr 1fr 1fr;
            gap: 18px;
            align-items: stretch;
        }
        .grid-two {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 18px;
            align-items: start;
        }
        .stack-col {
            display: flex;
            flex-direction: column;
            gap: 18px;
        }

        /* ── Signal Hero (Tier 1 Dominance) ── */
        .signal-hero-panel {
            position: relative;
            border-radius: var(--radius-lg);
            border: 1px solid var(--border);
            background: linear-gradient(165deg, rgba(255,255,255,0.04), rgba(255,255,255,0.01));
            box-shadow: 0 16px 48px rgba(0, 0, 0, 0.4);
            transition: border-color 0.3s, box-shadow 0.3s;
        }
        .signal-hero-panel.ce {
            border-color: rgba(16, 185, 129, 0.45);
            box-shadow: 0 0 50px rgba(16, 185, 129, 0.12);
        }
        .signal-hero-panel.pe {
            border-color: rgba(244, 63, 94, 0.45);
            box-shadow: 0 0 50px rgba(244, 63, 94, 0.12);
        }
        .hero-panel-header {
            padding: 16px 24px;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .hero-tag {
            font-size: 9px;
            font-weight: 700;
            letter-spacing: 1.5px;
            color: var(--blue);
            display: block;
            margin-bottom: 2px;
        }
        .hero-title {
            font-size: 15px;
            font-weight: 700;
            letter-spacing: 0.5px;
            color: var(--text-primary);
        }
        .hero-panel-body {
            padding: 24px;
            display: flex;
            flex-direction: column;
            gap: 20px;
        }
        .hero-primary-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 16px;
            padding-bottom: 16px;
            border-bottom: 1px solid var(--border);
        }
        .hero-direction-sub {
            font-size: 10px;
            font-weight: 600;
            letter-spacing: 1.5px;
            text-transform: uppercase;
            color: var(--text-tertiary);
            margin-bottom: 4px;
        }
        .hero-decision-label {
            font-size: 10px;
            font-weight: 600;
            letter-spacing: 1.5px;
            text-transform: uppercase;
            color: var(--text-tertiary);
            text-align: right;
            margin-bottom: 4px;
        }
        .hero-decision-val {
            font-family: var(--font-mono);
            font-size: 16px;
            font-weight: 700;
            text-align: right;
            color: var(--text-primary);
        }
        .signal-rejection-banner {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px 18px;
            border-radius: var(--radius-sm);
            background: rgba(244, 63, 94, 0.08);
            border: 1px solid rgba(244, 63, 94, 0.25);
            flex-wrap: wrap;
        }
        .rej-badge {
            padding: 3px 8px;
            border-radius: 4px;
            background: var(--red);
            color: #fff;
            font-size: 9px;
            font-weight: 800;
            letter-spacing: 1px;
        }
        .rej-reason-text {
            font-family: var(--font-mono);
            font-size: 14px;
            font-weight: 700;
            color: var(--red);
        }
        .rej-stage-text {
            font-size: 11px;
            color: var(--text-secondary);
            margin-left: auto;
        }
        .signal-metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
            gap: 12px;
        }
        .hero-metric-card {
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            padding: 12px 14px;
            display: flex;
            flex-direction: column;
            gap: 4px;
        }
        .hm-label {
            font-size: 9px;
            font-weight: 600;
            letter-spacing: 1px;
            text-transform: uppercase;
            color: var(--text-tertiary);
        }
        .hm-val {
            font-family: var(--font-mono);
            font-size: 18px;
            font-weight: 700;
            color: var(--text-primary);
        }
        .hm-sub {
            font-size: 10px;
            color: var(--text-secondary);
        }
        .hero-footer {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 12px;
            padding-top: 12px;
            border-top: 1px solid var(--border);
            font-family: var(--font-mono);
            font-size: 11px;
        }
        .hf-label { color: var(--text-tertiary); margin-right: 6px; }
        .hf-val { color: var(--text-secondary); font-weight: 600; }
        .context-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
            gap: 12px;
        }
        .context-card {
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            padding: 12px 14px;
            display: flex;
            flex-direction: column;
            gap: 4px;
        }
        .context-card .ck {
            font-size: 9px;
            font-weight: 600;
            letter-spacing: 1px;
            text-transform: uppercase;
            color: var(--text-tertiary);
        }
        .context-card .cv {
            font-family: var(--font-mono);
            font-size: 15px;
            font-weight: 700;
            color: var(--text-primary);
        }

        .signal-contract {
            font-family: var(--font-mono);
            font-size: 44px;
            font-weight: 900;
            letter-spacing: 1.5px;
            line-height: 1.05;
        }
        .signal-contract.ce { color: var(--green); text-shadow: 0 0 32px rgba(16,185,129,0.45); }
        .signal-contract.pe { color: var(--red); text-shadow: 0 0 32px rgba(244,63,94,0.45); }
        .signal-contract.none {
            color: var(--text-tertiary);
            font-size: 24px;
            font-weight: 600;
        }

        .telemetry-list {
            width: 100%;
            border-collapse: collapse;
            font-family: var(--font-mono);
            font-size: 12px;
        }
        .telemetry-list td {
            padding: 10px 16px;
            border-bottom: 1px solid var(--border);
        }
        .telemetry-list tr:last-child td { border-bottom: none; }
        .telemetry-list td:first-child {
            color: var(--text-tertiary);
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .telemetry-list td:last-child {
            text-align: right;
            font-weight: 600;
            color: var(--text-primary);
        }

        /* ── Log Panel ── */
        .log-panel {
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            padding: 12px 14px;
            height: 190px;
            overflow-y: auto;
            font-family: var(--font-mono);
            font-size: 10.5px;
            color: var(--text-secondary);
            scrollbar-width: thin;
            scrollbar-color: var(--border-strong) transparent;
        }
        .log-line {
            padding: 3px 0;
            border-bottom: 1px solid rgba(255,255,255,0.04);
            animation: fadeSlideIn 0.25s ease;
        }
        .log-line.exec { color: var(--green); }
        .log-line.rej { color: var(--red); }
        .log-line.warn { color: var(--amber); }
        @keyframes fadeSlideIn {
            from { opacity: 0; transform: translateY(-4px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* ── Funnel ── */
        .funnel-wrap {
            display: flex;
            flex-direction: column;
            gap: 4px;
        }
        .funnel-stage {
            display: flex;
            align-items: center;
            gap: 12px;
            background: rgba(255,255,255,0.03);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            padding: 12px 14px;
            transition: border-color var(--transition), background var(--transition);
        }
        .funnel-stage:hover {
            border-color: var(--border-strong);
            background: var(--surface-hover);
        }
        .funnel-stage.executed {
            border-color: rgba(16, 185, 129, 0.5);
            background: var(--green-soft);
        }
        .funnel-stage.rejected {
            border-color: rgba(244, 63, 94, 0.4);
            background: var(--red-soft);
        }
        .funnel-stage.entry {
            border-color: rgba(56, 189, 248, 0.4);
            background: var(--blue-soft);
        }
        .funnel-gate {
            flex: 1;
            min-width: 0;
        }
        .funnel-stage .f-gate {
            font-size: 10px;
            font-weight: 600;
            letter-spacing: 0.8px;
            text-transform: uppercase;
            color: var(--text-secondary);
            margin-bottom: 2px;
        }
        .funnel-stage .f-req {
            font-size: 10px;
            color: var(--text-tertiary);
        }
        .funnel-count {
            text-align: right;
            flex-shrink: 0;
        }
        .funnel-stage .f-count {
            font-family: var(--font-mono);
            font-size: 22px;
            font-weight: 700;
            line-height: 1;
        }
        .funnel-stage .f-count.pass { color: var(--green); }
        .funnel-stage .f-count.fail { color: var(--red); }
        .funnel-stage .f-count.info { color: var(--blue); }
        .funnel-stage .f-rejected {
            font-size: 10px;
            color: var(--red);
            margin-top: 2px;
        }
        .funnel-stage .f-rejected.cap { color: var(--amber); }
        .funnel-connector {
            align-self: center;
            color: var(--text-tertiary);
            font-size: 14px;
            padding: 2px 0;
            opacity: 0.7;
        }
        .funnel-tags {
            display: flex;
            gap: 10px;
            margin-top: 8px;
            flex-wrap: wrap;
        }
        .funnel-tag {
            padding: 4px 10px;
            border-radius: 999px;
            font-size: 10px;
            font-weight: 600;
            letter-spacing: 0.5px;
        }
        .funnel-tag.pred {
            background: var(--red-soft);
            color: var(--red);
            border: 1px solid rgba(244, 63, 94, 0.3);
        }
        .funnel-tag.cap {
            background: var(--amber-soft);
            color: var(--amber);
            border: 1px solid rgba(245, 158, 11, 0.3);
        }

        /* ── Gate Matrix ── */
        .gate-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
        }
        .gate-table th {
            font-size: 9px;
            font-weight: 600;
            letter-spacing: 1px;
            text-transform: uppercase;
            color: var(--text-tertiary);
            padding: 10px 14px;
            text-align: left;
            border-bottom: 1px solid var(--border);
            background: rgba(255,255,255,0.02);
        }
        .gate-table td {
            padding: 10px 14px;
            border-bottom: 1px solid var(--border);
            vertical-align: middle;
        }
        .gate-table tr:last-child td { border-bottom: none; }
        .gate-table tbody tr:hover { background: var(--surface-hover); }
        .gate-name {
            font-weight: 500;
            color: var(--text-secondary);
            font-size: 11px;
        }
        .gate-result {
            font-family: var(--font-mono);
            font-size: 11px;
            font-weight: 600;
        }
        .gate-result.pass { color: var(--green); }
        .gate-result.fail { color: var(--red); }
        .gate-result.exec { color: var(--blue); }
        .gate-result.not-reached { color: var(--text-tertiary); font-style: italic; }
        .gate-value {
            font-family: var(--font-mono);
            font-size: 12px;
            font-weight: 600;
            color: var(--text-primary);
            text-align: right;
        }
        .gate-req {
            font-size: 10px;
            color: var(--text-tertiary);
            text-align: right;
        }

        /* ── Trade Ledger & Positions ── */
        .trade-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
        }
        .trade-table th {
            font-size: 9px;
            font-weight: 600;
            letter-spacing: 1px;
            text-transform: uppercase;
            color: var(--text-tertiary);
            padding: 11px 14px;
            text-align: left;
            border-bottom: 1px solid var(--border);
            background: rgba(255,255,255,0.02);
            white-space: nowrap;
        }
        .trade-table td {
            padding: 10px 14px;
            border-bottom: 1px solid var(--border);
            vertical-align: middle;
        }
        .trade-table tbody tr:hover { background: var(--surface-hover); }
        .trade-table tr:last-child td { border-bottom: none; }
        .t-time {
            font-family: var(--font-mono);
            color: var(--text-tertiary);
            font-size: 11px;
        }
        .t-contract {
            font-family: var(--font-mono);
            font-weight: 700;
            font-size: 13px;
        }
        .t-contract.ce { color: var(--green); }
        .t-contract.pe { color: var(--red); }
        .t-num {
            font-family: var(--font-mono);
            text-align: right;
        }
        .t-pnl {
            font-family: var(--font-mono);
            font-weight: 700;
            text-align: right;
        }
        .t-pnl.win { color: var(--green); }
        .t-pnl.loss { color: var(--red); }
        .t-r {
            font-family: var(--font-mono);
            font-weight: 600;
            text-align: right;
            font-size: 11px;
        }
        .t-outcome {
            display: inline-block;
            padding: 3px 9px;
            border-radius: 999px;
            font-size: 10px;
            font-weight: 600;
            letter-spacing: 0.5px;
            text-transform: uppercase;
        }
        .t-outcome.win { background: var(--green-soft); color: var(--green); border: 1px solid rgba(16,185,129,0.3); }
        .t-outcome.loss { background: var(--red-soft); color: var(--red); border: 1px solid rgba(244,63,94,0.3); }
        .t-outcome.open { background: var(--blue-soft); color: var(--blue); border: 1px solid rgba(56,189,248,0.3); }
        .reconstruct-badge {
            font-size: 9px;
            background: var(--amber-soft);
            color: var(--amber);
            border: 1px solid rgba(245,158,11,0.3);
            padding: 1px 6px;
            border-radius: 999px;
            margin-left: 6px;
            white-space: nowrap;
        }

        /* ── Agent Grid ── */
        .agent-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
            gap: 12px;
        }
        .agent-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            padding: 14px 16px;
            font-size: 11px;
            display: flex;
            flex-direction: column;
            gap: 8px;
            transition: border-color var(--transition), transform var(--transition), background var(--transition);
        }
        .agent-card:hover {
            border-color: var(--border-strong);
            transform: translateY(-2px);
            background: var(--surface-hover);
        }
        .ac-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 8px;
            margin-bottom: 4px;
        }
        .ac-name {
            font-weight: 600;
            font-size: 10px;
            letter-spacing: 0.5px;
            text-transform: uppercase;
            color: var(--blue);
        }
        .ac-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--text-tertiary);
            flex-shrink: 0;
        }
        .ac-dot.active {
            background: var(--green);
            box-shadow: 0 0 8px var(--green);
        }
        .ac-dot.inactive { background: var(--red); }
        .ac-row {
            display: flex;
            justify-content: space-between;
            gap: 8px;
            padding: 4px 0;
            border-bottom: 1px solid rgba(255,255,255,0.04);
        }
        .ac-row:last-child { border-bottom: none; }
        .ac-label { color: var(--text-tertiary); }
        .ac-val { font-family: var(--font-mono); font-weight: 600; }
        .bullish { color: var(--green); }
        .bearish { color: var(--red); }
        .neutral { color: var(--amber); }

        /* ── Badges / Alerts ── */
        .badge-text {
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 0.6px;
        }
        .badge-waiting { color: var(--text-tertiary); }
        .badge-pending { color: var(--amber); }
        .badge-executed { color: var(--green); }
        .badge-rejected { color: var(--red); }

        /* ── Toast ── */
        .toast-container {
            position: fixed;
            bottom: 24px;
            right: 24px;
            z-index: 500;
            display: flex;
            flex-direction: column;
            gap: 10px;
            pointer-events: none;
        }
        .toast {
            background: var(--surface-solid);
            border: 1px solid var(--border-strong);
            border-radius: var(--radius-md);
            box-shadow: var(--shadow);
            padding: 12px 18px;
            font-size: 12px;
            color: var(--text-primary);
            display: flex;
            align-items: center;
            gap: 10px;
            animation: toastIn 0.25s ease, toastOut 0.25s ease 3.5s forwards;
            pointer-events: auto;
        }
        .toast.success { border-left: 3px solid var(--green); }
        .toast.warning { border-left: 3px solid var(--amber); }
        .toast.error { border-left: 3px solid var(--red); }
        @keyframes toastIn {
            from { opacity: 0; transform: translateY(16px); }
            to { opacity: 1; transform: translateY(0); }
        }
        @keyframes toastOut {
            to { opacity: 0; transform: translateY(16px); }
        }

        /* ── Scrollbars ── */
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: var(--bg); }
        ::-webkit-scrollbar-thumb { background: var(--border-strong); border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: var(--text-tertiary); }

        /* ── Responsive / Reduced Motion ── */
        @media (max-width: 1200px) {
            .grid-main { grid-template-columns: 1fr 1fr; }
            .grid-main .last-full-mobile { grid-column: span 2; }
        }
        @media (max-width: 768px) {
            .topbar { flex-wrap: wrap; padding: 10px 16px; }
            .topbar-meta { gap: 12px; }
            .main-wrap { padding: 14px 12px 24px; }
            .grid-main, .grid-two { grid-template-columns: 1fr; }
            .grid-main .last-full-mobile { grid-column: auto; }
            .stats-grid { grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); }
            .signal-contract { font-size: 24px; }
        }

        @media (prefers-reduced-motion: reduce) {
            *, *::before, *::after {
                animation-duration: 0.01ms !important;
                animation-iteration-count: 1 !important;
                transition-duration: 0.01ms !important;
            }
        }
    </style>
</head>
<body>

<!-- App Loader -->
<div class="app-loader" id="app-loader">
    <div class="loader-ring"></div>
    <span>Loading operations console…</span>
</div>

<!-- ── Topbar ── -->
<header class="topbar" id="campaign-bar">
    <div class="brand">
        <div class="brand-mark">◆</div>
        <div class="brand-copy">
            <span class="brand-title" id="campaign-id">LOADING CAMPAIGN...</span>
            <span class="brand-subtitle">Nifty AI · Operations</span>
        </div>
    </div>
    <div class="topbar-meta" id="campaign-meta">
        <span class="meta-item"><span class="label">Engine</span> <span id="cb-engine">---</span></span>
        <span class="meta-item"><span class="label">Session</span> <span id="cb-session">---</span></span>
        <span class="meta-item"><span class="label">Commit</span> <span id="cb-commit">---</span></span>
        <span id="campaign-mode" class="pill sim">SIMULATION</span>
        <span id="code-freeze-badge" class="freeze-badge">⛔ CODE FREEZE</span>
    </div>
    <div class="sync-status">
        <span id="sync-dot" class="sync-dot"></span>
        <span id="last-sync">Connecting...</span>
    </div>
</header>

<main class="main-wrap">

    <!-- ════════════════════════════════════════════════════════════════ -->
    <!-- TIER 1: 🔥 SIGNAL HERO — LATEST EVALUATED OPPORTUNITY (DOMINATES) -->
    <!-- ════════════════════════════════════════════════════════════════ -->
    <section class="panel signal-hero-panel" id="signal-panel" aria-label="Latest Evaluated Opportunity">
        <div class="panel-header hero-panel-header">
            <div class="hero-header-left">
                <span class="hero-tag">🔥 OPPORTUNITY & SIGNAL RADAR</span>
                <span class="hero-title">Latest Evaluated Opportunity</span>
            </div>
            <div class="hero-header-right">
                <span id="sig-badge" class="badge-text badge-waiting">WAITING</span>
            </div>
        </div>
        <div class="panel-body hero-panel-body">
            <!-- Hero Top Row: Big Direction & Candidate + Primary Rejection Callout -->
            <div class="hero-primary-row">
                <div class="hero-direction-wrap">
                    <div class="hero-direction-sub">CANDIDATE DIRECTION</div>
                    <div id="sig-contract" class="signal-contract none">NO ACTIVE CANDIDATE</div>
                </div>
                <div class="hero-decision-wrap">
                    <div class="hero-decision-label">DECISION LIFECYCLE</div>
                    <div id="sig-decision" class="hero-decision-val">WAITING FOR NEXT OPPORTUNITY</div>
                </div>
            </div>

            <!-- Primary Rejection Callout Banner (visible when rejected) -->
            <div id="sig-rejection-banner" class="signal-rejection-banner" style="display:none;">
                <span class="rej-badge">PRIMARY REJECTION</span>
                <span id="sig-rejection-text" class="rej-reason-text">—</span>
                <span id="sig-rejection-stage" class="rej-stage-text">—</span>
            </div>

            <!-- Hero Metrics Bento Grid -->
            <div class="signal-metrics-grid">
                <div class="hero-metric-card">
                    <span class="hm-label">Confidence</span>
                    <span class="hm-val" id="sig-conf">—</span>
                    <span class="hm-sub" id="sig-conf-sub">Adaptive Target</span>
                </div>
                <div class="hero-metric-card">
                    <span class="hm-label">Grade</span>
                    <span class="hm-val" id="sig-grade">—</span>
                    <span class="hm-sub">Quality Tier</span>
                </div>
                <div class="hero-metric-card">
                    <span class="hm-label">Expected Value</span>
                    <span class="hm-val" id="sig-ev">—</span>
                    <span class="hm-sub" id="sig-ev-sub">R Expectancy</span>
                </div>
                <div class="hero-metric-card">
                    <span class="hm-label">Regime</span>
                    <span class="hm-val" id="sig-regime">—</span>
                    <span class="hm-sub">Market Phase</span>
                </div>
                <div class="hero-metric-card">
                    <span class="hm-label">Structure</span>
                    <span class="hm-val" id="sig-structure">—</span>
                    <span class="hm-sub">Price Pattern</span>
                </div>
                <div class="hero-metric-card">
                    <span class="hm-label">Agent Agreement</span>
                    <span class="hm-val" id="sig-agree">—</span>
                    <span class="hm-sub">Confluence (≥35%)</span>
                </div>
                <div class="hero-metric-card">
                    <span class="hm-label">Signal Spot</span>
                    <span class="hm-val" id="sig-spot">—</span>
                    <span class="hm-sub">Evaluated Price</span>
                </div>
            </div>

            <!-- Hero Snapshot Footer -->
            <div class="hero-footer">
                <div class="hero-footer-item">
                    <span class="hf-label">Snapshot Correlation ID:</span>
                    <span class="hf-val" id="sig-snap-id">—</span>
                </div>
                <div class="hero-footer-item">
                    <span class="hf-label">Evaluated At:</span>
                    <span class="hf-val" id="sig-eval-time">—</span>
                </div>
            </div>
        </div>
    </section>

    <!-- ════════════════════════════════════════════════════════════════ -->
    <!-- TIER 2: 📊 TODAY'S SIGNAL FUNNEL & 🛡️ WHY WAS IT REJECTED?      -->
    <!-- ════════════════════════════════════════════════════════════════ -->
    <div class="grid-two">
        <!-- Signal Funnel -->
        <section class="panel" aria-label="Signal Execution Funnel">
            <div class="panel-header">
                <span>Today's Signal Funnel</span>
                <span id="fn-signals-badge" class="pill blue" style="font-size:11px; font-weight:700;">-- SIGNALS TODAY</span>
            </div>
            <div class="panel-body">
                <div class="funnel-wrap" id="funnel-wrap">
                    <div class="funnel-stage entry">
                        <div class="funnel-gate">
                            <div class="f-gate">Opportunities Evaluated</div>
                            <div class="f-req">all engine cycles</div>
                        </div>
                        <div class="funnel-count"><div class="f-count info" id="fn-signals">--</div></div>
                    </div>
                    <div class="funnel-connector">↓</div>
                    <div class="funnel-stage">
                        <div class="funnel-gate">
                            <div class="f-gate">Confidence Filter</div>
                            <div class="f-req">≥ adaptive threshold</div>
                            <div class="f-rejected" id="fn-conf-rej">--</div>
                        </div>
                        <div class="funnel-count"><div class="f-count pass" id="fn-conf">--</div></div>
                    </div>
                    <div class="funnel-connector">↓</div>
                    <div class="funnel-stage">
                        <div class="funnel-gate">
                            <div class="f-gate">Agent Agreement</div>
                            <div class="f-req">≥ 35% confluence</div>
                            <div class="f-rejected" id="fn-agree-rej">--</div>
                        </div>
                        <div class="funnel-count"><div class="f-count pass" id="fn-agree">--</div></div>
                    </div>
                    <div class="funnel-connector">↓</div>
                    <div class="funnel-stage">
                        <div class="funnel-gate">
                            <div class="f-gate">PEV Filter</div>
                            <div class="f-req">breakeven clearance</div>
                            <div class="f-rejected" id="fn-pev-rej">--</div>
                        </div>
                        <div class="funnel-count"><div class="f-count pass" id="fn-pev">--</div></div>
                    </div>
                    <div class="funnel-connector">↓</div>
                    <div class="funnel-stage">
                        <div class="funnel-gate">
                            <div class="f-gate">Expected Value (EV)</div>
                            <div class="f-req">≥ 0.50R</div>
                            <div class="f-rejected" id="fn-ev-rej">--</div>
                        </div>
                        <div class="funnel-count"><div class="f-count pass" id="fn-ev">--</div></div>
                    </div>
                    <div class="funnel-connector">↓</div>
                    <div class="funnel-stage">
                        <div class="funnel-gate">
                            <div class="f-gate">Strategy Approved</div>
                            <div class="f-req">passed predictive gates</div>
                            <div class="f-rejected" id="fn-grade-rej">--</div>
                        </div>
                        <div class="funnel-count"><div class="f-count pass" id="fn-grade">--</div></div>
                    </div>
                    <div class="funnel-connector">↓</div>
                    <div class="funnel-stage">
                        <div class="funnel-gate">
                            <div class="f-gate">Capacity Guard</div>
                            <div class="f-req">max 1 active position</div>
                            <div class="f-rejected cap" id="fn-oms-rej">--</div>
                        </div>
                        <div class="funnel-count"><div class="f-count pass" id="fn-oms">--</div></div>
                    </div>
                    <div class="funnel-connector">↓</div>
                    <div class="funnel-stage executed">
                        <div class="funnel-gate">
                            <div class="f-gate">Confirmed Fills (OMS)</div>
                            <div class="f-req">order filled via OMS</div>
                        </div>
                        <div class="funnel-count"><div class="f-count pass" id="fn-executed">--</div></div>
                    </div>
                    <div class="funnel-tags">
                        <div class="funnel-tag pred">Predictive Rej: <span id="fn-total-pred" style="font-weight:700;">--</span></div>
                        <div class="funnel-tag cap">Capacity Rej: <span id="fn-total-cap" style="font-weight:700;">--</span></div>
                    </div>
                </div>
            </div>
        </section>

        <!-- Why Was It Rejected? / Gate Matrix -->
        <div class="stack-col">
            <section class="panel" aria-label="Why Was It Rejected?">
                <div class="panel-header">
                    <span>Why Was It Rejected? — Gate Matrix</span>
                    <span id="ghm-ts" style="font-size:10px; color:var(--text-tertiary); font-family:var(--font-mono); font-weight:500;">—</span>
                </div>
                <div class="panel-body" style="padding:0;">
                    <table class="gate-table">
                        <thead>
                            <tr>
                                <th>Gate</th>
                                <th>Result</th>
                                <th style="text-align:right;">Evaluated Value</th>
                                <th style="text-align:right;">Gate Requirement</th>
                            </tr>
                        </thead>
                        <tbody id="gate-matrix-body">
                            <tr><td colspan="4" style="padding:14px; color:var(--text-tertiary); text-align:center;">Awaiting evaluated opportunity...</td></tr>
                        </tbody>
                    </table>
                </div>
            </section>

            <section class="panel" aria-label="Rejection Breakdown">
                <div class="panel-header">Today's Rejection Accounting</div>
                <div class="panel-body" style="padding:0;">
                    <table style="width:100%; border-collapse:collapse; font-size:11px;">
                        <tr style="border-bottom:1px solid var(--border);">
                            <td colspan="2" style="padding:8px 16px; font-size:9px; font-weight:700; letter-spacing:1px; text-transform:uppercase; color:var(--red);">Predictive Gate Rejections</td>
                        </tr>
                        <tbody id="pred-rej-body">
                            <tr><td colspan="2" style="padding:8px 16px; color:var(--text-tertiary);">Loading...</td></tr>
                        </tbody>
                        <tr style="border-top:1px solid var(--border); border-bottom:1px solid var(--border);">
                            <td colspan="2" style="padding:8px 16px; font-size:9px; font-weight:700; letter-spacing:1px; text-transform:uppercase; color:var(--amber);">Capacity / OMS Blocks</td>
                        </tr>
                        <tbody id="cap-rej-body">
                            <tr><td colspan="2" style="padding:8px 16px; color:var(--text-tertiary);">Loading...</td></tr>
                        </tbody>
                    </table>
                </div>
            </section>
        </div>
    </div>

    <!-- ════════════════════════════════════════════════════════════════ -->
    <!-- TIER 3: 🌐 MARKET CONTEXT (EXPLAINING SIGNAL BEHAVIOR)           -->
    <!-- ════════════════════════════════════════════════════════════════ -->
    <section class="panel" aria-label="Market Context">
        <div class="panel-header">
            <span>Market Context · Explaining Signal Behavior</span>
            <span id="rc-snap" style="font-size:9px; color:var(--text-tertiary); font-family:var(--font-mono);">—</span>
        </div>
        <div class="panel-body" style="padding:14px 18px;">
            <div class="context-grid" id="context-grid">
                <div class="context-card"><span class="ck">Live Nifty</span><span class="cv" id="rc-live-spot">—</span></div>
                <div class="context-card"><span class="ck">Signal Spot</span><span class="cv" id="rc-snap-spot">—</span></div>
                <div class="context-card"><span class="ck">Regime</span><span class="cv" id="rc-regime">—</span></div>
                <div class="context-card"><span class="ck">Structure</span><span class="cv" id="rc-structure">—</span></div>
                <div class="context-card"><span class="ck">Session Phase</span><span class="cv" id="rc-session">—</span></div>
                <div class="context-card"><span class="ck">India VIX</span><span class="cv" id="rc-vix">—</span></div>
                <div class="context-card"><span class="ck">VWAP</span><span class="cv" id="rc-vwap">—</span></div>
                <div class="context-card"><span class="ck">PCR</span><span class="cv" id="rc-pcr">—</span></div>
                <div class="context-card"><span class="ck">ATR</span><span class="cv" id="rc-atr">—</span></div>
                <div class="context-card"><span class="ck">OI Data Health</span><span class="cv" id="rc-oi">—</span></div>
            </div>
        </div>
    </section>

    <!-- ════════════════════════════════════════════════════════════════ -->
    <!-- TIER 4: 🧠 AGENT INTELLIGENCE — PRE-GATE DIRECTIONAL VOTES       -->
    <!-- ════════════════════════════════════════════════════════════════ -->
    <section class="panel" aria-label="Agent Intelligence Matrix">
        <div class="panel-header">
            <span>Agent Intelligence — Pre-Gate Directional Votes</span>
            <span id="agents-snap" style="font-size:9px; color:var(--text-tertiary); font-family:var(--font-mono); font-weight:500;">—</span>
        </div>
        <div class="panel-body">
            <div class="agent-grid" id="agents-grid">
                <div style="grid-column:1/-1; padding:24px; text-align:center; border:1px solid rgba(255,255,255,0.05); border-radius:4px; background:rgba(255,255,255,0.02);">
                    <div style="color:var(--text-secondary); font-weight:600; margin-bottom:4px; letter-spacing:0.5px;">AWAITING EVALUATED AGENT VOTES</div>
                    <div style="color:var(--text-tertiary); font-size:11px;">Agent opinions will display when the first opportunity is evaluated</div>
                </div>
            </div>
        </div>
    </section>

    <!-- ════════════════════════════════════════════════════════════════ -->
    <section class="panel" aria-label="Execution Reconciliation">
        <div class="panel-header" style="background:var(--blue-soft);">
            <span style="color:var(--blue);">EXECUTION RECONCILIATION</span>
            <span id="recon-status-badge" class="badge-text" style="font-family:var(--font-mono);">—</span>
        </div>
        <div class="panel-body" style="padding:14px 18px;">
            <div class="context-grid" id="recon-grid">
                <div class="context-card"><span class="ck">OMS Routed Intents</span><span class="cv" id="recon-routed">—</span></div>
                <div class="context-card"><span class="ck">Orders Filled</span><span class="cv" id="recon-filled">—</span></div>
                <div class="context-card"><span class="ck">Open Positions</span><span class="cv" id="recon-open">—</span></div>
                <div class="context-card"><span class="ck">Closed Outcomes</span><span class="cv" id="recon-closed">—</span></div>
                <div class="context-card"><span class="ck">Failed / Cancelled</span><span class="cv" id="recon-failed">—</span></div>
            </div>
            <div id="recon-mismatches" style="margin-top:12px; font-size:11px; color:var(--red); font-family:var(--font-mono); display:none;">
            </div>
        </div>
    </section>

    <!-- ════════════════════════════════════════════════════════════════ -->
    <!-- TIER 6: 💼 EXECUTION / POSITIONS / P&L (OPERATIONAL OUTCOMES)   -->
    <!-- ════════════════════════════════════════════════════════════════ -->
    <section class="panel" aria-label="Execution & Outcomes Summary">
        <div class="panel-header">
            <span>Execution & Outcomes Summary</span>
            <span style="font-size:9px; color:var(--text-tertiary);">closed outcomes only</span>
        </div>
        <div class="stats-grid" id="stats-strip">
            <article class="stat-card green">
                <div class="stat-head"><span class="s-label">Executed Today</span><span class="stat-icon" style="background:var(--green-soft)">✅</span></div>
                <span class="s-value" id="ss-executed">--</span>
                <span class="s-sub">reached OMS</span>
            </article>
            <article class="stat-card">
                <div class="stat-head"><span class="s-label">Wins / Losses</span><span class="stat-icon" style="background:var(--surface-hover)">⚖️</span></div>
                <span class="s-value" id="ss-wl">--</span>
                <span class="s-sub" id="ss-winrate">win rate ---</span>
            </article>
            <article class="stat-card green">
                <div class="stat-head"><span class="s-label">Net P&L Today</span><span class="stat-icon" style="background:var(--green-soft)">💰</span></div>
                <span class="s-value" id="ss-pnl">--</span>
                <span class="s-sub">closed trades only</span>
            </article>
            <article class="stat-card">
                <div class="stat-head"><span class="s-label">Net R Multiple</span><span class="stat-icon" style="background:var(--surface-hover)">📐</span></div>
                <span class="s-value" id="ss-r">--</span>
                <span class="s-sub">expectancy</span>
            </article>
            <article class="stat-card blue">
                <div class="stat-head"><span class="s-label">Avg Conf.</span><span class="stat-icon" style="background:var(--blue-soft)">🎯</span></div>
                <span class="s-value" id="ss-avgconf">--</span>
                <span class="s-sub">executed signals</span>
            </article>
        </div>
    </section>

    <!-- Active + Closed Positions -->
    <div class="grid-two">
        <section class="panel" aria-label="Active Positions">
            <div class="panel-header">Active Executing Positions</div>
            <div class="panel-body" style="padding:0; overflow-x:auto;">
                <table class="trade-table">
                    <thead>
                        <tr>
                            <th>Contract</th>
                            <th>Direction</th>
                            <th style="text-align:right;">Entry</th>
                            <th style="text-align:right;">SL</th>
                            <th style="text-align:right;">Target</th>
                            <th style="text-align:right;">Qty</th>
                            <th style="text-align:right;">Unrealized P&L</th>
                            <th>TSL Phase</th>
                            <th>Health</th>
                        </tr>
                    </thead>
                    <tbody id="active-pos-body">
                        <tr><td colspan="9" style="padding:14px; color:var(--text-tertiary); text-align:center;">No active positions</td></tr>
                    </tbody>
                </table>
            </div>
        </section>
        <section class="panel" aria-label="Closed Positions">
            <div class="panel-header">Closed Positions — Today</div>
            <div class="panel-body" style="padding:0; overflow-x:auto;">
                <table class="trade-table">
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Contract</th>
                            <th style="text-align:right;">Entry</th>
                            <th style="text-align:right;">Exit</th>
                            <th style="text-align:right;">P&L</th>
                            <th style="text-align:right;">Hold</th>
                            <th>Exit Reason</th>
                        </tr>
                    </thead>
                    <tbody id="closed-pos-body">
                        <tr><td colspan="7" style="padding:14px; color:var(--text-tertiary); text-align:center;">No closed positions today</td></tr>
                    </tbody>
                </table>
            </div>
        </section>
    </div>

    <!-- Executed Trades Ledger -->
    <section class="panel" aria-label="Executed Trades">
        <div class="panel-header">
            <span>Executed Trades Ledger</span>
            <span style="font-size:9px; color:var(--text-tertiary); font-weight:500;">source: execution_ledger · all filled orders · P&L realized on close</span>
        </div>
        <div class="panel-body" style="padding:0; overflow-x:auto;">
            <table class="trade-table" id="trade-ledger-table">
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>Contract</th>
                        <th>Strike</th>
                        <th>Expiry</th>
                        <th style="text-align:right;">Entry</th>
                        <th style="text-align:right;">SL</th>
                        <th style="text-align:right;">Target</th>
                        <th style="text-align:right;">Qty</th>
                        <th style="text-align:right;">Net P&L</th>
                        <th style="text-align:right;">R</th>
                        <th>Outcome</th>
                        <th style="text-align:right;">Conf.</th>
                        <th style="text-align:right;">Grade</th>
                    </tr>
                </thead>
                <tbody id="trade-ledger-body">
                    <tr><td colspan="13" style="padding:18px; color:var(--text-tertiary); text-align:center;">No trades recorded</td></tr>
                </tbody>
            </table>
        </div>
    </section>

    <!-- ════════════════════════════════════════════════════════════════ -->
    <!-- TIER 6: ⚙️ ENGINE TELEMETRY & SYSTEM ACTIVITY LOG                -->
    <!-- ════════════════════════════════════════════════════════════════ -->
    <div class="grid-two">
        <section class="panel" aria-label="Engine Operational Telemetry">
            <div class="panel-header">Engine Operational Telemetry</div>
            <div class="panel-body" style="padding:0;">
                <table class="telemetry-list">
                    <tr><td>Session State</td><td id="tel-session">—</td></tr>
                    <tr><td>Runtime Posture</td><td id="tel-posture" style="font-weight:600;">—</td></tr>
                    <tr><td>Data Health</td><td id="tel-data" style="font-weight:600;">—</td></tr>
                    <tr><td>Engine Latency</td><td id="tel-latency">—</td></tr>
                    <tr><td>OI Health Rate</td><td id="tel-oi">—</td></tr>
                </table>
            </div>
        </section>

        <section class="panel" aria-label="System Activity Log">
            <div class="panel-header">System Activity Log</div>
            <div class="panel-body" style="padding:10px;">
                <div class="log-panel" id="log-panel"></div>
            </div>
        </section>
    </div>

</main>

<!-- Toast Container -->
<div class="toast-container" id="toast-container" aria-live="polite" aria-atomic="true"></div>

<script>
    const socket = io();
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const loggedSnapshotIds = new Set();

    function showToast(message, type = 'success') {
        const container = document.getElementById('toast-container');
        if (!container) return;
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        container.appendChild(toast);
        setTimeout(() => {
            if (toast.parentNode) toast.parentNode.removeChild(toast);
        }, 4000);
    }

    function setSyncState(state) {
        const dot = document.getElementById('sync-dot');
        const label = document.getElementById('last-sync');
        if (!dot || !label) return;
        if (state === 'live') {
            dot.className = 'sync-dot live';
            label.textContent = 'Live';
            label.style.color = 'var(--green)';
        } else if (state === 'offline') {
            dot.className = 'sync-dot offline';
            label.textContent = 'Offline';
            label.style.color = 'var(--red)';
        } else {
            dot.className = 'sync-dot';
            label.textContent = 'Connecting...';
            label.style.color = 'var(--text-tertiary)';
        }
    }

    socket.on('connect', () => {
        setSyncState('live');
        showToast('System connected', 'success');
    });

    socket.on('disconnect', () => {
        setSyncState('offline');
        showToast('System offline', 'error');
    });

    socket.on('system_status', (data) => onStatusUpdate(data));
    socket.on('signal_update', (data) => onStatusUpdate(data));

    function onStatusUpdate(data) {
        if (!data) return;

        // Remove app loader after first data
        document.body.classList.add('loaded');

        // Campaign bar
        const cfg = data.config || data.campaign || {};
        if (cfg.campaign_id) document.getElementById('campaign-id').textContent = cfg.campaign_id;
        if (cfg.engine) document.getElementById('cb-engine').textContent = cfg.engine;
        if (cfg.git_commit) document.getElementById('cb-commit').textContent = (cfg.git_commit || '').slice(0, 7);
        if (cfg.session_num !== undefined && cfg.session_total !== undefined) {
            document.getElementById('cb-session').textContent = `${cfg.session_num} / ${cfg.session_total}`;
        }
        const modeEl = document.getElementById('campaign-mode');
        if (cfg.mode === 'LIVE') {
            modeEl.textContent = 'LIVE';
            modeEl.className = 'pill live';
        } else {
            modeEl.textContent = cfg.mode || 'SIMULATION';
            modeEl.className = 'pill sim';
        }

        // Telemetry
        if (data.orchestrator) {
            document.getElementById('tel-session').textContent = data.orchestrator.session_state || '—';
            const pEl = document.getElementById('tel-posture');
            pEl.textContent = data.orchestrator.runtime_posture || '—';
            pEl.style.color = data.orchestrator.runtime_posture === 'LIVE' ? 'var(--green)' : data.orchestrator.runtime_posture === 'DEGRADED' ? 'var(--red)' : 'var(--amber)';
            const dEl = document.getElementById('tel-data');
            dEl.textContent = data.orchestrator.data_health || '—';
            dEl.style.color = data.orchestrator.data_health === 'FRESH' ? 'var(--green)' : data.orchestrator.data_health === 'STALE' ? 'var(--amber)' : 'var(--red)';
        }
        if (data.latency_ms !== undefined) {
            const lEl = document.getElementById('tel-latency');
            lEl.textContent = data.latency_ms + 'ms';
            lEl.style.color = data.latency_status === 'CRITICAL' ? 'var(--red)' : data.latency_status === 'WARNING' ? 'var(--amber)' : 'var(--green)';
        }

        // Live Market quote data
        if (data.market) {
            document.getElementById('rc-atr').textContent = data.market.atr ? Number(data.market.atr).toFixed(2) : '—';
            document.getElementById('rc-vix').textContent = data.market.india_vix ? Number(data.market.india_vix).toFixed(2) : '—';
            document.getElementById('rc-vwap').textContent = data.market.vwap ? Number(data.market.vwap).toFixed(2) : '—';
            document.getElementById('rc-pcr').textContent = data.market.pcr ? Number(data.market.pcr).toFixed(2) : '—';
            
            const liveSpotEl = document.getElementById('rc-live-spot');
            if (liveSpotEl) liveSpotEl.textContent = '₹' + Number(data.market.live_nifty || data.price || 0).toFixed(2);

            if (data.market.oi_health || data.oi_health) {
                const health = data.market.oi_health || data.oi_health;
                const oiEl = document.getElementById('rc-oi');
                if (oiEl) {
                    oiEl.textContent = (health.status || 'LIVE') + ' ' + (health.rate || '');
                    oiEl.style.color = health.status === 'FALLBACK' ? 'var(--amber)' : 'var(--green)';
                }
            }
        } else {
            if (data.price) {
                const liveSpotEl = document.getElementById('rc-live-spot');
                if (liveSpotEl) liveSpotEl.textContent = '₹' + Number(data.price).toFixed(2);
            }
            if (data.oi_health) {
                const oiEl = document.getElementById('rc-oi');
                if (oiEl) {
                    oiEl.textContent = (data.oi_health.status || 'LIVE') + ' ' + (data.oi_health.rate || '');
                    oiEl.style.color = data.oi_health.status === 'FALLBACK' ? 'var(--amber)' : 'var(--green)';
                }
            }
        }

        // Execution Reconciliation
        if (data.execution) {
            const ex = data.execution;
            document.getElementById('recon-routed').textContent = ex.orders_routed;
            document.getElementById('recon-filled').textContent = ex.orders_filled;
            document.getElementById('recon-open').textContent = ex.open_positions;
            document.getElementById('recon-closed').textContent = ex.closed_outcomes;
            document.getElementById('recon-failed').textContent = ex.failed + ' / ' + ex.cancelled;
        }

        if (data.reconciliation) {
            const rc = data.reconciliation;
            const badge = document.getElementById('recon-status-badge');
            if (rc.status === 'CONSISTENT') {
                badge.textContent = '✓ CONSISTENT';
                badge.className = 'badge-text badge-executed';
                document.getElementById('recon-mismatches').style.display = 'none';
            } else {
                badge.textContent = '🔴 EXECUTION RECONCILIATION INVALID';
                badge.className = 'badge-text badge-rejected';
                const mmEl = document.getElementById('recon-mismatches');
                mmEl.innerHTML = `<div style="padding:6px 10px; background:rgba(239,68,68,0.15); border:1px solid var(--red); border-radius:4px; margin-bottom:6px; font-weight:600;">⚠ EXECUTION RECONCILIATION INVALID: OMS filled orders do not reconcile with PositionManager ledger. Realized session performance metrics are suppressed.</div>` + (rc.mismatches || []).map(m => `<div>• ${m}</div>`).join('');
                mmEl.style.display = 'block';
            }
        }

        renderActivePositions(data.positions || []);
        renderClosedPositions(data.closed_positions_today || []);

        if (data.latest_snapshot) {
            renderCanonicalSnapshot(data.latest_snapshot, data.positions);
        }
    }

    function renderCanonicalSnapshot(snap, positions) {
        if (!snap) return;

        const panel = document.getElementById('signal-panel');
        const contractEl = document.getElementById('sig-contract');
        const badge = document.getElementById('sig-badge');
        const rejBanner = document.getElementById('sig-rejection-banner');
        const decValEl = document.getElementById('sig-decision');

        // Check if there is an active executing position
        if (positions && positions.length > 0) {
            const p = positions[0];
            const isCE = (p.signal_type || '').includes('CE') || (p.direction || '') === 'BULLISH';
            contractEl.className = 'signal-contract ' + (isCE ? 'ce' : 'pe');
            contractEl.textContent = p.signal_type || (isCE ? 'BUY CE' : 'BUY PE');
            panel.className = 'panel signal-hero-panel ' + (isCE ? 'ce' : 'pe');
            badge.textContent = '🟢 ACTIVE';
            badge.className = 'badge-text badge-executed';
            if (decValEl) {
                decValEl.textContent = 'EXECUTING IN MARKET';
                decValEl.style.color = 'var(--green)';
            }
            if (rejBanner) rejBanner.style.display = 'none';

            setSigRow('sig-conf', p.confidence_at_entry ? Number(p.confidence_at_entry).toFixed(1) + '%' : '—');
            setSigRow('sig-conf-sub', 'Entry Conf');
            setSigRow('sig-grade', '—');
            setSigRow('sig-ev', '—');
            setSigRow('sig-ev-sub', 'R Expectancy');
            setSigRow('sig-regime', p.regime_at_entry || '—');
            setSigRow('sig-structure', '—');
            setSigRow('sig-agree', '—');
            setSigRow('sig-spot', p.entry_price ? '₹' + Number(p.entry_price).toFixed(2) : '—');
            setSigRow('sig-snap-id', p.trade_id || '—');
            setSigRow('sig-eval-time', p.entry_time || '—');
            return;
        }

        const candDir = snap.candidate_direction || 'NONE';
        const isCE = candDir === 'BUY_CE';
        const isPE = candDir === 'BUY_PE';
        const hasCand = isCE || isPE;
        const dState = snap.decision_state || 'NO_CANDIDATE';

        // 1. Candidate Hero & Panel Badge
        if (hasCand) {
            contractEl.className = 'signal-contract ' + (isCE ? 'ce' : 'pe');
            contractEl.textContent = isCE ? 'BUY CE' : 'BUY PE';
            panel.className = 'panel signal-hero-panel ' + (isCE ? 'ce' : 'pe');
        } else {
            contractEl.className = 'signal-contract none';
            contractEl.textContent = 'NO ACTIVE CANDIDATE';
            panel.className = 'panel signal-hero-panel';
        }

        if (dState === 'EXECUTED') {
            badge.textContent = '✅ EXECUTED';
            badge.className = 'badge-text badge-executed';
            if (decValEl) { decValEl.textContent = 'EXECUTED VIA OMS'; decValEl.style.color = 'var(--green)'; }
            if (rejBanner) rejBanner.style.display = 'none';
        } else if (dState === 'EVALUATED_REJECTED') {
            badge.textContent = '🚫 REJECTED';
            badge.className = 'badge-text badge-rejected';
            if (decValEl) { decValEl.textContent = 'REJECTED (PRE-OMS)'; decValEl.style.color = 'var(--red)'; }
            if (rejBanner) {
                rejBanner.style.display = 'flex';
                const reasonText = document.getElementById('sig-rejection-text');
                if (reasonText) reasonText.textContent = snap.rejection_reason || 'FILTERED';
                const stageText = document.getElementById('sig-rejection-stage');
                if (stageText) stageText.textContent = snap.rejection_stage ? `Stage: ${snap.rejection_stage}` : '';
            }
        } else if (dState === 'EVALUATED_EXECUTABLE') {
            badge.textContent = '⚡ APPROVED';
            badge.className = 'badge-text badge-executed';
            if (decValEl) { decValEl.textContent = 'APPROVED FOR OMS'; decValEl.style.color = 'var(--green)'; }
            if (rejBanner) rejBanner.style.display = 'none';
        } else if (dState === 'PENDING') {
            badge.textContent = '⏳ PENDING';
            badge.className = 'badge-text badge-pending';
            if (decValEl) { decValEl.textContent = 'PENDING EVALUATION'; decValEl.style.color = 'var(--amber)'; }
            if (rejBanner) rejBanner.style.display = 'none';
        } else {
            badge.textContent = 'WAITING';
            badge.className = 'badge-text badge-waiting';
            if (decValEl) { decValEl.textContent = 'WAITING FOR NEXT OPPORTUNITY'; decValEl.style.color = 'var(--text-tertiary)'; }
            if (rejBanner) rejBanner.style.display = 'none';
        }

        // 2. Metrics Bento
        let confText = '—';
        if (snap.confidence !== null && snap.confidence !== undefined) {
            confText = Number(snap.confidence).toFixed(1) + '%';
        }
        setSigRow('sig-conf', confText);

        let confSub = 'Adaptive Target';
        const effThresh = snap.effective_threshold !== null && snap.effective_threshold !== undefined ? Number(snap.effective_threshold) : (snap.adaptive_threshold ? Number(snap.adaptive_threshold) : null);
        const baseAdapt = snap.adaptive_threshold !== null && snap.adaptive_threshold !== undefined ? Number(snap.adaptive_threshold) : null;
        if (effThresh !== null && baseAdapt !== null && effThresh !== baseAdapt) {
            confSub = `Need ${effThresh.toFixed(1)}% (Base: ${baseAdapt.toFixed(1)}%)`;
        } else if (effThresh !== null) {
            confSub = `Need ${effThresh.toFixed(1)}%`;
        }
        setSigRow('sig-conf-sub', confSub);

        setSigRow('sig-grade', snap.grade || '—');

        let evText = '—';
        if (snap.ev_r !== null && snap.ev_r !== undefined) {
            evText = Number(snap.ev_r).toFixed(2) + 'R';
        }
        setSigRow('sig-ev', evText);
        setSigRow('sig-ev-sub', snap.ev_score !== null && snap.ev_score !== undefined ? `${Number(snap.ev_score).toFixed(1)}% Score` : 'R Expectancy');

        setSigRow('sig-regime', snap.regime || '—');
        setSigRow('sig-structure', snap.structure || '—');
        setSigRow('sig-agree', snap.agreement_pct !== null && snap.agreement_pct !== undefined ? Number(snap.agreement_pct).toFixed(1) + '%' : '—');
        
        // Signal Spot vs Live Spot
        const spotFormatted = snap.spot_price ? '₹' + Number(snap.spot_price).toFixed(2) : '—';
        setSigRow('sig-spot', spotFormatted);
        const snapSpotEl = document.getElementById('rc-snap-spot');
        if (snapSpotEl) snapSpotEl.textContent = spotFormatted;
        const liveSpotEl = document.getElementById('rc-live-spot');
        if (liveSpotEl && (!liveSpotEl.textContent || liveSpotEl.textContent === '—')) {
            liveSpotEl.textContent = spotFormatted;
        }

        setSigRow('sig-snap-id', snap.snapshot_id || '—');
        setSigRow('sig-eval-time', snap.time_str || snap.timestamp || '—');

        // 3. Update Market Context with Canonical Evaluated Snapshot Info
        if (snap.regime && snap.regime !== '—') document.getElementById('rc-regime').textContent = snap.regime;
        if (snap.structure && snap.structure !== '—') document.getElementById('rc-structure').textContent = snap.structure;
        const rcSnap = document.getElementById('rc-snap');
        if (rcSnap && snap.snapshot_id) {
            rcSnap.textContent = `ID: ${snap.snapshot_id} · ${snap.time_str}`;
        }

        // 4. Update Gate Health Matrix Panel with Canonical Snapshot
        const ghmSnap = document.getElementById('ghm-ts');
        if (ghmSnap && snap.snapshot_id) {
            ghmSnap.textContent = `ID: ${snap.snapshot_id} · ${snap.time_str}`;
        }
        if (snap.gate_rows && snap.gate_rows.length) {
            let gHtml = '';
            snap.gate_rows.forEach(g => {
                const rClass = g.result === 'PASS' ? 'pass' : g.result === 'EXECUTED' ? 'exec' : (g.result === 'NOT REACHED' ? 'not-reached' : 'fail');
                const rIcon = g.result === 'PASS' ? '✅ PASS' : g.result === 'EXECUTED' ? '✅ EXECUTED' : (g.result === 'NOT REACHED' ? '⚪ NOT REACHED' : '🚫 FAIL');
                gHtml += `<tr>
                    <td class="gate-name">${g.gate}</td>
                    <td class="gate-result ${rClass}">${rIcon}</td>
                    <td class="gate-value">${g.value || '—'}</td>
                    <td class="gate-req">${g.requirement || '—'}</td>
                </tr>`;
            });
            document.getElementById('gate-matrix-body').innerHTML = gHtml;
        }

        // 5. Update Agent Intelligence Matrix with Pre-Gate Directional Votes
        const agentsSnap = document.getElementById('agents-snap');
        if (agentsSnap && snap.snapshot_id) {
            agentsSnap.textContent = `ID: ${snap.snapshot_id} · ${snap.time_str}`;
        }
        if (snap.agents && Object.keys(snap.agents).length) {
            renderAgents(snap.agents);
        }

        // 6. Deduplicated System Logging
        addSnapshotLog(snap);
    }

    function setSigRow(id, val) {
        const el = document.getElementById(id);
        if (el) el.textContent = val;
    }

    function addSnapshotLog(snap) {
        if (!snap || !snap.snapshot_id || snap.decision_state === 'NO_CANDIDATE') return;
        if (loggedSnapshotIds.has(snap.snapshot_id)) return;
        loggedSnapshotIds.add(snap.snapshot_id);

        const log = document.getElementById('log-panel');
        if (!log) return;
        const el = document.createElement('div');
        const t = snap.time_str || snap.timestamp || new Date().toLocaleTimeString('en-IN');
        const dir = snap.candidate_direction || 'SIGNAL';
        const conf = snap.confidence !== null && snap.confidence !== undefined ? Number(snap.confidence).toFixed(1) + '%' : '—';
        
        if (snap.decision_state === 'EVALUATED_REJECTED' || snap.decision_action === 'REJECTED') {
            el.className = 'log-line rej';
            el.textContent = `[${t}] ${dir} | Conf:${conf} | REJECTED: ${snap.rejection_reason || '—'}`;
        } else if (snap.decision_state === 'EXECUTED' || snap.decision_action === 'EXECUTE') {
            el.className = 'log-line exec';
            el.textContent = `[${t}] ${dir} | Conf:${conf} | EXECUTED`;
        } else if (snap.decision_state === 'EVALUATED_EXECUTABLE') {
            el.className = 'log-line';
            el.textContent = `[${t}] ${dir} | Conf:${conf} | APPROVED`;
        } else {
            el.className = 'log-line';
            el.textContent = `[${t}] ${dir} | Conf:${conf}`;
        }
        log.prepend(el);
        if (log.children.length > 80) log.removeChild(log.lastChild);
    }

    function renderActivePositions(positions) {
        const tbody = document.getElementById('active-pos-body');
        if (!positions.length) {
            tbody.innerHTML = '<tr><td colspan="9" style="padding:14px; color:var(--text-tertiary); text-align:center;">No active positions</td></tr>';
            return;
        }
        let html = '';
        positions.forEach(p => {
            const isCE = (p.signal_type || '').includes('CE') || p.direction === 'BULLISH';
            const pnlNum = typeof p.unrealized_pnl === 'number' ? p.unrealized_pnl : parseFloat((p.unrealized_pnl || '0').replace(/[^0-9.-]/g, ''));
            const pnlColor = pnlNum >= 0 ? 'var(--green)' : 'var(--red)';
            const hColor = p.health_state === 'HEALTHY' ? 'var(--green)' : p.health_state === 'WARNING' ? 'var(--amber)' : 'var(--red)';
            const sig = p.signal_type || (isCE ? 'CE' : 'PE');
            const reconBadge = p.is_reconstructed ? '<span class="reconstruct-badge" title="Historical Reconstruction (Offline)">RECONSTRUCTED</span>' : '';
            html += `<tr>
                <td class="t-contract ${isCE ? 'ce' : 'pe'}">${sig} ${reconBadge}</td>
                <td style="color:${isCE ? 'var(--green)' : 'var(--red)'}; font-weight:600;">${p.direction || '—'}</td>
                <td class="t-num">₹${Number(p.entry_price || 0).toFixed(2)}</td>
                <td class="t-num" style="color:var(--red)">₹${Number(p.stop_loss || 0).toFixed(2)}</td>
                <td class="t-num" style="color:var(--green)">₹${Number(p.target_1 || 0).toFixed(2)}</td>
                <td class="t-num">${p.qty || '—'}</td>
                <td class="t-num" style="color:${pnlColor}; font-weight:700;">₹${pnlNum.toFixed(1)}</td>
                <td style="color:var(--text-secondary); font-size:10px;">${p.tsl_phase || '—'}</td>
                <td style="color:${hColor}; font-weight:600; font-size:10px;">${p.health_state || '—'}</td>
            </tr>`;
        });
        tbody.innerHTML = html;
    }

    function renderClosedPositions(positions) {
        const tbody = document.getElementById('closed-pos-body');
        if (!positions.length) {
            tbody.innerHTML = '<tr><td colspan="7" style="padding:14px; color:var(--text-tertiary); text-align:center;">No closed positions today</td></tr>';
            return;
        }
        let html = '';
        positions.forEach(p => {
            const pnl = p.pnl || p.net_pnl || 0;
            const pnlColor = pnl >= 0 ? 'var(--green)' : 'var(--red)';
            const sig = p.signal || p.signal_type || '—';
            const isCE = sig.includes('CE') || sig === 'BULLISH';
            const timeStr = (p.time_of_day || p.entry_time || p.time || '—').split('T').pop().split('.')[0];
            
            let mins = p.time_in_trade || p.hold_minutes || 0;
            if (p.opened_at && p.closed_at && !mins) {
                const ms = new Date(p.closed_at) - new Date(p.opened_at);
                if (ms > 0) mins = ms / 60000;
            }
            
            html += `<tr>
                <td class="t-time">${timeStr}</td>
                <td class="t-contract ${isCE ? 'ce' : 'pe'}">${sig}</td>
                <td class="t-num">₹${Number(p.entry_price || p.entry || 0).toFixed(2)}</td>
                <td class="t-num">₹${Number(p.exit_price || 0).toFixed(2)}</td>
                <td class="t-num" style="color:${pnlColor}; font-weight:700;">₹${Number(pnl).toFixed(1)}</td>
                <td class="t-num">${Number(mins).toFixed(0)}m</td>
                <td style="color:var(--text-secondary); font-size:10px;">${p.exit_reason || p.result || '—'}</td>
            </tr>`;
        });
        tbody.innerHTML = html;
    }

    function renderAgents(agents) {
        const grid = document.getElementById('agents-grid');
        let html = '';
        for (const [name, out] of Object.entries(agents)) {
            let dir = 'NEUTRAL';
            let conf = 0;
            let strength = '—';
            let details = {};

            if (out && typeof out === 'object') {
                const rawSig = out.signal || out.direction || '';
                if (rawSig.includes('BULLISH')) dir = 'BULLISH';
                else if (rawSig.includes('BEARISH')) dir = 'BEARISH';
                else dir = 'NEUTRAL';

                conf = out.confidence !== undefined ? out.confidence : 0;
                details = out.details || {};
                strength = details.strength || details.candle_strength || details.pattern || details.regime || details.status || '—';
            }

            const dirClass = dir === 'BULLISH' ? 'bullish' : (dir === 'BEARISH' ? 'bearish' : 'neutral');
            html += `<div class="agent-card">
                <div class="ac-header">
                    <span class="ac-name">${name.replace(/_/g, ' ')}</span>
                    <span class="ac-dot active" title="Active"></span>
                </div>
                <div class="ac-row"><span class="ac-label">Direction</span><span class="ac-val ${dirClass}">${dir}</span></div>
                <div class="ac-row"><span class="ac-label">Confidence</span><span class="ac-val">${Number(conf).toFixed(1)}%</span></div>
                <div class="ac-row"><span class="ac-label">Signal Key</span><span class="ac-val" style="font-size:10px; color:var(--text-secondary);">${strength}</span></div>
            </div>`;
        }
        grid.innerHTML = html || '<div style="color:var(--text-tertiary);">No agents</div>';
    }

    let cachedTrades = [];

    function fetchSessionStats() {
        fetch('/api/session_stats')
            .then(r => r.json())
            .then(d => {
                if (!d || d.status !== 'ok') return;
                document.body.classList.add('loaded');
                const s = d.session;
                const c = d.campaign;
                const f = d.funnel;
                const rej = d.rejections;
                const snap = d.latest_snapshot;

                if (c) {
                    document.getElementById('campaign-id').textContent = c.campaign_id || '—';
                    document.getElementById('cb-engine').textContent = c.engine || '—';
                    document.getElementById('cb-commit').textContent = (c.git_commit || '').slice(0, 7);
                    if (c.session_num !== undefined) {
                        document.getElementById('cb-session').textContent = `${c.session_num} / ${c.session_total || 20}`;
                    }
                    const mEl = document.getElementById('campaign-mode');
                    if (c.mode === 'LIVE') { mEl.textContent = 'LIVE'; mEl.className = 'pill live'; }
                    else { mEl.textContent = c.mode || 'SIMULATION'; mEl.className = 'pill sim'; }
                }

                if (s) {
                    setText('ss-signals', s.total_signals || 0);
                    const sub = document.getElementById('ss-sub-signals');
                    if (sub && s.session_date) {
                        sub.innerHTML = `<span style="color:var(--text-primary); font-weight:600;">LAST SESSION</span> ${s.session_date}`;
                    }
                    setText('ss-executed', s.executed || 0);
                    setText('ss-pred-rej', s.predictive_rejections || 0);
                    setText('ss-cap-rej', s.capacity_rejections || 0);

                    if (s.is_reconciled === false) {
                        const wlEl = document.getElementById('ss-wl');
                        wlEl.textContent = '—';
                        wlEl.style.color = 'var(--red)';
                        const wrEl = document.getElementById('ss-winrate');
                        wrEl.textContent = 'RECONCILIATION INVALID';
                        wrEl.style.color = 'var(--red)';

                        const pnlEl = document.getElementById('ss-pnl');
                        pnlEl.textContent = s.pnl_display || '— (RECONCILIATION INVALID)';
                        pnlEl.style.color = 'var(--red)';

                        const rEl = document.getElementById('ss-r');
                        rEl.textContent = s.r_display || '— (RECONCILIATION INVALID)';
                        rEl.style.color = 'var(--red)';

                        setText('ss-avgconf', '—');
                    } else {
                        const wins = s.wins || 0;
                        const losses = s.losses || 0;
                        const wlEl = document.getElementById('ss-wl');
                        wlEl.textContent = `${wins}W / ${losses}L`;
                        wlEl.style.color = wins > losses ? 'var(--green)' : wins < losses ? 'var(--red)' : 'var(--amber)';
                        const wr = (wins + losses) > 0 ? ((wins / (wins + losses)) * 100).toFixed(0) : '—';
                        const wrEl = document.getElementById('ss-winrate');
                        wrEl.textContent = `win rate ${wr}%`;
                        wrEl.style.color = 'var(--text-secondary)';

                        const pnl = s.net_pnl || 0;
                        const pnlEl = document.getElementById('ss-pnl');
                        pnlEl.textContent = (pnl >= 0 ? '+' : '') + '₹' + Math.round(pnl).toLocaleString('en-IN');
                        pnlEl.style.color = pnl >= 0 ? 'var(--green)' : 'var(--red)';

                        const netR = s.net_r || 0;
                        const rEl = document.getElementById('ss-r');
                        rEl.textContent = (netR >= 0 ? '+' : '') + Number(netR).toFixed(2) + 'R';
                        rEl.style.color = netR >= 0 ? 'var(--green)' : 'var(--red)';

                        const ac = s.avg_conf_executed;
                        setText('ss-avgconf', ac !== undefined && ac !== null ? Number(ac).toFixed(1) + '%' : '—');
                    }
                }

                if (f) {
                    setText('fn-signals', f.signals || 0);
                    setText('fn-signals-badge', `${f.signals || 0} SIGNALS TODAY`);
                    setText('fn-conf', f.after_confidence || 0);
                    setText('fn-conf-rej', `-${f.rej_confidence || 0} rejected`);
                    setText('fn-agree', f.after_agreement || 0);
                    setText('fn-agree-rej', `-${f.rej_agreement || 0} rejected`);
                    setText('fn-pev', f.after_pev || 0);
                    setText('fn-pev-rej', `-${f.rej_pev || 0} rejected`);
                    setText('fn-ev', f.after_ev || 0);
                    setText('fn-ev-rej', `-${f.rej_ev || 0} rejected`);
                    setText('fn-grade', f.after_grade || 0);
                    setText('fn-grade-rej', `-${f.rej_grade || 0} rejected`);
                    setText('fn-oms', f.after_oms_check || 0);
                    setText('fn-oms-rej', `-${f.rej_capacity || 0} capacity blocked`);
                    setText('fn-executed', f.executed || 0);
                    setText('fn-total-pred', f.total_predictive || 0);
                    setText('fn-total-cap', f.total_capacity || 0);
                }

                if (rej) {
                    let predHtml = '';
                    (rej.predictive || []).forEach(r => {
                        predHtml += `<tr style="border-bottom:1px solid var(--border);">
                            <td style="padding:7px 16px; font-family:var(--font-mono); font-size:11px; color:var(--text-primary);">${r.reason}</td>
                            <td style="padding:7px 16px; text-align:right; font-family:var(--font-mono); font-weight:700; color:var(--red);">${r.count}</td>
                        </tr>`;
                    });
                    document.getElementById('pred-rej-body').innerHTML = predHtml || '<tr><td colspan="2" style="padding:8px 16px; color:var(--text-tertiary); font-size:11px;">None</td></tr>';

                    let capHtml = '';
                    (rej.capacity || []).forEach(r => {
                        capHtml += `<tr style="border-bottom:1px solid var(--border);">
                            <td style="padding:7px 16px; font-family:var(--font-mono); font-size:11px; color:var(--text-primary);">${r.reason}</td>
                            <td style="padding:7px 16px; text-align:right; font-family:var(--font-mono); font-weight:700; color:var(--amber);">${r.count}</td>
                        </tr>`;
                    });
                    document.getElementById('cap-rej-body').innerHTML = capHtml || '<tr><td colspan="2" style="padding:8px 16px; color:var(--text-tertiary); font-size:11px;">None</td></tr>';
                }

                if (snap) {
                    renderCanonicalSnapshot(snap, []);
                }
            })
            .catch(() => {});
    }

    function setText(id, val) {
        const el = document.getElementById(id);
        if (el) el.textContent = val;
    }

    function fetchTrades() {
        fetch('/api/trades')
            .then(r => r.json())
            .then(d => {
                if (!d || d.status !== 'ok') return;
                document.body.classList.add('loaded');
                cachedTrades = d.trades || [];
                renderTradeLedger(cachedTrades);
                
                const localToday = new Date();
                const todayStr = localToday.getFullYear() + '-' + String(localToday.getMonth() + 1).padStart(2, '0') + '-' + String(localToday.getDate()).padStart(2, '0');
                const closedToday = cachedTrades.filter(t => t.time && t.time.startsWith(todayStr) && t.result && t.result !== 'OPEN');
                renderClosedPositions(closedToday);
            })
            .catch(() => {});
    }

    function renderTradeLedger(trades) {
        const tbody = document.getElementById('trade-ledger-body');
        if (!trades || !trades.length) {
            tbody.innerHTML = '<tr><td colspan="13" style="padding:16px; color:var(--text-tertiary); text-align:center;">No trades recorded</td></tr>';
            return;
        }

        const localToday = new Date();
        const todayStr = localToday.getFullYear() + '-' + String(localToday.getMonth() + 1).padStart(2, '0') + '-' + String(localToday.getDate()).padStart(2, '0');
        const todayTrades = trades.filter(t => t.time && t.time.startsWith(todayStr));
        const recoveredTrades = trades.filter(t => t.time && !t.time.startsWith(todayStr));

        let html = '';

        // 1. Today's Session
        html += `<tr style="border-bottom:1px solid var(--border);"><td colspan="13" style="padding:10px 14px; font-weight:700; color:var(--blue); background:rgba(56,189,248,0.06); letter-spacing:0.8px; font-size:11px; text-transform:uppercase;">● TODAY'S SESSION · ${todayStr}</td></tr>`;
        if (todayTrades.length === 0) {
            html += `<tr><td colspan="13" style="padding:16px; color:var(--text-tertiary); text-align:center; font-style:italic; border-bottom:1px solid var(--border);">No executed trades in today's session (${todayStr})</td></tr>`;
        } else {
            todayTrades.forEach(t => { html += renderTradeRow(t); });
        }

        // 2. Recovered Session Trades
        if (recoveredTrades.length > 0) {
            const prevDate = recoveredTrades[0].time ? recoveredTrades[0].time.slice(0, 10) : 'Previous';
            html += `<tr style="border-top:2px solid var(--border); border-bottom:1px solid var(--border);"><td colspan="13" style="padding:10px 14px; font-weight:700; color:var(--amber); background:rgba(245,158,11,0.06); letter-spacing:0.8px; font-size:11px; text-transform:uppercase;">▲ RECOVERED EXECUTED TRADES — PREVIOUS SESSION (${prevDate}) <span style="font-size:10px; color:var(--text-tertiary); font-weight:400; text-transform:none; margin-left:8px;">Closed outcomes recovered from audit ledger</span></td></tr>`;
            recoveredTrades.forEach(t => { html += renderTradeRow(t); });
        }

        tbody.innerHTML = html;
    }

    function renderTradeRow(t) {
        const isCE = (t.signal || '').includes('CE') || t.direction === 'BULLISH';
        const pnl = t.net_pnl || 0;
        const pnlClass = pnl > 0 ? 'win' : pnl < 0 ? 'loss' : '';
        const isOpen = t.result === 'OPEN';
        const r = t.r_multiple !== undefined && t.r_multiple !== null ? Number(t.r_multiple).toFixed(2) : (t.net_pnl && t.sl && t.entry ? (pnl / (Math.abs(t.entry - t.sl) * (t.adapted_qty || t.qty || 1))).toFixed(2) : '—');
        const rClass = parseFloat(r) > 0 ? 'color:var(--green)' : parseFloat(r) < 0 ? 'color:var(--red)' : '';
        const outcomeLabel = isOpen ? 'OPEN' : (pnl > 0 ? 'WIN' : 'LOSS');
        const outcomeClass = isOpen ? 'open' : (pnl > 0 ? 'win' : 'loss');
        const expiry = t.expiry ? t.expiry.slice(0, 10) : '—';
        const timeStr = (t.time || '').split('T').pop().split('.')[0] || t.time || '—';

        return `<tr>
            <td class="t-time">${timeStr}</td>
            <td class="t-contract ${isCE ? 'ce' : 'pe'}">${t.signal || '—'}</td>
            <td class="t-num" style="color:var(--blue)">${t.strike || '—'}</td>
            <td class="t-num" style="text-align:right; color:var(--text-tertiary); font-size:10px;">${expiry}</td>
            <td class="t-num">₹${Number(t.entry || 0).toFixed(2)}</td>
            <td class="t-num" style="color:var(--red)">₹${Number(t.sl || 0).toFixed(2)}</td>
            <td class="t-num" style="color:var(--green)">₹${Number(t.target1 || 0).toFixed(2)}</td>
            <td class="t-num">${t.adapted_qty || t.qty || '—'}</td>
            <td class="t-pnl ${pnlClass}">₹${Number(pnl).toFixed(0)}</td>
            <td class="t-r" style="${rClass}">${r !== '—' ? (parseFloat(r) >= 0 ? '+' : '') + r + 'R' : '—'}</td>
            <td><span class="t-outcome ${outcomeClass}">${outcomeLabel}</span></td>
            <td class="t-num" style="text-align:right; font-size:11px;">${Number(t.confidence || 0).toFixed(1)}%</td>
            <td class="t-num" style="text-align:right; font-family:var(--font-mono); font-size:11px;">${t.grade || '—'}</td>
        </tr>`;
    }

    // ── Polling ──
    fetchSessionStats();
    fetchTrades();
    setInterval(fetchSessionStats, 10000);
    setInterval(fetchTrades, 10000);
</script>
</body>
</html>
"""


class Dashboard:
    """Web dashboard for monitoring the AI system"""

    def __init__(self, host: str = "0.0.0.0", port: int = 5000, telemetry_emit_interval_seconds: float = 2.0):
        self.app = Flask(__name__)
        self.socketio = SocketIO(self.app, cors_allowed_origins="*", async_mode='threading')
        self.host = host
        self.port = port
        self._status_data = {}
        self._errors = 0
        self._last_cycle = 0
        self._trading_enabled = True

        # Telemetry throttling controls
        self._last_emit_ts = 0.0
        self._emit_interval_seconds = telemetry_emit_interval_seconds
        self._last_emitted_posture = None
        self._last_emitted_trading_status = None

        # ── Phase B: Burn-In Tracker + Readiness Scorer (injected from main) ──
        self._burnin_tracker = None
        self._readiness_scorer = None

        # ── Priority 1: Trade Replay Viewer ──
        self._simulation_engine = None
        self._position_manager = None
        self._oms = None

        self._setup_routes()
        self._setup_error_handlers()
        self._setup_socket_events()

    def _setup_routes(self):
        @self.app.route("/")
        def index():
            return render_template_string(DASHBOARD_HTML)

        @self.app.route("/api/status")
        def api_status():
            try:
                if not self._status_data:
                    return _safe_jsonify({
                        "status": "initializing",
                        "last_signal": None
                    })
                return _safe_jsonify({
                    "status": "active",
                    "data": self._status_data,
                    "last_signal": self._status_data.get("last_signal")
                })
            except Exception as e:
                logger.error(f"STATUS ENDPOINT ERROR: {e}")
                return _safe_jsonify({"status": "error", "message": str(e)}), 500

        @self.app.route("/api/burnin")
        def api_burnin():
            """Burn-In Metrics + Readiness Score endpoint for dashboard panel."""
            try:
                if not self._burnin_tracker or not self._readiness_scorer:
                    return _safe_jsonify({"status": "no_data", "message": "BurninTracker not initialized"})
                stats = self._burnin_tracker.get_lifetime_stats()
                score = self._readiness_scorer.score(stats)
                return _safe_jsonify({"status": "ok", "stats": stats, "score": score})
            except Exception as e:
                logger.error(f"BURNIN ENDPOINT ERROR: {e}")
                return _safe_jsonify({"status": "error", "message": str(e)}), 500

        @self.app.route("/api/session_stats")
        def api_session_stats():
            """
            Session stats endpoint — read-only.
            Data hierarchy (strict):
              Signal telemetry   → decision_snapshots_v2
              Execution/P&L      → simulation_engine.all_trades (closed outcomes only)
              Campaign identity  → runtime config in _status_data
              Gate state / latest candidate snapshot → decision_snapshots_v2 (Single Canonical Snapshot)
            No path back to trading engine.
            """
            import sqlite3
            import json as _json
            from datetime import date as _date
            try:
                today_str = _date.today().isoformat()

                cfg_raw = self._status_data.get("config") or self._status_data.get("campaign") or {}
                campaign = {
                    "campaign_id": cfg_raw.get("campaign_id", self._status_data.get("campaign_id", "SHADOW-V2")),
                    "engine":      cfg_raw.get("engine", self._status_data.get("engine_version", "---")),
                    "git_commit":  cfg_raw.get("git_commit", self._status_data.get("git_commit", "---")),
                    "mode":        cfg_raw.get("mode", self._status_data.get("mode", "SIMULATION")),
                    "session_num": cfg_raw.get("session_num", self._status_data.get("session_num", 1)),
                    "session_total": cfg_raw.get("session_total", self._status_data.get("session_total", 20)),
                }

                db_path = os.getenv("NIFTY_DB_PATH", "data/trading_v4_sim.db")
                funnel = {
                    "signals": 0,
                    "after_confidence": 0, "rej_confidence": 0,
                    "after_agreement": 0, "rej_agreement": 0,
                    "after_pev": 0, "rej_pev": 0,
                    "after_ev": 0, "rej_ev": 0,
                    "after_grade": 0, "rej_grade": 0,
                    "after_oms_check": 0, "rej_capacity": 0,
                    "executed": 0,
                    "total_predictive": 0, "total_capacity": 0,
                }
                pred_reasons = {}
                cap_reasons = {}

                latest_snapshot = {
                    "snapshot_id": None,
                    "timestamp": None,
                    "time_str": "—",
                    "candidate_direction": "NONE",
                    "decision_state": "NO_CANDIDATE",
                    "decision_action": "NO_CANDIDATE",
                    "rejection_reason": "—",
                    "rejection_stage": "—",
                    "spot_price": None,
                    "confidence": None,
                    "adaptive_threshold": None,
                    "agreement_pct": None,
                    "ev_r": None,
                    "ev_score": None,
                    "grade": "—",
                    "regime": "—",
                    "structure": "—",
                    "confluence": {},
                    "agents": {},
                    "gate_rows": []
                }

                try:
                    conn = sqlite3.connect(db_path, timeout=5)
                    conn.row_factory = sqlite3.Row
                    cur = conn.cursor()

                    cur.execute(
                        "SELECT snapshot_id, timestamp, market_json, agents_json, confidence_json, confluence_json, expected_value_json, gate_results_json, decision_json, execution_json FROM decision_snapshots_v2 WHERE date(timestamp) = ? ORDER BY timestamp DESC",
                        (today_str,)
                    )
                    rows = cur.fetchall()

                    total = len(rows)
                    funnel["signals"] = total

                    pred_rej = 0
                    cap_rej = 0

                    passed_conf = 0
                    passed_agree = 0
                    passed_pev = 0
                    passed_ev = 0
                    passed_grade = 0

                    latest_candidate_row = None

                    for row in rows:
                        dj = {}
                        try:
                            dj = _json.loads(row["decision_json"] or "{}")
                        except Exception:
                            pass

                        action = (dj.get("action") or "").upper()
                        reason = (dj.get("reason") or "")

                        if latest_candidate_row is None and action in ("REJECTED", "EXECUTE", "APPROVED", "PENDING"):
                            latest_candidate_row = row

                        is_approved = action == "EXECUTE"
                        is_capacity = "Max Open Positions" in reason or "CAPACITY" in reason.upper() or "POSITION_LIMIT" in reason.upper()

                        if is_approved:
                            passed_conf += 1
                            passed_agree += 1
                            passed_pev += 1
                            passed_ev += 1
                            passed_grade += 1
                        elif is_capacity:
                            cap_rej += 1
                            passed_conf += 1
                            passed_agree += 1
                            passed_pev += 1
                            passed_ev += 1
                            passed_grade += 1
                            cap_reasons[reason] = cap_reasons.get(reason, 0) + 1
                        else:
                            pred_rej += 1
                            reason_up = reason.upper()
                            if "LOW_CONFIDENCE" in reason_up or "CONF" in reason_up:
                                pass
                            elif "CONFLUENCE" in reason_up or "AGREE" in reason_up or "AGENT" in reason_up:
                                passed_conf += 1
                            elif "PEV" in reason_up or "BREAKEVEN" in reason_up:
                                passed_conf += 1
                                passed_agree += 1
                            elif "LOW_EV" in reason_up or "EXPECTED_VALUE" in reason_up:
                                passed_conf += 1
                                passed_agree += 1
                                passed_pev += 1
                            elif "GRADE" in reason_up or "STRUCTURE" in reason_up or "CHOP" in reason_up or "REGIME" in reason_up:
                                passed_conf += 1
                                passed_agree += 1
                                passed_pev += 1
                                passed_ev += 1
                            else:
                                passed_conf += 1
                            pred_reasons[reason] = pred_reasons.get(reason, 0) + 1

                    # Determine OMS downstream execution authorization and fills
                    oms_routed = 0
                    oms_filled = 0
                    try:
                        cur.execute(
                            "SELECT COUNT(*), SUM(CASE WHEN state IN ('FILLED_ACTIVE', 'ENTRY_FILLED', 'POSITION_CLOSED') THEN 1 ELSE 0 END) FROM orders WHERE date(created_at) = ?",
                            (today_str,)
                        )
                        ord_row = cur.fetchone()
                        if ord_row:
                            oms_routed = ord_row[0] or 0
                            oms_filled = ord_row[1] or 0
                    except Exception:
                        pass

                    if self._oms and hasattr(self._oms, "get_execution_stats_today"):
                        try:
                            oms_st = self._oms.get_execution_stats_today()
                            if oms_st.get("orders_submitted", 0) > 0:
                                oms_routed = oms_st.get("orders_submitted", 0)
                            if oms_st.get("orders_filled", 0) > 0:
                                oms_filled = oms_st.get("orders_filled", 0)
                        except Exception:
                            pass

                    strategy_approved = passed_grade
                    cap_rej_count = max(0, strategy_approved - oms_routed)
                    if cap_rej_count > 0 and "Max Open Positions (1/1)" not in cap_reasons:
                        cap_reasons["Max Open Positions (1/1)"] = cap_rej_count

                    funnel.update({
                        "signals": total,
                        "after_confidence": passed_conf,
                        "rej_confidence": total - passed_conf,
                        "after_agreement": passed_agree,
                        "rej_agreement": passed_conf - passed_agree,
                        "after_pev": passed_pev,
                        "rej_pev": passed_agree - passed_pev,
                        "after_ev": passed_ev,
                        "rej_ev": passed_pev - passed_ev,
                        "after_grade": strategy_approved,
                        "rej_grade": passed_ev - strategy_approved,
                        "after_oms_check": oms_routed,
                        "rej_capacity": cap_rej_count,
                        "executed": oms_filled,
                        "total_predictive": total - strategy_approved,
                        "total_capacity": cap_rej_count,
                    })

                    conn.close()

                    # If an evaluated candidate row was found, parse into canonical snapshot
                    if latest_candidate_row is not None:
                        row = latest_candidate_row
                        snap_id = row["snapshot_id"]
                        ts_raw = row["timestamp"]
                        time_str = "—"
                        try:
                            from datetime import datetime as _dt
                            ts_obj = _dt.fromisoformat(ts_raw.replace("Z", "+00:00"))
                            time_str = ts_obj.strftime("%H:%M:%S")
                        except Exception:
                            time_str = str(ts_raw).split("T")[-1][:8] if "T" in str(ts_raw) else str(ts_raw)

                        dj = _json.loads(row["decision_json"] or "{}")
                        action = (dj.get("action") or "").upper()
                        reason = dj.get("reason") or ""
                        
                        conf_j = _json.loads(row["confidence_json"] or "{}")
                        ev_j = _json.loads(row["expected_value_json"] or "{}")
                        confl_j = _json.loads(row["confluence_json"] or "{}")
                        mkt_j = _json.loads(row["market_json"] or "{}")
                        agents_j = _json.loads(row["agents_json"] or "{}")
                        gates_j = _json.loads(row["gate_results_json"] or "{}")

                        if action == "EXECUTE":
                            decision_state = "EXECUTED"
                        elif action == "REJECTED":
                            decision_state = "EVALUATED_REJECTED"
                        elif action == "APPROVED":
                            decision_state = "EVALUATED_EXECUTABLE"
                        elif action == "PENDING":
                            decision_state = "PENDING"
                        else:
                            decision_state = "NO_CANDIDATE"

                        bullish = confl_j.get("bullish", 0)
                        bearish = confl_j.get("bearish", 0)
                        if bearish > bullish:
                            candidate_direction = "BUY_PE"
                        elif bullish > bearish:
                            candidate_direction = "BUY_CE"
                        else:
                            struct_sig = str(agents_j.get("structure", {}).get("signal", ""))
                            mom_sig = str(agents_j.get("momentum", {}).get("signal", ""))
                            if "BEAR" in struct_sig or "BEAR" in mom_sig:
                                candidate_direction = "BUY_PE"
                            elif "BULL" in struct_sig or "BULL" in mom_sig:
                                candidate_direction = "BUY_CE"
                            else:
                                candidate_direction = "BUY_PE" if "PE" in reason else ("BUY_CE" if "CE" in reason else "NONE")

                        regime_val = "—"
                        if "regime" in agents_j:
                            regime_val = agents_j["regime"].get("details", {}).get("regime", "—")
                        if regime_val == "—" and "Regime" in gates_j:
                            regime_val = str(gates_j["Regime"].get("detail", "")).replace("Regime: ", "").strip()

                        structure_val = "—"
                        if "structure" in agents_j:
                            struct_details = agents_j["structure"].get("details", {}).get("structure", {})
                            if isinstance(struct_details, dict):
                                structure_val = struct_details.get("type", "—")
                            else:
                                structure_val = str(struct_details)
                        if structure_val == "—" and "Structure" in gates_j:
                            structure_val = str(gates_j["Structure"].get("detail", "")).replace("Structure: ", "").strip()

                        stage = "—"
                        reason_up = reason.upper()
                        if "LOW_CONFIDENCE" in reason_up or "CONF" in reason_up:
                            stage = "Confidence"
                        elif "CONFLUENCE" in reason_up or "AGREE" in reason_up:
                            stage = "Agent Agreement"
                        elif "PEV" in reason_up or "BREAKEVEN" in reason_up:
                            stage = "Cost/Breakeven (PEV)"
                        elif "LOW_EV" in reason_up or "EXPECTED_VALUE" in reason_up:
                            stage = "Expected Value (EV)"
                        elif "SAME_STRUCTURAL_TREND" in reason_up:
                            stage = "Structure Reset Guard"
                        elif "GRADE" in reason_up or "SQUEEZE" in reason_up or "STRUCTURE" in reason_up or "CHOP" in reason_up or "REGIME" in reason_up:
                            stage = "Grade / Structure"
                        elif "CAPACITY" in reason_up or "MAX OPEN POSITIONS" in reason_up:
                            stage = "OMS / Capacity"

                        effective_conf = conf_j.get("adaptive_threshold")
                        if "Confidence" in gates_j:
                            conf_detail = gates_j["Confidence"].get("detail", "")
                            import re as _re
                            m = _re.search(r'need\s+([\d\.]+)%', conf_detail)
                            if m:
                                try:
                                    effective_conf = float(m.group(1))
                                except Exception:
                                    pass

                        gate_map = [
                            ("Confidence",            "Confidence"),
                            ("Agent Agreement",        "Agreement  ≥35%"),
                            ("Cost/Breakeven (PEV)",   "PEV"),
                            ("Expected Value (EV)",    "EV"),
                            ("Regime-Aware Grade",     "Grade / Structure"),
                            ("Structure",              "Structure"),
                            ("Structure Reset",        "Structure Reset Guard"),
                            ("Decay/Theta",            "Decay/Theta"),
                        ]
                        gate_rows = []
                        for db_key, display in gate_map:
                            g = gates_j.get(db_key)
                            if g is None:
                                continue
                            passed = g.get("passed") in (True, "True", "true")
                            actual = g.get("actual", "—")
                            detail = g.get("detail", "")
                            result = "PASS" if passed else "FAIL"
                            if isinstance(actual, float):
                                val_str = f"{actual:.1f}%" if actual <= 100 else f"{actual:.2f}"
                            else:
                                val_str = str(actual)

                            # Reconcile Confidence gate display requirement
                            if db_key == "Confidence" and effective_conf is not None:
                                base_adapt = conf_j.get("adaptive_threshold")
                                if base_adapt is not None and effective_conf != base_adapt:
                                    detail = f"≥ {effective_conf:.1f}% (Relaxed from {base_adapt:.1f}% · Grade {conf_j.get('grade', '—')})"
                                else:
                                    detail = f"≥ {effective_conf:.1f}%"
                            elif db_key == "Cost/Breakeven (PEV)":
                                import re as _re
                                m_pev = _re.search(r'PEV:\s*([\d\.]+)', detail)
                                m_req = _re.search(r'Req:\s*([\d\.]+)', detail)
                                if m_pev:
                                    val_str = m_pev.group(1)
                                if m_req:
                                    detail = f"PEV ≥ {m_req.group(1)}"
                            elif db_key == "Expected Value (EV)":
                                ev_r = ev_j.get("ev_r")
                                if ev_r is not None:
                                    val_str = f"{ev_r:.2f}R"
                                    detail = "EV ≥ 0.50R threshold"
                            elif db_key == "Regime-Aware Grade":
                                import re as _re
                                m_grade = _re.search(r'Grade:\s*([A-Z\+]+)', detail)
                                if m_grade:
                                    val_str = m_grade.group(1)
                                    m_regime = _re.search(r'Regime:\s*([A-Z_]+)', detail)
                                    m_req = _re.search(r'Required:\s*([A-Z\+_]+)', detail)
                                    if m_regime and m_req:
                                        detail = f"Grade {m_req.group(1)} required in {m_regime.group(1)}"
                            elif db_key == "Structure Reset":
                                if passed:
                                    val_str = "OK"
                                else:
                                    import re as _re
                                    m_count = _re.search(r'Already entered (\d+) times', detail)
                                    if m_count:
                                        val_str = f"{m_count.group(1)} prior entries"

                            gate_rows.append({"gate": display, "result": result, "value": val_str, "requirement": detail})

                        if decision_state == "EXECUTED":
                            oms_result = "EXECUTED"
                            oms_val = candidate_direction
                            oms_req = "order filled via OMS"
                        elif is_capacity:
                            oms_result = "FAIL"
                            oms_val = "CAPACITY BLOCKED"
                            oms_req = reason
                        elif decision_state == "EVALUATED_REJECTED":
                            oms_result = "NOT REACHED"
                            oms_val = "—"
                            oms_req = f"rejected upstream ({stage})"
                        elif decision_state == "EVALUATED_EXECUTABLE":
                            oms_result = "PASS"
                            oms_val = "READY"
                            oms_req = "pending OMS routing"
                        else:
                            oms_result = "NOT REACHED"
                            oms_val = "—"
                            oms_req = "max 1 pos"

                        gate_rows.append({"gate": "OMS / Capacity", "result": oms_result, "value": oms_val, "requirement": oms_req})

                        agree_pct = None
                        if "Agent Agreement" in gates_j:
                            agree_actual = gates_j["Agent Agreement"].get("actual")
                            if agree_actual is not None and agree_actual != "—":
                                try:
                                    agree_pct = float(agree_actual)
                                except Exception:
                                    pass

                        latest_snapshot = {
                            "snapshot_id": snap_id,
                            "timestamp": ts_raw,
                            "time_str": time_str,
                            "candidate_direction": candidate_direction,
                            "decision_state": decision_state,
                            "decision_action": action,
                            "rejection_reason": reason,
                            "rejection_stage": stage,
                            "spot_price": mkt_j.get("spot_price"),
                            "confidence": conf_j.get("raw"),
                            "adaptive_threshold": conf_j.get("adaptive_threshold"),
                            "effective_threshold": effective_conf,
                            "agreement_pct": agree_pct,
                            "ev_r": ev_j.get("ev_r"),
                            "ev_score": ev_j.get("normalized_score"),
                            "grade": conf_j.get("grade", "—"),
                            "regime": regime_val,
                            "structure": structure_val,
                            "confluence": confl_j,
                            "agents": agents_j,
                            "gate_rows": gate_rows
                        }

                except Exception as db_err:
                    logger.warning(f"session_stats DB query failed: {db_err}")

                wins = 0
                losses = 0
                net_pnl = 0.0
                net_r = 0.0
                conf_executed = []

                if os.path.exists(db_path):
                    with sqlite3.connect(db_path) as conn:
                        conn.row_factory = sqlite3.Row
                        cur = conn.cursor()
                        cur.execute(
                            "SELECT result, net_pnl, r_multiple, confidence FROM trade_outcomes "
                            "WHERE date(signal_timestamp) = ? "
                            "AND trade_id NOT LIKE 'POS_%' AND trade_id NOT LIKE 'sig_%' AND trade_id NOT LIKE 'test-%' AND trade_id NOT LIKE 'INT_POS_%'",
                            (today_str,)
                        )
                        rows = cur.fetchall()
                        for r in rows:
                            res = r["result"]
                            if res == "WIN":
                                wins += 1
                            elif res == "LOSS":
                                losses += 1
                            if r["net_pnl"] is not None:
                                net_pnl += float(r["net_pnl"])
                            if r["r_multiple"] is not None:
                                net_r += float(r["r_multiple"])
                            if r["confidence"] and float(r["confidence"]) > 0:
                                conf_executed.append(float(r["confidence"]))

                # Fail-Closed Reality Ledger Reconciliation Check (P0.5 & P5)
                recon_status = "CONSISTENT"
                recon_mismatches = []
                if self._oms and self._position_manager:
                    try:
                        from core.reconciliation import compute_execution_reconciliation
                        recon_status, recon_mismatches = compute_execution_reconciliation(self._oms, self._position_manager)
                    except Exception as re_err:
                        logger.warning(f"Reconciliation check failed: {re_err}")
                else:
                    try:
                        with sqlite3.connect(db_path) as conn:
                            c = conn.cursor()
                            c.execute("SELECT COUNT(*) FROM orders WHERE date(created_at) = ? AND state IN ('FILLED_ACTIVE', 'ENTRY_FILLED', 'POSITION_CLOSED')", (today_str,))
                            db_filled = c.fetchone()[0] or 0
                            c.execute("SELECT COUNT(*) FROM trade_outcomes WHERE date(signal_timestamp) = ? AND trade_id NOT LIKE 'POS_%' AND trade_id NOT LIKE 'sig_%' AND trade_id NOT LIKE 'test-%' AND trade_id NOT LIKE 'INT_POS_%'", (today_str,))
                            db_outcomes = c.fetchone()[0] or 0
                            if db_filled != db_outcomes:
                                recon_status = "COUNT_MISMATCH"
                                recon_mismatches.append(f"DB Reality Invariant: OMS filled ({db_filled}) != trade outcomes ({db_outcomes})")
                    except Exception as e:
                        recon_status = "ERROR"
                        recon_mismatches.append(f"DB reconciliation query error: {e}")

                is_reconciled = (recon_status == "CONSISTENT")

                if not is_reconciled:
                    session = {
                        "session_date": today_str,
                        "total_signals": funnel["signals"],
                        "strategy_approved": funnel["after_grade"],
                        "executed": funnel["executed"],
                        "predictive_rejections": funnel["total_predictive"],
                        "capacity_rejections": funnel["total_capacity"],
                        "wins": None,
                        "losses": None,
                        "net_pnl": None,
                        "net_r": None,
                        "avg_conf_executed": None,
                        "is_reconciled": False,
                        "reconciliation_status": recon_status,
                        "reconciliation_mismatches": recon_mismatches,
                        "pnl_display": "— (RECONCILIATION INVALID)",
                        "r_display": "— (RECONCILIATION INVALID)",
                        "winrate_display": "RECONCILIATION INVALID",
                    }
                else:
                    session = {
                        "session_date": today_str,
                        "total_signals": funnel["signals"],
                        "strategy_approved": funnel["after_grade"],
                        "executed": funnel["executed"],
                        "predictive_rejections": funnel["total_predictive"],
                        "capacity_rejections": funnel["total_capacity"],
                        "wins": wins,
                        "losses": losses,
                        "net_pnl": round(net_pnl, 2),
                        "net_r": round(net_r, 2),
                        "avg_conf_executed": round(sum(conf_executed) / len(conf_executed), 1) if conf_executed else None,
                        "is_reconciled": True,
                        "reconciliation_status": "CONSISTENT",
                        "reconciliation_mismatches": [],
                    }

                rejections = {
                    "predictive": [{"reason": k, "count": v} for k, v in sorted(pred_reasons.items(), key=lambda x: -x[1])],
                    "capacity":   [{"reason": k, "count": v} for k, v in sorted(cap_reasons.items(), key=lambda x: -x[1])],
                }

                return _safe_jsonify({
                    "status": "ok",
                    "date": today_str,
                    "campaign": campaign,
                    "session": session,
                    "funnel": funnel,
                    "rejections": rejections,
                    "latest_snapshot": latest_snapshot,
                    "latest_gate": {
                        "timestamp": latest_snapshot["time_str"],
                        "snapshot_id": latest_snapshot["snapshot_id"],
                        "rows": latest_snapshot["gate_rows"]
                    },
                })

            except Exception as e:
                logger.error(f"SESSION_STATS ENDPOINT ERROR: {e}")
                return _safe_jsonify({"status": "error", "message": str(e)}), 500

        @self.app.route("/api/trades")
        def api_trades():
            """
            Trade Ledger & Replay endpoint for dashboard panel.
            Authority model:
              Today's executions: Canonical live memory (PositionManager & OMS orders today)
              Historical recovery: SQLite trade_outcomes table
            """
            try:
                today_str = datetime.now().date().isoformat()
                trades = []
                seen_ids = set()
                seen_keys = set()

                def _normalize_trade_id(raw_id) -> str:
                    if not raw_id:
                        return ""
                    s = str(raw_id)
                    for prefix in ["TRD_", "INT_", "SIM_ORD_", "SIM_SL_"]:
                        if s.startswith(prefix):
                            s = s[len(prefix):]
                    s = s.replace("-", "_")
                    parts = s.split("_")
                    if len(parts) >= 4:
                        s = f"{parts[0]}_{parts[1]}_{parts[3]}"
                    return s

                import re
                def _extract_fallback_strike_and_expiry(symbol, strike, expiry):
                    # User Directive: Only parse if concrete contract symbol e.g. NIFTY26SEP24000PE or NIFTY24300CE
                    # NEVER guess or parse from generic "NIFTY", "BUY_CE", "BUY_PE"
                    if not symbol or str(symbol).upper() in ("NIFTY", "BUY_CE", "BUY_PE", "SIMULATED", "UNKNOWN"):
                        return strike, expiry
                    if strike is None:
                        m = re.search(r"NIFTY(?:\d{2}[A-Z]{3})?(\d{4,5})(CE|PE)", str(symbol).upper())
                        if m:
                            try:
                                strike = float(m.group(1))
                            except Exception:
                                pass
                    return strike, expiry

                def _add_trade(trade_obj, orig_ids=None):
                    t_id = trade_obj.get("trade_id")
                    norm_key = _normalize_trade_id(t_id)
                    if (t_id and t_id in seen_ids) or (norm_key and norm_key in seen_keys):
                        return False
                    if t_id:
                        seen_ids.add(t_id)
                    if norm_key:
                        seen_keys.add(norm_key)
                    if orig_ids:
                        for oid in orig_ids:
                            if oid:
                                seen_ids.add(oid)
                                k = _normalize_trade_id(oid)
                                if k:
                                    seen_keys.add(k)
                    trades.append(trade_obj)
                    return True

                # 1. Canonical Live Open Positions
                open_pos_list = []
                if self._position_manager and hasattr(self._position_manager, "open_positions"):
                    open_pos_list = list(self._position_manager.open_positions.values())
                elif self._status_data and "positions" in self._status_data:
                    open_pos_list = self._status_data.get("positions", [])

                for pos in open_pos_list:
                    pos_dict = pos.to_dict() if hasattr(pos, "to_dict") else dict(pos)
                    pos_id = pos_dict.get("id") or pos_dict.get("trade_id") or pos_dict.get("snapshot_id")
                    intent_id = pos_dict.get("intent_id", "")
                    canon_trade_id = f"TRD_{intent_id[4:]}" if intent_id.startswith("INT_") else (pos_id or "")

                    entry_p = float(pos_dict.get("entry_price") or pos_dict.get("entry") or 0.0)
                    sl_p = float(pos_dict.get("stop_loss") or pos_dict.get("sl") or 0.0)
                    t1_p = float(pos_dict.get("target_1") or pos_dict.get("target1") or 0.0)
                    qty_val = int(pos_dict.get("qty") or 50)
                    unrealized_pnl = pos_dict.get("net_pnl")
                    if unrealized_pnl is None:
                        raw_pnl = pos_dict.get("unrealized_pnl", 0.0)
                        if isinstance(raw_pnl, str):
                            try:
                                unrealized_pnl = float(raw_pnl.replace("₹", "").replace(",", "").strip())
                            except Exception:
                                unrealized_pnl = 0.0
                        else:
                            unrealized_pnl = float(raw_pnl or 0.0)

                    r_mult = None
                    if sl_p > 0 and entry_p > 0 and qty_val > 0 and abs(entry_p - sl_p) > 0:
                        r_mult = unrealized_pnl / (abs(entry_p - sl_p) * qty_val)

                    opened_time = pos_dict.get("opened_at") or pos_dict.get("time") or datetime.now().isoformat()
                    is_today = opened_time.startswith(today_str)
                    contract_sym = pos_dict.get("contract") or pos_dict.get("symbol") or pos_dict.get("signal_type") or pos_dict.get("type") or "UNKNOWN"
                    stk_val = pos_dict.get("strike")
                    exp_val = pos_dict.get("expiry")
                    stk_val, exp_val = _extract_fallback_strike_and_expiry(contract_sym, stk_val, exp_val)

                    _add_trade({
                        "trade_id": canon_trade_id or pos_id,
                        "time": opened_time,
                        "signal": contract_sym,
                        "strike": stk_val,
                        "expiry": exp_val,
                        "entry": entry_p,
                        "exit_price": None,
                        "sl": sl_p,
                        "target1": t1_p,
                        "qty": qty_val,
                        "net_pnl": unrealized_pnl,
                        "result": "OPEN",
                        "opened_at": opened_time,
                        "closed_at": None,
                        "confidence": float(pos_dict.get("confidence") or pos_dict.get("calibrated_confidence") or pos_dict.get("weighted_score") or 0.0),
                        "grade": pos_dict.get("grade") or pos_dict.get("tsl_grade") or "—",
                        "is_reconstructed": not is_today,
                        "r_multiple": r_mult
                    }, orig_ids=[pos_id, intent_id, canon_trade_id])

                # 2. Canonical Live Closed Positions Today
                closed_pos_list = []
                if self._position_manager and hasattr(self._position_manager, "closed_positions_today"):
                    closed_pos_list = list(self._position_manager.closed_positions_today)
                elif self._status_data and "closed_positions_today" in self._status_data:
                    closed_pos_list = self._status_data.get("closed_positions_today", [])

                for c_pos in closed_pos_list:
                    c_dict = c_pos.to_dict() if hasattr(c_pos, "to_dict") else dict(c_pos)
                    trade_id = c_dict.get("trade_id") or c_dict.get("id")
                    intent_id = c_dict.get("intent_id", "")
                    canon_trade_id = f"TRD_{intent_id[4:]}" if intent_id.startswith("INT_") else (trade_id or "")

                    c_time = c_dict.get("timestamp") or c_dict.get("time") or datetime.now().isoformat()
                    is_today = c_time.startswith(today_str)
                    contract_sym = c_dict.get("contract") or c_dict.get("signal") or c_dict.get("signal_type") or ""
                    stk_val = c_dict.get("strike")
                    exp_val = c_dict.get("expiry")
                    stk_val, exp_val = _extract_fallback_strike_and_expiry(contract_sym, stk_val, exp_val)

                    _add_trade({
                        "trade_id": canon_trade_id or trade_id,
                        "time": c_time,
                        "signal": contract_sym,
                        "strike": stk_val,
                        "expiry": exp_val,
                        "entry": float(c_dict.get("entry_price") or c_dict.get("entry") or 0.0),
                        "exit_price": float(c_dict.get("exit_price") or c_dict.get("exit") or 0.0),
                        "sl": float(c_dict.get("stop_loss") or c_dict.get("sl") or 0.0),
                        "target1": float(c_dict.get("target_1") or c_dict.get("target1") or 0.0),
                        "qty": int(c_dict.get("quantity") or c_dict.get("qty") or 50),
                        "net_pnl": float(c_dict.get("pnl") or c_dict.get("net_pnl") or 0.0),
                        "result": c_dict.get("outcome") or "CLOSED",
                        "opened_at": c_dict.get("timestamp") or c_dict.get("opened_at"),
                        "closed_at": c_dict.get("closed_at") or datetime.now().isoformat(),
                        "confidence": float(c_dict.get("confidence") or c_dict.get("weighted_score") or 0.0),
                        "grade": c_dict.get("grade") or "—",
                        "is_reconstructed": not is_today,
                        "r_multiple": c_dict.get("r_multiple")
                    }, orig_ids=[trade_id, intent_id, canon_trade_id])

                # 3. Check OMS Orders Table for Today
                if self._oms:
                    try:
                        open_orders = self._oms.get_open_orders()
                        for order in open_orders:
                            o_id = order.get("signal_id") or order.get("intent_id")
                            intent_id = order.get("intent_id", "")
                            canon_trade_id = f"TRD_{intent_id[4:]}" if intent_id.startswith("INT_") else (o_id or "")
                            state = order.get("state")
                            if state in ("ENTRY_SUBMITTED", "PARTIAL_FILLED", "FILLED_ACTIVE", "ENTRY_FILLED"):
                                fill_p = float(order.get("avg_fill_price") or order.get("requested_price") or 0.0)
                                sl_p = float(order.get("stop_loss_price") or 0.0)
                                qty_v = int(order.get("qty") or 50)
                                o_time = order.get("created_at") or datetime.now().isoformat()
                                is_today = o_time.startswith(today_str)
                                contract_sym = order.get("symbol") or "NIFTY"
                                stk_val = order.get("strike")
                                exp_val = order.get("expiry")
                                stk_val, exp_val = _extract_fallback_strike_and_expiry(contract_sym, stk_val, exp_val)
                                _add_trade({
                                    "trade_id": canon_trade_id or o_id,
                                    "time": o_time,
                                    "signal": contract_sym,
                                    "strike": stk_val,
                                    "expiry": exp_val,
                                    "entry": fill_p,
                                    "exit_price": None,
                                    "sl": sl_p,
                                    "target1": float(order.get("target_price") or (fill_p + (abs(fill_p - sl_p) * 1.5) if sl_p > 0 else 0.0)),
                                    "qty": qty_v,
                                    "net_pnl": 0.0,
                                    "result": "OPEN",
                                    "opened_at": order.get("created_at"),
                                    "closed_at": None,
                                    "confidence": 0.0,
                                    "grade": "—",
                                    "is_reconstructed": not is_today,
                                    "r_multiple": 0.0
                                }, orig_ids=[o_id, intent_id, canon_trade_id])
                    except Exception as oms_e:
                        logger.warning(f"OMS order check in /api/trades failed: {oms_e}")

                # 3b. Check Canonical Simulation Engine State
                if self._simulation_engine:
                    try:
                        sim_open = getattr(self._simulation_engine, "open_trades", [])
                        for s_trade in sim_open:
                            s_dict = s_trade.to_dict() if hasattr(s_trade, "to_dict") else dict(s_trade)
                            s_id = s_dict.get("trade_id") or s_dict.get("id")
                            s_time = s_dict.get("opened_at") or s_dict.get("time") or datetime.now().isoformat()
                            is_today = s_time.startswith(today_str)
                            contract_sym = s_dict.get("contract") or (s_dict.get("instrument") or {}).get("symbol") or s_dict.get("signal_type") or "SIMULATED"
                            stk_val = s_dict.get("strike") or (s_dict.get("instrument") or {}).get("strike")
                            exp_val = s_dict.get("expiry") or (s_dict.get("instrument") or {}).get("expiry")
                            stk_val, exp_val = _extract_fallback_strike_and_expiry(contract_sym, stk_val, exp_val)
                            _add_trade({
                                "trade_id": s_id,
                                "time": s_time,
                                "signal": contract_sym,
                                "strike": stk_val,
                                "expiry": exp_val,
                                "entry": float(s_dict.get("entry_price") or 0.0),
                                "exit_price": None,
                                "sl": float(s_dict.get("sl") or s_dict.get("stop_loss") or 0.0),
                                "target1": float(s_dict.get("target") or s_dict.get("target_1") or 0.0),
                                "qty": int(s_dict.get("qty") or 50),
                                "net_pnl": float(s_dict.get("unrealized_pnl") or 0.0),
                                "result": "OPEN",
                                "opened_at": s_dict.get("opened_at"),
                                "closed_at": None,
                                "confidence": float(s_dict.get("confidence") or 0.0),
                                "grade": s_dict.get("grade", "—"),
                                "is_reconstructed": not is_today,
                                "r_multiple": None
                            }, orig_ids=[s_id])
                    except Exception as sim_e:
                        logger.warning(f"Simulation engine check in /api/trades failed: {sim_e}")

                # 4. Fetch Historical Recovery State (SQLite DB)
                db_paths = [
                    os.getenv("NIFTY_DB_PATH", "data/trading_v4_sim.db"),
                    "data/trading_v4_live.db"
                ]
                for db_path in db_paths:
                    if os.path.exists(db_path):
                        try:
                            with sqlite3.connect(db_path) as conn:
                                conn.row_factory = sqlite3.Row
                                cur = conn.cursor()
                                cur.execute(
                                    "SELECT * FROM trade_outcomes "
                                    "WHERE trade_id NOT LIKE 'POS_%' AND trade_id NOT LIKE 'sig_%' AND trade_id NOT LIKE 'test-%' AND trade_id NOT LIKE 'INT_POS_%' "
                                    "ORDER BY signal_timestamp DESC LIMIT 100"
                                )
                                rows = cur.fetchall()
                                for r in rows:
                                    t = dict(r)
                                    t_id = t.get("trade_id")
                                    sig_ts = t.get("signal_timestamp") or ""
                                    is_today = sig_ts.startswith(today_str)
                                    is_recon = not is_today

                                    contract_sym = t.get("contract")
                                    stk_val = t.get("strike")
                                    exp_val = t.get("expiry")
                                    stk_val, exp_val = _extract_fallback_strike_and_expiry(contract_sym, stk_val, exp_val)

                                    _add_trade({
                                        "trade_id": t_id,
                                        "campaign_id": "SHADOW-V2",
                                        "time": sig_ts,
                                        "signal": contract_sym,
                                        "strike": stk_val,
                                        "expiry": exp_val,
                                        "entry": t.get("entry"),
                                        "exit_price": t.get("exit_price"),
                                        "sl": t.get("sl"),
                                        "target1": t.get("target"),
                                        "qty": t.get("qty"),
                                        "net_pnl": t.get("net_pnl"),
                                        "result": t.get("result"),
                                        "opened_at": t.get("opened_at"),
                                        "closed_at": t.get("closed_at"),
                                        "confidence": t.get("confidence"),
                                        "grade": t.get("grade") or "—",
                                        "is_reconstructed": is_recon,
                                        "r_multiple": t.get("r_multiple"),
                                        "scope_status": "VALID_SESSION" if is_today else "UNSCOPED / HISTORICAL"
                                    }, orig_ids=[t_id])
                        except Exception as dbe:
                            logger.warning(f"Failed to query {db_path} in /api/trades: {dbe}")

                # 5. Sort completely chronologically (newest first)
                trades.sort(key=lambda x: str(x.get("time") or ""), reverse=True)

                return _safe_jsonify({"status": "ok", "trades": trades, "source": "execution_ledger"})

            except Exception as e:
                logger.error(f"TRADES ENDPOINT ERROR: {e}", exc_info=True)
                return _safe_jsonify({"status": "error", "message": str(e)}), 500

        @self.app.route("/health")
        def health():
            now = time.time()
            loop_alive = (now - self._last_cycle) < 60 if self._last_cycle else True
            is_healthy = loop_alive and self._errors < 10
            return jsonify({
                "status": "ok" if is_healthy else "degraded",
                "loop_alive": loop_alive,
                "engine": "running" if loop_alive else "stalled",
                "last_cycle_sec_ago": round(now - self._last_cycle, 1) if self._last_cycle else 0,
                "errors": self._errors,
                "trading_enabled": self._trading_enabled
            })

        @self.app.route("/halt", methods=["POST"])
        def halt():
            try:
                with open("HALT", "w") as f:
                    f.write("HALT triggered via dashboard /halt endpoint")
                logger.critical("🛑 HALT file created via dashboard endpoint")
                return jsonify({
                    "status": "halted",
                    "message": "HALT file created. System will stop at next cycle. Delete HALT file to resume."
                }), 200
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 500

        @self.app.route("/resume", methods=["POST"])
        def resume():
            try:
                if os.path.exists("HALT"):
                    os.remove("HALT")
                    logger.info("▶️ HALT file removed via dashboard /resume endpoint")
                return jsonify({
                    "status": "resumed",
                    "message": "HALT file removed. Use /start via Telegram to re-enable trading_enabled."
                }), 200
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 500

    def _setup_error_handlers(self):
        @self.app.errorhandler(404)
        def not_found(e):
            return _safe_jsonify({"error": "Not found", "message": str(e)}), 404

        @self.app.errorhandler(405)
        def method_not_allowed(e):
            return _safe_jsonify({"error": "Method not allowed", "message": str(e)}), 405

        @self.app.errorhandler(500)
        def internal_error(e):
            logger.error(f"INTERNAL SERVER ERROR: {e}")
            self._errors += 1
            return _safe_jsonify({
                "error": "Internal Server Error",
                "message": str(e)
            }), 500

    def _setup_socket_events(self):
        @self.socketio.on('connect')
        def handle_connect(*args, **kwargs):
            logger.debug("🌐 Client connected to WebSocket")
            try:
                safe_data = json.loads(json.dumps(self._status_data, cls=_SafeEncoder))
                emit('system_status', safe_data)
            except Exception as e:
                logger.error(f"Error emitting system_status on connect: {e}")

    def emit_signal(self, signal_data: dict):
        try:
            safe_data = json.loads(json.dumps(signal_data, cls=_SafeEncoder))
            self.socketio.emit('signal_update', safe_data)
        except Exception as e:
            logger.error(f"Socket emit error: {e}")

    def set_burnin_components(self, burnin_tracker, readiness_scorer):
        self._burnin_tracker = burnin_tracker
        self._readiness_scorer = readiness_scorer

    def set_simulation_engine(self, sim_engine):
        self._simulation_engine = sim_engine

    def set_position_manager(self, pos_manager):
        self._position_manager = pos_manager

    def set_oms(self, oms):
        self._oms = oms

    def update_status(self, data: dict):
        self._status_data = data
        self._last_cycle = time.time()
        self._trading_enabled = data.get("risk", {}).get("trading_enabled", True)
        if "errors" in data:
            self._errors = data["errors"]

        now = time.time()
        current_posture = data.get("orchestrator", {}).get("runtime_posture")
        current_trading_enabled = self._trading_enabled

        state_changed = (
            current_posture != self._last_emitted_posture or
            current_trading_enabled != self._last_emitted_trading_status
        )

        if state_changed or (now - self._last_emit_ts >= self._emit_interval_seconds):
            try:
                safe_data = json.loads(json.dumps(data, cls=_SafeEncoder))
                self.socketio.emit('system_status', safe_data)
                self._last_emit_ts = now
                self._last_emitted_posture = current_posture
                self._last_emitted_trading_status = current_trading_enabled
            except Exception as e:
                logger.error(f"Socket status emit error: {e}")

    def start(self):
        def run_server():
            logger.info(f"🚀 Dashboard (SocketIO) starting at http://0.0.0.0:{self.port}")
            self.socketio.run(
                self.app,
                host=self.host,
                port=self.port,
                debug=False,
                use_reloader=False,
                log_output=False,
                allow_unsafe_werkzeug=True
            )

        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()