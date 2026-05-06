"""
============================================
📊 LIVE MONITORING DASHBOARD
Web-based real-time dashboard showing
agent statuses and signals
============================================
"""

import threading
import time
from flask import Flask, render_template_string, jsonify
from flask_socketio import SocketIO, emit
from utils.logger import get_logger

logger = get_logger("dashboard")


# Dashboard HTML template
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nifty AI Agent System</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', monospace;
            background: #0a0a0f;
            color: #e0e0e0;
            padding: 20px;
        }
        .header {
            text-align: center;
            padding: 20px;
            background: linear-gradient(135deg, #1a1a2e, #16213e);
            border-radius: 12px;
            margin-bottom: 20px;
            border: 1px solid #333;
        }
        .header h1 { color: #00d4ff; font-size: 24px; }
        .header .subtitle { color: #888; font-size: 14px; margin-top: 5px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 15px; margin-bottom: 20px; }
        .card {
            background: #1a1a2e;
            border-radius: 10px;
            padding: 20px;
            border: 1px solid #333;
        }
        .card h3 { color: #00d4ff; margin-bottom: 10px; font-size: 16px; }
        .metric { display: flex; justify-content: space-between; padding: 5px 0; border-bottom: 1px solid #222; }
        .metric-label { color: #888; }
        .metric-value { font-weight: bold; }
        .bullish { color: #00ff88; }
        .bearish { color: #ff4444; }
        .neutral { color: #ffaa00; }
        .signal-panel {
            background: #1a1a2e;
            border-radius: 10px;
            padding: 25px;
            border: 2px solid #333;
            text-align: center;
            transition: all 0.5s ease;
        }
        .signal-panel.buy-ce { border-color: #00ff88; box-shadow: 0 0 20px rgba(0, 255, 136, 0.2); }
        .signal-panel.buy-pe { border-color: #ff4444; box-shadow: 0 0 20px rgba(255, 68, 68, 0.2); }
        .signal-type { font-size: 28px; font-weight: bold; margin: 10px 0; }
        .confidence-bar {
            width: 100%;
            height: 8px;
            background: #333;
            border-radius: 4px;
            margin-top: 10px;
        }
        .confidence-fill {
            height: 100%;
            border-radius: 4px;
            transition: width 0.5s;
        }
        .status-dot {
            display: inline-block;
            width: 8px; height: 8px;
            border-radius: 50%;
            margin-right: 5px;
        }
        .status-active { background: #00ff88; }
        .status-inactive { background: #ff4444; }
        #log {
            background: #111;
            padding: 15px;
            border-radius: 8px;
            max-height: 300px;
            overflow-y: auto;
            font-family: monospace;
            font-size: 12px;
            line-height: 1.6;
        }
        .log-entry { border-bottom: 1px solid #1a1a1a; padding: 3px 0; }
        
        /* Flash Animations */
        @keyframes flash-green { 0% { background: #00ff88; } 100% { background: #1a1a2e; } }
        @keyframes flash-red { 0% { background: #ff4444; } 100% { background: #1a1a2e; } }
        .flash-buy-ce { animation: flash-green 1s ease-out; }
        .flash-buy-pe { animation: flash-red 1s ease-out; }
    </style>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.4/socket.io.min.js"></script>
</head>
<body>
    <div class="header">
        <h1>🧠 Nifty AI Agent System</h1>
        <div class="subtitle">Real-time Multi-Agent Trading Intelligence</div>
        <div class="subtitle" id="update-time">Connecting to WebSocket...</div>
    </div>

    <div id="signal-container" class="signal-panel">
        <div style="font-size: 40px">⏳</div>
        <div class="signal-type">WAITING FOR SIGNAL</div>
        <div id="market-state">System initializing...</div>
    </div>

    <br>

    <div class="grid" id="agents-grid">
        <!-- Agent cards will be injected here -->
    </div>

    <div class="card">
        <h3>📋 System Log</h3>
        <div id="log"></div>
    </div>

    <script>
        const socket = io();

        socket.on('connect', () => {
            console.log('Connected to WebSocket server');
            document.getElementById('update-time').textContent = 'Live Connection Active';
        });

        socket.on('disconnect', () => {
            document.getElementById('update-time').textContent = 'Disconnected - Attempting Reconnect...';
        });

        socket.on('system_status', (data) => {
            updateDashboard(data);
        });

        socket.on('signal_update', (data) => {
            console.log('LIVE SIGNAL:', data);
            triggerFlash(data);
            updateDashboard(data);
        });

        function triggerFlash(sig) {
            const container = document.getElementById('signal-container');
            if (sig.signal === 'BUY_CE') {
                container.classList.add('flash-buy-ce');
                setTimeout(() => container.classList.remove('flash-buy-ce'), 1000);
            } else if (sig.signal === 'BUY_PE') {
                container.classList.add('flash-buy-pe');
                setTimeout(() => container.classList.remove('flash-buy-pe'), 1000);
            }
        }

        function updateDashboard(data) {
            if (!data) return;
            
            // Handle both full status and single signal updates
            const sig = data.last_signal || (data.signal ? data : null);
            const agents = data.agents || null;

            document.getElementById('update-time').textContent =
                'Last update: ' + new Date().toLocaleTimeString();

            // Update signal panel
            const container = document.getElementById('signal-container');
            if (sig) {
                let cls = '';
                let icon = '⚪';
                if (sig.signal === 'BUY_CE') { cls = 'buy-ce'; icon = '🟢'; }
                else if (sig.signal === 'BUY_PE') { cls = 'buy-pe'; icon = '🔴'; }

                container.className = 'signal-panel ' + cls;
                container.innerHTML = `
                    <div style="font-size:40px">${icon}</div>
                    <div class="signal-type">${sig.signal}</div>
                    <div id="market-state"><strong>${sig.regime || 'DETERMINING STATE...'}</strong></div>
                    <div>Confidence: <strong>${sig.confidence}</strong></div>
                    ${sig.signal !== 'NO_TRADE' ? `
                    <div>Entry: ₹${sig.entry} | SL: ₹${sig.sl} | T1: ₹${sig.target1}</div>
                    ` : `<div>${(sig.reasons || ['Waiting for conditions']).join(' | ')}</div>`}
                    <div class="confidence-bar">
                        <div class="confidence-fill" style="width:${parseFloat(sig.confidence)}%;background:${cls === 'buy-ce' ? '#00ff88' : cls === 'buy-pe' ? '#ff4444' : '#ffaa00'}"></div>
                    </div>
                `;
            }

            // Update agent cards if provided
            if (agents) {
                const grid = document.getElementById('agents-grid');
                grid.innerHTML = '';
                for (const [name, agent] of Object.entries(agents)) {
                    const out = agent.last_output;
                    const dirClass = out ? (out.direction === 'BULLISH' ? 'bullish' : out.direction === 'BEARISH' ? 'bearish' : 'neutral') : 'neutral';

                    grid.innerHTML += `
                        <div class="card">
                            <h3>
                                <span class="status-dot ${agent.active ? 'status-active' : 'status-inactive'}"></span>
                                ${name.toUpperCase()} Agent
                            </h3>
                            ${out ? `
                                <div class="metric">
                                    <span class="metric-label">Direction</span>
                                    <span class="metric-value ${dirClass}">${out.direction}</span>
                                </div>
                                <div class="metric">
                                    <span class="metric-label">Confidence</span>
                                    <span class="metric-value">${out.confidence}%</span>
                                </div>
                                <div class="metric">
                                    <span class="metric-label">Strength</span>
                                    <span class="metric-value">${out.strength}</span>
                                </div>
                            ` : '<div>No data yet</div>'}
                        </div>
                    `;
                }
            }

            // Add log entry if it's a new signal
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
                # v4.6.1 Safe API Layer
                if not self._status_data:
                    return jsonify({
                        "status": "initializing",
                        "last_signal": None
                    })

                return jsonify({
                    "status": "active",
                    "data": self._status_data,
                    "last_signal": self._status_data.get("last_signal")
                })
            except Exception as e:
                logger.error(f"🔥 STATUS ERROR: {e}")
                return jsonify({"status": "error", "message": str(e)}), 500

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
        @self.app.errorhandler(Exception)
        def handle_exception(e):
            # Global Production Error Handler
            logger.error(f"🔥 GLOBAL API ERROR: {e}")
            self._errors += 1
            return jsonify({
                "error": "Internal Server Error",
                "message": str(e) if self.app.debug else "Check server logs"
            }), 500

    def _setup_socket_events(self):
        @self.socketio.on('connect')
        def handle_connect():
            logger.debug("🌐 Client connected to WebSocket")
            emit('system_status', self._status_data)

    def emit_signal(self, signal_data: dict):
        """Broadcast a live signal to all connected clients"""
        try:
            self.socketio.emit('signal_update', signal_data)
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
                log_output=False
            )

        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()
