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
