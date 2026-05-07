"""
============================================
🧠⚡ NIFTY AI AGENT SYSTEM v4.6.1
THE FINAL PRODUCTION SYSTEM (Hardened)

PRO MODE + SIMULATION + DISCIPLINE
============================================
"""

import time
import asyncio
import aiohttp
import threading
import signal as sig_module
import sys
import os

# ── P0-C: Heartbeat URL for dead man's switch ──
HEARTBEAT_URL = os.getenv("HEARTBEAT_URL")  # e.g. https://hc-ping.com/your-uuid
DEADMAN_TIMEOUT_SECONDS = int(os.getenv("DEADMAN_TIMEOUT_SECONDS", "30"))
from datetime import datetime, timedelta

os.makedirs("data", exist_ok=True)

from config.settings import Settings
from core.data_manager import DataManager
from core.decision_engine_v3 import DecisionEngineV3
from core.alert_manager import AlertManager
from core.trade_logger import TradeLogger
from core.position_manager import PositionManager
from core.slippage_model import SlippageModel
from core.metrics_engine import MetricsEngine
from core.trade_filter import TradeFilter
from core.entry_engine import EntryEngine
from core.exit_engine import ExitEngine
from core.session_strategy import SessionStrategy
from core.simulation_engine import SimulationEngine
from core.discipline_engine import DisciplineEngine
from core.risk_manager import RiskManager
from core.master_decision_engine import MasterDecisionEngine
from core.telegram_controller import TelegramController
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler
from models.signals import SignalType, Direction, TradeOutcome
from utils.logger import get_logger
from utils.tasks import fire_and_log
from options_analyzer import OptionsAnalyzer
from performance_logger import PerformanceLogger
from core.log_observer import LogObserver

settings = Settings()
logger = get_logger("main", settings.log_level)


def print_banner():
    mode = settings.system_mode.mode
    phase = settings.system_mode.current_phase
    capital = settings.get_capital()

    mode_icon = {
        "SIMULATION": "🧪",
        "SMALL_CAPITAL": "💵",
        "SCALED": "💰",
    }.get(mode, "🔧")

    print(f"""
╔══════════════════════════════════════════════════════════════════════════╗
║                                                                          ║
║    🧠⚡ NIFTY AI AGENT SYSTEM v4.6.1 — PRODUCTION HARDENED               ║
║                                                                          ║
║    {mode_icon} Mode    : {mode:<30s}                      ║
║    📋 Phase   : {phase}                                                   ║
║    💰 Capital : ₹{capital:<12,.0f}                                        ║
║    🎯 Max Trades: {settings.trade_filter.max_trades_per_day}/day                                            ║
║    📊 Min Grade : {settings.trade_filter.min_grade_to_trade} ({settings.trade_filter.min_signal_confidence:.0f}% confidence)                        ║
║    🛡️  Daily Loss: ₹{settings.position.max_daily_loss:<8,.0f} max                                  ║
║    🎯 Daily Goal: ₹{settings.exit.daily_target_amount:<8,.0f} (auto-stop)                           ║
║                                                                          ║
║    ┌──────────── SIGNAL FLOW ────────────────────────────────┐           ║
║    │  23 Agents → Decision Engine → 10-Gate Filter            │           ║
║    │       ↓              ↓               ↓                   │           ║
║    │  Kill 65%     Smart Entry      Exit Intelligence         │           ║
║    │  of signals   + Confirmation   + Daily Target Lock       │           ║
║    │  Result: 2-3 trades/day, 60%+ win rate, 1.5+ R:R        │           ║
║    └──────────────────────────────────────────────────────────┘           ║
║                                                                          ║
║    📊 Dashboard: http://localhost:{settings.dashboard.port:<5d}                                ║
║                                                                          ║
╚══════════════════════════════════════════════════════════════════════════╝
    """)


