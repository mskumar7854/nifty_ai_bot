import time
import uuid
from datetime import datetime
from typing import Optional, Tuple, Dict, Any, List
import pandas as pd
from dataclasses import dataclass, field

from models import Signal, MarketSnapshot, SignalType

@dataclass
class GateResult:
    name: str
    passed: bool
    reason: Optional[str] = None

@dataclass
class DecisionPipelineResult:
    approved: bool
    signal: Optional[Signal]
    confidence: float
    gate_results: List[GateResult] = field(default_factory=list)
    rejection_reason: Optional[str] = None
    telemetry: Dict = field(default_factory=dict)
    latency_ms: float = 0.0
from core.decision_engine import DecisionEngine
from core.master_decision_engine import MasterDecisionEngine
from core.trade_filter import TradeFilter
from core.confidence_calibrator import ConfidenceCalibrator
from core.expected_value_engine import ExpectedValueEngine
from core.opportunity_ranker import OpportunityRanker
from core.trend_structure_tracker import TrendStructureTracker
from options_analyzer import OptionsAnalyzer
from utils.logger import get_logger
from core.raw_capture import RawDecisionLogger

logger = get_logger("decision_pipeline")

class DecisionPipeline:
    """
    Orchestrates the signal generation, calibration, gating, and validation process (v2.1):
    Snapshot -> Agents -> Calibration -> EV Engine -> Trade Filter -> Master Gate -> Options -> OMS
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
        self.calibrator = ConfidenceCalibrator()
        self.ev_engine = ExpectedValueEngine(min_ev_r=0.50, min_ev_score=60.0)
        self.opportunity_ranker = OpportunityRanker()
        self.trend_tracker = TrendStructureTracker(max_reentry_per_trend=2)
        # Link trend_tracker to trade_filter
        self.trade_filter.trend_tracker = self.trend_tracker
        
        # Instantiate AMDEngine (V1 Read-Only Shadow Mode)
        from core.amd_engine import AMDEngine
        
        tf_str = getattr(self.settings, "entry_timeframe", "5min")
        try:
            tf_mins = int(tf_str.replace("min", "").replace("m", ""))
        except:
            tf_mins = 5
            
        if hasattr(self.settings, "amd"):
            self.amd_engine = AMDEngine(self.settings.amd, symbol=getattr(self.settings, "symbol", "NIFTY"), timeframe_minutes=tf_mins)
        else:
            from config.settings import AMDConfig
            self.amd_engine = AMDEngine(AMDConfig(), symbol=getattr(self.settings, "symbol", "NIFTY"), timeframe_minutes=tf_mins)

        self.options_analyzer = OptionsAnalyzer(mode=self.settings.system_mode.mode)
        
        self.trade_sequence = 0
        self.no_trade_streak = 0
        
        self.raw_logger = RawDecisionLogger()

        # Shadow Variant Runner — post-commit observer for policy experiments
        # Failure here cannot affect V2 decisions (defensive initialization)
        try:
            from core.shadow_variant_runner import ShadowVariantRunner
            self.variant_runner = ShadowVariantRunner()
            logger.info(f"[VARIANT] Shadow variant runner initialized with {len(self.variant_runner.variants)} variants")
        except Exception as e:
            logger.error(f"[VARIANT] Failed to initialize shadow variant runner: {e}")
            self.variant_runner = None

        
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


    def _record_v2_snapshot(self, signal, snapshot, outputs=None, filter_result=None, final_decision="REJECTED", rejection_reason="", timeline=None):
        if signal.signal_type == SignalType.NO_TRADE:
            return
            
        try:
            from models.snapshot_v2 import DecisionSnapshotV2, SnapshotMetadata, AgentOpinion, GateResult, ReplayStatus
            from core.snapshot_v2 import persist_snapshot_v2
            import datetime
            import uuid
            
            mode_str = self.settings.system_mode.mode if hasattr(self.settings.system_mode, "mode") else str(self.settings.system_mode)
            
            # --- Lineage ---
            trade_id = None
            shadow_trade_id = None
            
            if final_decision == "EXECUTE":
                trade_id = signal.id
            
            # --- Shadow Candidate Policy ---
            GATE_SEVERITY = {
                "FAIL_CLOSED": "CRITICAL",
                "UNKNOWN_MARKET_REGIME": "CRITICAL",
                "Strike Policy Blocked": "CRITICAL",
                "DATA_INTEGRITY": "CRITICAL",
                
                "BAD_STRUCTURE_EXPANDING": "HARD",
                "REJECTED_REGIME_GRADE_B+_IN_SQUEEZE": "HARD",
                "STRUCTURAL_CONTRADICTION": "HARD",
                "UNACCEPTABLE_RISK": "HARD",
                
                "PEV_TOO_LOW": "SOFT",
                "REJECTED_LOW_EV": "SOFT",
                "LOW_EV": "SOFT",
                "MARGINAL_CONFIDENCE": "SOFT",
                
                "CHOP_ZONE_ACTIVE": "CONTEXTUAL",
                "REJECTED_SAME_STRUCTURAL_TREND": "CONTEXTUAL",
                "TIMING_RESTRICTION": "CONTEXTUAL"
            }
            
            initial_rejection_class = None
            if final_decision == "REJECTED":
                # Check eligibility: Must have structural levels (entry, stop, target)
                entry_p = getattr(signal, "entry_price", 0.0)
                sl_p = getattr(signal, "stop_loss", 0.0)
                tp_p = getattr(signal, "target_1", 0.0)
                
                has_levels = bool(entry_p and sl_p and tp_p)
                
                if has_levels:
                    shadow_trade_id = f"shadow-{signal.id}"
                    
                    # Determine highest severity
                    failed_gate_names = []
                    if filter_result and hasattr(filter_result, "gate_details"):
                        for g in filter_result.gate_details:
                            if not g.get("pass", False):
                                failed_gate_names.append(g.get("gate", "Unknown"))
                    if rejection_reason and not failed_gate_names:
                        failed_gate_names.append(rejection_reason)
                        
                    highest_sev_level = 0
                    severity_rank = {"CONTEXTUAL": 1, "SOFT": 2, "HARD": 3, "CRITICAL": 4}
                    
                    for gate_name in failed_gate_names:
                        gate_sev = "CONTEXTUAL" # Default
                        for key, sev in GATE_SEVERITY.items():
                            if key.lower() in gate_name.lower():
                                gate_sev = sev
                                break
                        rank = severity_rank.get(gate_sev, 1)
                        if rank > highest_sev_level:
                            highest_sev_level = rank
                            
                    if highest_sev_level >= 3: # HARD or CRITICAL
                        initial_rejection_class = "GENUINELY_BAD"
                    else:
                        initial_rejection_class = "MARGINAL"
            
            metadata = SnapshotMetadata(
                snapshot_id=signal.id,
                timestamp=datetime.datetime.now().isoformat(),
                symbol="NIFTY",
                expiry="UNKNOWN",
                mode=mode_str,
                parent_snapshot_id=None,
                trade_id=trade_id,
                shadow_trade_id=shadow_trade_id,
                experiment_id=None,
                replay_run_id=None
            )
            
            market_json = {
                "spot_price": getattr(snapshot, "price", 0.0),
                "vix": getattr(snapshot, "vix", None),
                "atr": getattr(snapshot, "atr", None),
            }
            
            agents_json = {}
            if outputs:
                for name, out in outputs.items():
                    if isinstance(out, dict):
                        agents_json[name] = AgentOpinion(signal=out.get("direction", "UNKNOWN"), confidence=out.get("confidence", 0.0), details=out)
                    elif hasattr(out, "direction"):
                        agents_json[name] = AgentOpinion(signal=out.direction, confidence=out.confidence, details=getattr(out, "details", {}))
            
            conf_json = {
                "raw": getattr(signal, "confidence", 0.0),
                "calibrated": signal.metadata.get("calibrated_pwin", getattr(signal, "confidence", 0.0))
            }
            
            confluence_json = {}
            if getattr(signal, "confluence", None):
                confluence_json = {
                    "ratio": signal.confluence.confluence_ratio,
                    "bullish": signal.confluence.bullish_agents,
                    "bearish": signal.confluence.bearish_agents
                }
                
            ev_json = getattr(signal, "ev_info", {})
            
            gate_results = {}
            if filter_result and hasattr(filter_result, "gate_details"):
                for g in filter_result.gate_details:
                    gate_results[g.get("gate", "Unknown")] = GateResult(
                        passed=g.get("pass", False),
                        actual=g.get("score", 0.0),
                        required=0.0,
                        detail=g.get("detail", "")
                    )
                    
            decision_json = {
                "action": final_decision,
                "reason": rejection_reason,
                "initial_rejection_class": initial_rejection_class
            }
            
            # --- Structural Trade Specification (Decision-Time) ---
            execution_json = {
                "entry_price": getattr(signal, "entry_price", 0.0),
                "stop_loss": getattr(signal, "stop_loss", 0.0),
                "target_1": getattr(signal, "target_1", 0.0),
                "direction": signal.direction.value if hasattr(signal, "direction") and hasattr(signal.direction, "value") else str(getattr(signal, "direction", "")),
                "risk_distance": abs(getattr(signal, "entry_price", 0.0) - getattr(signal, "stop_loss", 0.0)) if getattr(signal, "entry_price", 0) and getattr(signal, "stop_loss", 0) else 0.0
            }
            
            amd_json = {}
            if getattr(signal, "amd_state", None):
                try:
                    amd_json = {
                        "status": getattr(signal.amd_state, "amd_status", "UNKNOWN"),
                        "trend_context": getattr(signal.amd_state, "trend_context", "UNKNOWN"),
                        "structure_context": getattr(signal.amd_state, "structure_context", "UNKNOWN"),
                        "shadow_score": getattr(signal.amd_state, "shadow_score", 0.0),
                        "shadow_grade": getattr(signal.amd_state, "shadow_grade", "N/A")
                    }
                except Exception:
                    pass

            replay_status = ReplayStatus(
                deterministic=True,
                missing_fields=[],
                fallback_values=[]
            )
            
            snap_v2 = DecisionSnapshotV2(
                metadata=metadata,
                market=market_json,
                agents=agents_json,
                confidence=conf_json,
                confluence=confluence_json,
                expected_value=ev_json,
                structure={},
                risk={},
                amd=amd_json,
                gate_results=gate_results,
                decision=decision_json,
                execution=execution_json,
                event_timeline=timeline or {},
                replay=replay_status,
                outcome=None
            )
            persist_snapshot_v2(snap_v2)

            # ── POST-COMMIT: Shadow Variant Observer ──
            # V2 snapshot is now committed. The variant runner
            # replays gate results under alternative policies.
            # This is purely observational telemetry.
            if self.variant_runner:
                try:
                    self.variant_runner.evaluate_variants(
                        snapshot_id=signal.id,
                        gate_results={k: {"passed": v.passed, "actual": v.actual, "required": v.required, "detail": v.detail} for k, v in snap_v2.gate_results.items()},
                        v2_decision=final_decision,
                        v2_reason=rejection_reason,
                        timestamp=metadata.timestamp,
                    )
                except Exception as ve:
                    logger.error(f"[VARIANT] Observer failed (V2 unaffected): {ve}")
        except Exception as e:
            logger.error(f"Failed to record V2 snapshot: {e}")

    def evaluate(self, df: pd.DataFrame, snapshot: MarketSnapshot, cycle_count: int, latencies: dict) -> DecisionPipelineResult:
        """
        Runs the decision flow.
        Returns a structured DecisionPipelineResult containing all gate decisions.
        """
        import pytz
        from datetime import datetime
        
        # Ensure IST timezone for session boundary
        ist = pytz.timezone("Asia/Kolkata")
        
        if hasattr(snapshot, "timestamp") and snapshot.timestamp:
            try:
                # Convert snapshot timestamp to IST
                if getattr(snapshot.timestamp, "tzinfo", None) is None:
                    dt_ist = pytz.utc.localize(snapshot.timestamp).astimezone(ist)
                else:
                    dt_ist = snapshot.timestamp.astimezone(ist)
                current_date = dt_ist.date()
            except Exception:
                current_date = datetime.now(ist).date()
        else:
            current_date = datetime.now(ist).date()
            
        if not hasattr(self, "_current_date") or self._current_date != current_date:
            self.trend_tracker.reset_session()
            self._current_date = current_date
            
        t_decision = time.perf_counter()
        gate_results = []
        
        timeline = {"Market Snapshot Created": datetime.now().strftime("%H:%M:%S.%f")[:-3]}
        
        # 1. Generate Signal
        signal = self.decision_engine.process(df, snapshot)
        timeline["Agents Completed"] = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        # 1b. Evaluate AMD Shadow Mode
        try:
            if not df.empty:
                current_candle = df.iloc[-1]
                ts = df.index[-1] if hasattr(df.index, 'date') else datetime.now()
                atr = getattr(snapshot, "atr", current_candle.get("atr", 50.0))
                struct_facts = getattr(signal, "structure_info", {})
                
                # Check for Identity / Session Changes
                snap_sym = getattr(snapshot, "symbol", self.amd_engine.symbol)
                snap_tf = getattr(snapshot, "timeframe", self.amd_engine.timeframe_minutes)
                
                identity_changed = (snap_sym != self.amd_engine.symbol) or (snap_tf != self.amd_engine.timeframe_minutes)
                session_changed = self.amd_engine.state.timestamp and self.amd_engine.state.timestamp.date() != ts.date()
                
                if identity_changed or session_changed:
                    self.amd_engine.symbol = snap_sym
                    self.amd_engine.timeframe_minutes = snap_tf
                    self.amd_engine.reset()
                
                # Evaluate State
                amd_state = self.amd_engine.evaluate(
                    candle=current_candle,
                    atr=atr,
                    structural_facts=struct_facts,
                    timestamp=ts
                )
                signal.amd_state = amd_state
                timeline["AMD Evaluated"] = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        except Exception as e:
            logger.error(f"AMD Engine failed: {e}")
            from models.amd_state import AMDState
            err_state = AMDState()
            err_state.amd_status = "ERROR"
            err_state.amd_error_type = type(e).__name__
            signal.amd_state = err_state

        latencies["decision_ms"] = int((time.perf_counter() - t_decision) * 1000)
        
        self.trade_sequence += 1
        signal.id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{self.trade_sequence:03d}-{uuid.uuid4().hex[:4].upper()}"
        signal.status = "PENDING"

        # ── v2.1 Calibration & EV Engine ──
        if signal.signal_type != SignalType.NO_TRADE:
            regime_name = signal.regime.value if hasattr(signal.regime, "value") else str(signal.regime)
            calibrated_pwin, calib_telemetry = self.calibrator.calibrate(signal.confidence, regime_name)
            timeline["Confidence Calibrated"] = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            # Add telemetry to signal metadata
            if not hasattr(signal, "metadata") or signal.metadata is None:
                signal.metadata = {}
            signal.metadata["calibration_telemetry"] = calib_telemetry
            rr = getattr(signal, "risk_reward_ratio", 2.0)
            spread_pct = getattr(snapshot, "spread_pct", 0.8)
            
            ev_result = self.ev_engine.evaluate(
                calibrated_pwin=calibrated_pwin,
                risk_reward_ratio=rr,
                spread_pct=spread_pct
            )
            timeline["EV Calculated"] = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            signal.ev_info = ev_result
            signal.metadata["calibrated_pwin"] = calibrated_pwin
            signal.metadata["ev_r"] = ev_result["ev_r"]
            signal.metadata["ev_score"] = ev_result["normalized_score"]

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
            return DecisionPipelineResult(
                approved=False, signal=None, confidence=0.0, 
                gate_results=gate_results, rejection_reason=reason,
                telemetry={}, latency_ms=latencies.get("decision_ms", 0.0)
            )

        self.no_trade_streak = 0

        # Simulation Guard
        if self.ctx.is_simulation and self.ctx.simulation:
            active_sim_trades = len(self.ctx.simulation.open_trades)
            max_pos = self.settings.position.max_open_positions
            if active_sim_trades >= max_pos:
                gate_results.append(GateResult("Simulation Guard", False, "Max Open Positions"))
                if cycle_count % 30 == 0:
                    logger.warning(f"🛡️ Simulation Guard: Max open positions reached ({active_sim_trades}/{max_pos})")
                self.ctx.simulation.record_signal(passed=False)
                signal.execution_status = "rejected"
                signal.metadata["rejection_status"] = "Blocked by Simulation Guard"
                signal.metadata["rejection_reason"] = "Max Open Positions"
                signal.metadata["rejection_stage"] = "Simulation Guard"
                self._record_v2_snapshot(signal, snapshot, None, None, "REJECTED", "Max Open Positions", timeline)
                if hasattr(self.ctx.system, "_update_dashboard"):
                    self.ctx.system._update_dashboard(snapshot, signal)
                return DecisionPipelineResult(
                    approved=False, signal=signal, confidence=signal.confidence,
                    gate_results=gate_results, rejection_reason="Max Open Positions",
                    telemetry={}, latency_ms=latencies.get("decision_ms", 0.0)
                )
            else:
                gate_results.append(GateResult("Simulation Guard", True))

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
        timeline["Master Gate Evaluated"] = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        gate_results.append(GateResult("Master Gate", master_result.approved, getattr(master_result, "reason", None) if not master_result.approved else None))
        
        if not master_result.approved:
            if cycle_count % 30 == 0:
                logger.warning(f"🛡️ Master Gate blocked: {master_result.reason}")
            if self.ctx.simulation:
                self.ctx.simulation.record_signal(passed=False)
            signal.execution_status = "rejected"
            signal.metadata["rejection_status"] = "Blocked by Master Gate"
            signal.metadata["rejection_reason"] = master_result.reason
            signal.metadata["rejection_stage"] = "Master Gate"
            if hasattr(self.ctx.system, "_update_dashboard"):
                self.ctx.system._update_dashboard(snapshot, signal)
            self._record_v2_snapshot(signal, snapshot, None, None, "REJECTED", master_result.reason, timeline)
            self._log_canonical_truth(signal, cycle_count, False, master_result.reason, latencies)
            return DecisionPipelineResult(
                approved=False, signal=signal, confidence=signal.confidence,
                gate_results=gate_results, rejection_reason=master_result.reason,
                telemetry={}, latency_ms=latencies.get("decision_ms", 0.0)
            )

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
        
        signal.metadata["structural_state"] = _structure_info
            
        _learning_info = {
            "confidence": outputs["learning"].confidence if "learning" in outputs else 50,
            "current_streak": getattr(self.decision_engine.memory, 'current_streak', 0) if hasattr(self.decision_engine, 'memory') else 0,
        }
        _decay_info = outputs["decay"].details.copy() if "decay" in outputs else {}
        
        _est_slippage = max(1.0, snapshot.atr * 0.02) if snapshot.atr > 0 else 2.0
        _est_brokerage = 40
        _total_costs = _est_brokerage + (_est_slippage * max(getattr(signal, 'position_size', 50), 50))
        _cost_info = {"total_costs": _total_costs, "break_even_points": _est_slippage + 1.0}
        
        # --- RAW DECISION CAPTURE LAYER ---
        try:
            raw_record = {
                "schema_version": 1,
                "correlation_id": signal.id,
                "signal_id": signal.id,
                "timestamp": snapshot.timestamp.isoformat() if hasattr(snapshot.timestamp, 'isoformat') else str(snapshot.timestamp),
                "market_context": {
                    "spot": getattr(snapshot, "spot", 0.0),
                    "atr": getattr(snapshot, "atr", 0.0),
                    "vwap": getattr(snapshot, "vwap", 0.0),
                    "regime": signal.regime.value if hasattr(signal.regime, "value") else str(signal.regime),
                    "vix": getattr(snapshot, "vix", 0.0)
                },
                "agent_payloads": {name: getattr(a, 'last_output', None).__dict__ if hasattr(getattr(a, 'last_output', None), '__dict__') else str(getattr(a, 'last_output', None)) for name, a in self.decision_engine.agents.items()},
                "option_context": {}, # Future options analyzer integration
                "derived_pre_gate": {
                    "confidence": signal.confidence,
                    "grade": "N/A", # Computed by filter but we capture input state
                    "pev": "N/A", 
                    "ev": getattr(signal, "ev_info", {}).get("ev_r", "N/A"),
                    "agreement": getattr(signal.confluence, "confluence_ratio", 0.0) if getattr(signal, "confluence", None) else 0.0
                },
                "structural_state": _structure_info,
                "provenance": {
                    "engine_version": "v5.0.2-REF",
                    "git_commit": getattr(self.ctx, "git_commit", "unknown"),
                    "config_hash": "N/A",
                    "captured_at": datetime.now().isoformat(),
                    "source": "decision_pipeline"
                }
            }
            self.raw_logger.capture(raw_record)
        except Exception as e:
            logger.error(f"Failed to capture raw record: {e}")
            # Ensure failure never alters trading decisions
            pass
        # ----------------------------------
        
        filter_result = self.trade_filter.evaluate(
            signal=signal, snapshot=snapshot, agent_outputs=outputs,
            regime_info=_regime_info, structure_info=_structure_info,
            learning_info=_learning_info, decay_info=_decay_info,
            cost_info=_cost_info, position_manager_status=pm_status,
            confluence_score=(signal.confluence.confluence_ratio * 100 if signal.confluence else 0)
        )
        timeline["TradeFilter Decision"] = datetime.now().strftime("%H:%M:%S.%f")[:-3]

        rej_reason = filter_result.kill_reason or '10-Gate Filter' if not filter_result.passed else None
        gate_results.append(GateResult("TradeFilter", filter_result.passed, rej_reason))

        if self.ctx.simulation:
            self.ctx.simulation.record_signal(passed=filter_result.passed)

        if not filter_result.passed:
            log_entry["risk_reason"] = f"Filter Rejected: {rej_reason}"
            if hasattr(self.ctx.telemetry, "perf_logger"):
                self.ctx.telemetry.perf_logger.log_signal(log_entry)
            self._log_canonical_truth(signal, cycle_count, False, f"Gate Filter: {rej_reason}", latencies)
            
            signal.execution_status = "rejected"
            signal.metadata["rejection_status"] = "Blocked by Signal Integrity" if "integrity" in rej_reason.lower() else "Blocked by 10-Gate Filter"
            signal.metadata["rejection_reason"] = rej_reason
            signal.metadata["rejection_stage"] = "10-Gate Filter"
            
            self._record_v2_snapshot(signal, snapshot, outputs, filter_result, "REJECTED", rej_reason, timeline)

            if hasattr(self.ctx.system, "_update_dashboard"):
                self.ctx.system._update_dashboard(snapshot, signal)
            return DecisionPipelineResult(
                approved=False, signal=signal, confidence=signal.confidence,
                gate_results=gate_results, rejection_reason=rej_reason,
                telemetry={}, latency_ms=latencies.get("decision_ms", 0.0)
            )

        # 4. Regime Policy
        regime_adapter = getattr(self.ctx.system, "regime_adapter", None)
        if regime_adapter:
            signal = regime_adapter.apply_policy(signal)
            passed_regime = not (signal.execution_policy and signal.execution_policy.suppressed)
            gate_results.append(GateResult("Regime Policy", passed_regime, getattr(signal.execution_policy, "reason", None) if not passed_regime else None))
            
            if not passed_regime:
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
                signal.metadata["rejection_stage"] = "Regime Adapter"
                
                if hasattr(self.ctx.system, "_update_dashboard"):
                    self.ctx.system._update_dashboard(snapshot, signal)
                self._log_canonical_truth(signal, cycle_count, False, f"RegimeAdapter: {signal.execution_policy.reason}", latencies)
                return DecisionPipelineResult(
                    approved=False, signal=signal, confidence=signal.confidence,
                    gate_results=gate_results, rejection_reason=signal.execution_policy.reason,
                    telemetry={}, latency_ms=latencies.get("decision_ms", 0.0)
                )

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
                gate_results.append(GateResult("OptionsAnalyzer", False, "Near max-pain"))
                logger.warning(f"⚠️ [OPTIONS] Near max-pain ({options['max_pain_distance']:.0f} pts) — trade skipped")
                log_entry["filter_passed"] = False
                log_entry["risk_reason"] = "max_pain_distance < 50"
                if hasattr(self.ctx.telemetry, "perf_logger"):
                    self.ctx.telemetry.perf_logger.log_signal(log_entry)
                signal.execution_status = "rejected"
                signal.metadata["rejection_status"] = "Blocked by Options Filter"
                signal.metadata["rejection_reason"] = log_entry["risk_reason"]
                signal.metadata["rejection_stage"] = "Options Hard Filter"
                if self.ctx.simulation:
                    self.ctx.simulation.record_signal(passed=False)
                if hasattr(self.ctx.system, "_update_dashboard"):
                    self.ctx.system._update_dashboard(snapshot, signal)
                self._log_canonical_truth(signal, cycle_count, False, "Options: Near Max-Pain", latencies)
                return DecisionPipelineResult(
                    approved=False, signal=signal, confidence=signal.confidence,
                    gate_results=gate_results, rejection_reason="Near max-pain",
                    telemetry={}, latency_ms=latencies.get("decision_ms", 0.0)
                )

            if options_score >= 2:
                gate_results.append(GateResult("OptionsAnalyzer", True))
                log_entry["filter_passed"] = True
                logger.info(f"✅ [OPTIONS] Passed — Score: {options_score} | PCR: {options.get('pcr', 0):.3f} | MaxPain: {options['max_pain_distance']:.0f} pts away")
            else:
                gate_results.append(GateResult("OptionsAnalyzer", False, f"Low options score ({options_score})"))
                logger.warning(f"❌ [OPTIONS] Score too low ({options_score}) — Signal: {signal.signal_type.value} | Sentiment: {options['sentiment']}")
                log_entry["filter_passed"] = False
                log_entry["risk_reason"] = f"Low options score ({options_score})"
                if hasattr(self.ctx.telemetry, "perf_logger"):
                    self.ctx.telemetry.perf_logger.log_signal(log_entry)
                signal.execution_status = "rejected"
                signal.metadata["rejection_status"] = "Blocked by Options Score"
                signal.metadata["rejection_reason"] = log_entry["risk_reason"]
                signal.metadata["rejection_stage"] = "Options Hard Filter"
                if self.ctx.simulation:
                    self.ctx.simulation.record_signal(passed=False)
                if hasattr(self.ctx.system, "_update_dashboard"):
                    self.ctx.system._update_dashboard(snapshot, signal)
                self._log_canonical_truth(signal, cycle_count, False, f"Options: Low score ({options_score})", latencies)
                return DecisionPipelineResult(
                    approved=False, signal=signal, confidence=signal.confidence,
                    gate_results=gate_results, rejection_reason=f"Low options score ({options_score})",
                    telemetry={}, latency_ms=latencies.get("decision_ms", 0.0)
                )
        else:
            logger.debug("[OPTIONS] Data unavailable — skipping hard filter this cycle")
            log_entry["filter_passed"] = True

        log_entry["spot_entry_price"] = snapshot.price
        log_entry["trade_id"] = signal.id

        # Record trade entry in TrendStructureTracker (v2.1)
        sig_dir_str = signal.direction.value if hasattr(signal.direction, "value") else str(signal.direction)
        
        pending_reset_event = None
        if filter_result.telemetry and "Structure Reset" in filter_result.telemetry:
            pending_reset_event = filter_result.telemetry["Structure Reset"].get("pending_reset_event")
            
        exec_ts = snapshot.timestamp.timestamp() if hasattr(snapshot.timestamp, 'timestamp') else time.time()
        self.trend_tracker.record_trade_execution(
            sig_dir_str, 
            snapshot.price, 
            timestamp=exec_ts, 
            reset_event=pending_reset_event
        )
        
        timeline["OMS Intent Generated"] = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self._record_v2_snapshot(signal, snapshot, outputs, filter_result, "EXECUTE", "Passed all gates", timeline)
        
        return DecisionPipelineResult(
            approved=True, signal=signal, confidence=signal.confidence,
            gate_results=gate_results, telemetry=log_entry,
            latency_ms=latencies.get("decision_ms", 0.0)
        )

