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
from decimal import Decimal
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


# Dashboard HTML template
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nifty AI Trading Operations Console</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Inter', 'Segoe UI', monospace;
            background: #0a0a0f;
            color: #e0e0e0;
            padding: 20px;
        }
        .header {
            text-align: center;
            padding: 15px;
            background: linear-gradient(135deg, #1a1a2e, #16213e);
            border-radius: 8px;
            margin-bottom: 15px;
            border: 1px solid #333;
        }
        .header h1 { color: #00d4ff; font-size: 22px; text-transform: uppercase; letter-spacing: 1px; }
        .header .subtitle { color: #888; font-size: 13px; margin-top: 5px; }
        
        .regime-banner {
            background: #111;
            border: 1px solid #444;
            color: #fff;
            padding: 10px 20px;
            border-radius: 6px;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-weight: bold;
            font-size: 14px;
        }
        
        .layout-grid {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 20px;
            margin-bottom: 20px;
        }
        
        .panel {
            background: #1a1a2e;
            border-radius: 8px;
            padding: 20px;
            border: 1px solid #333;
            margin-bottom: 15px;
        }
        .panel-title { color: #888; font-size: 12px; text-transform: uppercase; margin-bottom: 15px; letter-spacing: 1px; }
        
        .signal-panel { text-align: center; transition: all 0.3s ease; padding: 30px; border: 2px solid #333; }
        .signal-panel.buy-ce { border-color: #00ff88; box-shadow: 0 0 20px rgba(0, 255, 136, 0.15); }
        .signal-panel.buy-pe { border-color: #ff4444; box-shadow: 0 0 20px rgba(255, 68, 68, 0.15); }
        .signal-type { font-size: 24px; font-weight: bold; margin: 10px 0; color: #fff;}
        
        .exec-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            text-align: left;
            margin-top: 20px;
            background: #111;
            padding: 15px;
            border-radius: 6px;
        }
        .exec-item { display: flex; justify-content: space-between; font-size: 14px; padding: 4px 0; border-bottom: 1px dashed #222; }
        .exec-item:last-child { border-bottom: none; }
        .exec-label { color: #888; }
        .exec-value { font-weight: bold; color: #fff; }
        
        .confluence-meter { margin-top: 20px; }
        .confluence-bar { width: 100%; height: 10px; background: #ff4444; border-radius: 5px; overflow: hidden; display: flex; }
        .confluence-bull { height: 100%; background: #00ff88; transition: width 0.3s; }
        
        .telemetry-item { display: flex; justify-content: space-between; margin-bottom: 10px; font-size: 13px; padding-bottom: 5px; border-bottom: 1px solid #222; }
        
        .agents-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }
        .agent-card { background: #161625; padding: 12px; border-radius: 6px; border: 1px solid #2a2a35; font-size: 12px; }
        .agent-header { display: flex; justify-content: space-between; margin-bottom: 8px; font-weight: bold; color: #00d4ff; }
        .agent-metric { display: flex; justify-content: space-between; margin-bottom: 4px; }
        .agent-weight { color: #aa88ff; font-style: italic; margin-top: 5px; border-top: 1px dashed #333; padding-top: 5px; }
        
        .bullish { color: #00ff88; }
        .bearish { color: #ff4444; }
        .neutral { color: #ffaa00; }
        
        #log { background: #0d0d14; padding: 10px; border-radius: 6px; height: 200px; overflow-y: auto; font-family: monospace; font-size: 11px; color: #aaa; }
        .log-entry { margin-bottom: 4px; border-bottom: 1px solid #1a1a1a; padding-bottom: 2px;}
        
        .no-trade-reasons { background: #221111; color: #ff8888; padding: 10px; border-radius: 4px; text-align: left; margin-top: 15px; font-size: 13px; }
        .no-trade-reasons ul { padding-left: 20px; margin-top: 5px; }
    </style>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.4/socket.io.min.js"></script>
</head>
<body>
    <div class="header">
        <h1>🧠 Nifty AI Trading Operations Console</h1>
        <div class="subtitle" id="update-time">Connecting to engine...</div>
    </div>

    <div class="regime-banner" id="regime-banner">
        <span>REGIME: <span id="regime-val" style="color:#00d4ff;">DETERMINING...</span></span>
        <span id="regime-flags" style="color:#ffaa00; font-size: 12px;">Initializing systems</span>
    </div>

    <div class="layout-grid">
        <!-- LEFT COLUMN: EXECUTION -->
        <div>
            <div class="panel signal-panel" id="signal-container">
                <div class="panel-title">LIVE EXECUTION PANEL</div>
                <div id="signal-icon" style="font-size: 40px">⏳</div>
                <div class="signal-type" id="signal-type">WAITING FOR SIGNAL</div>
                
                <div id="execution-details" style="display:none;">
                    <div class="exec-grid">
                        <div class="exec-item"><span class="exec-label">Premium Entry</span><span class="exec-value" id="p-entry">—</span></div>
                        <div class="exec-item"><span class="exec-label">Premium SL</span><span class="exec-value" id="p-sl">—</span></div>
                        <div class="exec-item"><span class="exec-label">Target 1</span><span class="exec-value" id="p-t1">—</span></div>
                        <div class="exec-item"><span class="exec-label">Target 2</span><span class="exec-value" id="p-t2">—</span></div>
                    </div>
                    <div class="exec-grid" style="margin-top:10px;">
                        <div class="exec-item"><span class="exec-label">Spot Trigger</span><span class="exec-value" id="s-trigger">—</span></div>
                        <div class="exec-item"><span class="exec-label">Confidence</span><span class="exec-value" id="s-conf">—</span></div>
                        <div class="exec-item"><span class="exec-label">Grade</span><span class="exec-value" id="s-grade">—</span></div>
                        <div class="exec-item"><span class="exec-label">Decay Risk</span><span class="exec-value" id="s-decay">—</span></div>
                    </div>
                </div>

                <div id="no-trade-details" class="no-trade-reasons" style="display:none;">
                    <strong>NO TRADE REASON</strong>
                    <ul id="reasons-list"></ul>
                </div>
                
                <div class="confluence-meter">
                    <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:5px; color:#888;">
                        <span>BULLISH CONFLUENCE</span>
                        <span id="conf-text">0 / 0</span>
                    </div>
                    <div class="confluence-bar">
                        <div class="confluence-bull" id="conf-fill" style="width: 50%;"></div>
                    </div>
                </div>
            </div>
        </div>

        <!-- RIGHT COLUMN: TELEMETRY -->
        <div>
            <div class="panel">
                <div class="panel-title">ENGINE TELEMETRY</div>
                <div class="telemetry-item">
                    <span class="exec-label">Engine Latency</span>
                    <span class="exec-value" id="t-latency">---ms</span>
                </div>
                <div class="telemetry-item">
                    <span class="exec-label">OI Real Data Rate</span>
                    <span class="exec-value" id="t-oi-rate">---%</span>
                </div>
                <div class="telemetry-item">
                    <span class="exec-label">OI Chain Status</span>
                    <span class="exec-value" id="t-oi-status">---</span>
                </div>
                <div class="telemetry-item" style="margin-top: 15px; border-top: 1px dashed #333; padding-top: 10px;">
                    <span class="exec-label">Structure Quality</span>
                    <span class="exec-value" id="t-struct">---</span>
                </div>
                <div class="telemetry-item">
                    <span class="exec-label">Execution Quality</span>
                    <span class="exec-value" id="t-exec">---</span>
                </div>
                <div class="telemetry-item">
                    <span class="exec-label">Integrity Score</span>
                    <span class="exec-value" id="t-integ">---</span>
                </div>
            </div>
            
            <div class="panel">
                <div class="panel-title">SYSTEM LOGS</div>
                <div id="log"></div>
            </div>
        </div>
    </div>

    <div class="panel">
        <div class="panel-title">AGENT INTELLIGENCE MATRIX</div>
        <div class="agents-grid" id="agents-grid">
            <!-- Agent cards injected here -->
        </div>
    </div>

    <div class="panel" id="burnin-panel">
        <div class="panel-title">🎯 BURN-IN READINESS DASHBOARD</div>
        <div style="display:grid; grid-template-columns: 1fr 2fr; gap:20px;">
            <!-- Left: Readiness Score -->
            <div style="text-align:center; padding:20px; background:#0d0d14; border-radius:8px; border:1px solid #333;">
                <div style="font-size:11px; color:#888; text-transform:uppercase; letter-spacing:1px; margin-bottom:10px;">Readiness Score</div>
                <div id="bi-score" style="font-size:56px; font-weight:bold; color:#00d4ff; line-height:1;">--</div>
                <div id="bi-gate" style="font-size:13px; margin-top:10px; color:#ffaa00;">Loading...</div>
                <div style="margin-top:15px; font-size:11px; color:#555;">P × 0.35 + S × 0.25 + D × 0.20 + E × 0.20</div>
                <div style="margin-top:10px; display:flex; justify-content:space-between; font-size:11px;">
                    <span id="bi-trades" style="color:#888;">-- trades</span>
                    <span id="bi-days" style="color:#888;">-- days</span>
                </div>
            </div>
            <!-- Right: Category scores + Regime -->
            <div>
                <div style="margin-bottom:15px;">
                    <div style="font-size:11px; color:#888; margin-bottom:8px;">CATEGORY BREAKDOWN</div>
                    <div id="bi-categories"></div>
                </div>
                <div>
                    <div style="font-size:11px; color:#888; margin-bottom:8px;">EXECUTION QUALITY</div>
                    <div id="bi-exec" style="font-size:12px; color:#aaa;"></div>
                </div>
            </div>
        </div>
        <div style="margin-top:15px;">
            <div style="font-size:11px; color:#888; margin-bottom:8px;">REGIME INTELLIGENCE</div>
            <div id="bi-regime" style="display:flex; gap:10px; flex-wrap:wrap;"></div>
        </div>
        <div id="bi-recs" style="margin-top:15px; background:#101020; padding:12px; border-radius:6px; font-size:12px; color:#aaa;"></div>
    </div>

    <!-- Priority 1: Trade Replay & Ledger -->
    <div class="panel" id="trade-replay-panel">
        <div class="panel-title" style="display:flex; justify-content:space-between; align-items:center;">
            <span>📼 TRADE REPLAY & LEDGER</span>
            <span id="adaptation-alpha" style="font-size:12px; font-weight:normal; color:#00ff88;"></span>
        </div>
        
        <!-- Phase C: Replay Filters -->
        <div style="margin-bottom:10px; display:flex; gap:10px; font-size:12px; background:#151525; padding:8px; border-radius:4px;">
            <select id="filter-regime" style="background:#222; color:#fff; border:1px solid #444; padding:2px 5px;">
                <option value="ALL">All Regimes</option>
                <option value="CHOPPY">Choppy</option>
                <option value="TRENDING_UP">Trending Up</option>
                <option value="TRENDING_DOWN">Trending Down</option>
                <option value="VOLATILE">Volatile</option>
                <option value="BREAKOUT">Breakout</option>
            </select>
            <select id="filter-failure" style="background:#222; color:#fff; border:1px solid #444; padding:2px 5px;">
                <option value="ALL">All Failure Types</option>
                <option value="FALSE_BREAKOUT">False Breakout</option>
                <option value="SLIPPAGE_LOSS">Slippage Loss</option>
                <option value="SPREAD_DEGRADATION">Spread Degradation</option>
                <option value="EARLY_EXIT">Early Exit</option>
                <option value="GOOD_LOSS">Good Loss</option>
            </select>
            <select id="filter-quality" style="background:#222; color:#fff; border:1px solid #444; padding:2px 5px;">
                <option value="ALL">All Execution Qualities</option>
                <option value="GOOD">Good</option>
                <option value="FAIR">Fair</option>
                <option value="POOR">Poor</option>
            </select>
            <label style="display:flex; align-items:center; gap:5px; color:#aaa; cursor:pointer;">
                <input type="checkbox" id="filter-adapted" /> Adapted Only
            </label>
        </div>

        <div style="overflow-x:auto;">
            <table style="width:100%; border-collapse:collapse; font-size:12px; text-align:left;">
                <thead>
                    <tr style="border-bottom:1px solid #333; color:#888;">
                        <th style="padding:8px;">Time</th>
                        <th style="padding:8px;">Signal</th>
                        <th style="padding:8px;">Regime</th>
                        <th style="padding:8px;">Execution</th>
                        <th style="padding:8px;">Result (Actual vs Base)</th>
                        <th style="padding:8px;">Failure Type</th>
                        <th style="padding:8px;">Adaptation Outcome</th>
                    </tr>
                </thead>
                <tbody id="trade-ledger-body">
                    <!-- Populated via JS -->
                </tbody>
            </table>
        </div>
    </div>

    <script>
        const socket = io();

        socket.on('connect', () => {
            document.getElementById('update-time').textContent = 'Live Connection Active';
        });

        socket.on('disconnect', () => {
            document.getElementById('update-time').textContent = 'Disconnected - Attempting Reconnect...';
            document.getElementById('update-time').style.color = '#ff4444';
        });

        socket.on('system_status', (data) => updateDashboard(data));
        socket.on('signal_update', (data) => updateDashboard(data));

        function updateDashboard(data) {
            if (!data) return;
            
            const sig = data.last_signal || (data.signal ? data : null);
            const agents = data.agents || null;
            
            document.getElementById('update-time').textContent = 'Last sync: ' + new Date().toLocaleTimeString();
            document.getElementById('update-time').style.color = '#888';

            // Telemetry Update
            if (data.latency_ms !== undefined) {
                const latEl = document.getElementById('t-latency');
                latEl.textContent = data.latency_ms + 'ms';
                latEl.style.color = data.latency_status === 'CRITICAL' ? '#ff4444' : (data.latency_status === 'WARNING' ? '#ffaa00' : '#00ff88');
            }
            if (data.oi_health) {
                document.getElementById('t-oi-rate').textContent = data.oi_health.rate || '100%';
                document.getElementById('t-oi-status').textContent = data.oi_health.status || 'LIVE';
                document.getElementById('t-oi-status').style.color = data.oi_health.status === 'FALLBACK' ? '#ffaa00' : '#00ff88';
            }

            // Regime Banner
            if (sig) {
                document.getElementById('regime-val').textContent = sig.regime + ' ⚡';
                let flags = [];
                if (data.latency_status === 'CRITICAL') flags.push('LATENCY RISK');
                if (data.oi_health && data.oi_health.status === 'FALLBACK') flags.push('OI FALLBACK ACTIVE');
                if (sig.reasons && sig.reasons.some(r => r.includes('gap') || r.includes('Gap'))) flags.push('GAP SHOCK ACTIVE');
                document.getElementById('regime-flags').textContent = flags.join(' | ');
            }

            // Active Signal
            const container = document.getElementById('signal-container');
            const execDetails = document.getElementById('execution-details');
            const noTradeDetails = document.getElementById('no-trade-details');

            if (sig) {
                const isTrade = sig.signal === 'BUY_CE' || sig.signal === 'BUY_PE';
                const isCE = sig.signal === 'BUY_CE';
                
                document.getElementById('signal-type').textContent = sig.signal !== 'NO_TRADE' ? `🟢 ACTIVE SIGNAL — ${sig.symbol || 'NIFTY'} ${isCE ? 'CE' : 'PE'}` : 'NO TRADE DETECTED';
                document.getElementById('signal-icon').textContent = isTrade ? (isCE ? '🟢' : '🔴') : '⏳';
                
                container.className = 'panel signal-panel ' + (isCE ? 'buy-ce' : (sig.signal==='BUY_PE' ? 'buy-pe' : ''));

                if (isTrade) {
                    execDetails.style.display = 'block';
                    noTradeDetails.style.display = 'none';
                    
                    const pl = sig.premium_levels || {};
                    document.getElementById('p-entry').textContent = pl.premium_entry ? '₹' + pl.premium_entry : '—';
                    document.getElementById('p-sl').textContent = pl.premium_sl ? '₹' + pl.premium_sl : '—';
                    document.getElementById('p-t1').textContent = pl.premium_t1 ? '₹' + pl.premium_t1 : '—';
                    document.getElementById('p-t2').textContent = pl.premium_t2 ? '₹' + pl.premium_t2 : '—';
                    
                    document.getElementById('s-trigger').textContent = '₹' + sig.entry;
                    document.getElementById('s-conf').textContent = sig.confidence;
                    document.getElementById('s-grade').textContent = sig.grade;
                    document.getElementById('s-decay').textContent = pl.decay_risk || 'Moderate';
                    
                    // Trade Quality Breakdown from Grade/Confidence
                    document.getElementById('t-struct').textContent = sig.grade;
                    document.getElementById('t-exec').textContent = (sig.grade === 'A+' || sig.grade === 'A') ? 'A' : 'B';
                    document.getElementById('t-integ').textContent = sig.confluence ? (parseInt(sig.confluence.ratio)/100).toFixed(2) : '0.85';

                } else {
                    execDetails.style.display = 'none';
                    noTradeDetails.style.display = 'block';
                    const list = document.getElementById('reasons-list');
                    list.innerHTML = '';
                    (sig.reasons || ['Waiting for conditions']).forEach(r => {
                        const li = document.createElement('li');
                        li.textContent = r;
                        list.appendChild(li);
                    });
                    document.getElementById('t-struct').textContent = '---';
                    document.getElementById('t-exec').textContent = '---';
                    document.getElementById('t-integ').textContent = '---';
                }

                // Confluence Meter
                if (sig.confluence) {
                    const bull = sig.confluence.bullish;
                    const bear = sig.confluence.bearish;
                    const total = bull + bear;
                    document.getElementById('conf-text').textContent = `${bull} bullish / ${bear} bearish`;
                    const pct = total > 0 ? (bull / total) * 100 : 50;
                    document.getElementById('conf-fill').style.width = pct + '%';
                }
            }

            // Agents Grid
            if (agents) {
                const grid = document.getElementById('agents-grid');
                grid.innerHTML = '';
                for (const [name, agent] of Object.entries(agents)) {
                    const out = agent.last_output;
                    const dirClass = out ? (out.direction === 'BULLISH' ? 'bullish' : out.direction === 'BEARISH' ? 'bearish' : 'neutral') : 'neutral';
                    
                    let weightText = out ? `Weight: ${(out.weight || 1.0).toFixed(2)}x` : 'Waiting...';
                    if (out && out.weight < 0.5) weightText = "Suppressed";

                    grid.innerHTML += `
                        <div class="agent-card">
                            <div class="agent-header">
                                <span>${name.toUpperCase()}</span>
                                <span style="color:${agent.active ? '#00ff88' : '#ff4444'}">●</span>
                            </div>
                            ${out ? `
                                <div class="agent-metric"><span style="color:#888">Direction</span> <span class="${dirClass}">${out.direction}</span></div>
                                <div class="agent-metric"><span style="color:#888">Confidence</span> <span>${out.confidence}%</span></div>
                                <div class="agent-metric"><span style="color:#888">Strength</span> <span>${out.strength}</span></div>
                                <div class="agent-weight">${weightText}</div>
                            ` : '<div style="color:#888; font-style:italic;">No data yet</div>'}
                        </div>
                    `;
                }
            }

            // Log appending
            if (sig && sig.signal !== 'NO_TRADE') {
                const log = document.getElementById('log');
                const entry = document.createElement('div');
                entry.className = 'log-entry';
                entry.textContent = `[${sig.time}] ${sig.signal} | Conf: ${sig.confidence} | ${(sig.reasons || []).join(', ')}`;
                log.prepend(entry);
                if (log.children.length > 50) log.removeChild(log.lastChild);
            }
        }
        // Burn-In Stats polling
        function fetchBurnin() {
            fetch('/api/burnin').then(r => r.json()).then(d => {
                if (!d || d.status === 'no_data') return;
                const s = d.score || {};
                const st = d.stats || {};

                // Score
                document.getElementById('bi-score').textContent = s.final_score ?? '--';
                const gate = s.gate || 'LOADING';
                const gateColors = {
                    'OPERATIONALLY_MATURE': '#00ff88',
                    'SMALL_CAPITAL_ELIGIBLE': '#88ff44',
                    'CONTROLLED_BURNIN': '#ffaa00',
                    'EXPERIMENTAL': '#ff8800',
                    'UNSAFE': '#ff4444',
                };
                const gateEl = document.getElementById('bi-gate');
                gateEl.textContent = gate.replace(/_/g, ' ');
                gateEl.style.color = gateColors[gate] || '#ffaa00';

                // Evidence
                const ev = s.evidence || {};
                document.getElementById('bi-trades').textContent = (ev.trades || 0) + ' trades';
                document.getElementById('bi-days').textContent = (ev.trading_days || 0) + ' days';

                // Categories
                const cats = s.categories || {};
                const catLabels = {
                    profitability: { label: 'Profitability', color: '#00ff88' },
                    stability:     { label: 'Stability',     color: '#00d4ff' },
                    discipline:    { label: 'Discipline',    color: '#aa88ff' },
                    execution:     { label: 'Execution',     color: '#ffaa00' },
                };
                let catHtml = '';
                for (const [key, cfg] of Object.entries(catLabels)) {
                    const cat = cats[key] || {};
                    const pct = cat.score || 0;
                    catHtml += `
                        <div style="margin-bottom:8px;">
                            <div style="display:flex; justify-content:space-between; font-size:11px; margin-bottom:3px;">
                                <span style="color:#ccc;">${cfg.label} (×${cat.weight || 0})</span>
                                <span style="color:${cfg.color};">${pct.toFixed(1)}</span>
                            </div>
                            <div style="height:6px; background:#222; border-radius:3px; overflow:hidden;">
                                <div style="height:100%; width:${pct}%; background:${cfg.color}; border-radius:3px; transition:width 0.5s;"></div>
                            </div>
                        </div>`;
                }
                document.getElementById('bi-categories').innerHTML = catHtml;

                // Execution quality
                const exec = st.execution || {};
                document.getElementById('bi-exec').innerHTML = [
                    `Fill Rate: <span style="color:#00ff88">${(exec.fill_success_rate_pct||100).toFixed(1)}%</span>`,
                    `Avg Slippage: <span style="color:#ffaa00">${(exec.avg_slippage_pts||0).toFixed(3)}pts</span>`,
                    `Avg Spread: <span style="color:#ffaa00">${(exec.avg_spread_pts||0).toFixed(3)}pts</span>`,
                    `Rejection Rate: <span style="color:#ff8800">${(exec.rejection_rate_pct||0).toFixed(2)}%</span>`,
                    `Avg Latency: <span style="color:#aaa">${Math.round(exec.avg_latency_ms||0)}ms</span>`,
                ].join(' &nbsp;|&nbsp; ');

                // Regime breakdown
                const regime = st.regime || {};
                let regHtml = '';
                for (const [name, r] of Object.entries(regime)) {
                    const pnlColor = r.pnl >= 0 ? '#00ff88' : '#ff4444';
                    regHtml += `<div style="background:#161625; border:1px solid #2a2a35; border-radius:6px; padding:10px 14px; font-size:11px; min-width:130px;">
                        <div style="color:#00d4ff; font-weight:bold; margin-bottom:5px;">${name}</div>
                        <div>Win Rate: <span style="color:#fff">${r.win_rate}%</span></div>
                        <div>P&amp;L: <span style="color:${pnlColor}">₹${r.pnl}</span></div>
                        <div>Trades: <span style="color:#888">${r.trades}</span></div>
                    </div>`;
                }
                document.getElementById('bi-regime').innerHTML = regHtml || '<span style="color:#555">No trades yet</span>';

                // Recommendations
                const recs = s.recommendations || [];
                document.getElementById('bi-recs').innerHTML =
                    '<strong style="color:#888">📌 Recommendations:</strong> <br>' +
                    recs.map(r => `▸ ${r}`).join('<br>');
            }).catch(() => {});
        }

        let cachedTrades = [];

        function renderTrades() {
            const fRegime = document.getElementById('filter-regime').value;
            const fFailure = document.getElementById('filter-failure').value;
            const fQuality = document.getElementById('filter-quality').value;
            const fAdapted = document.getElementById('filter-adapted').checked;
            
            let html = '';
            cachedTrades.forEach(t => {
                // Apply Filters
                if (fRegime !== 'ALL' && t.regime !== fRegime) return;
                if (fFailure !== 'ALL' && t.failure_type !== fFailure) return;
                if (fQuality !== 'ALL' && t.exec_quality !== fQuality) return;
                if (fAdapted && !t.adaptation_reason) return;

                const resColor = t.result === 'WIN' ? '#00ff88' : t.result === 'LOSS' ? '#ff4444' : '#888';
                const execQualityColor = t.exec_quality === 'GOOD' ? '#00ff88' : t.exec_quality === 'FAIR' ? '#ffaa00' : '#ff4444';
                
                let adaptationText = '';
                if (t.adaptation_reason) {
                    const outcomeColor = (t.adaptation_outcome === 'LOSS_MITIGATED' || t.adaptation_outcome === 'WIN_ENHANCED' || t.adaptation_outcome === 'LOSS_AVOIDED' || t.adaptation_outcome === 'REVERSAL_CAPTURED' || t.adaptation_outcome === 'RUNNER_CAPTURED') ? '#00ff88' : (t.adaptation_outcome === 'PROFIT_SUPPRESSED' ? '#ff4444' : '#888');
                    let deltaBadge = t.adaptation_pnl_delta > 0 ? `<span style="color:#00ff88;">+₹${t.adaptation_pnl_delta}</span>` : `<span style="color:#ff4444;">₹${t.adaptation_pnl_delta}</span>`;
                    
                    adaptationText = `
                    <div style="color:${outcomeColor}; font-weight:bold; font-size:11px;">${t.adaptation_outcome} (${deltaBadge})</div>
                    <div style="color:#00d4ff; font-size:10px; margin-top:3px;">${t.adaptation_reason}</div>
                    <div style="color:#888; font-size:10px;">SL: ${t.original_sl} → ${t.adapted_sl} | Qty: ${t.original_qty} → ${t.adapted_qty}</div>`;
                }
                
                let failureText = '';
                if (t.failure_type) {
                    failureText = `<span style="background:#ff444433; color:#ff4444; padding:2px 6px; border-radius:4px; font-size:10px;">${t.failure_type.replace(/_/g, ' ')}</span>`;
                }
                
                let baselineHtml = '';
                if (t.baseline_outcome && t.baseline_outcome.pnl !== undefined) {
                    baselineHtml = `<div style="font-size:10px; color:#777;">Base: ₹${t.baseline_outcome.pnl.toFixed(1)} (${t.baseline_outcome.exit_reason})</div>`;
                }

                html += `<tr style="border-bottom:1px solid #222;">
                    <td style="padding:8px; color:#aaa;">${t.time.split('.')[0]}</td>
                    <td style="padding:8px; font-weight:bold; color:${t.direction === 'BULLISH' ? '#00ff88' : t.direction === 'BEARISH' ? '#ff4444' : '#fff'}">${t.signal}</td>
                    <td style="padding:8px; color:#888;">${t.regime}</td>
                    <td style="padding:8px;">
                        <div>Fill: ${(t.fill_ratio * 100).toFixed(0)}% | Latency: ${t.latency_ms}ms</div>
                        <div style="font-size:10px; color:${execQualityColor}">Friction: +${t.total_friction_pts}pts (${t.exec_quality})</div>
                    </td>
                    <td style="padding:8px;">
                        <strong style="color:${resColor}">₹${t.net_pnl.toFixed(1)}</strong>
                        <div style="font-size:10px; color:#888;">Actual: ${t.exit_reason || 'OPEN'}</div>
                        ${baselineHtml}
                    </td>
                    <td style="padding:8px;">${failureText}</td>
                    <td style="padding:8px;">${adaptationText}</td>
                </tr>`;
            });
            document.getElementById('trade-ledger-body').innerHTML = html || '<tr><td colspan="7" style="padding:8px; color:#555; text-align:center;">No trades match filters</td></tr>';
        }

        document.getElementById('filter-regime').addEventListener('change', renderTrades);
        document.getElementById('filter-failure').addEventListener('change', renderTrades);
        document.getElementById('filter-quality').addEventListener('change', renderTrades);
        document.getElementById('filter-adapted').addEventListener('change', renderTrades);

        function fetchTrades() {
            fetch('/api/trades').then(r => r.json()).then(d => {
                if (!d || d.status !== 'ok') return;
                cachedTrades = d.trades;
                
                let alphaStr = d.total_adaptation_alpha > 0 ? `+₹${d.total_adaptation_alpha.toFixed(1)}` : `₹${d.total_adaptation_alpha.toFixed(1)}`;
                let alphaColor = d.total_adaptation_alpha > 0 ? '#00ff88' : '#ff4444';
                document.getElementById('adaptation-alpha').innerHTML = `Adaptation Alpha: <span style="color:${alphaColor}; font-weight:bold;">${alphaStr}</span>`;
                
                renderTrades();
            }).catch(() => {});
        }

        fetchBurnin();
        fetchTrades();
        setInterval(fetchBurnin, 30000);  // refresh every 30s
        setInterval(fetchTrades, 30000);
    </script>
</body>
</html>
"""


class Dashboard:
    """Web dashboard for monitoring the AI system"""

    def __init__(self, host: str = "0.0.0.0", port: int = 5000):
        self.app = Flask(__name__)
        self.socketio = SocketIO(self.app, cors_allowed_origins="*", async_mode='threading')
        self.host = host
        self.port = port
        self._status_data = {}
        self._errors = 0
        self._last_cycle = 0
        self._trading_enabled = True

        # ── Phase B: Burn-In Tracker + Readiness Scorer (injected from main) ──
        self._burnin_tracker = None
        self._readiness_scorer = None
        
        # ── Priority 1: Trade Replay Viewer ──
        self._simulation_engine = None

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

        @self.app.route("/api/trades")
        def api_trades():
            """Trade Ledger & Replay endpoint for dashboard panel."""
            try:
                if not self._simulation_engine:
                    return _safe_jsonify({"status": "no_data", "message": "SimulationEngine not initialized"})
                
                # Get last 50 completed trades, reversed so newest is first
                trades = [t.to_dict() for t in self._simulation_engine.all_trades[-100:]]
                trades.reverse()
                
                # Phase C: Calculate Aggregate Adaptation Alpha
                total_alpha = sum(t.adaptation_pnl_delta for t in self._simulation_engine.all_trades if t.adaptation_reason)
                
                return _safe_jsonify({"status": "ok", "trades": trades, "total_adaptation_alpha": total_alpha})
            except Exception as e:
                logger.error(f"TRADES ENDPOINT ERROR: {e}")
                return _safe_jsonify({"status": "error", "message": str(e)}), 500

        @self.app.route("/health")
        def health():
            # Intelligent Healthcheck for Docker
            import time
            now = time.time()
            loop_alive = (now - self._last_cycle) < 60 if self._last_cycle else True
            
            # Minimum viable health metrics
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
            """
            🛑 Emergency Dashboard Kill Switch (Telegram-Independent)
            Creates a HALT file on disk — main.py checks for it every cycle.
            Use: curl -X POST http://localhost:5000/halt
            """
            import os
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
            """
            ▶️ Resume trading by deleting the HALT file.
            Use: curl -X POST http://localhost:5000/resume
            """
            import os
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
        # Use specific HTTP error handlers instead of a catch-all Exception handler.
        # A catch-all @errorhandler(Exception) on Flask-SocketIO apps intercepts
        # SocketIO's internal exceptions and returns HTML error pages instead of JSON.
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
                # Safe-encode to handle Enums, Decimals, datetimes deeply nested in details
                safe_data = json.loads(json.dumps(self._status_data, cls=_SafeEncoder))
                emit('system_status', safe_data)
            except Exception as e:
                logger.error(f"Error emitting system_status on connect: {e}")

    def emit_signal(self, signal_data: dict):
        """Broadcast a live signal to all connected clients"""
        try:
            # Safe-encode before emitting to avoid SocketIO serialisation crashes
            safe_data = json.loads(json.dumps(signal_data, cls=_SafeEncoder))
            self.socketio.emit('signal_update', safe_data)
        except Exception as e:
            logger.error(f"Socket emit error: {e}")

    def set_burnin_components(self, burnin_tracker, readiness_scorer):
        """Inject BurninTracker and ReadinessScorer (called from main after init)."""
        self._burnin_tracker = burnin_tracker
        self._readiness_scorer = readiness_scorer

    def set_simulation_engine(self, sim_engine):
        """Inject SimulationEngine for Trade Ledger / Replay functionality."""
        self._simulation_engine = sim_engine

    def update_status(self, data: dict):
        """Update dashboard data (called from main loop)"""
        self._status_data = data
        self._last_cycle = time.time()
        self._trading_enabled = data.get("risk", {}).get("trading_enabled", True)
        # Update error count from system if available
        if "errors" in data:
            self._errors = data["errors"]

    def start(self):
        """Start dashboard using gevent worker"""
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
