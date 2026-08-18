import time
import uuid
from datetime import datetime
from typing import Optional, Dict, Any

from models import Signal, MarketSnapshot, ExecutionResult
from core.options_resolver import OptionContractBuilder, OptionExecutionTranslator
from core.execution_fidelity import ExecutionFidelityEngine
from core.structural_breaker import StructuralBreaker
from core.system_state import get_state_manager
from utils.logger import get_logger

logger = get_logger("execution_pipeline")

class ExecutionPipeline:
    """
    Transforms a TradingDecision (Signal) into an ExecutionResult.
    Responsibilities:
      - Instrument resolution & premium retrieval
      - Spot-to-Premium level translation
      - Position sizing computation
      - Execution Fidelity simulation
      - StructuralBreaker safety checks (Live)
      - OMS Intent & Live Broker execution (SL Guarantee)
      - Entry confirmation routing
    """
    def __init__(self, ctx):
        self.ctx = ctx
        self.settings = ctx.settings
        self.fidelity_engine = ExecutionFidelityEngine()

    async def execute(self, signal: Signal, snapshot: MarketSnapshot, is_simulation: bool, mode: str = "new") -> ExecutionResult:
        """
        Executes the signal deterministically, returning standard ExecutionResult.
        mode="new" -> Evaluates Phase A (quotes, liquidity) and either simulates or queues for confirmation.
        mode="confirmed" -> Proceeds directly to Phase B (live execution) assuming Phase A already passed.
        """
        t0 = time.perf_counter()

        if mode == "confirmed":
            return await self._execute_live_phase_b(signal, snapshot)

        # ── PHASE A ──
        # 1. Resolve Instrument
        try:
            regime_ctx = signal.metadata.get("regime_context") if hasattr(signal, "metadata") and signal.metadata else None
            regime_val = regime_ctx or signal.regime
            
            instrument_info = OptionContractBuilder.resolve_instrument(
                direction=signal.direction.value,
                spot=snapshot.price,
                confidence=signal.confidence,
                regime=regime_val
            )
            if instrument_info.get("strike") is None or instrument_info.get("selection_type") == "NO_TRADE":
                reason = instrument_info.get("selection_reason", "NO_TRADE policy")
                logger.warning(f"🚫 [EXEC] Strike policy blocked execution: {reason}")
                return self._build_failed_result(f"Strike Policy Blocked: {reason}")
        except Exception as e:
            logger.error(f"❌ [EXEC] Instrument resolution failed: {e}")
            return self._build_failed_result(f"Instrument Resolution Failed: {e}")

        # 2. Fetch Premium Quote
        try:
            expiry_context = OptionContractBuilder.get_expiry_context()
            quote = await __import__('asyncio').wait_for(
                __import__('asyncio').to_thread(
                    self.ctx.data_manager.fetch_option_quote,
                    instrument_info["strike"],
                    instrument_info["type"],
                    instrument_info["expiry"]
                ),
                timeout=12.0
            )
            if quote is None:
                return self._build_failed_result("Premium Fetch Returned None")
            instrument_info["security_id"] = getattr(quote, "security_id", "")
            instrument_info["actual_iv"] = getattr(quote, "iv", None)
            instrument_info["spread_pct"] = getattr(quote, "spread_pct", None)
            instrument_info["volume"] = getattr(quote, "volume", None)
        except Exception as e:
            logger.error(f"❌ [EXEC] Quote fetch failed: {e}")
            return self._build_failed_result(f"Premium Fetch Failed: {e}")

        premium = quote.ask if getattr(quote, 'ask', 0) > 0 else getattr(quote, 'ltp', 0)
        if premium <= 0:
            premium = 100.0

        # Liquidity & Spread Protection
        spread_pct = getattr(quote, 'spread_pct', 0) / 100.0
        if spread_pct > 0.05 or getattr(quote, 'volume', 0) < 500:
            return self._build_failed_result(f"Liquidity/Spread Block: Spread {spread_pct:.1%} Vol {getattr(quote, 'volume', 0)}")

        # 3. Translate Levels
        levels = OptionExecutionTranslator.translate_levels(signal, quote, instrument_info)
        
        signal.metadata["instrument"] = instrument_info
        signal.metadata["quote"] = quote
        signal.metadata["premium_entry"] = levels["premium_entry"]
        signal.metadata["premium_sl"] = levels["premium_sl"]
        signal.metadata["premium_t1"] = levels["premium_t1"]
        signal.metadata["premium_t2"] = levels["premium_t2"]
        signal.metadata["decay_risk"] = levels["decay_risk"]
        signal.metadata["pricing_method"] = levels.get("pricing_method", "DELTA_APPROXIMATION")
        signal.metadata["delta_source"] = levels.get("delta_source", "HEURISTIC")
        signal.metadata["delta_used"] = levels.get("delta_used", 0.50)

        # 4. Route to Queue
        if hasattr(self.ctx.system, "entry_engine"):
            self.ctx.system.entry_engine.create_pending_entry(signal, snapshot, None)
        return ExecutionResult(
            status="queued",
            broker_order_id="",
            filled_price=0.0,
            fill_time=None,
            latency_ms=int((time.perf_counter() - t0) * 1000),
            slippage=0.0,
            execution_quality="UNKNOWN",
            errors=[],
            position_id=""
        )

    async def _execute_simulated(self, signal: Signal, snapshot: MarketSnapshot, instrument_info: dict, premium: float, qty: int) -> ExecutionResult:
        """Handles execution fidelity and simulation logic."""
        regime_str = signal.regime.value if hasattr(signal.regime, "value") else str(getattr(signal, "regime", "UNKNOWN"))
        
        # Ask FidelityEngine for realistic entry
        fid_result = self.fidelity_engine.simulate_entry(
            signal_price=premium,
            spot_price=snapshot.price,
            strike=instrument_info["strike"],
            option_type=instrument_info["type"],
            qty=qty,
            regime=regime_str,
            vix=snapshot.india_vix if hasattr(snapshot, "india_vix") else getattr(snapshot, "vix", 14.0)
        )
        
        if fid_result.rejected:
            logger.warning(f"🚫 [EXEC] Fidelity rejection: {fid_result.rejection_reason}")
            signal.execution_status = "rejected"
            signal.metadata["rejection_reason"] = f"Fidelity: {fid_result.rejection_reason}"
            return self._build_failed_result(f"Fidelity Rejection: {fid_result.rejection_reason}")
            
        # Update signal with fidelity details
        signal.adjusted_entry = fid_result.fill_price
        
        sim_trade = None
        if hasattr(self.ctx.system, "simulation"):
            # Mock filter_result since it's already approved
            sim_trade = self.ctx.system.simulation.open_simulated_trade(
                signal=signal,
                snapshot=snapshot,
                filter_score=100.0,
                filter_grade="A",
                gates_passed=10,
                gates_total=10,
                costs_estimate=40,
                data_manager=self.ctx.system.data_manager
            )
            if sim_trade:
                sim_trade.instrument = instrument_info
                sim_trade.qty = fid_result.filled_qty
                sim_trade.entry_price = fid_result.fill_price
                sim_trade.slippage_pts = fid_result.slippage_pts
                sim_trade.spread_cost_pts = fid_result.spread_cost_pts
                sim_trade.total_friction_pts = fid_result.total_friction_pts
                sim_trade.latency_ms = fid_result.latency_ms
                sim_trade.moneyness_category = fid_result.moneyness_category
                sim_trade.execution_quality = fid_result.execution_quality
                sim_trade.execution_quality_score = fid_result.execution_quality_score

        if hasattr(self.ctx.telemetry, "perf_logger"):
            self.ctx.telemetry.perf_logger.mark_trade_executed(getattr(signal, "id", "unknown"), "EXECUTED" if sim_trade else "FAILED")

        logger.info(f"✅ [EXEC] SIMULATED TRADE EXECUTED | {signal.signal_type.value} @ ₹{fid_result.fill_price:,.1f}")

        return ExecutionResult(
            status="simulated",
            broker_order_id=f"SIM_{uuid.uuid4().hex[:8].upper()}",
            filled_price=fid_result.fill_price,
            fill_time=datetime.now(),
            latency_ms=fid_result.latency_ms,
            slippage=fid_result.slippage_pts,
            execution_quality=fid_result.execution_quality,
            errors=[],
            position_id=getattr(sim_trade, "trade_id", "") if sim_trade else ""
        )

    async def _execute_live_phase_b(self, signal: Signal, snapshot: MarketSnapshot) -> ExecutionResult:
        """Handles structural breakers and live broker entry for a confirmed order."""
        system = self.ctx.system
        t0 = time.perf_counter()
        
        # A. Broker Health Gate
        if hasattr(system, "broker_health") and not system.broker_health.is_healthy:
            reason = getattr(system.broker_health, "degraded_reason", "Broker Degraded")
            logger.critical(f"🚫 [EXEC] Broker health DEGRADED. Trade blocked. Reason: {reason}")
            if hasattr(system, "entry_engine"): system.entry_engine.cancel_pending(getattr(signal, "id", "unknown"))
            return self._build_failed_result(f"Broker Health: {reason}")

        premium = signal.metadata.get("premium_entry", snapshot.price)
            
        # Sizing
        pos_manager = getattr(system, "position_manager", None)
        size_info = {"allowed": False, "reason": "No PositionManager"}
        if pos_manager:
            size_info = pos_manager.calculate_position_size(signal, premium, snapshot.atr)
            
        if not size_info.get("allowed", False):
            logger.warning(f"🛡️ [EXEC] Sizing check blocked: {size_info.get('reason')}")
            if hasattr(system, "entry_engine"): system.entry_engine.cancel_pending(getattr(signal, "id", "unknown"))
            return self._build_failed_result(f"Sizing Blocked: {size_info.get('reason')}")
            
        qty = size_info["qty"]
        signal.position_size = qty
            
        # B. Structural Breaker Checks
        state_mgr = get_state_manager()
        breaker = StructuralBreaker(state_mgr)
        direction_str = signal.direction.value if hasattr(signal.direction, "value") else str(getattr(signal, "direction", "UNKNOWN"))
        
        if not breaker.check_duplicate_order(signal.symbol, direction_str):
            logger.error("🚫 [EXEC] Duplicate order detected by StructuralBreaker.")
            if hasattr(system, "trading_enabled"): system.trading_enabled = False
            if hasattr(system, "entry_engine"): system.entry_engine.cancel_pending(getattr(signal, "id", "unknown"))
            return self._build_failed_result("Duplicate Order Detected")
            
        current_price = snapshot.price
        is_valid, should_halt = breaker.check_telegram_execution_sync(
            signal.id, signal.created_at, time.time(), current_price, getattr(signal, "entry_price", current_price)
        )
        if not is_valid:
            if should_halt and hasattr(system, "trading_enabled"): system.trading_enabled = False
            if hasattr(system, "entry_engine"): system.entry_engine.cancel_pending(getattr(signal, "id", "unknown"))
            return self._build_failed_result("Telegram Sync/Price Drift Failed")
            
        sl_price = size_info.get("sl_price", 0.0)
        if not breaker.check_stop_loss_attached(signal.id, sl_price):
            logger.error("🚫 [EXEC] Stop Loss missing or invalid.")
            if hasattr(system, "trading_enabled"): system.trading_enabled = False
            if hasattr(system, "entry_engine"): system.entry_engine.cancel_pending(getattr(signal, "id", "unknown"))
            return self._build_failed_result("Invalid Stop Loss")

        # C. OMS Intent
        intent_id = f"INT_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:6].upper()}"
        if hasattr(system, "oms"):
            system.oms.create_intent(
                signal_id=getattr(signal, "id", "unknown"),
                intent_id=intent_id,
                symbol=signal.symbol,
                side="BUY" if direction_str.upper() == "BUY" else "SELL",
                qty=qty,
                requested_price=premium,
                stop_loss_price=sl_price
            )
            setattr(signal, "intent_id", intent_id)

        # D. Live Broker Execution
        pos = None
        if pos_manager:
            try:
                if hasattr(pos_manager, "broker") and pos_manager.broker and hasattr(pos_manager.broker, "set_context"):
                    instrument_info = getattr(signal, "metadata", {}).get("instrument", {})
                    pos_manager.broker.set_context(signal, snapshot, instrument_info)
                    
                t_exec = time.perf_counter()
                pos = await pos_manager.open_position_with_sl_guarantee(signal, size_info, premium)
                latency = int((time.perf_counter() - t_exec) * 1000)
            except Exception as e:
                logger.error(f"❌ [EXEC] Broker execution failed: {e}")
                latency = 0
                
        if hasattr(system, "entry_engine"):
            system.entry_engine.cancel_pending(getattr(signal, "id", "unknown"))
                
        if pos:
            if hasattr(system, "oms"):
                system.oms.update_order_state(
                    intent_id=intent_id,
                    new_state="ENTRY_FILLED",
                    event_type="BROKER_EXECUTION_SUCCESS",
                    avg_fill_price=pos.entry_price,
                    filled_qty=pos.qty,
                    payload={"position_id": pos.position_id}
                )
            logger.info(f"✅ [EXECUTE_SIGNAL] LIVE TRADE EXECUTED | {signal.signal_type.value} @ ₹{premium:,.1f}")
            if hasattr(system, "execution_failures"):
                system.execution_failures = 0
            if hasattr(self.ctx.telemetry, "perf_logger"):
                self.ctx.telemetry.perf_logger.mark_trade_executed(getattr(signal, "id", "unknown"), "EXECUTED")
            if hasattr(system, "broker_health"):
                system.broker_health.record_order_success()
                
            return ExecutionResult(
                status="filled",
                broker_order_id=getattr(pos, "broker_order_id", f"LIVE_{uuid.uuid4().hex[:8].upper()}"),
                filled_price=pos.entry_price,
                fill_time=datetime.now(),
                latency_ms=latency,
                slippage=round(pos.entry_price - premium, 2),
                execution_quality="UNKNOWN",
                errors=[],
                position_id=pos.position_id
            )
        else:
            if hasattr(system, "oms"):
                system.oms.update_order_state(
                    intent_id=intent_id,
                    new_state="FAILED",
                    event_type="BROKER_EXECUTION_FAILED",
                    payload={"reason": "open_position_with_sl_guarantee returned None"}
                )
            if hasattr(system, "execution_failures"):
                system.execution_failures += 1
            if hasattr(self.ctx.telemetry, "perf_logger"):
                self.ctx.telemetry.perf_logger.mark_trade_executed(getattr(signal, "id", "unknown"), "FAILED")
                
            return self._build_failed_result("Broker Execution Returned None")

    def _build_failed_result(self, reason: str) -> ExecutionResult:
        return ExecutionResult(
            status="failed",
            broker_order_id="",
            filled_price=0.0,
            fill_time=None,
            latency_ms=0.0,
            slippage=0.0,
            execution_quality="FAILED",
            errors=[reason]
        )

    async def apply_position_actions(self, actions: list, snapshot=None) -> None:
        """
        Executes position actions returned by the PositionPipeline.
        This is the only place that should talk to the broker for position management.
        """
        system = self.ctx.system  # To fallback if components aren't directly in ctx yet
        pos_manager = getattr(system, "position_manager", None)
        if not pos_manager:
            return

        if snapshot and hasattr(pos_manager, "broker") and pos_manager.broker and hasattr(pos_manager.broker, "set_context"):
            pos_manager.broker.set_context(None, snapshot, {})

        for action in actions:
            action_type = getattr(action, "action_type", "")
            pid = getattr(action, "position_id", "")
            
            try:
                if action_type == "FULL_EXIT":
                    close_res = await __import__('asyncio').to_thread(
                        pos_manager.close_position, 
                        pid, 
                        0.0,  # Price usually fetched inside or passed if available
                        getattr(action, "reason", "FULL_EXIT")
                    )
                    if close_res and hasattr(self.ctx, "telemetry") and self.ctx.telemetry:
                        try:
                            await self.ctx.telemetry.dispatch_trade_close(
                                trade_id=pid,
                                pnl=close_res.get("net_pnl", close_res.get("pnl", 0.0)),
                                outcome=close_res.get("reason", "FULL_EXIT"),
                                symbol=getattr(self.settings, "symbol", "NIFTY"),
                                hold_mins=close_res.get("hold_minutes", 0.0)
                            )
                        except Exception as alert_err:
                            logger.error(f"Live exit alert failed safely: {alert_err}")
                
                elif action_type == "PARTIAL_EXIT":
                    # Currently not implemented heavily in existing PositionManager, but we can call it if it exists
                    if hasattr(pos_manager, "partial_close_position") and self.settings.system_mode.mode != "SIMULATION":
                        await __import__('asyncio').to_thread(
                            pos_manager.partial_close_position,
                            pid,
                            getattr(action, "qty", 0),
                            0.0,
                            getattr(action, "reason", "PARTIAL_EXIT")
                        )
                
                elif action_type == "UPDATE_SL":
                    new_sl = getattr(action, "target_price", 0.0)
                    if self.settings.system_mode.mode != "SIMULATION":
                        await __import__('asyncio').to_thread(
                            pos_manager.update_stop_loss,
                            pid,
                            new_sl
                        )
                    else:
                        if hasattr(system, "simulation") and pid in system.simulation.open_trades:
                            trade = system.simulation.open_trades[pid]
                            trade.stop_loss = new_sl
                            logger.info(f"✅ [SIM] Updated SL for {pid} to {new_sl}")

            except Exception as e:
                logger.error(f"❌ [EXEC] Failed to apply position action {action_type} for {pid}: {e}")