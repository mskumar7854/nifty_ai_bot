import time
import asyncio
import aiohttp
import os
from typing import Optional, Dict, Any

from utils.logger import get_logger
from core.telegram_controller import TelegramController
from core.alert_manager import AlertManager
from core.log_observer import LogObserver
from core.metrics_logger import MetricsLogger
from performance_logger import PerformanceLogger
from utils.tasks import fire_and_log
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler

from models import Signal, SignalType

logger = get_logger("telemetry")

class TelemetryPipeline:
    """
    Handles logging, metrics, dashboard updates, telegram notifications,
    latency reporting, and external heartbeats.
    """
    def __init__(self, ctx):
        self.ctx = ctx
        self.settings = ctx.settings
        
        # 1. Observers & Loggers
        self.perf_logger = PerformanceLogger()
        self.observer = LogObserver()
        if hasattr(ctx, "data_manager"):
            self.observer.data_manager = ctx.data_manager
            
        self.metrics_logger = MetricsLogger()
        
        # 2. Telegram & Alerts
        # We pass ctx.system for the bot to control halts (until orchestrator is fully extracted)
        db_mgr = ctx.db_manager
        if not db_mgr and hasattr(ctx, "decision") and hasattr(ctx.decision, "memory"):
             db_mgr = ctx.decision.memory.db
             
        self.telegram_bot = TelegramController(
            settings=self.settings,
            system=ctx.system,
            db_manager=db_mgr
        )
        self.alert_manager = AlertManager(self.settings, self.telegram_bot)
        
        # Idempotency cache for trade close notifications
        self._notified_close_trades: set = set()
        
        # 3. Dashboard
        self.dashboard = None
        if self.settings.dashboard.enabled:
            try:
                from web.dashboard import Dashboard
                self.dashboard = Dashboard(
                    host=self.settings.dashboard.host,
                    port=self.settings.dashboard.port,
                    telemetry_emit_interval_seconds=self.settings.dashboard.telemetry_emit_interval_seconds,
                )
                if self.ctx.burnin_tracker and self.ctx.readiness_scorer:
                    self.dashboard.set_burnin_components(
                        self.ctx.burnin_tracker,
                        self.ctx.readiness_scorer,
                    )
                if self.ctx.simulation:
                    self.dashboard.set_simulation_engine(self.ctx.simulation)
                if hasattr(self.ctx, "system") and self.ctx.system:
                    if hasattr(self.ctx.system, "position_manager") and self.ctx.system.position_manager:
                        self.dashboard.set_position_manager(self.ctx.system.position_manager)
                    if hasattr(self.ctx.system, "oms") and self.ctx.system.oms:
                        self.dashboard.set_oms(self.ctx.system.oms)
            except Exception as e:
                logger.warning(f"Dashboard not available: {e}")
                
        # Latency State
        self._latency_history = []
        self._current_latencies = {}
        self._last_telemetry_log_ts = 0.0

    async def dispatch_signal(self, signal: Signal) -> None:
        """
        Dispatches actionable trading signals to alert channels (Telegram/Console).
        Guaranteed non-blocking, isolated from decision and execution pipelines.
        """
        if signal is None:
            return
            
        stype = getattr(signal, "signal_type", None)
        if stype == SignalType.NO_TRADE or str(stype).upper() in ("NO_TRADE", "SIGNALTYPE.NO_TRADE"):
            return

        if self.alert_manager:
            try:
                await self.alert_manager.dispatch(signal)
            except Exception as e:
                logger.error(f"Signal alert dispatch failed safely: {e}")

    async def dispatch_trade_close(
        self,
        trade_id: str,
        pnl: float,
        outcome: str,
        symbol: str = "",
        hold_mins: float = 0.0
    ) -> None:
        """
        Dispatches trade-close outcome alert to Telegram with idempotency protection.
        """
        if not trade_id:
            return

        tid_str = str(trade_id)
        if tid_str in self._notified_close_trades:
            logger.debug("Trade close alert already sent for %s — skipping duplicate", tid_str)
            return

        self._notified_close_trades.add(tid_str)
        if len(self._notified_close_trades) > 1000:
            try:
                self._notified_close_trades.pop()
            except KeyError:
                pass

        if self.telegram_bot and hasattr(self.telegram_bot, "notify_trade_close"):
            try:
                await self.telegram_bot.notify_trade_close(
                    trade_id=tid_str,
                    pnl=float(pnl),
                    outcome=str(outcome),
                    symbol=str(symbol),
                    hold_mins=float(hold_mins)
                )
            except Exception as e:
                logger.error(f"Trade close alert dispatch failed safely: {e}")

    def start_dashboard(self):
        if self.dashboard:
            self.dashboard.start()

    async def init_telegram(self):
        if not self.ctx.telegram_enabled:
            return
            
        app = ApplicationBuilder().token(self.settings.alerts.telegram_bot_token).build()
        app.add_handler(CommandHandler("start", self.telegram_bot.start_cmd))
        app.add_handler(CommandHandler("stop", self.telegram_bot.stop_cmd))
        app.add_handler(CommandHandler("status", self.telegram_bot.status_cmd))
        app.add_handler(CommandHandler("kill", self.telegram_bot.kill_cmd))
        app.add_handler(CommandHandler("restart", self.telegram_bot.restart_cmd))
        app.add_handler(CommandHandler("pause", self.telegram_bot.pause_cmd))
        app.add_handler(CommandHandler("resume", self.telegram_bot.resume_cmd))
        app.add_handler(CommandHandler("force_reconcile", self.telegram_bot.force_reconcile_cmd))
        app.add_handler(CallbackQueryHandler(self.telegram_bot.handle_callback_query))

        self.telegram_bot.app = app

        # Register central State Manager Telegram alert callback
        from core.system_state import get_state_manager
        def send_telegram_alert(msg: str):
            if self.ctx.telegram_enabled and self.telegram_bot:
                asyncio.create_task(self.telegram_bot._send_admin_msg(msg))
        get_state_manager().register_alert_callback(send_telegram_alert)

        try:
            await app.initialize()
            try:
                await app.bot.delete_webhook(drop_pending_updates=True)
            except Exception as weberr:
                logger.warning(f"Webhook deletion warning: {weberr}")
            await app.start()
            await app.updater.start_polling(drop_pending_updates=True)
            
            mode_str = "SIMULATION mode — alerts only" if self.ctx.is_simulation else "LIVE mode"
            logger.info(f"📱 Telegram Active ({mode_str})")
        except Exception as e:
            logger.error("Telegram init failed: %s", e)
            self.ctx.telegram_enabled = False

    async def shutdown_telegram(self):
        if self.ctx.telegram_enabled and self.telegram_bot and hasattr(self.telegram_bot, "app"):
            app = self.telegram_bot.app
            try:
                await app.updater.stop()
            except Exception:
                pass
            try:
                await app.stop()
                await app.shutdown()
            except Exception:
                pass

    def record_latencies(self, elapsed_ms: float, detail_latencies: dict):
        self._current_latencies = detail_latencies
        self._latency_history.append(elapsed_ms)
        if len(self._latency_history) > 100:
            self._latency_history = self._latency_history[-100:]

    def get_latency_summary(self):
        if not self._latency_history:
            return 0, 0, 0
        avg_ms = sum(self._latency_history) / len(self._latency_history)
        max_ms = max(self._latency_history)
        sorted_lat = sorted(self._latency_history)
        p95_ms = sorted_lat[min(int(len(self._latency_history) * 0.95), len(sorted_lat) - 1)]
        return avg_ms, p95_ms, max_ms

    async def ping_heartbeat(self, session: aiohttp.ClientSession, last_cycle_duration: float):
        url = os.getenv("HEARTBEAT_URL")
        if not url:
            return
        if last_cycle_duration > 0.5:
            return
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=2)):
                pass
        except Exception:
            pass
