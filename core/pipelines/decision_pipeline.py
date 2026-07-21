import time
import uuid
from datetime import datetime
from typing import Optional, Tuple, Dict, Any
import pandas as pd

from models import Signal, MarketSnapshot, SignalType
from core.decision_engine import DecisionEngine
from core.master_decision_engine import MasterDecisionEngine
from core.trade_filter import TradeFilter
from options_analyzer import OptionsAnalyzer
from utils.logger import get_logger

logger = get_logger("decision_pipeline")

class DecisionPipeline:
    """
    Orchestrates the signal generation and validation process:
    Snapshot -> Agents -> Decision Engine -> Trade Filter -> Master Decision -> Options Filter -> Signal
    """
    def __init__(self, ctx):
        self.ctx = ctx
        self.settings = ctx.settings
        
        self.decision_engine = DecisionEngine(self.settings)
        _sys = getattr(ctx, "system", None)
        self.master = MasterDecisionEngine(
            risk_manager=getattr(_sys, "risk_manager", None),
            position_manager=getattr(_sys, "position_manager", None),
            exit_engine=getattr(_sys, "exit_engine", None),
        )
        self.trade_filter = TradeFilter(self.settings)
        self.options_analyzer = OptionsAnalyzer(mode=self.settings.system_mode.mode)
        
        self.trade_sequence = 0
        self.no_trade_streak = 0
        
    def _fetch_options_sentiment(self, price_trend: str) -> Dict[str, Any]:
        """Wrapper for options analyzer fetch"""
        oi_cache = getattr(self.ctx.data_manager, "_oi_cache", {})
        if not oi_cache or not oi_cache.get("ce_oi") or not oi_cache.get("pe_oi"):
            return {"available": False, "sentiment": "unknown"}
            
        try:
            return self.options_analyzer.analyze_options_data(
                oi_cache,
                price_trend=price_trend
            )
        except Exception as e:
            logger.error(f"Options sentiment extraction failed: {e}")
            return {"available": False, "sentiment": "unknown"}

    def _log_canonical_truth(self, signal: Signal, cycle_count: int, auth: bool, reason: str, latencies: dict):
        if not self.ctx.telemetry:
            return
            
        cycle_lat = sum(latencies.values())
        summary = {
            "engine_cycle_id": cycle_count,
            "signal_id": getattr(signal, "id", f"sig_{cycle_count}"),
            "regime": signal.regime.value if hasattr(signal.regime, "value") else str(signal.regime),
            "regime_confidence": signal.metadata.get("regime_conf", 0.0) if hasattr(signal, "metadata") else 0.0,
            "environment_valid": True,
            "opportunity_valid": signal.signal_type != SignalType.NO_TRADE,
            "execution_authorized": auth,
            "rejection_reason": reason,
            "kill_reason": reason if not auth else None,
            "adaptive_threshold": round(getattr(self.decision_engine, "_last_adaptive_threshold", 0.0), 3),
            "agent_score": round(getattr(self.decision_engine, "_last_agent_score", 0.0), 3),
            "gap_multiplier": round(getattr(self.decision_engine, "_last_gap_multiplier", 1.0), 3),
            "final_score": round(getattr(self.decision_engine, "_last_raw_confidence", 0.0), 3),
            "raw_confidence": round(getattr(self.decision_engine, "_last_raw_confidence", 0.0), 3),
            "buy_score": round(getattr(signal, "buy_score", 0.0), 3),
            "sell_score": round(getattr(signal, "sell_score", 0.0), 3),
            "uncertainty_multiplier": round(getattr(signal, "uncertainty_multiplier", 1.0), 3),
            "decision_path": getattr(self.decision_engine, "_last_decision_path", []),
            "latency": {
                "cycle_ms": cycle_lat,
                "fetch_ms": latencies.get("fetch_ms", 0),
                "oi_ms": latencies.get("oi_ms", 0),
                "agents_ms": latencies.get("agents_ms", 0),
                "decision_ms": latencies.get("decision_ms", 0),
                "execution_ms": latencies.get("execution_ms", 0),
                "dashboard_ms": latencies.get("dashboard_ms", 0),
                "db_ms": latencies.get("db_ms", 0)
            }
        }
        logger.info(f"📊 EXECUTION TRUTH:\nimport json; print(json.dumps({summary}, indent=2))")
        if hasattr(self.ctx.telemetry, "metrics_logger"):
            self.ctx.telemetry.metrics_logger.log_cycle(summary)
            self.ctx.telemetry.metrics_logger.log_execution_truth(summary)

    def evaluate(self, df: pd.DataFrame, snapshot: MarketSnapshot, cycle_count: int, latencies: dict) -> Tuple[Optional[Signal], dict, float]:
        """
        Runs the decision flow.
        Returns (approved_signal, log_entry, execution_ms).
        If rejected, approved_signal is None.
        """
        t_decision = time.perf_counter()
        
        # 1. Generate Signal
        signal = self.decision_engine.process(df, snapshot)
        latencies["decision_ms"] = int((time.perf_counter() - t_decision) * 1000)
        
        self.trade_sequence += 1
        signal.id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{self.trade_sequence:03d}-{uuid.uuid4().hex[:4].upper()}"
        signal.status = "PENDING"

        if hasattr(self.ctx.telemetry, "observer") and signal.signal_type != SignalType.NO_TRADE:
            self.ctx.telemetry.observer.on_signal()

        # Handle NO_TRADE
        if signal.signal_type == SignalType.NO_TRADE:
            if self.ctx.simulation:
                self.ctx.simulation.record_signal(passed=False)
            if hasattr(self.ctx.system, "_update_dashboard"):
                self.ctx.system._update_dashboard(snapshot, signal)
            
            reason = signal.reasons[0] if signal.reasons else "dominant_score_below_floor"
            self._log_canonical_truth(signal, cycle_count, False, reason, latencies)
            
            self.no_trade_streak += 1
            if self.no_trade_streak in (100, 300, 500) or self.no_trade_streak % 500 == 0:
                logger.warning(
                    f"⏳ NO-TRADE STREAK: {self.no_trade_streak} consecutive cycles with no signal. "
                    f"Last reason: [{reason}]."
                )
            return None, {}, latencies["decision_ms"]

        self.no_trade_streak = 0

        # Simulation Guard
        if self.ctx.is_simulation and self.ctx.simulation:
            active_sim_trades = len(self.ctx.simulation.open_trades)
            max_pos = self.settings.position.max_open_positions
            if active_sim_trades >= max_pos:
                if cycle_count % 30 == 0:
                    logger.warning(f"🛡️ Simulation Guard: Max open positions reached ({active_sim_trades}/{max_pos})")
                self.ctx.simulation.record_signal(passed=False)
                signal.execution_status = "rejected"
                signal.metadata["rejection_status"] = "Blocked by Simulation Guard"
                signal.metadata["rejection_reason"] = "Max Open Positions"
                if hasattr(self.ctx.system, "_update_dashboard"):
                    self.ctx.system._update_dashboard(snapshot, signal)
                return None, {}, latencies["decision_ms"]

        # 2. Master Gate
        exit_engine = getattr(self.ctx.system, "exit_engine", None)
        pos_manager = getattr(self.ctx.system, "position_manager", None)
        
        master_result = self.master.approve(
            signal.signal_type.value,
            context={
                "signal_obj": signal,
                "weighted_score": signal.weighted_score,
                "gap_manager": getattr(self.decision_engine, "gap_penalty_manager", None),
                "discipline_context": {
                    "daily_target_hit": getattr(exit_engine, "daily_target_hit", False) if exit_engine else False,
                    "consecutive_losses": getattr(exit_engine, "consecutive_losses", 0) if exit_engine else 0,
                    "seconds_since_last_trade": 999,
                    "open_positions": len(pos_manager.open_positions) if pos_manager else 0,
                    "max_positions": self.settings.position.max_open_positions,
                }
            },
        )
        if not master_result.approved:
            if cycle_count % 30 == 0:
                logger.warning(f"🛡️ Master Gate blocked: {master_result.reason}")
            if self.ctx.simulation:
                self.ctx.simulation.record_signal(passed=False)
            signal.execution_status = "rejected"
            signal.metadata["rejection_status"] = "Blocked by Master Gate"
            signal.metadata["rejection_reason"] = master_result.reason
            if hasattr(self.ctx.system, "_update_dashboard"):
                self.ctx.system._update_dashboard(snapshot, signal)
            self._log_canonical_truth(signal, cycle_count, False, master_result.reason, latencies)
            return None, {}, latencies["decision_ms"]

        # 3. 10-Gate Filter
        outputs = {n: a.last_output for n, a in self.decision_engine.agents.items() if hasattr(a, 'last_output') and a.last_output is not None}
        
        pm_status = pos_manager.get_full_status() if pos_manager else {}
        if "today_trades" not in pm_status and exit_engine:
            pm_status["today_trades"] = getattr(exit_engine, "today_trades", 0)

        dm_oi_cache = getattr(self.ctx.data_manager, "_oi_cache", {}) if hasattr(self.ctx, "data_manager") else {}
        real_oi_available = dm_oi_cache.get("data_source") == "REAL"

        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "time": datetime.now().strftime("%H:%M"),
            "signal": signal.signal_type.value,
            "price_action_passed": True,
            "options_available": real_oi_available,
            "options_sentiment": "unknown",
            "options_score": 0,
            "max_pain_distance": -1,
            "filter_passed": False,
            "trade_executed": False,
            "spot_entry_price": None,
            "option_entry_price": None,
            "option_exit_price": None,
            "pnl": None,
            "would_have_taken_without_filter": True,
            "exit_reason": None,
            "risk_reason": None,
            "ai_reason": None,
            "trade_id": None,
            "raw_confidence": signal.metadata.get("raw_confidence", signal.confidence),
            "confidence_suppression": round(signal.metadata.get("raw_confidence", signal.confidence) - signal.confidence, 1),
            "suppression_reason": signal.metadata.get("suppression_reason", "UNKNOWN")
        }

        _regime_info = outputs["regime"].details.copy() if "regime" in outputs else {}
        _regime_info["regime"] = _regime_info.get("regime", "UNKNOWN")
        
        _structure_info = outputs["structure"].details.copy() if "structure" in outputs else {}
        if isinstance(_structure_info.get("structure"), dict):
            _structure_info["structure"] = _structure_info["structure"].get("type", "OK")
        else:
            _structure_info["structure"] = _structure_info.get("structure", "OK")
            
        _learning_info = {
            "confidence": outputs["learning"].confidence if "learning" in outputs else 50,
            "current_streak": getattr(self.decision_engine.memory, 'current_streak', 0) if hasattr(self.decision_engine, 'memory') else 0,
        }
        _decay_info = outputs["decay"].details.copy() if "decay" in outputs else {}
        
        _est_slippage = max(1.0, snapshot.atr * 0.02) if snapshot.atr > 0 else 2.0
        _est_brokerage = 40
        _total_costs = _est_brokerage + (_est_slippage * max(getattr(signal, 'position_size', 50), 50))
        _cost_info = {"total_costs": _total_costs, "break_even_points": _est_slippage + 1.0}
        
        filter_result = self.trade_filter.evaluate(
            signal=signal, snapshot=snapshot, agent_outputs=outputs,
            regime_info=_regime_info, structure_info=_structure_info,
            learning_info=_learning_info, decay_info=_decay_info,
            cost_info=_cost_info, position_manager_status=pm_status,
            confluence_score=(signal.confluence.confluence_ratio * 100 if signal.confluence else 0)
        )

        if self.ctx.simulation:
            self.ctx.simulation.record_signal(passed=filter_result.passed)

        if not filter_result.passed:
            rej_reason = filter_result.kill_reason or '10-Gate Filter'
            log_entry["risk_reason"] = f"Filter Rejected: {rej_reason}"
            if hasattr(self.ctx.telemetry, "perf_logger"):
                self.ctx.telemetry.perf_logger.log_signal(log_entry)
            self._log_canonical_truth(signal, cycle_count, False, f"Gate Filter: {rej_reason}", latencies)
            
            signal.execution_status = "rejected"
            signal.metadata["rejection_status"] = "Blocked by Signal Integrity" if "integrity" in rej_reason.lower() else "Blocked by 10-Gate Filter"
            signal.metadata["rejection_reason"] = rej_reason
            
            # Shadow Journal
            try:
                from core.snapshot import build_snapshot, persist_snapshot
                _gap_mgr = getattr(self.decision_engine, "gap_penalty_manager", None)
                _gap_status = _gap_mgr.get_status() if _gap_mgr else {}
                rej_snap = build_snapshot(
                    signal=signal, snapshot=snapshot, filter_result=filter_result,
                    agent_outputs=outputs, gate_results={}, final_decision="REJECTED",
                    rejection_reason=rej_reason, gap_context={
                        "gap_penalty_active": _gap_mgr.is_active() if _gap_mgr else False,
                        "gap_penalty_multiplier": _gap_status.get("multiplier", 1.0),
                        "gap_severity":  _gap_status.get("severity", "NONE"),
                        "gap_points":    _gap_status.get("gap_points", 0.0),
                    }
                )
                persist_snapshot(rej_snap)
            except Exception:
                pass

            if hasattr(self.ctx.system, "_update_dashboard"):
                self.ctx.system._update_dashboard(snapshot, signal)
            return None, {}, latencies["decision_ms"]

        # 4. Regime Policy
        regime_adapter = getattr(self.ctx.system, "regime_adapter", None)
        if regime_adapter:
            signal = regime_adapter.apply_policy(signal)
            if signal.execution_policy and signal.execution_policy.suppressed:
                logger.warning(f"🛡️ Regime Adapter blocked: {signal.execution_policy.reason}")
                log_entry["filter_passed"] = False
                log_entry["risk_reason"] = f"Regime Block: {signal.execution_policy.reason}"
                if hasattr(self.ctx.telemetry, "perf_logger"):
                    self.ctx.telemetry.perf_logger.log_signal(log_entry)
                if self.ctx.simulation:
                    self.ctx.simulation.record_signal(passed=False)
                
                signal.execution_status = "rejected"
                signal.metadata["rejection_status"] = "Blocked by Regime Adapter"
                signal.metadata["rejection_reason"] = signal.execution_policy.reason
                
                if hasattr(self.ctx.system, "_update_dashboard"):
                    self.ctx.system._update_dashboard(snapshot, signal)
                self._log_canonical_truth(signal, cycle_count, False, f"RegimeAdapter: {signal.execution_policy.reason}", latencies)
                return None, {}, latencies["decision_ms"]

        logger.info(f"🟢 Signal Engine CONFIRMED | Grade: {filter_result.grade} | Score: {filter_result.final_score:.0f} | {signal.signal_type.value}")

        # 5. Options Hard Filter
        try:
            ema20 = df['close'].ewm(span=20, adjust=False).mean().iloc[-1]
            price_trend = "up" if df['close'].iloc[-1] > ema20 else "down"
        except Exception:
            price_trend = "unknown"

        options = self._fetch_options_sentiment(price_trend)
        
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
            
            if options.get("max_pain_distance", 0) > 100:
                options_score += 1

        log_entry.update({
            "options_available": options.get("available", False),
            "options_sentiment": options.get("sentiment", "unknown"),
            "options_score": options_score,
            "max_pain_distance": options.get("max_pain_distance", -1),
        })

        if options.get("available", False):
            if options["max_pain_distance"] < OptionsAnalyzer.MAX_PAIN_MIN_DISTANCE:
                logger.warning(f"⚠️ [OPTIONS] Near max-pain ({options['max_pain_distance']:.0f} pts) — trade skipped")
                log_entry["filter_passed"] = False
                log_entry["risk_reason"] = "max_pain_distance < 50"
                if hasattr(self.ctx.telemetry, "perf_logger"):
                    self.ctx.telemetry.perf_logger.log_signal(log_entry)
                signal.execution_status = "rejected"
                signal.metadata["rejection_status"] = "Blocked by Options Filter"
                signal.metadata["rejection_reason"] = log_entry["risk_reason"]
                if self.ctx.simulation:
                    self.ctx.simulation.record_signal(passed=False)
                if hasattr(self.ctx.system, "_update_dashboard"):
                    self.ctx.system._update_dashboard(snapshot, signal)
                self._log_canonical_truth(signal, cycle_count, False, "Options: Near Max-Pain", latencies)
                return None, {}, latencies["decision_ms"]

            if options_score >= 2:
                log_entry["filter_passed"] = True
                logger.info(f"✅ [OPTIONS] Passed — Score: {options_score} | PCR: {options.get('pcr', 0):.3f} | MaxPain: {options['max_pain_distance']:.0f} pts away")
            else:
                logger.warning(f"❌ [OPTIONS] Score too low ({options_score}) — Signal: {signal.signal_type.value} | Sentiment: {options['sentiment']}")
                log_entry["filter_passed"] = False
                log_entry["risk_reason"] = f"Low options score ({options_score})"
                if hasattr(self.ctx.telemetry, "perf_logger"):
                    self.ctx.telemetry.perf_logger.log_signal(log_entry)
                signal.execution_status = "rejected"
                signal.metadata["rejection_status"] = "Blocked by Options Score"
                signal.metadata["rejection_reason"] = log_entry["risk_reason"]
                if self.ctx.simulation:
                    self.ctx.simulation.record_signal(passed=False)
                if hasattr(self.ctx.system, "_update_dashboard"):
                    self.ctx.system._update_dashboard(snapshot, signal)
                self._log_canonical_truth(signal, cycle_count, False, f"Options: Low score ({options_score})", latencies)
                return None, {}, latencies["decision_ms"]
        else:
            logger.debug("[OPTIONS] Data unavailable — skipping hard filter this cycle")
            log_entry["filter_passed"] = True

        log_entry["spot_entry_price"] = snapshot.price
        log_entry["trade_id"] = signal.id
        
        return signal, log_entry, latencies["decision_ms"]
