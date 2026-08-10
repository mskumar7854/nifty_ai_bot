import asyncio
import time
import logging
import traceback

from models import SignalType
from typing import Optional

from core.context import RuntimeContext
from models.events import SessionChanged, MarketSnapshotCreated, EndOfDayTriggered

logger = logging.getLogger("orchestrator")

class TradingOrchestrator:
    """
    Coordinates the trading system cycle without containing business logic.
    Responsibilities:
    - Initialization and graceful shutdown
    - Cycle execution sequencing
    - Exception catching and routing
    - Scheduling periodic tasks
    """
    def __init__(self, ctx: RuntimeContext):
        self.ctx = ctx
        self.running = False
        self.cycle_count = 0
        self.error_count = 0
        self.last_cycle_time = 0

        # Grab pipelines from context for fast access
        self.telemetry = ctx.telemetry
        self.market_pipeline = getattr(ctx, "market_data", getattr(ctx.system, "market_pipeline", None))
        self.decision_pipeline = getattr(ctx, "decision", getattr(ctx.system, "decision_pipeline", None))
        self.execution_pipeline = getattr(ctx, "execution", getattr(ctx.system, "execution_pipeline", None))
        self.position_pipeline = getattr(ctx, "position", None) # May need to initialize if not in ctx

    async def start(self):
        """Starts the orchestrator and background tasks."""
        self.running = True
        logger.info("🚀 Starting Trading Orchestrator...")
        
        if self.ctx.event_manager:
            self.ctx.event_manager.publish(SessionChanged(source="orchestrator", payload={"status": "STARTING"}))

        import aiohttp
        async with aiohttp.ClientSession() as session:
            try:
                # ── Background Tasks ──
                # Let's say OI updater is managed by market pipeline or data manager
                if hasattr(self.ctx.data_manager, "start_oi_updater"):
                    await self.ctx.data_manager.start_oi_updater()

                # ── Initialize Telegram Bot ──
                if self.telemetry and hasattr(self.telemetry, "init_telegram"):
                    await self.telemetry.init_telegram()

                # ── Main Loop ──
                from core.session_guard import orchestrator as session_guard, MarketSessionState

                while self.running:
                    start_time = time.perf_counter()
                    self.last_cycle_time = time.time()
                    
                    await self._run_cycle(session)
                    
                    # Check for auto-shutdown after market hours
                    if getattr(self.ctx.settings.trading, "auto_shutdown_after_market", False):
                        state = session_guard.get_session_state()
                        if state in (MarketSessionState.POST_MARKET, MarketSessionState.CLOSED, MarketSessionState.WEEKEND_CLOSED):
                            logger.info("Auto shutdown enabled and market is closed. Triggering orchestrator shutdown...")
                            self.stop()
                            break

                    # Compute session-aware sleep interval from single authoritative RuntimeState
                    last_ts = getattr(self.ctx.data_manager, "last_market_activity_ts", None)
                    runtime_state = session_guard.get_runtime_state(last_ts)
                    elapsed = time.perf_counter() - start_time
                    
                    infra_state = getattr(self.ctx.data_manager, "infrastructure_state", None)
                    if infra_state and infra_state.suspended and infra_state.resume_at:
                        remaining = infra_state.resume_at - time.time()
                        base_interval = max(5.0, min(60.0, remaining))
                    else:
                        base_interval = runtime_state.poll_interval_s
                        
                    sleep_time = max(0.1, base_interval - elapsed)
                    await asyncio.sleep(sleep_time)
            except asyncio.CancelledError:
                logger.info("Shutdown signal received")
            finally:
                if hasattr(self.ctx.data_manager, "stop_oi_updater"):
                    await self.ctx.data_manager.stop_oi_updater()
                if self.telemetry and hasattr(self.telemetry, "shutdown_telegram"):
                    await self.telemetry.shutdown_telegram()
                logger.info("🛑 Orchestrator shutdown complete.")
                if self.ctx.event_manager:
                    self.ctx.event_manager.publish(SessionChanged(source="orchestrator", payload={"status": "STOPPED"}))

    def stop(self):
        """Stops the orchestrator."""
        self.running = False

    async def _run_cycle(self, session):
        """Executes a single cycle."""
        self.cycle_count += 1
        start_time = time.perf_counter()
        from core.session_guard import orchestrator as session_guard
        last_ts = getattr(self.ctx.data_manager, "last_market_activity_ts", None)
        runtime_state = session_guard.get_runtime_state(last_ts)

        try:
            # 1. Market Data Pipeline (Telemetry, indicators, and snapshots continue on every cycle)
            if hasattr(self.market_pipeline, "data_manager"):
                df, snapshot = await self.market_pipeline.data_manager.update_latest_candle_async(session)
            else:
                # Fallback to older system pattern for backward compatibility
                df, snapshot = await self.ctx.system.data_manager.update_latest_candle_async(session)

            if snapshot is None or snapshot.price == 0:
                return
                
            if self.ctx.event_manager:
                self.ctx.event_manager.publish(MarketSnapshotCreated(source="orchestrator", payload={"price": snapshot.price}))

            # 2. Position Pipeline -> Check exits first (EOD or stops)
            # Before generating new decisions, manage existing positions.
            system = getattr(self.ctx, "system", None)
            pos_manager = getattr(system, "position_manager", None)
            
            # EOD force exit
            if session_guard.is_force_exit_time():
                if self.ctx.event_manager:
                    self.ctx.event_manager.publish(EndOfDayTriggered(source="orchestrator"))

            actions_to_execute = []
            if self.position_pipeline and pos_manager:
                # For each open position, run position pipeline evaluate
                open_positions = pos_manager.open_positions if not self.ctx.is_simulation else getattr(self.ctx.simulation, "open_trades", {})
                for pid, pos in open_positions.items():
                    actions = self.position_pipeline.evaluate(pos, snapshot, df)
                    actions_to_execute.extend(actions)

            # 3. Execution Pipeline (Apply Exit Actions)
            if actions_to_execute and self.execution_pipeline:
                await self.execution_pipeline.apply_position_actions(actions_to_execute)

            # 3b. Simulation Exit Monitoring
            if self.ctx.is_simulation and self.ctx.simulation:
                sim = self.ctx.simulation
                if sim.open_trades:
                    closed = sim.update_open_trades(
                        snapshot.price, snapshot,
                        data_manager=self.ctx.data_manager
                    )
                    for c in closed:
                        logger.info(f"📕 SIM EXIT: {c.get('id')} | "
                                    f"Reason: {c.get('exit_reason')} | "
                                    f"PnL: ₹{c.get('net_pnl', 0):,.1f}")

            # 4. Decision Pipeline (Gated by RuntimeState: only evaluate new entries if trading is allowed)
            infra_state = getattr(self.ctx.data_manager, "infrastructure_state", None)
            is_suspended = infra_state.suspended if infra_state else False
            
            if is_suspended:
                if not getattr(self, "_logged_suspend", False):
                    logger.warning(f"Infrastructure degraded. Trading suspended. Reason: {infra_state.reason}")
                    self._logged_suspend = True
            else:
                if getattr(self, "_logged_suspend", False):
                    logger.info("Infrastructure recovered. Resuming trading.")
                self._logged_suspend = False

            if self.decision_pipeline and runtime_state.is_trading_allowed:
                if hasattr(self.ctx.system, "entry_engine"):
                    # Check pending first (execution engine continues)
                    confirmed = self.ctx.system.entry_engine.check_confirmations(snapshot, df)
                    for eid, pending in confirmed:
                        if self.execution_pipeline:
                            await self.execution_pipeline.execute(pending, snapshot, self.ctx.is_simulation, mode="confirmed")
                
                if not is_suspended:
                    # New decisions via DecisionPipeline
                    latencies = {"fetch_ms": int((time.perf_counter() - start_time) * 1000)}
                    result = self.decision_pipeline.evaluate(df, snapshot, self.cycle_count, latencies)
                
                if result.signal:
                    gate_logs = []
                    for g in result.gate_results:
                        gate_logs.append(f"{'✓' if g.passed else '✗'} {g.name}")
                        if not g.passed and g.reason:
                            gate_logs.append(f"  Reason: {g.reason}")
                            
                    base_threshold = result.signal.metadata.get("base_threshold", 47.0)
                    adaptive_threshold = getattr(result.signal, "adaptive_threshold", None) or result.signal.metadata.get("adaptive_threshold", base_threshold)
                    threshold_str = f"{adaptive_threshold:.1f}%"
                    if adaptive_threshold != base_threshold:
                        threshold_str += " (Adaptive)"
                            
                    logger.info(
                        f"\n{'═'*30}\n\n"
                        f"Signal Generated\n"
                        f"Confidence : {result.confidence:.1f}%\n"
                        f"Threshold  : {threshold_str}\n\n"
                        f"Decision Pipeline\n\n"
                        + "\n".join(gate_logs) + "\n\n"
                        f"{'APPROVED' if result.approved else 'REJECTED'}\n\n"
                        f"{'═'*30}"
                    )
                    
                if not is_suspended:
                    if result.approved and self.execution_pipeline:
                        self.ctx.system._last_decision_ts = time.time()
                        await self.execution_pipeline.execute(result.signal, snapshot, self.ctx.is_simulation, mode="new")

            # 6. Telemetry Pipeline — push full status to dashboard
            if self.telemetry and hasattr(self.telemetry, "dashboard") and self.telemetry.dashboard:
                try:
                    from core.session_guard import orchestrator as sg
                    last_ts = getattr(self.ctx.data_manager, "last_market_activity_ts", None)

                    # Session awareness fields
                    dash_fields = sg.get_dashboard_fields(last_ts)

                    # Decision engine status (last_signal + agents)
                    de_status = {}
                    de = getattr(self.ctx.system, "decision_engine", None)
                    if de:
                        de_status = de.get_status()

                    # OI health from observer
                    oi_health = {}
                    observer = getattr(self.telemetry, "observer", None)
                    if observer:
                        oi_health = observer.get_oi_health()

                    # Latency
                    cycle_elapsed = time.perf_counter() - start_time
                    latency_ms = int(cycle_elapsed * 1000)

                    status_data = {
                        "orchestrator": {
                            "session_state": dash_fields.get("session_state", "---"),
                            "runtime_posture": f"SUSPENDED ({infra_state.reason})" if (infra_state and infra_state.suspended) else dash_fields.get("runtime_posture", "---"),
                            "data_health": dash_fields.get("data_health", "---"),
                        },
                        "latency_ms": latency_ms,
                        "latency_status": "CRITICAL" if latency_ms > 2000 else ("WARNING" if latency_ms > 500 else "OK"),
                        "oi_health": oi_health,
                        "last_signal": de_status.get("last_signal"),
                        "agents": de_status.get("agents"),
                        "price": snapshot.price if snapshot else 0,
                        "cycle": self.cycle_count,
                        "risk": {
                            "trading_enabled": getattr(self.ctx.system, "trading_enabled", True),
                        },
                    }
                    self.telemetry.dashboard.update_status(status_data)
                except Exception as te:
                    logger.error(f"Telemetry update error: {te}", exc_info=True)
                    
        except Exception as e:
            logger.error(f"🔴 ERROR IN CYCLE: {e}", exc_info=True)
            self.error_count += 1
            if self.error_count > 10:
                logger.critical("Too many errors. Halting orchestrator.")
                self.running = False