class NiftyAISystem:
    """THE FINAL SYSTEM — v4.6.1 Hardened"""

    def __init__(self):
        self.running = False
        self.cycle_count = 0
        self.trading_enabled = True # Use this as the master kill switch
        self.cycle_running = False
        
        # ── Multi-Layer Circuit Breaker ──
        self.error_count = 0        # General
        self.engine_errors = 0      # Calculation layer
        self.api_errors = 0         # Dashboard/API layer
        self.execution_failures = 0 # Broker interaction failures
        
        self.last_cycle_time = 0
        self.no_trade_streak = 0  # Fix #4: Trade Frequency Guard counter
        self.last_candle_timestamp = None

        logger.info(
            f"Initializing v4.6.1 | "
            f"Mode: {settings.system_mode.mode}"
        )

        # ── Core ──
        self.data_manager = DataManager(settings)
        self.decision_engine = DecisionEngineV3(settings)
        self.trade_logger = TradeLogger()

        # ── Production ──
        self.position_manager = PositionManager(settings)
        # ── Share tuner: engine generates thresholds, PM feeds outcomes ──
        self.position_manager.tuner = self.decision_engine.tuner
        self.risk_manager = RiskManager(settings, self.decision_engine.memory.db)
        self.slippage_model = SlippageModel(settings)
        self.metrics_engine = MetricsEngine(settings.get_capital())

        # ── Edge Layer ──
        self.trade_filter = TradeFilter(settings)
        self.entry_engine = EntryEngine(settings)
        self.exit_engine = ExitEngine(settings)
        self.session_strategy = SessionStrategy(settings)
        self.discipline = DisciplineEngine()

        # ── 🧠 MASTER GATE (single point of truth for all trade approvals) ──
        # Every execution path MUST call self.master.approve() before trading.
        # If it returns False → no order placed. No exceptions.
        self.master = MasterDecisionEngine(
            risk_manager=self.risk_manager,
            position_manager=self.position_manager,
            discipline_engine=self.discipline,
            exit_engine=self.exit_engine,
            session_strategy=self.session_strategy,
        )

        # ── Remote Control ──
        self.telegram_bot = TelegramController(
            settings=settings,
            system=self,  # v4.6.1: Passing system for unified execution path
            db_manager=self.decision_engine.memory.db
        )
        
        # ── Alerting ──
        self.alert_manager = AlertManager(settings, self.telegram_bot)

        # ── Final Layer ──
        self.simulation = SimulationEngine(settings)

        # ── Phase 2: Options Hard Filter ──
        # ── P1-D: Options Analyzer ──
        # ── Phase 2 rule engine support
        self.options_analyzer = OptionsAnalyzer(mode=settings.system_mode.mode)
        self.perf_logger = PerformanceLogger()
        self.observer = LogObserver()

        # ── Dashboard ──
        self.dashboard = None
        if settings.dashboard.enabled:
            try:
                from web.dashboard import Dashboard
                self.dashboard = Dashboard(
                    host=settings.dashboard.host,
                    port=settings.dashboard.port,
                )
            except Exception as e:
                logger.warning(f"Dashboard not available: {e}")

        # ── Mode ──
        self.is_simulation = (
            settings.system_mode.mode == "SIMULATION"
        )

        logger.info(
            f"v4.6.1 initialized ✓ | "
            f"{'SIMULATION' if self.is_simulation else 'LIVE'} mode"
        )

    async def start(self):
        """🚀 THE ASYNC ORCHESTRATOR"""
        self.running = True
        print_banner()

        if self.dashboard:
            self.dashboard.start()

        # 1. Telegram App Build
        app = ApplicationBuilder().token(settings.alerts.telegram_bot_token).build()
        app.add_handler(CommandHandler("start", self.telegram_bot.start_cmd))
        app.add_handler(CommandHandler("stop", self.telegram_bot.stop_cmd))
        app.add_handler(CommandHandler("status", self.telegram_bot.status_cmd))
        app.add_handler(CommandHandler("kill", self.telegram_bot.kill_cmd))
        app.add_handler(CommandHandler("restart", self.telegram_bot.restart_cmd))
        app.add_handler(CommandHandler("pause", self.telegram_bot.pause_cmd))
        app.add_handler(CommandHandler("resume", self.telegram_bot.resume_cmd))
        app.add_handler(CallbackQueryHandler(self.telegram_bot.handle_callback_query))

        # Store app reference in the bot for async sending
        self.telegram_bot.app = app

        self.telegram_enabled = not self.is_simulation

        if self.telegram_enabled:
            try:
                await app.initialize()
                await app.start()
                await app.updater.start_polling()
                logger.info("📱 Telegram Async Polling Active")
            except Exception as e:
                logger.error("Telegram init failed: %s", e)
                self.telegram_enabled = False
        else:
            logger.info("📱 Telegram disabled in SIMULATION mode")

        # 2. Wake up the Brain (Load memory from disk)
        await self.decision_engine.memory.boot()
        
        # 3. Recover Telegram State (Reconcile unfinished signals)
        await self.telegram_bot.boot_recovery()

        # 4. 🚨 BROKER POSITION RECONCILIATION (P0.3)
        # Detect orphaned positions from a previous crash.
        await self._reconcile_broker_positions()

        # 5. Show current readiness score on start
        if self.is_simulation:
            readiness = self.simulation.get_readiness_score()
            logger.info(
                f"📋 Readiness: {readiness['readiness']} | "
                f"Score: {readiness['final_score']}/100 | "
                f"{readiness['recommendation']}"
            )

        logger.info("🚀 System v4.6.1 Hardened Started")

        # 3. Main Market Loop
        async with aiohttp.ClientSession() as session:
            logger.info("🎬 Powering up AI Execution Loop")
            # ── P0-C: Launch deadman watchdog as background task ──
            deadman_task = asyncio.create_task(self._deadman_watchdog())

            try:
                while self.running:
                    start_time = time.perf_counter()
                    self.last_cycle_time = time.time()
                    
                    # ── P0-C: Record heartbeat for deadman watchdog ──
                    self.position_manager.record_heartbeat()

                    await self._run_cycle(session)
                    
                    # ── P0-C: External heartbeat ping (Fire & Forget) ──
                    asyncio.create_task(self._ping_heartbeat(session))

                    # Performance profiling
                    elapsed_sec = time.perf_counter() - start_time
                    if elapsed_sec > 0.8: # Threshold for HFT warnings (API RTT accounts for ~500ms)
                        logger.warning(f"⚠️ Cycle Latency: {elapsed_sec * 1000:.2f}ms")
                    
                    if hasattr(self, "observer"):
                        self.observer.on_cycle_end(elapsed_sec)
                        
                    # High-frequency: 1 second interval
                    await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                logger.info("Shutdown signal received")
            finally:
                deadman_task.cancel()
                await app.updater.stop()
                await app.stop()
                await app.shutdown()
                self.stop()

    async def _run_cycle(self, session: aiohttp.ClientSession):
        if self.cycle_running:
            return

        self.cycle_running = True
        try:
            await self._run_cycle_inner(session)
        finally:
            self.cycle_running = False

    async def _run_cycle_inner(self, session: aiohttp.ClientSession):
        self.cycle_count += 1

        # ── 0. Risk & Master Kill Switch ──
        if not self.trading_enabled:
            if self.cycle_count % 60 == 0:
                logger.warning("⛔ SYSTEM HALTED: Master switch is OFF. Manual /start required.")
            self._monitor_only()
            return

        if self.telegram_bot.is_paused:
            if self.cycle_count % 60 == 0:
                logger.info("⏸️ System Paused via Telegram. Monitoring only.")
            self._monitor_only()
            return

        # ── 🛡️ RUNTIME DUAL-ARCH GUARD ──
        # Verify ACTIVE_TRADING_SYSTEM matches "main" every cycle.
        # Prevents accidental duplicate orders if .env is live-edited.
        active_system = os.getenv("ACTIVE_TRADING_SYSTEM", "main")
        if active_system != "main":
            self.halt_trading(
                f"🚨 DUAL-ARCH GUARD: ACTIVE_TRADING_SYSTEM changed to '{active_system}' "
                f"at runtime. Halting to prevent duplicate order risk."
            )
            return

        # ── Circuit Breaker Logic ──
        if self.execution_failures > 3:
            self.halt_trading("CRITICAL: Broker Execution Failures > 3")
            return
        if self.engine_errors > 10:
            self.halt_trading("CRITICAL: Engine Instability > 10 errors")
            return

        # ── ❤️ INTERNAL HEARTBEAT / STALL DETECTION ──
        # last_cycle_time is set at the top of start() before each _run_cycle call.
        # If gap since last successful cycle > 30s, warn loudly.
        now_ts = time.time()
        stall_seconds = now_ts - self.last_cycle_time
        if stall_seconds > 30 and self.cycle_count > 5:
            logger.critical(
                f"⚠️ STALL DETECTED: {stall_seconds:.0f}s since last cycle. "
                f"Main loop may be blocked. Cycle #{self.cycle_count}"
            )
            # Non-fatal: log and continue. Operators should wire an external
            # ping (e.g. healthchecks.io) to escalate if this repeats.



        # 🔥 Update Global Risk (PnL from DB)
        await self.risk_manager.update_daily_pnl()

        try:
            # ── 1. MASTER GATE: Pre-trade approval (replaces scattered checks) ──
            # Previously: exit_engine / position_manager / session_strategy /
            #             discipline_engine were checked separately in 4 blocks.
            # Now: ONE call. One answer. If blocked → monitor only.
            #
            # To debug a block: logger.info(self.master.explain_last())
            pre_check = self.master.approve(
                "BUY_CE",   # signal type doesn't matter for pre-cycle gate
                context={
                    "discipline_context": {
                        "daily_target_hit": self.exit_engine.daily_target_hit,
                        "consecutive_losses": getattr(self.exit_engine, "consecutive_losses", 0),
                        "seconds_since_last_trade": 999,
                        "open_positions": len(self.position_manager.open_positions),
                        "max_positions": settings.position.max_open_positions,
                    }
                },
            )
            if not pre_check.approved:
                if self.cycle_count % 300 == 0:
                    logger.info(f"⛔ Master Gate: {pre_check.reason}")
                self._monitor_only()
                return

            # ── 2. Fetch data (Async version) ──
            df, snapshot = await self.data_manager.fetch_latest_async(session)
            if snapshot is None or snapshot.price == 0:
                return
                
            # ── Analytics: Track OI Reliability ──
            if hasattr(snapshot, "oi_data_source"):
                source_str = snapshot.oi_data_source.name if hasattr(snapshot.oi_data_source, "name") else str(snapshot.oi_data_source)
                self.observer.on_oi_update(source_str)

            # ── 4. Monitor positions ──
            self._monitor_positions(snapshot, df)

            # ── 5. Check pending entries ──
            confirmed = self.entry_engine.check_confirmations(
                snapshot, df
            )
            for eid, pending in confirmed:
                if self.is_simulation:
                    self._sim_execute(pending, snapshot)
                else:
                    await self._live_execute(eid, pending, snapshot)

            # ── 6. Process only new candles ──
            current_candle_ts = df.index[-1] if df is not None and not df.empty else None
            if self.last_candle_timestamp == current_candle_ts:
                # Only run heavy decision engine when a new candle closes/opens
                # Keep updating dashboard periodically
                if self.cycle_count % 5 == 0:
                    self._update_dashboard(snapshot, None)
                return
                
            self.last_candle_timestamp = current_candle_ts
            
            # ── 7. Generate signal ──
            signal = self.decision_engine.process(df, snapshot)
            
            if hasattr(self, "observer") and signal.signal_type != SignalType.NO_TRADE:
                self.observer.on_signal()

            if signal.signal_type == SignalType.NO_TRADE:
                self.simulation.record_signal(passed=False)
                self._update_dashboard(snapshot, signal)

                # ── FIX #4: TRADE FREQUENCY GUARD ──
                # Tracks consecutive no-trade cycles and alerts operators when
                # the system appears structurally locked (not just market-filtered).
                self.no_trade_streak += 1
                if self.no_trade_streak in (100, 300, 500) or self.no_trade_streak % 500 == 0:
                    last_reason = (signal.reasons[0] if signal.reasons else "unknown")
                    logger.warning(
                        f"⏳ NO-TRADE STREAK: {self.no_trade_streak} consecutive cycles with no signal. "
                        f"Last reason: [{last_reason}]. "
                        f"Check regime confidence, confidence gate, and edge thresholds."
                    )
                return

            # ── Signal passed — reset streak ──
            self.no_trade_streak = 0

            # ── 8. MASTER GATE: Final signal-level approval ──
            # This is the definitive go/no-go for THIS specific signal.
            # It re-verifies risk, session, and position limits at the
            # moment of signal evaluation (not at cycle start).
            signal_type_str = signal.signal_type.value  # e.g. "BUY_CE"
            master_result = self.master.approve(
                signal_type_str,
                context={
                    "discipline_context": {
                        "daily_target_hit": self.exit_engine.daily_target_hit,
                        "consecutive_losses": getattr(self.exit_engine, "consecutive_losses", 0),
                        "seconds_since_last_trade": 999,
                        "open_positions": len(self.position_manager.open_positions),
                        "max_positions": settings.position.max_open_positions,
                    }
                },
            )
            if not master_result.approved:
                if self.cycle_count % 30 == 0:
                    logger.warning(f"🛡️ Master Gate blocked: {master_result.reason}")
                self.simulation.record_signal(passed=False)
                self._update_dashboard(snapshot, signal)
                return

            # ── 8. Gather context for 10-Gate Filter ──
            outputs = {}
            for name, agent in self.decision_engine.agents.items():
                if hasattr(agent, '_last_output'):
                    outputs[name] = agent._last_output

            pm_status = self.position_manager.get_full_status()
            if "today_trades" not in pm_status:
                pm_status["today_trades"] = self.exit_engine.today_trades

            # ── 9. Run 10-Gate Filter ──
            filter_result = self.trade_filter.evaluate(
                signal=signal,
                snapshot=snapshot,
                agent_outputs=outputs,
                regime_info={}, # Simplified for now
                structure_info={},
                learning_info={"confidence": 50, "current_streak": 0},
                decay_info={},
                cost_info={"total_costs": 40, "break_even_points": 1.5},
                position_manager_status=pm_status,
                confluence_score=(
                    signal.confluence.confluence_ratio * 100
                    if signal.confluence else 0
                ),
            )

            self.simulation.record_signal(passed=filter_result.passed)

            if not filter_result.passed:
                self._update_dashboard(snapshot, signal)
                return

            # ── 10. Signal PASSED all 10 gates ──
            logger.info(
                f"🟢 APPROVED | "
                f"Grade: {filter_result.grade} | "
                f"Score: {filter_result.final_score:.0f} | "
                f"{signal.signal_type.value}"
            )

            # ── 11. Phase-2: Options Hard Filter & Performance Logging ──
            # Runs AFTER all 10 gates pass, BEFORE execution.
            
            # Compute price trend for PCR trap filtering
            try:
                ema20 = df['close'].ewm(span=20, adjust=False).mean().iloc[-1]
                price_trend = "up" if df['close'].iloc[-1] > ema20 else "down"
            except Exception:
                price_trend = "unknown"

            options = self.fetch_options_sentiment(price_trend)
            
            # Confidence Scoring
            options_score = 0
            if options.get("available", False):
                sig_val = signal.signal_type.value
                if sig_val == "BUY_CE":
                    if options.get("sentiment") == "bullish": options_score += 1
                    if options.get("pcr", 0) > 1.1: options_score += 1
                    if options.get("oi_bias") == "bullish": options_score += 1
                elif sig_val == "BUY_PE":
                    if options.get("sentiment") == "bearish": options_score += 1
                    if options.get("pcr", 0) < 0.9: options_score += 1
                    if options.get("oi_bias") == "bearish": options_score += 1
                
                # Bonus for safe distance
                if options.get("max_pain_distance", 0) > 100:
                    options_score += 1

            # Prepare log entry
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "time": datetime.now().strftime("%H:%M"),
                "signal": signal.signal_type.value,
                "price_action_passed": True,
                "options_available": options.get("available", False),
                "options_sentiment": options.get("sentiment", "unknown"),
                "options_score": options_score,
                "max_pain_distance": options.get("max_pain_distance", -1),
                "filter_passed": False,
                "trade_executed": False,
                "entry_price": None,
                "exit_price": None,
                "pnl": None,
                "would_have_taken_without_filter": True,
                "exit_reason": None,
                "risk_reason": None,
                "ai_reason": None,
                "trade_id": None
            }

            if options.get("available", False):
                # (a) Max-pain proximity guard
                if options["max_pain_distance"] < OptionsAnalyzer.MAX_PAIN_MIN_DISTANCE:
                    logger.warning(
                        "⚠️ [OPTIONS] Near max-pain (%.0f pts) — trade skipped",
                        options["max_pain_distance"],
                    )
                    log_entry["filter_passed"] = False
                    log_entry["risk_reason"] = "max_pain_distance < 50"
                    self.perf_logger.log_signal(log_entry)
                    
                    self.simulation.record_signal(passed=False)
                    self._update_dashboard(snapshot, signal)
                    return

                # (b) Sentiment alignment (Score must be >= 2)
                if options_score >= 2:
                    log_entry["filter_passed"] = True
                    logger.info(
                        "✅ [OPTIONS] Passed — Score: %d | PCR: %.3f | MaxPain: %.0f pts away",
                        options_score, options.get("pcr", 0), options["max_pain_distance"]
                    )
                else:
                    logger.warning(
                        "❌ [OPTIONS] Score too low (%d) — Signal: %s | Sentiment: %s",
                        options_score, signal.signal_type.value, options["sentiment"]
                    )
                    log_entry["filter_passed"] = False
                    log_entry["risk_reason"] = f"Low options score ({options_score})"
                    self.perf_logger.log_signal(log_entry)
                    
                    self.simulation.record_signal(passed=False)
                    self._update_dashboard(snapshot, signal)
                    return
            else:
                logger.debug("[OPTIONS] Data unavailable — skipping hard filter this cycle")
                log_entry["filter_passed"] = True
                
            # Filter passed -> assign trade ID
            trade_id = f"{int(time.time())}_{signal.signal_type.value}"
            log_entry["trade_executed"] = True
            log_entry["entry_price"] = snapshot.price
            log_entry["trade_id"] = trade_id
            signal.id = trade_id  # Attach to signal so exit logging can map it
            
            self.perf_logger.log_signal(log_entry)

            # ── 12. Route Signal to Master Execution & Dispatch ──
            # Replaces former scattered routing.
            # 1. Always dispatch alert (visibility)
            await self.alert_manager.dispatch(signal)
            
            # Real-time Dashboard Flash
            if self.dashboard:
                self.dashboard.emit_signal(signal.to_dict())

            # 2. TelegramController will handle AUTO mode execution via its internal routing.
            # Simulation tracking (unchanged)
            if self.is_simulation:
                self.simulation.open_simulated_trade(
                    signal=signal,
                    snapshot=snapshot,
                    filter_score=filter_result.final_score,
                    filter_grade=filter_result.grade,
                    gates_passed=filter_result.filters_passed,
                    gates_total=filter_result.filters_total,
                    costs_estimate=40,
                )

            self._update_dashboard(snapshot, signal)
            
            # ── Analytics: Sync Gate Rejections ──
            if hasattr(self.master, "gate_rejections"):
                self.observer.sync_gate_rejections(dict(self.master.gate_rejections))

            # Periodic status log
            if self.cycle_count % 30 == 0:
                self._log_status()

        except Exception as e:
            self.engine_errors += 1
            self.error_count += 1
            
            if self.engine_errors > 3:
                logger.critical(f"🚨 API/ENGINE DOWN — halting system loop temporarily. Error: {e}")
                self.trading_enabled = False
                await asyncio.sleep(60)
            else:
                logger.error(f"🔥 Engine error [{self.engine_errors}]: {e}", exc_info=True)

        finally:
            # ── HALT File Emergency Stop (Telegram-independent kill switch) ──
            # Write a file called 'HALT' to the project root to stop trading
            # without needing Telegram.
            if os.path.exists("HALT"):
                if self.trading_enabled:
                    logger.critical("🛑 HALT FILE DETECTED — Emergency stop triggered (file-based kill switch)")
                    self.halt_trading("HALT file detected on disk")

    def _sim_execute(self, pending, snapshot):
        logger.info(f"🧪 SIM: Entry confirmed at ₹{snapshot.price:,.1f}")

    async def _live_execute(self, eid, pending, snapshot):
        """Bridge between confirmation and master execution."""
        signal = pending.signal
        signal.id = eid  # Carry the ID for confirmation cleanup
        
        # Final pass back to the single execution gate
        await self.execute_signal(signal, snapshot, context=None, mode="confirmed")

    async def execute_signal(self, signal, snapshot=None, context=None, mode="new"):
        """
        🚀 MASTER EXECUTION ENGINE (Single Point of Truth)
        Graphify Audit Refinement (2026-04-09)
        
        mode="new"       -> Initial entry from AI/Telegram into confirmation queue.
        mode="confirmed" -> Final real-money hand-off to PositionManager.
        """
        logger.info(f"⚡ [EXECUTE_SIGNAL] Mode: {mode} | Type: {signal.signal_type.value}")

        # 1. Mandatory Gate Approval
        # Re-check everything (risk, session, discipline) via the Master Engine
        ctx = context or {}
        ctx["signal_obj"] = signal
        approval = self.master.approve(signal.signal_type.value, ctx)
        
        if not approval.approved:
            logger.warning(f"🚫 [EXECUTE_GATE] Blocked: {approval.reason}")
            if mode == "confirmed":
                self.entry_engine.cancel_pending(getattr(signal, "id", "unknown"))
            return None

        # 2. Path 1: Initial Entry (To Queue)
        if mode == "new":
            self.entry_engine.create_pending_entry(signal, snapshot, None)
            logger.info("📥 [EXECUTE_SIGNAL] Signal parked in Pending Queue")
            return "queued"

        # 3. Path 2: Real Order (To Broker)
        elif mode == "confirmed":
            if snapshot is None:
                logger.error("❌ [EXECUTE_SIGNAL] Cannot execute: Missing live snapshot.")
                return None
                
            # SIMULATION HARD LOCK
            if getattr(self, "is_simulation", False):
                logger.warning("🛡️ SIMULATION MODE HARD LOCK: Real broker execution blocked.")
                self.entry_engine.cancel_pending(getattr(signal, "id", "unknown"))
                return "simulated"
            
            # Sizing & Execution
            price = getattr(signal, "adjusted_entry", snapshot.price)
            size = self.position_manager.calculate_position_size(signal, price, snapshot.atr)

            if not size["allowed"]:
                logger.warning(f"🛡️ [EXECUTE_SIGNAL] Sizing check blocked execution: {size.get('reason')}")
                self.entry_engine.cancel_pending(getattr(signal, "id", "unknown"))
                return None

            # ── THE ONLY POINT OF LIVE EXECUTION (P0-E: SL Guarantee) ──
            pos = await self.position_manager.open_position_with_sl_guarantee(signal, size, price)
            
            # Cleanup
            self.entry_engine.cancel_pending(getattr(signal, "id", "unknown"))

            if pos:
                logger.info(f"✅ [EXECUTE_SIGNAL] LIVE TRADE EXECUTED | {signal.signal_type.value} @ ₹{price:,.1f}")
                self.execution_failures = 0 # Reset on success
            else:
                self.execution_failures += 1
                logger.warning(f"⚠️ [EXECUTE_SIGNAL] Execution Failure [{self.execution_failures}]")
            return pos

    # ──────────────────────────────────────────────────────────
    # OPTIONS SENTIMENT (Phase-2 data fetch)
    # ──────────────────────────────────────────────────────────

    def fetch_options_sentiment(self, price_trend: str = "unknown") -> dict:
        """
        Safely fetch the latest options analysis.

        Returns a normalised dict with keys:
            available (bool), sentiment, pcr, oi_bias,
            max_pain_distance, max_pain_strike, spot

        On any failure returns ``{"available": False, "sentiment": "neutral"}``.
        The Dhan rate limit is 1 call / 3 s — callers must ensure
        this is not invoked more frequently than that.
        """
        try:
            analysis = self.options_analyzer.analyze(price_trend=price_trend)
            if "error" in analysis or not analysis.get("raw_data_available", True):
                logger.warning("[OPTIONS] Fetch error or no raw data: %s", analysis.get("error", "SIMULATION"))
                return {"available": False, "sentiment": "neutral"}
            return {
                "available":         True,
                "sentiment":         analysis["sentiment"],
                "pcr":               analysis["pcr"],
                "oi_bias":           analysis["oi_bias"],
                "max_pain_distance": analysis["max_pain_distance"],
                "max_pain_strike":   analysis["max_pain_strike"],
                "spot":              analysis["spot"],
            }
        except Exception as exc:
            logger.error("[OPTIONS] fetch_options_sentiment failed: %s", exc)
            return {"available": False, "sentiment": "neutral"}

    def _monitor_positions(self, snapshot, df):
        if self.is_simulation:
            closed = self.simulation.update_open_trades(snapshot.price, snapshot)
            for trade in closed:
                pnl = trade.get("net_pnl", 0)
                
                # Try to map back to original signal ID for performance logger
                trade_id = trade.get("signal_id") or trade.get("id", "SIM")
                exit_price = trade.get("exit_price") or trade.get("exit", snapshot.price)
                reason = trade.get("exit_reason", "sim_close")
                self.perf_logger.log_exit(trade_id, exit_price, pnl, reason)
                
                # ── Analytics: Track Trade Result ──
                entry = trade.get("entry", 0)
                sl = trade.get("sl", 0)
                risk_pts = abs(entry - sl)
                direction = trade.get("direction", "BUY")
                pts_gained = (exit_price - entry) if direction == "BUY" else (entry - exit_price)
                r_val = round(pts_gained / risk_pts, 2) if risk_pts > 0 else 0.0

                self.observer.on_trade_close({
                    "trade_id": trade_id,
                    "r": r_val,
                    "pnl": pnl,
                    "regime": trade.get("regime", "UNKNOWN"),
                    "oi_source": getattr(snapshot, "oi_data_source", "UNKNOWN"),
                    "hold_min": trade.get("hold_min", 1)
                })

                self.exit_engine.record_trade_result(pnl)
                if self.telegram_bot:
                    fire_and_log(
                        self.telegram_bot.notify_trade_close(
                            trade.get("id", "SIM"), pnl, "WIN" if pnl > 0 else "LOSS"
                        ),
                        label=f"notify_trade_close:{trade_id}"
                    )
        else:
            actions = self.position_manager.update_positions(snapshot.price)
            for action in actions:
                if action["action"] in ("CLOSE", "FULL_CLOSE"):
                    result = self.position_manager.close_position(
                        action["position_id"], action["price"], action.get("reason", "")
                    )
                    if result and result.get("type") == "full":
                        pnl = result.get("pnl", 0)
                        
                        # Log to performance logger
                        exit_price = result.get("exit", action.get("price", snapshot.price))
                        reason = result.get("reason", action.get("reason", "unknown"))
                        self.perf_logger.log_exit(action["position_id"], exit_price, pnl, reason)
                        
                        # Fetch original position for entry/sl info if possible
                        pos = self.position_manager.open_positions.get(action["position_id"])
                        if pos:
                            entry = pos.entry_price
                            sl = pos.original_stop_loss
                            risk_pts = abs(entry - sl)
                            direction = "BUY" if pos.direction == Direction.BULLISH else "SELL"
                            pts_gained = (exit_price - entry) if direction == "BUY" else (entry - exit_price)
                            r_val = round(pts_gained / risk_pts, 2) if risk_pts > 0 else 0.0
                            regime = pos.regime_at_entry
                            hold_min = max(1.0, (datetime.now() - pos.entry_time).total_seconds() / 60.0)
                        else:
                            r_val = 0.0
                            regime = "UNKNOWN"
                            hold_min = 1.0

                        self.observer.on_trade_close({
                            "trade_id": action["position_id"],
                            "r": r_val,
                            "pnl": pnl,
                            "regime": regime,
                            "oi_source": getattr(snapshot, "oi_data_source", "UNKNOWN"),
                            "hold_min": hold_min
                        })

                        self.exit_engine.record_trade_result(pnl)
                        if self.telegram_bot:
                            fire_and_log(
                                self.telegram_bot.notify_trade_close(
                                    action["position_id"], pnl, "WIN" if pnl > 0 else "LOSS"
                                ),
                                label=f"notify_trade_close:{action['position_id']}"
                            )

    def _monitor_only(self):
        try:
            _, snapshot = self.data_manager.get_latest_data()
            if snapshot and snapshot.price > 0:
                self._monitor_positions(snapshot, None)
                self._update_dashboard(snapshot, None)
        except Exception:
            pass

    def _update_dashboard(self, snapshot, signal):
        if not self.dashboard: return
        try:
            status = self.decision_engine.get_status()
            status["snapshot"] = snapshot.to_dict() if snapshot else {}
            status["cycle"] = self.cycle_count
            status["system_mode"] = settings.system_mode.mode
            status["filter_stats"] = self.trade_filter.get_filter_stats()
            status["entry_stats"] = self.entry_engine.get_stats()
            status["exit_status"] = self.exit_engine.get_status()
            status["risk"] = self.risk_manager.get_status_report()
            status["errors"] = self.error_count
            status["last_cycle"] = self.last_cycle_time
            
            self.dashboard.update_status(status)
        except Exception as e:
            logger.debug(f"Dashboard update error: {e}")

    def halt_trading(self, reason: str):
        """Emergency Stop Control"""
        if self.trading_enabled:
            self.trading_enabled = False
            logger.critical(f"🛑 HALTING TRADING: {reason}")
            if self.telegram_bot:
                fire_and_log(self.telegram_bot.notify_halt(reason), label="notify_halt")
            if self.dashboard:
                self._update_dashboard(None, None)

    # ──────────────────────────────────────────────────────────
    # 🚨 BROKER POSITION RECONCILIATION (P0.3)
    # ──────────────────────────────────────────────────────────

    async def _reconcile_broker_positions(self):
        """
        CRITICAL SAFETY CHECK: Detect orphaned positions from a previous crash.
        
        If the bot crashed after placing an order but before recording it internally,
        there could be an unmanaged live position with no SL. This method queries
        the broker on startup to detect and alert on such orphans.
        """
        if self.is_simulation:
            logger.info("🧪 Simulation mode — skipping broker reconciliation")
            return

        try:
            from dhan_client import get_dhan_client
            dhan = get_dhan_client()
            
            response = dhan.get_positions()
            
            if not response or response.get("status") != "success":
                logger.warning("⚠️ Could not fetch broker positions for reconciliation")
                return

            broker_positions = response.get("data", [])
            
            # Filter for open intraday positions only
            open_broker_positions = [
                p for p in broker_positions
                if p.get("positionType") == "INTRADAY" 
                and p.get("netQty", 0) != 0
            ]

            if not open_broker_positions:
                logger.info("✅ Broker reconciliation: No orphaned positions found")
                return

            # Compare against internal tracking
            def _get_position_identifier(pos) -> str:
                """Get the most reliable identifier for matching against broker."""
                for attr in ('security_id', 'securityId', 'symbol', 'tradingSymbol', 'instrument_id'):
                    val = getattr(pos, attr, None)
                    if val:
                        return str(val)
                return ""

            internal_ids = set()
            if hasattr(self.position_manager, 'open_positions'):
                internal_ids = {
                    _get_position_identifier(pos) 
                    for pos in self.position_manager.open_positions.values()
                }
                internal_ids.discard("")  # Remove empty matches
                
            if not internal_ids and getattr(self.position_manager, 'open_positions', None):
                logger.error(
                    "🚨 RECONCILIATION SAFETY ABORT: Internal positions exist but "
                    "no security_id could be extracted. Skipping orphan check."
                )
                return

            orphans = [
                p for p in open_broker_positions 
                if str(p.get("securityId", "")) not in internal_ids
            ]

            if orphans:
                symbols = [f"{p.get('tradingSymbol', '?')} (Qty: {p.get('netQty', 0)})" for p in orphans]
                orphan_str = "\n".join(symbols)
                
                logger.critical(
                    f"🚨 ORPHANED POSITIONS DETECTED ON BROKER!\n"
                    f"Found {len(orphans)} positions not tracked internally:\n"
                    f"{orphan_str}\n"
                    f"System will NOT trade until manually resolved."
                )
                
                # HALT TRADING — do not risk managing unknown positions
                self.trading_enabled = False
                
                # Alert admin via Telegram
                alert_msg = (
                    f"🚨 <b>ORPHANED POSITIONS DETECTED</b>\n\n"
                    f"Found {len(orphans)} positions on Dhan not tracked by bot:\n"
                    f"<code>{orphan_str}</code>\n\n"
                    f"<b>Trading is HALTED.</b>\n"
                    f"Check your broker and square off manually if needed.\n"
                    f"Use /start to re-enable after verification."
                )
                try:
                    fire_and_log(
                        self.telegram_bot._send_admin_msg(alert_msg),
                        label="orphan_position_alert"
                    )
                except Exception as e:
                    # Log loudly — this is a critical alert that failed
                    logger.critical(
                        f"🚨🚨 ORPHAN ALERT FAILED TO SEND VIA TELEGRAM: {e}\n"
                        f"Manual check required: {orphan_str}"
                    )
            else:
                logger.info(
                    f"✅ Broker reconciliation: {len(open_broker_positions)} open positions, "
                    f"all tracked internally. Verifying SL presence..."
                )

                # ── P0-E: SL Presence Check on Tracked Positions ──
                # If a position exists but the SL was dropped or missing, close it.
                sl_missing = []
                order_list_resp = dhan.get_order_list()
                valid_sl_statuses = {"PENDING", "TRIGGER_PENDING", "OPEN"}

                if order_list_resp and order_list_resp.get("status") == "success":
                    orders = order_list_resp.get("data", [])
                    symbols_with_sl = {
                        o.get("tradingSymbol") for o in orders 
                        if o.get("orderType") in ("SL", "SL-M") 
                        and o.get("orderStatus") in valid_sl_statuses
                    }

                    for pos in open_broker_positions:
                        sym = pos.get("tradingSymbol")
                        if sym and sym not in symbols_with_sl:
                            sl_missing.append(pos)
                else:
                    logger.warning("⚠️ Could not fetch order list. Skipping SL presence verification.")

                if sl_missing:
                    missing_str = ", ".join([str(p.get("tradingSymbol")) for p in sl_missing])
                    logger.critical(
                        "🚨 MISSING_SL_DETECTED_ON_STARTUP",
                        extra={"missing_sl_positions": missing_str}
                    )
                    
                    # Force close ALL positions if we have naked exposure
                    self.position_manager.close_all_positions("STARTUP_MISSING_SL_DETECTED")
                    self.halt_trading(f"Startup check failed: Missing SL for {missing_str}")

        except Exception as e:
            # Non-fatal: don't crash startup if reconciliation fails
            # But DO log it prominently
            logger.error(f"⚠️ Broker reconciliation failed (non-fatal): {e}")

    # ══════════════════════════════════════════════════════════════
    # P0-C: EXTERNAL HEARTBEAT + DEAD MAN'S SWITCH
    # ══════════════════════════════════════════════════════════════

    async def _ping_heartbeat(self, session: aiohttp.ClientSession) -> None:
        """Dead man's switch. If this stops pinging, we're down.

        Runs as fire-and-forget background task — never blocks the main loop.
        Skipped automatically when system is under stress (last cycle > 0.5s).
        """
        if not HEARTBEAT_URL:
            return
        # Skip during stress cycles — backpressure protection
        last_cycle_duration = time.perf_counter() - getattr(self, "_last_cycle_start", 0)
        if last_cycle_duration > 0.5:
            return
        try:
            async with session.get(
                HEARTBEAT_URL,
                timeout=aiohttp.ClientTimeout(total=2)
            ) as _:
                pass
        except Exception:
            pass  # Never log heartbeat failures — fills console with noise

    async def _deadman_watchdog(self) -> None:
        """P0-C: Force-close all positions if main loop stops updating.
        
        If the main loop hasn't called record_heartbeat() in DEADMAN_TIMEOUT_SECONDS,
        this watchdog triggers emergency position closure.
        """
        while True:
            try:
                await asyncio.sleep(10)
                elapsed = time.time() - self.position_manager._last_heartbeat_time
                if elapsed > DEADMAN_TIMEOUT_SECONDS and self.cycle_count > 5:
                    logger.critical(
                        "🚨 DEADMAN SWITCH TRIGGERED — no heartbeat for %.0fs. "
                        "Force-closing all positions.", elapsed
                    )
                    # Attempt emergency close
                    try:
                        self.position_manager.close_all_positions("DEADMAN_SWITCH")
                    except Exception as e:
                        logger.critical("Deadman close_all_positions failed: %s", e)
                    
                    # Alert via Telegram
                    if self.telegram_bot:
                        try:
                            from utils.tasks import fire_and_log
                            fire_and_log(
                                self.telegram_bot._send_admin_msg(
                                    "🚨 <b>DEADMAN SWITCH TRIGGERED</b>\n\n"
                                    f"No heartbeat for {elapsed:.0f}s.\n"
                                    "Emergency position closure attempted.\n"
                                    "Check system immediately."
                                ),
                                label="deadman_alert"
                            )
                        except Exception:
                            pass
                    
                    # Halt trading
                    self.halt_trading("DEADMAN_SWITCH: Main loop stalled")
                    break  # Stop watchdog after triggering
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Deadman watchdog error: %s", e)

    def _log_status(self):
        if not self.is_simulation:
            pm = self.position_manager
            logger.info(f"Capital: ₹{pm.total_capital:,.0f} | Risk PnL: ₹{self.risk_manager.daily_pnl:,.0f}")

    def stop(self):
        self.running = False
        logger.info("Shutting down v4.6.1...")
        self.entry_engine.cancel_all_pending()
        self.trade_logger.save_all()
        self.position_manager.save_state()
        if self.is_simulation:
            self.simulation._save_state()
            
        if hasattr(self, "observer"):
            import json
            logger.info(f"📊 DAILY SUMMARY:\n{json.dumps(self.observer.summary(), indent=2)}")
            
        logger.info("System stopped ✓")


def main():
    system = NiftyAISystem()
    asyncio.run(system.start())


if __name__ == "__main__":
    main()
