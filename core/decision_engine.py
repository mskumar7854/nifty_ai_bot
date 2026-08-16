"""
============================================
🧠 DECISION ENGINE v3 (CLAUDE-STYLE ROUTING)
Why: Transforms the system from a linear 
     pipeline to a dynamic, phase-based 
     agentic loop. Saves compute, reduces 
     latency, and stops bad trades early.

── v3.5 PENALTY CASCADE FIX ─────────────────
Previous architecture stacked 3 independent
penalties on the same underlying uncertainty:
  gap_penalty × regime_lerp × PEV degradation

This created hidden double/triple counting.
Fix: merge gap + regime into a SINGLE unified
uncertainty multiplier before scoring. PEV
(execution gate) is not further penalised.

── v3.6 EXECUTION CALIBRATION ───────────────
Added Market Participation Mode (MPM) layer:
  DEFENSIVE   — original strict logic (loss cluster / gap shock)
  BALANCED    — normal operations
  AGGRESSIVE  — directional trend expansion confirmed

Key calibration changes:
  A. OI Fallback: unreliable OI redistributes weight; does NOT degrade strategy
  B. Adaptive early-kill threshold: 0.18/0.20/0.25 based on MPM + trend strength
  C. Trend Continuation Mode: one-sided market allows directional pass
  D. Dynamic confidence gate: relaxes when momentum+structure align (not just gap decay)

⚠️ AI WARNING: core/decision_engine_v3.py
Unified uncertainty factor MUST remain min(gap, regime) — NOT multiplied.
Sigmoid normalization MUST run BEFORE grading.
ThresholdTuner is ADVISORY — never blocks execution directly.
MPM is READ-ONLY metadata — it adjusts thresholds, never halts execution.
============================================
"""

import os
import math
from typing import List, Optional, Dict
from datetime import datetime
from enum import Enum
import time
from time import perf_counter
import uuid

from analytics.analytics_bus import analytics_bus


class MarketParticipationMode(Enum):
    """
    v3.6 Execution Calibration — Three-state execution mode.

    DEFENSIVE:  OI degraded, loss cluster, gap shock, or regime uncertain.
                Use original strict thresholds.
    BALANCED:   Normal market conditions. Moderate filtering.
    AGGRESSIVE: Trend regime confirmed + multi-agent alignment.
                Lower thresholds to capture directional continuation.

    Mode is computed at the start of Phase 5 and used ONLY to adjust
    the early-kill and confidence thresholds — it never blocks trades.
    """
    DEFENSIVE  = "DEFENSIVE"
    BALANCED   = "BALANCED"
    AGGRESSIVE = "AGGRESSIVE"

from models import (
    Signal, SignalType, Direction, Strength, MarketSnapshot, AgentOutput
)
from agents import (
    MarketAgent, MomentumAgent, OIAgent, TrapAgent, SentimentAgent, RiskAgent,
    TimeSessionAgent, MultiTimeframeAgent, PriceActionAgent, VolatilityAgent,
    CorrelationAgent, ExpiryAgent, OrderFlowAgent, LevelAgent,
    DeltaGammaAgent, InstitutionalAgent, GapAgent, ConsolidationAgent,
    LearningAgent, ExpiryDayAgent, DecayAgent, RegimeAgent, StructureAgent
)
from core.confluence_scorer import ConfluenceScorer
from core.signal_quality import SignalQualityGrader
from core.memory_manager import MemoryManager
from core.gap_penalty_manager import GapPenaltyManager
from utils.logger import AgentLogger
from config.settings import Settings
from models import MarketRegime, RegimeContext
from models.decision_trace import DecisionTrace, TraceStage, StageAction
from config.signal_weights import AGENT_WEIGHTS, MIN_CONFIDENCE, MIN_DIRECTION_GAP
from core.threshold_tuner import ThresholdTuner
from core.system_fingerprint import SystemFingerprint
from core.confidence_calibrator import ConfidenceCalibrator


def _sigmoid_normalize(x: float, center: float = 0.55, sharpness: float = 8.0) -> float:
    """
    Sigmoid normalization restores distribution spread after multiplicative
    penalties compress all scores into a narrow 0.48–0.62 band.

    With center=0.55 and sharpness=8:
      0.40 → ~0.18   (correctly rejected)
      0.50 → ~0.38
      0.55 → 0.50    (pivot)
      0.62 → ~0.68   (now distinguishable from 0.58)
      0.72 → ~0.87   (strong setup clearly separated)

    This does NOT change the ordering — it only widens the gaps
    between scores so that elite setups are clearly distinct.
    """
    return round(1.0 / (1.0 + math.exp(-sharpness * (x - center))), 4)

# ── Agent Reliability Multipliers ──
# Based on empirical observation of which agents consistently carry expectancy.
# Higher = more weight when this agent fires. Range: 0.5 – 1.5
# Do NOT edit until you have 50+ trade sample. Use log analysis to update.
#
# v3.7 ANTI-CONCENTRATION FIX:
# structure was 1.30 × base_weight(0.15) = 0.195 effective weight = 22% of total budget.
# That made a single counter-directional structure signal erase momentum + price_action.
# Reduced structure to 1.05 and multi_timeframe to 1.15 to balance agent influence.
# compute_weighted_score also applies a per-agent concentration cap (MAX_SINGLE_WEIGHT_SHARE).
AGENT_RELIABILITY = {
    "multi_timeframe": 1.15,   # Was 1.40 — reduced to prevent single-agent dominance
    "structure":       1.05,   # Was 1.30 — reduced; was 22% of weight budget alone
    "price_action":    1.20,   # Slightly raised — direct price evidence, less noisy
    "momentum":        1.10,   # MODERATE-HIGH
    "regime":          1.10,   # STABLE base layer
    "level":           1.05,   # Levels add precision
    "trap":            0.80,   # NOISY — often contradictory
    "oi":              0.75,   # UNSTABLE — simulated in non-live mode
    "institutional":   0.70,   # MOSTLY INACTIVE in current env
    "order_flow":      0.70,   # MOSTLY INACTIVE in current env
    "sentiment":       0.65,   # LOW signal-to-noise
    "learning":        1.00,   # Neutral until we have enough trades
    "risk":            1.00,
    "decay":           0.90,
    "expiry_day":      0.90,
    "market":          0.80,
    "volatility":      0.90,
}

# ── OI Fallback Redistribution ──
# When OI data is unreliable, its weight budget is redistributed to the
# next-most reliable agents (momentum + structure + price_action).
# This keeps the total weight budget constant while reducing OI's noisy
# contribution instead of degrading the whole strategy.
#
# OI normal weight = 0.08 (from signal_weights.py)
# Redistribution split: momentum=40%, structure=35%, price_action=25%
_OI_FALLBACK_RECIPIENTS = {
    "momentum":     0.40,
    "structure":    0.35,
    "price_action": 0.25,
}

class DecisionEngine:
    def __init__(self, settings: Settings, experiment_config=None):
        self.settings = settings
        self.logger = AgentLogger("decision_v3")
        self.scorer = ConfluenceScorer(settings)
        self.quality_grader = SignalQualityGrader(settings)
        self.calibrator = ConfidenceCalibrator()
        
        # ── Experiment Config for Research Platform ──
        if experiment_config is None:
            from core.experiment_config import ExperimentConfig
            self.experiment_config = ExperimentConfig() # Default features
        else:
            self.experiment_config = experiment_config

        self.spike_freeze_until = 0.0
        self.session_started_date = None
        self.fingerprint = SystemFingerprint()
        
        # ── Market Acceptance Validator (MAV) ──
        from core.market_acceptance_validator import MarketAcceptanceValidator
        self.mav = MarketAcceptanceValidator()
        
        # ── State Tracking for Telemetry ──
        self.last_signal = None
        self.signal_count = 0
        self.signal_history = []
        
        # ── OI Analytics (Shadow Mode) ──
        from core.oi_analytics_logger import OIAnalyticsLogger
        from agents.oi_agent import OIAgent
        self.oi_logger = OIAnalyticsLogger()
        self._shadow_oi = OIAgent(settings)

        # ── S/R Engine (Shadow Mode — Gate 1) ──
        # Runs every cycle but does NOT influence trade decisions.
        # Logs zones, interactions, and forward returns to CSV.
        # Promotion to active scoring requires Gate 2 validation.
        from core.sr_engine import SREngine
        from core.sr_analytics_logger import SRAnalyticsLogger
        self.sr_engine = SREngine(settings)
        self.sr_logger = SRAnalyticsLogger()

        # ── Mode detection — used for simulation-safe threshold relaxation ──
        self._is_simulation = os.getenv("SYSTEM_MODE", "SIMULATION").upper() == "SIMULATION"

        # ── v3.6: Market Participation Mode tracker ──
        self._current_mpm: MarketParticipationMode = MarketParticipationMode.BALANCED
        self._mpm_reason: str = "initializing"

        # ── v3.6: OI reliability tracker ──
        # Maintained here (independent of LogObserver) so the engine can
        # react within the same cycle rather than waiting for log emission.
        self._oi_real_count: int = 0
        self._oi_total_count: int = 0

        # ── 📓 Trade Opportunity Analytics (Shadow Journal) ──
        # Every blocked cycle is recorded here so we can audit which filters
        # suppress real alpha vs. protecting against noise.
        # In-memory rolling cache + persistent JSONL on disk.
        self.opportunity_journal: list = []
        self._opportunity_journal_limit = 500  # rolling in-memory cap
        self._opp_journal_path = os.path.join("data", "opportunity_journal.jsonl")
        os.makedirs("data", exist_ok=True)  # ensure data/ exists

        # ── ⏳ Pending Outcome Queue ──
        # Entries queued here get their future_move_5m/15m/30m filled
        # on subsequent cycles once enough time has elapsed.
        # Structure: [{"id", "block_ts", "block_price", "direction", "entry"}]
        self._pending_outcomes: list = []

        # ── Priority 4: ATR-Normalised Gap Penalty (replaces static bool) ──
        # session_gap_detected is kept for metadata compatibility only.
        self.session_gap_detected = False
        self.gap_penalty_mgr = GapPenaltyManager()

        # ── Self-learning threshold tuner ──
        self.tuner = ThresholdTuner(
            initial_gap=MIN_DIRECTION_GAP,
            initial_conf=MIN_CONFIDENCE
        )

        # 1. Define Agent Registry (all possible agents)
        AGENT_REGISTRY = {
            "market": MarketAgent,
            "momentum": MomentumAgent,
            "oi": OIAgent,
            "trap": TrapAgent,
            "sentiment": SentimentAgent,
            "risk": RiskAgent,
            "time_session": TimeSessionAgent,
            "multi_timeframe": MultiTimeframeAgent,
            "price_action": PriceActionAgent,
            "volatility": VolatilityAgent,
            "correlation": CorrelationAgent,
            "expiry": ExpiryAgent,
            "order_flow": OrderFlowAgent,
            "level": LevelAgent,
            "delta_gamma": DeltaGammaAgent,
            "institutional": InstitutionalAgent,
            "gap": GapAgent,
            "consolidation": ConsolidationAgent,
            "learning": LearningAgent,
            "expiry_day": ExpiryDayAgent,
            "decay": DecayAgent,
            "regime": RegimeAgent,
            "structure": StructureAgent,
        }

        # 2. Only instantiate ACTIVE agents (Graphify-curated allowlist)
        #    Unused agents waste compute and add noise — skip them entirely.
        active = set(getattr(settings.pipeline, "active_agents", AGENT_REGISTRY.keys()))
        self.agents = {}
        skipped = []
        for name, agent_class in AGENT_REGISTRY.items():
            if name in active:
                self.agents[name] = agent_class(settings)
            else:
                skipped.append(name)

        self.logger.info(
            f"🤖 Agents loaded: {len(self.agents)} active, "
            f"{len(skipped)} skipped "
            f"({', '.join(skipped) if skipped else 'none'})"
        )

        # ── P1-B: Agent Count Assertion ──
        # Dynamically derive the expected count from settings.pipeline.active_agents
        # so we don't need a hardcoded magic number that breaks when agents are
        # added/removed during Phase 1 edge validation or future expansions.
        EXPECTED_ACTIVE_AGENT_COUNT = len(getattr(settings.pipeline, "active_agents", []))
        registered = len(self.agents)
        if registered != EXPECTED_ACTIVE_AGENT_COUNT:
            missing = set(getattr(settings.pipeline, "active_agents", [])) - set(self.agents.keys())
            extra = set(self.agents.keys()) - set(getattr(settings.pipeline, "active_agents", []))
            raise AssertionError(
                f"🚨 AGENT COUNT MISMATCH: {registered} loaded, "
                f"{EXPECTED_ACTIVE_AGENT_COUNT} expected from settings.pipeline.active_agents. "
                f"Missing: {sorted(missing) if missing else 'none'} | "
                f"Extra: {sorted(extra) if extra else 'none'} | "
                f"Active: {sorted(self.agents.keys())}"
            )

        # ── P1-B+: Startup Topology Validation (FAIL-FAST) ──
        # Trading systems should prefer "fail closed" over "run partially broken".
        # Topology mismatches mean agents will be SILENTLY SKIPPED during execution,
        # which corrupts confluence math and routing integrity.
        all_phase_agents = set(
            settings.pipeline.phase_1_gatekeepers +
            settings.pipeline.phase_2_core +
            settings.pipeline.phase_3_confirmation +
            settings.pipeline.phase_4_risk
        )

        # HARD FAIL: Phase lists reference agents that don't exist
        orphaned_phase_refs = all_phase_agents - set(self.agents.keys())
        if orphaned_phase_refs:
            raise RuntimeError(
                f"🚨 TOPOLOGY FATAL: Phase lists reference agents not in active_agents: "
                f"{sorted(orphaned_phase_refs)}. These would be SILENTLY SKIPPED. "
                f"Fix settings.py phase lists or active_agents before starting."
            )

        # HARD FAIL: Duplicate agent names across phases (routing ambiguity)
        all_phase_list = (
            settings.pipeline.phase_1_gatekeepers +
            settings.pipeline.phase_2_core +
            settings.pipeline.phase_3_confirmation +
            settings.pipeline.phase_4_risk
        )
        seen = set()
        duplicates = set()
        for name in all_phase_list:
            if name in seen:
                duplicates.add(name)
            seen.add(name)
        if duplicates:
            raise RuntimeError(
                f"🚨 TOPOLOGY FATAL: Duplicate agent names across phase lists: "
                f"{sorted(duplicates)}. Each agent must appear in exactly one phase."
            )

        # HARD FAIL: Agents loaded but not routed to any phase (topology gap)
        # Previously a warning — but unrouted agents corrupt confluence math
        # because they consume weight budget without contributing signal.
        unrouted_agents = set(self.agents.keys()) - all_phase_agents
        if unrouted_agents:
            raise RuntimeError(
                f"🚨 TOPOLOGY FATAL: Agents loaded but not in any phase list: "
                f"{sorted(unrouted_agents)}. Every active agent must be routed to "
                f"exactly one phase. Either add them to a phase list or remove "
                f"them from active_agents in settings.py."
            )

        routed_count = len(all_phase_agents & set(self.agents.keys()))
        self.logger.info(
            f"✅ Topology validation passed: "
            f"{registered} active, {routed_count} routed, 4 phases, "
            f"0 orphans, 0 unrouted"
        )

        # 3. Initialize Memory
        self.memory = MemoryManager(settings)

        # ── ⚡ HFT HEAVY CACHE (Phase 3 confirmation agents) ──
        self.last_heavy_results: Dict[str, AgentOutput] = {}
        self.last_heavy_run_time: Dict[str, datetime] = {}

        # ── 📊 LATENCY CACHE (Priority 1 Fix) ─────────────────────────────────
        # Regime and Structure agents do heavy computation (300–420ms and
        # 180–280ms respectively) by recalculating ADX, BB, swing points,
        # FVGs, and order blocks from scratch EVERY cycle.
        #
        # Fix: Cache Phase 1 agent results for a configurable TTL.
        # Cache is invalidated when a new candle closes (candle_ts changes)
        # OR when the TTL expires — whichever comes first.
        #
        # Target latency:
        #   regime:    300–420ms → <60ms  (5× speedup on cache hit)
        #   structure: 180–280ms → <40ms
        # ─────────────────────────────────────────────────────────────────────────
        self._p1_cache: Dict[str, AgentOutput] = {}
        self._p1_cache_ts: Dict[str, float] = {}  # epoch seconds of last compute
        self._p1_cache_candle: Dict[str, object] = {}  # last candle timestamp
        # TTL in seconds per agent — conservative: regime changes slowly
        self._p1_ttl: Dict[str, float] = {
            "regime":    90.0,   # 1.5 min — regime is very sticky, STAGGERED from structure
            "structure": 45.0,   # 45 secs — every ~1 candle, STAGGERED from regime
            # STAGGER RATIONALE: old TTLs (60/30) aligned at candle boundaries,
            # causing simultaneous recompute (regime=276ms + structure=364ms = 640ms+).
            # Offset TTLs ensure they never expire on the same cycle.
        }

        self.signal_history: List[Signal] = []
        self.last_signal: Optional[Signal] = None
        self.signal_count = 0
        self.recent_signals: Dict[str, float] = {}

    @property
    def learning_agent(self):
        return self.agents.get("learning")

    def process(self, df, snapshot: "MarketSnapshot", historical_override = None) -> "Signal":
        start_ts = perf_counter()
        try:
            signal = self._process_impl(df, snapshot, historical_override)
        except Exception as e:
            raise e
        finally:
            latency_ms = int((perf_counter() - start_ts) * 1000)
            try:
                sig_val = locals().get('signal')
                if hasattr(self, "current_trace") and self.current_trace and not self.current_trace._is_finalized:
                    if sig_val and sig_val.signal_type.value == "TRADE":
                        pipeline_stages = ["Agents", "Candidate Detection", "MAV", "Signal Integrity", "Risk Budget"]
                        for st in pipeline_stages:
                            if st == "MAV" and (not hasattr(self, 'experiment_config') or not self.experiment_config.enable_mav):
                                st_act = StageAction.SKIPPED
                            else:
                                st_act = StageAction.PASSED
                            self.current_trace.add_stage(
                                stage_name=st,
                                entered_at=self.current_trace.timestamp,
                                exited_at=self.current_trace.timestamp,
                                action=st_act
                            )
                        self.current_trace.add_stage(
                            stage_name="Execution",
                            entered_at=self.current_trace.timestamp,
                            exited_at=datetime.now(),
                            action=StageAction.PASSED,
                            reason="Signal Generated"
                        )
                    self.current_trace.finalize()
                    if sig_val:
                        sig_val.trace = self.current_trace
                
                analytics_bus.publish("decision_cycle_completed", {
                    "cycle_id": getattr(self, "current_signal_id", "unknown"),
                    "latency_ms": latency_ms,
                    "signal_generated": sig_val.signal_type.value != "NO_TRADE" if sig_val else False,
                    "agents_evaluated": len(sig_val.agent_votes) if sig_val and hasattr(sig_val, "agent_votes") else 0,
                    "agents_skipped": 18 - (len(sig_val.agent_votes) if sig_val and hasattr(sig_val, "agent_votes") else 0)
                })
            except Exception as e:
                self.logger.error(f"Analytics decision_cycle_completed publish failed: {e}")

            # ── 📓 OI Analytics Logging (Shadow Mode Validation) ──
            try:
                sig_val = locals().get('signal')
                if sig_val:
                    # Always run OI for analytics collection even if not in active_agents
                    oi_out = self._shadow_oi.run(df, snapshot)
                    if oi_out and oi_out.details and "market_structure" in oi_out.details:
                        msa = oi_out.details["market_structure"]
                        if "oi" in msa:
                            oi_data = msa["oi"]
                            event = {
                                "Timestamp": snapshot.timestamp.isoformat() if hasattr(snapshot.timestamp, "isoformat") else str(snapshot.timestamp),
                                "Symbol": getattr(snapshot, "symbol", "NIFTY"),
                                "Spot_Price": snapshot.price,
                                "Regime": sig_val.regime.name if sig_val.regime else "UNKNOWN",
                                "Engine_Decision": sig_val.signal_type.value,
                                "Trade_ID": "", 
                                "Position_Size": sig_val.position_size,
                                "Entry_Price": sig_val.entry_price
                            }
                            # Map OI fields
                            for k, v in oi_data.items():
                                if k == "feature_attribution":
                                    for ak, av in v.items():
                                        event[f"Attr_{ak}"] = av
                                elif k == "support_zone" and v:
                                    event["Support_Zone"] = f"{v['low']}-{v['high']}"
                                elif k == "resistance_zone" and v:
                                    event["Resistance_Zone"] = f"{v['low']}-{v['high']}"
                                elif k == "migration_direction":
                                    event["Migration"] = v
                                elif k == "trap_type":
                                    event["Trap"] = v
                                elif k == "wall_break_direction":
                                    event["Wall_Break"] = v
                                elif k == "wall_absorption":
                                    event["Wall_Absorption"] = str(v)
                                elif k not in ["explanation"]:
                                    event[k.title()] = v

                            self.oi_logger.log_event(event)
            except Exception as e:
                self.logger.error(f"Failed to log OI analytics: {e}")

        return signal

    def _process_impl(self, df, snapshot: "MarketSnapshot", historical_override = None) -> "Signal":
        from models.signal import Signal
        from models.decision_trace import DecisionTrace, TraceStage, StageAction, ReplayFidelity, ReplayMode
        self.current_signal_id = str(uuid.uuid4())[:8]
        outputs = []
        outputs_dict = {}
        self._last_decision_path = ["ENV_VALID"]
        self._sim_track_data = {}
        
        # Initialize DecisionTrace
        experiment_id = "live"
        benchmark_version = "N/A"
        if hasattr(self, 'experiment_config') and self.experiment_config:
            experiment_id = getattr(self.experiment_config, 'experiment_id', "live") or "live"
            benchmark_version = getattr(self.experiment_config, 'benchmark_version', "N/A") or "N/A"
            
        self.current_trace = DecisionTrace(
            cycle_id=self.current_signal_id,
            timestamp=snapshot.timestamp,
            engine_version="v3.8",
            experiment_id=experiment_id,
            benchmark_version=benchmark_version,
            git_commit="latest",
            replay_mode=historical_override.mode if hasattr(historical_override, 'mode') else ReplayMode.LIVE,
            replay_fidelity=historical_override.fidelity if hasattr(historical_override, 'fidelity') else ReplayFidelity.LIVE,
            replay_confidence=historical_override.confidence if hasattr(historical_override, 'confidence') else 1.0
        )

        self.logger.debug("⚡ Engine v3 Cycle Started")

        # ── Resolve pending outcome labels ──
        # Update blocked setups with future price moves now that time has elapsed.
        self._resolve_pending_outcomes(snapshot.price)

        # 0. Global Market Open Filter
        current_time = datetime.now().strftime("%H:%M")
        if current_time < self.settings.trade_filter.market_open_safe_time:
            return self._no_trade_signal(
                snapshot, 
                [f"Market Opening Chaos (Wait until {self.settings.trade_filter.market_open_safe_time})"],
                outputs_dict
            )

        # ─── PHASE 2: GAP & SPIKE PROTECTION ───
        # Priority 4 Fix: Use ATR-normalised, time-decaying gap penalty.
        # Old model: binary flag → full-session weight reduction (over-suppressive).
        # New model: GapPenaltyManager computes severity relative to ATR and        #            exponentially decays it so gap influence melts away naturally.
        today_date = datetime.now().date()
        if self.gap_penalty_mgr.is_new_session_needed():
            self.session_started_date = today_date
            if hasattr(snapshot, 'prev_day_close') and snapshot.prev_day_close > 0:
                gap_pts = abs(
                    (snapshot.day_open if snapshot.day_open > 0 else snapshot.price)
                    - snapshot.prev_day_close
                )
                raw_atr = snapshot.atr if snapshot.atr > 0 else 100.0
                
                # Convert intraday ATR to bounded daily estimate.
                # GapPenaltyManager is tuned for Daily ATR scale (150-300).
                estimated_daily_atr = max(raw_atr * 10, 80.0)
                self.logger.info(f"📊 [GAP_PENALTY] Intraday ATR: {raw_atr:.2f} | Estimated Daily ATR: {estimated_daily_atr:.2f}")
                
                self.gap_penalty_mgr.new_session(gap_pts, estimated_daily_atr)
                self.session_gap_detected = gap_pts > 0  # kept for metadata compat

        if df is not None and not df.empty:
            last_candle = df.iloc[-1]
            if 'high' in last_candle and 'low' in last_candle:
                candle_range = last_candle['high'] - last_candle['low']
                # Require range to be at least 30 points AND > 2x ATR for it to be considered a freeze-worthy spike
                if snapshot.atr > 0 and candle_range > 30 and candle_range > 2 * snapshot.atr:
                    self.spike_freeze_until = time.time() + 600  # 10 minute freeze
                    try:
                        # Extract candle details for diagnostics
                        c_open = last_candle.get('open', 0)
                        c_high = last_candle['high']
                        c_low = last_candle['low']
                        c_close = last_candle.get('close', 0)
                        c_vol = last_candle.get('volume', 0)
                        
                        # Calculate data staleness
                        if hasattr(last_candle, 'name') and hasattr(last_candle.name, 'timestamp'):
                            c_time = last_candle.name.timestamp()
                        else:
                            c_time = time.time()
                        staleness = time.time() - c_time
                        
                        # Check for API latency (from snapshot)
                        snap_latency = getattr(snapshot, 'latency_ms', 0)
                        
                        self.logger.warning(
                            f"⚡ INTRADAY SPIKE! Range {candle_range:.1f} > 30 & 2xATR ({2*snapshot.atr:.1f}). Freezing for 10m.\n"
                            f"   [DIAGNOSTICS] O:{c_open:.1f} H:{c_high:.1f} L:{c_low:.1f} C:{c_close:.1f} Vol:{c_vol} | "
                            f"Staleness: {staleness:.1f}s | API Latency: {snap_latency}ms"
                        )
                    except Exception as e:
                        self.logger.warning(f"⚡ INTRADAY SPIKE! Range {candle_range:.1f} > 30 & 2xATR ({2*snapshot.atr:.1f}). Freezing for 10m.")
        
        if time.time() < self.spike_freeze_until:
            return self._no_trade_signal(snapshot, ["Phase 2 Halt: Intraday Spike Freeze active"], outputs_dict)

        # ── Opening Volatility Context Flag ──
        # Use the live gap penalty multiplier as a proxy for "danger zone":
        # if gap_mult < 0.85, indicators are still settling from the overnight gap.
        # This flag is threaded into the dynamic router to suppress deep validation
        # (which burns 200–400ms on contaminated data during opening volatility).
        gap_mult_now = self.gap_penalty_mgr.get_unified_penalty_multiplier()
        opening_gap_session = gap_mult_now < 0.80  # was 0.85 → 0.80 (shrinks suppression window ~15min)

        # ── v3.8: Opening Auction Mode (9:15–9:25 IST) ──
        # During the opening auction window, EMAs/VWAP/oscillators are contaminated.
        # Only momentum, structure, and price_action provide usable signal.
        _is_opening_auction = self._is_opening_auction()

        # ── v3.8: High Conviction Exception Path ──
        # Detects when gap suppression is blocking genuinely strong momentum.
        # Allows partial bypass of gap penalties for elite setups.
        _conviction_exception = False

        if opening_gap_session:
            gap_status = self.gap_penalty_mgr.get_status()
            self.logger.info(
                f"⚠️ [OPENING GAP SESSION] gap_mult={gap_mult_now:.3f} < 0.80 | "
                f"Gap: {gap_status['gap_points']}pts ({gap_status['severity']}) | "
                f"Deep validation will be SUPPRESSED this cycle."
            )

        # ─── PHASE 1: THE GATEKEEPERS ───
        for name in self.settings.pipeline.phase_1_gatekeepers:
            if name in self.agents:
                # ── Latency Cache Check (Priority 1 Fix) ──
                now_ts = time.time()
                ttl = self._p1_ttl.get(name, 0.0)
                last_ts = self._p1_cache_ts.get(name, 0.0)
                last_candle = self._p1_cache_candle.get(name)
                # Determine current candle timestamp (use last row index if available)
                curr_candle = df.index[-1] if df is not None and not df.empty else None

                cache_valid = (
                    ttl > 0
                    and (now_ts - last_ts) < ttl
                    and curr_candle == last_candle
                    and name in self._p1_cache
                )

                if cache_valid:
                    out = self._p1_cache[name]
                    self.logger.debug(f"[CACHE HIT] {name} | age={(now_ts-last_ts):.1f}s < TTL={ttl:.0f}s")
                else:
                    start_p = perf_counter()
                    out = self.agents[name].run(df, snapshot)
                    latency = perf_counter() - start_p
                    self.logger.debug(f"Agent {name} latency = {latency:.3f}s")
                    # Update cache
                    if ttl > 0:
                        self._p1_cache[name] = out
                        self._p1_cache_ts[name] = now_ts
                        self._p1_cache_candle[name] = curr_candle

                outputs.append(out)
                outputs_dict[name] = out

                if out.is_blocker:
                    return self._no_trade_signal(snapshot, [f"Phase 1 Halt: {out.blocker_reason}"], outputs_dict)

        # ─── Unified Uncertainty Factor (Priority 2 Fix) ───────────────────────
        # OLD: gap_penalty × regime_lerp × PEV — three independent multipliers
        #      compounding on the same underlying uncertainty source.
        # NEW: ONE unified factor = max(gap_contribution, regime_contribution)
        #      taking the worst of the two, not multiplying them together.
        #      This eliminates hidden double-counting.
        # ─────────────────────────────────────────────────────────────────────────
        regime = MarketRegime.UNKNOWN
        regime_penalty = 1.0
        reg_conf = 1.0  # Default — no regime agent means full confidence
        gap_mult = self.gap_penalty_mgr.get_unified_penalty_multiplier()  # 0.70–1.00

        if "regime" in outputs_dict:
            regime_agent_output = outputs_dict["regime"]
            regime_val = regime_agent_output.details.get("regime", "RANGING")

            reg_conf = regime_agent_output.get_clamped_confidence()
            if reg_conf < 0.4:
                return self._no_trade_signal(snapshot, [f"Phase 4 Halt: Regime Confidence Too Low ({reg_conf:.2f})"], outputs_dict)

            # Regime contribution: smooth lerp from 0.85 at low conf → 1.0 at high conf
            if reg_conf < 0.8:
                t = max(0.0, (reg_conf - 0.50) / (0.80 - 0.50))
                regime_mult = round(0.85 + t * 0.15, 3)  # lerp 0.85 → 1.00
            else:
                regime_mult = 1.0

            # ── UNIFIED: use the MINIMUM of the two (worst-case, not compounded) ──
            # gap_mult already accounts for time-decay; regime_mult is real-time.
            # Compounding them double-penalizes the same open-gap uncertainty.
            regime_penalty = min(gap_mult, regime_mult)
            if regime_penalty < 1.0:
                gap_status = self.gap_penalty_mgr.get_status()
                self.logger.warning(
                    f"⚠️ Unified uncertainty: gap_mult={gap_mult:.3f} "
                    f"regime_mult={regime_mult:.3f} → combined={regime_penalty:.3f} "
                    f"| Initial Gap Severity: {gap_status['severity']} ({gap_status['gap_points']}pts) "
                    f"| Decay: {gap_status['minutes_since_open']:.0f}min elapsed"
                )

            # Map string to canonical enum
            regime_map = {
                "STRONG_TREND_UP": MarketRegime.STRONG_TREND_UP,
                "WEAK_TREND_UP": MarketRegime.WEAK_TREND_UP,
                "STRONG_TREND_DOWN": MarketRegime.STRONG_TREND_DOWN,
                "WEAK_TREND_DOWN": MarketRegime.WEAK_TREND_DOWN,
                "RANGING": MarketRegime.RANGING,
                "VOLATILE_CHOPPY": MarketRegime.VOLATILE_CHOPPY,
                "SQUEEZE": MarketRegime.SQUEEZE,
                "BREAKOUT": MarketRegime.BREAKOUT,
            }
            regime = regime_map.get(regime_val, MarketRegime.RANGING)

            if regime_val in self.settings.trade_filter.blocked_regimes:
                return self._no_trade_signal(snapshot, [f"Phase 1 Halt: Bad Regime ({regime_val})"], outputs_dict)

            if regime_val == "VOLATILE_CHOPPY" or "CHOPPY" in str(regime).upper():
                self.logger.warning(
                    "ADVISORY: CHOPPY Regime Detected. Historically PF=0.67, ECE=0.55. "
                    "Confidence scores may be highly unreliable."
                )

        # ─── PHASE 2: CORE DIRECTION ───
        for name in self.settings.pipeline.phase_2_core:
            if name in self.agents:
                start_p = perf_counter()
                out = self.agents[name].run(df, snapshot)
                latency = perf_counter() - start_p
                self.logger.debug(f"Agent {name} latency = {latency:.3f}s")
                
                outputs.append(out)
                outputs_dict[name] = out
                
                if out.is_blocker:
                    return self._no_trade_signal(snapshot, [f"Phase 2 Halt: {out.blocker_reason}"], outputs_dict)

        # Phase 2 Mini-Confluence: Do we have a setup?
        core_confluence = self.scorer.score(outputs)
        if core_confluence.dominant_direction == Direction.NEUTRAL:
             return self._no_trade_signal(snapshot, ["Phase 2 Halt: Core Agents Neutral (No Setup)"], outputs_dict)

        # ── S/R ENGINE UPDATE (Shadow Mode — runs every cycle) ──────────────
        # Extracts OI zones from shadow OI agent (if available) and combines
        # with price-action pivots to build a complete S/R zone map.
        # The sr_state is logged to CSV but does NOT affect trade decisions.
        # ───────────────────────────────────────────────────────────────────────
        _sr_state = None
        try:
            _oi_sup_zone = None
            _oi_res_zone = None
            # Try to extract OI zones from the shadow OI run (logged in the finally block)
            # or from outputs_dict if OI agent is active
            if "oi" in outputs_dict:
                _oi_msa = outputs_dict["oi"].details.get("market_structure", {})
                _oi_data = _oi_msa.get("oi", {})
                if _oi_data:
                    from models.oi_analysis import StrikeZone as _SZ
                    _sup_raw = _oi_data.get("support_zone")
                    _res_raw = _oi_data.get("resistance_zone")
                    if _sup_raw and isinstance(_sup_raw, dict):
                        _oi_sup_zone = _SZ(
                            low=_sup_raw["low"], high=_sup_raw["high"],
                            strength=_sup_raw.get("strength", 0),
                            total_oi=_sup_raw.get("total_oi", 0),
                            peak_strike=_sup_raw.get("peak_strike", 0),
                            num_strikes=_sup_raw.get("num_strikes", 0),
                        )
                    elif _sup_raw and hasattr(_sup_raw, "low"):
                        _oi_sup_zone = _sup_raw
                    if _res_raw and isinstance(_res_raw, dict):
                        _oi_res_zone = _SZ(
                            low=_res_raw["low"], high=_res_raw["high"],
                            strength=_res_raw.get("strength", 0),
                            total_oi=_res_raw.get("total_oi", 0),
                            peak_strike=_res_raw.get("peak_strike", 0),
                            num_strikes=_res_raw.get("num_strikes", 0),
                        )
                    elif _res_raw and hasattr(_res_raw, "low"):
                        _oi_res_zone = _res_raw

            _sr_state = self.sr_engine.update(df, snapshot, _oi_sup_zone, _oi_res_zone)
            self.sr_logger.log_state(_sr_state, snapshot, engine_decision="pending")

            # Log interaction events with forward return tracking
            if _sr_state.latest_event:
                self.sr_logger.log_interaction(_sr_state.latest_event)
                self.logger.debug(
                    f"📊 [SR] {_sr_state.latest_event.event_type} at "
                    f"{_sr_state.latest_event.zone_mid:.0f} | "
                    f"Bias: {_sr_state.sr_bias} ({_sr_state.sr_bias_score:+.1f}) | "
                    f"Zones: {_sr_state.total_zones} | "
                    f"{_sr_state.trade_context[:80]}"
                )
        except Exception as e:
            self.logger.error(f"S/R Engine update failed (non-fatal): {e}")

        # ─── EARLY KILL-SWITCH (Pre-Phase 3) ───────────────────────────────────────
        # Compute a quick preliminary score to detect hopeless cases BEFORE
        # we burn 200–400ms on deep validation agents.
        # If the dominant score is below MIN_DOMINANT_THRESHOLD, no amount of
        # deep validation will rescue this signal — bail now.
        #
        # This alone reduces latency by 25–40% on bad setups.
        #
        # CALIBRATION NOTE (2026-05-11): Lowered from 0.35 → 0.25.
        # Pre-Phase-3, only 5 agents (P1+P2) contribute. On live data where
        # agents trend directionally, max pre-deep score is ~0.38.
        # 0.35 rejected nearly all live cycles. 0.25 still kills noise.
        #
        # SIMULATION RELAXATION (2026-05-13): NIFTY intraday rarely achieves
        # perfect pre-Phase-3 consensus, especially post-gap sessions. Without
        # trade samples we can never validate expectancy. Lowered to 0.18 in SIM
        # ONLY to allow statistically meaningful samples to accumulate. LIVE: 0.25.
        # ─────────────────────────────────────────────────────────────────────────
        # ── v3.6: OI Fallback Weight Redistribution ──────────────────────────────
        # Check OI reliability. If unreliable, redistribute its weight budget to
        # momentum/structure/price_action instead of degrading the whole strategy.
        # This preserves total weight budget while neutralising noisy OI votes.
        _oi_reliable = self._check_and_handle_oi_reliability(outputs_dict)

        # ── v3.8: High Conviction Exception Check ─────────────────────────────────
        # Before computing MPM, check if we have an exceptionally strong directional
        # setup that should override gap-based DEFENSIVE mode.
        # This catches: trend days, panic selloffs, runaway gap continuations.
        _conviction_exception = self._check_high_conviction_exception(
            outputs_dict, snapshot, gap_mult
        )
        _effective_gap_mult = gap_mult
        if _conviction_exception and gap_mult < 0.80:
            # Partially relax gap suppression — boost by 0.12 but cap at 0.85
            _effective_gap_mult = min(0.85, gap_mult + 0.12)
            self.logger.info(
                f"🔥 [CONVICTION OVERRIDE] High conviction exception fired! "
                f"gap_mult {gap_mult:.3f} → {_effective_gap_mult:.3f} | "
                f"Allowing targeted participation in gap momentum."
            )
            self._last_decision_path.append("CONVICTION_OVERRIDE_APPLIED")

        # ── v3.6: Compute Market Participation Mode (MPM) ────────────────────────
        # Must happen AFTER OI fallback so the score reflects redistributed weights.
        # v3.8: Use _effective_gap_mult so conviction override affects MPM.
        _early_buy, _early_sell = self.compute_weighted_score(outputs_dict, _effective_gap_mult)
        mpm = self._compute_market_participation_mode(
            outputs_dict, snapshot, _effective_gap_mult, _oi_reliable
        )
        self._current_mpm = mpm
        self.logger.info(
            f"[MPM] Mode={mpm.value} | reason={self._mpm_reason} | "
            f"OI={'OK' if _oi_reliable else 'FALLBACK'}"
            f"{' | 🔥 CONVICTION_OVERRIDE' if _conviction_exception else ''}"
        )

        # ── v3.6: Adaptive Early-Kill Threshold ───────────────────────────────────
        # Static 0.25 rejected valid 0.22–0.24 setups that later worked.
        # Now threshold is dynamically set based on Market Participation Mode:
        #   AGGRESSIVE: 0.18 — trend confirmed, lower bar needed for continuation
        #   BALANCED:   0.20 — moderate filtering (was 0.18 sim / 0.25 live)
        #   DEFENSIVE:  0.25 — original strict logic, capital protection
        # SIM always applies a -0.02 relaxation on top for sample accumulation.
        # v3.8: During conviction override, use BALANCED threshold even if MPM=DEFENSIVE.
        _SIM_RELAX = 0.02 if self._is_simulation else 0.0
        if mpm == MarketParticipationMode.AGGRESSIVE:
            MIN_DOMINANT_THRESHOLD = max(0.15, 0.18 - _SIM_RELAX)
        elif mpm == MarketParticipationMode.BALANCED or _conviction_exception:
            MIN_DOMINANT_THRESHOLD = max(0.15, 0.20 - _SIM_RELAX)
        else:  # DEFENSIVE
            MIN_DOMINANT_THRESHOLD = max(0.18, 0.25 - _SIM_RELAX)

        _early_dominant = max(_early_buy, _early_sell)
        
        self._last_raw_confidence = _early_dominant
        self._last_gap_multiplier = _effective_gap_mult
        self._last_agent_score = _early_dominant / _effective_gap_mult if _effective_gap_mult > 0 else 0.0
        self._last_adaptive_threshold = MIN_DOMINANT_THRESHOLD
        
        if _early_dominant < MIN_DOMINANT_THRESHOLD:
            self.logger.info(
                f"[⚡ EARLY KILL] Dominant score {_early_dominant:.3f} < {MIN_DOMINANT_THRESHOLD} "
                f"(MPM={mpm.value}, {'SIM' if self._is_simulation else 'LIVE'}) — "
                f"skipping deep validation (Buy={_early_buy:.3f} Sell={_early_sell:.3f})"
            )
            self._record_opportunity(
                blocked_by="Early Kill: dominant_score",
                buy_prob=_early_buy, sell_prob=_early_sell,
                dominant=_early_dominant, threshold=MIN_DOMINANT_THRESHOLD,
                snapshot=snapshot, outputs_dict=outputs_dict
            )
            self._last_decision_path.append("LOW_DOMINANT_SCORE_REJECTED")
            return self._no_trade_signal(
                snapshot,
                [f"Early Kill: dominant_score {_early_dominant:.3f} < {MIN_DOMINANT_THRESHOLD} (MPM={mpm.value})"],
                outputs_dict
            )

        # ─── PHASE 3: DYNAMIC CONFIRMATION (THE ROUTER) ───
        # Instead of calling the static list from settings, we ask the router what tools we need.
        # v3.8: Pass conviction_exception so router can allow targeted deep validation.
        dynamic_phase_3_agents = self._get_dynamic_confirmation_route(
            outputs_dict, snapshot, core_confluence,
            opening_gap_session=opening_gap_session,
            conviction_exception=_conviction_exception
        )
        
        for name in self.settings.pipeline.phase_3_confirmation:
            if name in self.agents:
                # If agent is in the dynamic route, run it
                if name in dynamic_phase_3_agents:
                    start_p = perf_counter()
                    out = self.agents[name].run(df, snapshot)
                    latency = perf_counter() - start_p
                    self.logger.debug(f"Agent {name} latency = {latency:.3f}s")
                    
                    outputs.append(out)
                    outputs_dict[name] = out
                    # Cache it if it's a "heavy" agent
                    if name in ["multi_timeframe", "institutional"]:
                        self.last_heavy_results[name] = out
                        self.last_heavy_run_time[name] = datetime.now()
                        self._last_decision_path.append(f"HEAVY_AGENT_RUN:{name}")
                # If not in route but we have a cache, reuse it to sustain the thesis
                elif name in self.last_heavy_results:
                    outputs.append(self.last_heavy_results[name])
                    outputs_dict[name] = self.last_heavy_results[name]
                    self._last_decision_path.append(f"HEAVY_AGENT_CACHE:{name}")
                
                # Immediate halt if a dynamically called blocker (like Trap) fires
                if 'out' in locals() and out.is_blocker:
                    return self._no_trade_signal(snapshot, [f"Dynamic Phase 3 Halt ({name}): {out.blocker_reason}"], outputs_dict)

        # ─── PHASE 4: RISK & EXECUTION ───
        for name in self.settings.pipeline.phase_4_risk:
            if name in self.agents:
                start_p = perf_counter()
                out = self.agents[name].run(df, snapshot)
                latency = perf_counter() - start_p
                self.logger.debug(f"Agent {name} latency = {latency:.3f}s")
                
                outputs.append(out)
                outputs_dict[name] = out
                
                if out.is_blocker:
                    return self._no_trade_signal(snapshot, [f"Phase 4 Halt: {out.blocker_reason}"], outputs_dict)

        # Double check Risk confidence
        if "risk" in outputs_dict and outputs_dict["risk"].confidence == 0:
            return self._no_trade_signal(snapshot, ["Phase 4 Halt: Risk limits reached"], outputs_dict)

        # ─── PHASE 5: FINAL SYNTHESIS & PROBABILISTIC GRADING ───
        # 1. Compute Weighted Probability Matrix
        # regime_penalty here is the UNIFIED uncertainty factor (max-of-two, not compounded)
        # v3.8: If conviction exception fired, use _effective_gap_mult for regime_penalty
        _final_regime_penalty = min(_effective_gap_mult, regime_penalty) if _conviction_exception else regime_penalty
        adjusted_buy_prob, adjusted_sell_prob = self.compute_weighted_score(outputs_dict, _final_regime_penalty)

        raw_buy_prob = adjusted_buy_prob / _final_regime_penalty if _final_regime_penalty > 0 else 0.0
        raw_sell_prob = adjusted_sell_prob / _final_regime_penalty if _final_regime_penalty > 0 else 0.0

        # Priority 3 Fix: Apply sigmoid normalization BEFORE grading.
        # Multiplicative penalties compress all scores into 0.48–0.62.
        # Sigmoid widens the distribution so elite setups grade distinctly from marginal ones.
        buy_prob  = _sigmoid_normalize(adjusted_buy_prob)
        sell_prob = _sigmoid_normalize(adjusted_sell_prob)
        
        self._sim_track_data = {
            "raw_buy": raw_buy_prob, "raw_sell": raw_sell_prob,
            "gap_mult": _final_regime_penalty,
            "adj_buy": adjusted_buy_prob, "adj_sell": adjusted_sell_prob,
            "sig_buy": buy_prob, "sig_sell": sell_prob,
        }

        # ── INTEGRITY GATE (data validation — BEFORE any scoring logic) ──
        # This is NOT a quality filter — it's input validation.
        # One-sided signals (one side near zero) mean agents on that side
        # are dead/suppressed/missing data. That's NOT dominance — it's
        # incomplete information.
        #
        # v3.6 TREND CONTINUATION MODE:
        # In trending markets (AGGRESSIVE MPM), one-sided collapse is often
        # GENUINE conviction — the losing side has no thesis. We allow it
        # to pass if momentum + structure agents agree with the dominant side.
        # This replaces the old binary block with a context-aware gate.
        #
        # v3.8 GAP-ADAPTIVE THRESHOLDS:
        # In DEFENSIVE mode, thresholds now scale with gap_mult instead of
        # being static. A 177pt gap (gap_mult=0.65) drops the floor from
        # 0.22 to ~0.14, letting real momentum signals through while still
        # filtering noise. This prevents the integrity gate from killing
        # valid gap-momentum trades that the early-kill already approved.
        MIN_SIDE_FLOOR = 0.05     # each side must show SOME participation
        # Adjust onesided floor based on MPM:
        #   AGGRESSIVE: 0.15 — trend continuation valid even if one side silent
        #   BALANCED:   0.20 — moderate (same as old SIM threshold)
        #   DEFENSIVE:  dynamic — scales with gap_mult (was static 0.22/0.25)
        if mpm == MarketParticipationMode.AGGRESSIVE:
            MIN_DOMINANT_PROB   = 0.15 if self._is_simulation else 0.17
            MIN_ONESIDED_PROB   = 0.15 if self._is_simulation else 0.18
        elif mpm == MarketParticipationMode.BALANCED:
            MIN_DOMINANT_PROB   = 0.18 if self._is_simulation else 0.20
            MIN_ONESIDED_PROB   = 0.20 if self._is_simulation else 0.22
        else:  # DEFENSIVE
            # v3.8: Scale with gap_mult — large gaps legitimately compress scores
            _eff_gm = _effective_gap_mult  # includes conviction override if active
            MIN_DOMINANT_PROB   = max(0.14, (0.20 if self._is_simulation else 0.22) * _eff_gm)
            MIN_ONESIDED_PROB   = max(0.15, (0.22 if self._is_simulation else 0.25) * _eff_gm)
            if _eff_gm < 0.90:
                self.logger.info(
                    f"[INTEGRITY] Gap-adaptive thresholds: gap_mult={_eff_gm:.3f} → "
                    f"MIN_DOMINANT={MIN_DOMINANT_PROB:.3f} MIN_ONESIDED={MIN_ONESIDED_PROB:.3f}"
                )

        if buy_prob < MIN_SIDE_FLOOR and sell_prob < MIN_SIDE_FLOOR:
            self._record_opportunity(
                blocked_by="Signal Integrity: both sides collapsed",
                buy_prob=buy_prob, sell_prob=sell_prob,
                dominant=0.0, threshold=MIN_SIDE_FLOOR,
                snapshot=snapshot, outputs_dict=outputs_dict
            )
            return self._no_trade_signal(snapshot,
                [f"Signal Integrity: both sides collapsed (B={buy_prob:.3f} S={sell_prob:.3f})"],
                outputs_dict)

        if buy_prob < MIN_SIDE_FLOOR or sell_prob < MIN_SIDE_FLOOR:
            dominant = max(buy_prob, sell_prob)
            collapsed_side = "BUY" if buy_prob < MIN_SIDE_FLOOR else "SELL"

            # v3.6 Trend Continuation Mode:
            # Check if momentum + structure confirm the dominant direction.
            # If so, one-sided collapse IS genuine conviction — allow continuation.
            _trend_cont_pass = self._check_trend_continuation(
                outputs_dict, buy_prob, sell_prob, mpm
            )
            if _trend_cont_pass:
                self.logger.info(
                    f"[TREND CONT] One-sided allowed: {collapsed_side} collapsed but "
                    f"momentum+structure confirm dominant | MPM={mpm.value} | "
                    f"B={buy_prob:.3f} S={sell_prob:.3f}"
                )
                # Don't block — fall through to probability floor
            elif dominant < MIN_ONESIDED_PROB:
                self._record_opportunity(
                    blocked_by=f"Signal Integrity: {collapsed_side} side collapsed",
                    buy_prob=buy_prob, sell_prob=sell_prob,
                    dominant=dominant, threshold=MIN_ONESIDED_PROB,
                    snapshot=snapshot, outputs_dict=outputs_dict
                )
                return self._no_trade_signal(snapshot,
                    [f"Signal Integrity: {collapsed_side} side collapsed "
                     f"(B={buy_prob:.3f} S={sell_prob:.3f}, dominant={dominant:.3f} < {MIN_ONESIDED_PROB}, "
                     f"MPM={mpm.value})"],
                    outputs_dict)
            else:
                # Dominant is high enough but one side silent — warn only
                self.logger.warning(
                    f"[INTEGRITY] One-sided signal ({collapsed_side}=0): B={buy_prob:.3f} S={sell_prob:.3f} "
                    f"(dominant={dominant:.3f} passes elevated floor {MIN_ONESIDED_PROB})"
                )

        # ── Minimum Probability Floor (dominant side must have real substance) ──
        dominant_prob = max(buy_prob, sell_prob)
        if dominant_prob < MIN_DOMINANT_PROB:
            self._record_opportunity(
                blocked_by="Probability Floor",
                buy_prob=buy_prob, sell_prob=sell_prob,
                dominant=dominant_prob, threshold=MIN_DOMINANT_PROB,
                snapshot=snapshot, outputs_dict=outputs_dict
            )
            return self._no_trade_signal(snapshot,
                [f"Probability Floor: dominant={dominant_prob:.3f} < {MIN_DOMINANT_PROB} (high gap but no edge)"],
                outputs_dict)

        # 2. Determine Dominant Direction
        if buy_prob > sell_prob:
            direction = Direction.BULLISH
            confidence = buy_prob
        elif sell_prob > buy_prob:
            direction = Direction.BEARISH
            confidence = sell_prob
        else:
            direction = Direction.NEUTRAL
            confidence = 0.0

        # 3. Minimum Dominance Rule (Adaptive Edge Guard via Tuner)
        # Base thresholds come from the ThresholdTuner (self-adjusting).
        # In uncertain regime we relax by 0.01 to avoid lock-out.
        # v3.6: In AGGRESSIVE MPM, also relax by 0.01 to allow trend continuation.
        live_gap, live_conf = self.tuner.get_thresholds()
        _mpm_gap_relax = 0.01 if mpm == MarketParticipationMode.AGGRESSIVE else 0.0
        adaptive_gap = max(
            live_gap - _mpm_gap_relax - (0.01 if reg_conf < 0.6 else 0.0),
            0.035
        )
        gap = abs(buy_prob - sell_prob)
        if gap < adaptive_gap and direction != Direction.NEUTRAL:
            return self._no_trade_signal(snapshot,
                [f"Minimum Dominance Rule (Gap: {gap:.3f} < {adaptive_gap:.2f}, "
                 f"regime: {reg_conf:.2f}, MPM={mpm.value})"],
                outputs_dict)

        # 4. Market Acceptance Validator (MAV)
        # ─────────────────────────────────────────────────────────────────
        # Runs ONLY for candidates that have passed the integrity and dominance gates.
        # Defends against momentum spikes by requiring structural acceptance.
        from core.market_acceptance_validator import AcceptanceState
        from core.signal_lifecycle import log_mav_state
        
        # Check if we should track or evaluate a candidate
        struct_details = outputs_dict.get("structure")
        struct_lvl = None
        
        # We only care about breakout candidates if we have a structure read
        if struct_details and struct_details.details:
            s_dict = struct_details.details.get("structure", {})
            if direction == Direction.BULLISH:
                struct_lvl = s_dict.get("last_high")
            elif direction == Direction.BEARISH:
                struct_lvl = s_dict.get("last_low")
        
        # Evaluate against MAV (Feature Flagged)
        if self.experiment_config.enable_mav:
            if struct_lvl and df is not None and not df.empty:
                if self.mav.state == AcceptanceState.IDLE or self.mav.direction != direction.name:
                    self.mav.track_candidate(self.current_signal_id, direction.name, struct_lvl, snapshot.timestamp)
                    log_mav_state(self.current_signal_id, "CANDIDATE_TRACKED", struct_lvl, 0.0, "Started tracking candidate")
                
                # Extract EMA 50 if available for context
                ema_50 = None
                pa_details = outputs_dict.get("price_action")
                if pa_details and pa_details.details and "ema_50" in pa_details.details:
                    ema_50 = pa_details.details["ema_50"]
                    
                mav_state = self.mav.evaluate_1m_candle(df, ema_50)
                
                if mav_state in [AcceptanceState.CANDIDATE, AcceptanceState.STRUCTURAL_BREAK, AcceptanceState.WAITING_ACCEPTANCE]:
                    self.logger.info(f"🛡️ [MAV] Blocking trade: {mav_state.value} (Waiting for acceptance)")
                    log_mav_state(self.current_signal_id, mav_state.name, struct_lvl, self.mav.acceptance_score, "Waiting")
                    return self._no_trade_signal(
                        snapshot,
                        [f"Market Acceptance Validator: {mav_state.value} - waiting for acceptance candle"],
                        outputs_dict
                    )
                elif mav_state == AcceptanceState.FALSE_BREAKOUT:
                    self.logger.warning(f"🛡️ [MAV] FALSE BREAKOUT detected. Reason: {self.mav.failure_reason}")
                    log_mav_state(self.current_signal_id, "FALSE_BREAKOUT", struct_lvl, self.mav.acceptance_score, self.mav.failure_reason)
                    return self._no_trade_signal(
                        snapshot,
                        [f"Market Acceptance Validator: FALSE_BREAKOUT ({self.mav.failure_reason})"],
                        outputs_dict
                    )
                elif mav_state == AcceptanceState.TIMEOUT:
                    self.logger.warning(f"🛡️ [MAV] TIMEOUT detected. Resetting.")
                    log_mav_state(self.current_signal_id, "TIMEOUT", struct_lvl, self.mav.acceptance_score, "Timeout")
                    self.mav.reset()
                    return self._no_trade_signal(
                        snapshot,
                        [f"Market Acceptance Validator: TIMEOUT - no acceptance reached in time"],
                        outputs_dict
                    )
                elif mav_state == AcceptanceState.ACCEPTED:
                    self.logger.info(f"✅ [MAV] Breakout ACCEPTED! Score: {self.mav.acceptance_score}")
                    log_mav_state(self.current_signal_id, "ACCEPTED", struct_lvl, self.mav.acceptance_score, "Breakout Accepted")
                    # We let the signal proceed through to Threshold Relaxation

        # 5. Dynamic Confidence Gate
        # v3.6 UPGRADE:
        # Old: Relax ONLY when gap session is active (time-based).
        # New: Relax based on THREE independent signals:
        #   A. Gap decay (existing — time heals opening shock)
        #   B. MPM=AGGRESSIVE — trend confirmed, conviction is real
        #   C. Momentum+Structure alignment — price action says go
        #
        # Hard clamp at MIN_CONF_FLOOR (0.26) — never goes below that.
        # Relaxations are ADDITIVE up to MAX_TOTAL_RELAX.
        # ─────────────────────────────────────────────────────────────────
        gap_status = self.gap_penalty_mgr.get_status()
        gap_mins_elapsed = gap_status.get("minutes_since_open", 0.0)
        gap_severity = gap_status.get("severity", "NONE")

        # A. Gap-decay relaxation (same as before)
        _gap_decay_relax = 0.0
        if gap_severity != "NONE" and gap_mins_elapsed > 0:
            _CONF_DECAY_K   = 0.020
            _MAX_CONF_RELAX = 0.12
            _gap_decay_relax = _MAX_CONF_RELAX * (1.0 - math.exp(-_CONF_DECAY_K * gap_mins_elapsed))

        # B. MPM relaxation
        _mpm_conf_relax = 0.0
        if mpm == MarketParticipationMode.AGGRESSIVE:
            _mpm_conf_relax = 0.07   # trend confirmed — lower bar is justified
        elif mpm == MarketParticipationMode.BALANCED:
            _mpm_conf_relax = 0.03

        # C. Momentum+Structure alignment bonus
        _struct_bonus = self._momentum_structure_alignment_bonus(outputs_dict, direction)

        # Total relaxation (cap at 0.15 to prevent runaway loosening)
        _total_relax = min(_gap_decay_relax + _mpm_conf_relax + _struct_bonus, 0.15)
        adaptive_confidence = max(live_conf - _total_relax, 0.26)  # hard floor

        # Fallback: uncertain regime relaxation (same as before)
        fallback_applied = False
        if gap_severity == "NONE" and reg_conf < 0.6:
            adaptive_confidence = max(adaptive_confidence - 0.03, 0.26)
            fallback_applied = True
            
        # [HISTORICAL MODE OVERRIDE]
        if historical_override and historical_override.confidence_threshold is not None:
            if getattr(historical_override, 'mode', None) == ReplayMode.HISTORICAL:
                adaptive_confidence = historical_override.confidence_threshold
                self.logger.info(f"🔄 [REPLAY OVERRIDE] Mode A (HISTORICAL) active. Forcing threshold to {adaptive_confidence:.3f}")

        self._last_raw_confidence = confidence
        self._last_adaptive_threshold = adaptive_confidence

        actual_relax = live_conf - adaptive_confidence
        if actual_relax > 0.005:
            self.logger.info(
                f"[CONF GATE] Dynamic relax: live_conf={live_conf:.3f} - "
                f"gap_decay={_gap_decay_relax:.3f} - mpm={_mpm_conf_relax:.3f} - "
                f"struct={_struct_bonus:.3f} - fallback={0.03 if fallback_applied else 0.0:.3f} = "
                f"adaptive={adaptive_confidence:.3f} (MPM={mpm.value})"
            )
            try:
                from core.signal_lifecycle import log_threshold_applied
                reason_list = []
                if _gap_decay_relax > 0.005:
                    reason_list.append("gap_decay")
                if _mpm_conf_relax > 0.005:
                    reason_list.append("trend_continuation")
                if _struct_bonus > 0.005:
                    reason_list.append("conviction_override")
                if fallback_applied:
                    reason_list.append("uncertain_regime_relaxation")
                
                reason_str = "+".join(reason_list) if reason_list else "dynamic_relaxation"
                log_threshold_applied(
                    signal_id=self.current_signal_id,
                    base_threshold=live_conf,
                    adjusted_threshold=adaptive_confidence,
                    reason=reason_str,
                    elapsed_min=int(gap_mins_elapsed),
                    gap_severity=gap_severity
                )
            except Exception as e:
                self.logger.error(f"Failed to log threshold applied: {e}")

        if confidence < adaptive_confidence:
            reason = (f"Low Confidence ({confidence:.2f} < {adaptive_confidence:.2f}, "
                      f"regime: {reg_conf:.2f}, MPM={mpm.value}, gap_elapsed: {gap_mins_elapsed:.0f}min)")
            self._last_decision_path.append(reason)
            
        final_confluence = self.scorer.score(outputs)
        direction_agents = final_confluence.bullish_agents if direction == Direction.BULLISH else final_confluence.bearish_agents
        
        if direction_agents < self.settings.thresholds.min_confluence_agents:
            return self._no_trade_signal(snapshot, [f"Not enough agreeing agents ({direction_agents})"], outputs_dict)

        # ── FIX #5: MOMENTUM ALIGNMENT CHECK ──
        bullish_agents = final_confluence.bullish_agents
        bearish_agents = final_confluence.bearish_agents
        directional_alignment = (direction == Direction.BULLISH and bullish_agents >= 3 and bearish_agents <= 1) or \
                                (direction == Direction.BEARISH and bearish_agents >= 3 and bullish_agents <= 1)
        
        if not directional_alignment and gap < 0.05:
            return self._no_trade_signal(snapshot, [f"Directional Alignment Failed ({bullish_agents}B vs {bearish_agents}S) with weak gap {gap:.3f}"], outputs_dict)

        # Build Base Parameters
        signal_type = SignalType.BUY_CE if direction == Direction.BULLISH else SignalType.BUY_PE
        strength = Strength.STRONG if confidence >= 80 else (Strength.MODERATE if confidence >= 65 else Strength.WEAK)

        reasons = []
        warnings = []
        for out in outputs:
            if out.direction == direction and out.details:
                reasons.append(f"{out.agent_name}: {out.strength.value}")
            if out.warnings:
                warnings.extend(out.warnings)

        # Meta-Filter Adjustments (Expiry, Learning, Structure)
        expiry_out = outputs_dict.get("expiry_day")
        if expiry_out and expiry_out.strength == Strength.WEAK:
            confidence = max(0.0, confidence - 0.10)
            warnings.append("MetaFilter: Expiry Risk HIGH -> Reduced Confidence")

        learning_out = outputs_dict.get("learning")
        if learning_out and learning_out.strength == Strength.STRONG:
            confidence = min(1.0, confidence + 0.10)
            reasons.append("MetaFilter: Learning Agent Confirms -> Boosted Confidence")

        structure_out = outputs_dict.get("structure")
        if structure_out:
            if structure_out.details.get("bos"):
                reasons.append(f"Structure: BOS {structure_out.details['bos']['direction']}")
                confidence = min(1.0, confidence + 0.05)
            if structure_out.details.get("choch"):
                reasons.append(f"Structure: CHoCH to {structure_out.details['choch']['to']}")
                confidence = min(1.0, confidence + 0.10)

        # Fetch Risk Parameters
        trade_params = self.agents["risk"].get_trade_params(direction, snapshot.price, snapshot.atr)
        
        agent_votes = {
            name: {"direction": out.direction.value, "confidence": out.confidence}
            for name, out in outputs_dict.items()
        }

        # ── Entry Quality Log (Metric 2 monitor — parsed by analyze_logs.py) ──
        dominance_pct = (gap / max(buy_prob + sell_prob, 0.001)) * 100
        quality_tag = "STRONG" if dominance_pct >= 15 else ("MODERATE" if dominance_pct >= 8 else "WEAK")
        self.logger.info(
            f"[ENTRY_QUALITY] Signal: {signal_type.value} | "
            f"Buy: {buy_prob:.3f} | Sell: {sell_prob:.3f} | "
            f"Gap: {gap:.3f} | Dom: {dominance_pct:.1f}% | "
            f"Regime: {reg_conf:.2f} | Quality: {quality_tag}"
        )

        # ── Intelligence Breakdown Log ──
        self.logger.debug(
            f"🧠 [PROBABILITY] Signal: {signal_type.value} | "
            f"Score: {confidence:.2f} | "
            f"Buy: {buy_prob:.2f} | "
            f"Sell: {sell_prob:.2f} | "
            f"Gap: {gap:.2f}"
        )

        current_regime = str(self._classify_market(snapshot, outputs_dict).value)
        calibrated_confidence, calib_telemetry = self.calibrator.calibrate(confidence, current_regime)

        self.logger.info(
            f"🧠 [CALIBRATION] Signal: {signal_type.value} | "
            f"Raw Conf: {confidence:.2f} | "
            f"Calibrated: {calibrated_confidence:.2f} | "
            f"Regime: {current_regime}"
        )

        # Attach dynamic sizing metrics to metadata so PositionManager can size properly
        # ── Agent Sub-Scores (for Telegram signal formatter) ──
        # Normalised to 0-10 scale from agent confidence (0-1 clamped).
        # Only populated for active agents; formatter handles missing keys gracefully.
        def _agent_score_10(name: str) -> float:
            """Extract agent confidence as 0-10 score, or -1 if unavailable."""
            out = outputs_dict.get(name)
            if out is None:
                return -1.0
            return round(out.get_clamped_confidence() * 10, 1)

        meta = {
            "dominance_pct": dominance_pct,
            "dominance_gap": gap,
            "quality": quality_tag,
            "regime_conf": reg_conf,
            "directional_alignment": directional_alignment,
            "gap_detected": self.session_gap_detected,
            # ── Probability gate feed ──
            # Signal quality grader v3.1 reads this to cap the achievable grade.
            # Use the post-sigmoid dominant probability so the cap reflects
            # the REAL edge strength, not the raw pre-penalty score.
            "dominant_prob": round(confidence, 4),   # confidence IS dominant_prob at this point
            "calibrated_confidence": round(calibrated_confidence, 4),
            "calibration_telemetry": calib_telemetry,
            "adaptive_threshold": round(adaptive_confidence * 100, 1),
            "base_threshold": round(live_conf * 100, 1),
            # ── Runtime Fingerprint (incident replay / regression detection) ──
            "fingerprint": self.fingerprint.capture(
                active_agents=sorted(self.agents.keys()),
                weights=AGENT_WEIGHTS,
                thresholds={
                    "min_gap": self.tuner.get_thresholds()[0],
                    "min_conf": self.tuner.get_thresholds()[1],
                },
                regime=current_regime,
                gap_penalty=regime_penalty,
                system_mode=os.getenv("SYSTEM_MODE", "SIMULATION"),
            ),
            "decision_path": self._last_decision_path,
            "uncertainty_multiplier": regime_penalty,
            # ── Agent Sub-Scores for Telegram (v4.8) ──
            "agent_scores": {
                "oi": _agent_score_10("oi"),
                "trend": _agent_score_10("regime"),
                "flow": _agent_score_10("order_flow"),
                "volatility": _agent_score_10("volatility"),
                "momentum": _agent_score_10("momentum"),
                "structure": _agent_score_10("structure"),
                "price_action": _agent_score_10("price_action"),
            },
            "raw_confidence": round(getattr(self, "_last_raw_confidence", 0) * 100, 1),
            "suppression_reason": "REGIME_UNCERTAINTY" if _final_regime_penalty < 0.85 else ("RISK/VOLATILITY" if _final_regime_penalty < 0.95 else "AGENT_DIVERGENCE"),
            # ── S/R Engine Context (Shadow Mode — informational only) ──
            "sr_state": _sr_state.to_dict() if _sr_state else None,
            # ── Canonical Regime Context & Strike Policy ──
            "regime_context": RegimeContext(
                raw_regime=(outputs_dict.get("regime").details.get("regime", "") if outputs_dict.get("regime") else "") or (self._classify_market(snapshot, outputs_dict).value),
                normalized_regime=self._classify_market(snapshot, outputs_dict),
                trend_strength="STRONG" if self._classify_market(snapshot, outputs_dict) in (MarketRegime.STRONG_TREND_UP, MarketRegime.STRONG_TREND_DOWN, MarketRegime.BREAKOUT) else ("WEAK" if self._classify_market(snapshot, outputs_dict) in (MarketRegime.WEAK_TREND_UP, MarketRegime.WEAK_TREND_DOWN) else ("NEUTRAL" if self._classify_market(snapshot, outputs_dict) in (MarketRegime.RANGING, MarketRegime.SQUEEZE) else "CHOP")),
                strike_policy="ITM_1_STEP" if self._classify_market(snapshot, outputs_dict) in (MarketRegime.STRONG_TREND_UP, MarketRegime.STRONG_TREND_DOWN, MarketRegime.BREAKOUT) else ("ATM" if self._classify_market(snapshot, outputs_dict) in (MarketRegime.WEAK_TREND_UP, MarketRegime.WEAK_TREND_DOWN, MarketRegime.RANGING, MarketRegime.SQUEEZE) else "NO_TRADE"),
                details=outputs_dict.get("regime").details if outputs_dict.get("regime") else {}
            ).to_dict(),
        }

        signal = Signal(
            id=self.current_signal_id,
            timestamp=datetime.now(),
            signal_type=signal_type,
            direction=direction,
            confidence=round(confidence * 100, 1), # Store as % for display
            adaptive_threshold=round(adaptive_confidence * 100, 1),
            weighted_score=round(confidence, 3),   # Store as 0-1 for logic
            buy_score=round(buy_prob, 3),
            sell_score=round(sell_prob, 3),
            agent_breakdown={name: {"dir": o.direction.value, "conf": o.get_clamped_confidence()} for name, o in outputs_dict.items()},
            metadata=meta,
            strength=strength,
            entry_price=trade_params.get("entry", snapshot.price),
            stop_loss=trade_params.get("stop_loss", 0),
            target_1=trade_params.get("target_1", 0),
            target_2=trade_params.get("target_2", 0),
            target_3=trade_params.get("target_3", 0),
            position_size=trade_params.get("position_size", 0),
            regime=self._classify_market(snapshot, outputs_dict),
            confluence=final_confluence,
            risk_reward_ratio=self._compute_rr_ratio(trade_params), 
            agent_votes=agent_votes,
            reasons=reasons[:5],
            warnings=warnings[:5],
            created_at=time.time(),
            updated_at=time.time(),
            execution_status="pending"
        )

        # ── Priority 3 Fix: Grade AFTER all penalties & normalization ──
        # Signal score at this point already reflects:
        #   - unified uncertainty factor (gap + regime)
        #   - sigmoid distribution normalization
        # v3.1 grader also applies probability cap via dominant_prob in metadata.
        from models import SignalGrade
        signal.grade = self.quality_grader.grade(signal)
        _prob_cap_note = ""
        if confidence < 0.55:
            _cap_tier = "≤C" if confidence < 0.35 else ("≤B" if confidence < 0.45 else "≤B+")
            _prob_cap_note = f" | ProbCap={_cap_tier} (prob={confidence:.3f})"
        self.logger.info(
            f"[GRADE] Post-penalty score: {confidence:.3f} | "
            f"Grade: {signal.grade.value}{_prob_cap_note} | "
            f"Unified penalty: {regime_penalty:.3f}"
        )

        # v5.0.1-FIX: Runtime Grade Audit — captures all grading inputs for
        # replay fidelity verification. This log proves whether the runtime
        # grader produces the expected grade or whether the Grade D findings
        # from the snapshot analysis were a persistence artifact.
        _conf_ratio = signal.confluence.confluence_ratio if signal.confluence else 0
        _rr_ratio = getattr(signal, "risk_reward_ratio", 0)
        _dom_pct = meta.get("dominance_pct", 0)
        _dir_align = meta.get("directional_alignment", False)
        _dom_prob = meta.get("dominant_prob", None)
        self.logger.info(
            f"[GRADE_AUDIT] signal={signal.id} grade={signal.grade.value} "
            f"confluence_ratio={_conf_ratio:.3f} risk_reward={_rr_ratio:.2f} "
            f"dominance_pct={_dom_pct} directional_alignment={_dir_align} "
            f"regime={signal.regime.value if hasattr(signal.regime, 'value') else signal.regime} "
            f"dominant_prob={f'{_dom_prob:.4f}' if _dom_prob is not None else 'None'}"
        )
        
        # Enforce MIN_ACTIVE_DIRECTIONAL_AGENTS for A / A+
        MIN_ACTIVE_DIRECTIONAL_AGENTS = 4
        if signal.grade in [SignalGrade.A_PLUS, SignalGrade.A]:
            active_directional = 0
            if signal.confluence:
                active_directional = signal.confluence.bullish_agents + signal.confluence.bearish_agents
            if active_directional < MIN_ACTIVE_DIRECTIONAL_AGENTS:
                self.logger.info(f"Grade downgraded from {signal.grade.value} to B+ (only {active_directional}/{MIN_ACTIVE_DIRECTIONAL_AGENTS} active directional agents)")
                signal.grade = SignalGrade.B_PLUS

        # Check Minimum Quality standard
        min_grade = self.settings.trade_filter.min_grade_to_trade
        grade_map = {"A+": 5, "A": 4, "B+": 3, "B": 2, "C": 1}
        
        if grade_map.get(signal.grade.value, 1) < grade_map.get(min_grade, 2):
            signal = self._no_trade_signal(snapshot, [f"Signal Quality too low ({signal.grade.value})"], outputs_dict)
            self._record_signal(signal)
            return signal

        # Signal Deduplication
        # v4.9: Window increased from 60s to 300s. Old 60s window allowed the
        # same BUY_CE signal to fire every minute, each triggering a new quote
        # fetch → rate limit → circuit breaker trip.
        # Fingerprint now uses direction + signal_type only (drops exact price)
        # so near-identical signals at slightly different prices are caught.
        fingerprint = f"{signal.direction.value}_{signal.signal_type.value}"
        now_ts = time.time()
        
        # Clear old fingerprints (5-minute window)
        self.recent_signals = {k: v for k, v in self.recent_signals.items() if now_ts - v < 300}
        
        if fingerprint in self.recent_signals:
            return self._no_trade_signal(snapshot, ["Signal Deduplication: Same direction signal within 300s"], outputs_dict)
            
        self.recent_signals[fingerprint] = now_ts
        self._record_signal(signal)
        # We no longer print the raw signal here.
        # Instrument resolution (Spot -> Option Premium) happens in main.py, 
        # and AlertManager handles the final formatted console output.

        try:
            from core.signal_lifecycle import log_signal_created
            log_signal_created(
                signal_id=signal.id,
                direction=signal.direction.value,
                raw_score_buy=signal.buy_score,
                raw_score_sell=signal.sell_score,
                regime=signal.regime.value if hasattr(signal.regime, "value") else str(signal.regime)
            )
        except Exception as e:
            self.logger.error(f"Failed to log signal creation: {e}")

        track = getattr(self, "_sim_track_data", {})
        if track:
            self.logger.info(
                f"[SIMULATION_TRACKING] TradeTaken=TRUE "
                f"RawBuy={track.get('raw_buy', 0):.4f} RawSell={track.get('raw_sell', 0):.4f} "
                f"GapMult={track.get('gap_mult', 1):.4f} "
                f"AdjBuy={track.get('adj_buy', 0):.4f} AdjSell={track.get('adj_sell', 0):.4f} "
                f"SigmoidBuy={track.get('sig_buy', 0):.4f} SigmoidSell={track.get('sig_sell', 0):.4f} "
                f"Threshold={getattr(self, '_last_adaptive_threshold', 0):.4f} "
                f"RejectReason='None'"
            )

        return signal

    # ══════════════════════════════════════════════════════════════════════════
    # v3.6 EXECUTION CALIBRATION HELPERS
    # ══════════════════════════════════════════════════════════════════════════

    def _check_and_handle_oi_reliability(
        self, outputs_dict: Dict[str, "AgentOutput"]
    ) -> bool:
        """
        OI Fallback Architecture (v3.6 Change A)

        Instead of flagging the ENTIRE strategy as degraded when OI is
        unreliable, we redistribute OI's weight budget to the next-best
        agents (momentum, structure, price_action) so the weight matrix
        stays balanced and the score remains meaningful.

        Returns True if OI is reliable, False if fallback was applied.

        Note: OI reliability check is skipped in SIMULATION mode because
        simulated OI data is expected and acceptable (not a failure state).
        """
        # Simulated mode — never flag OI as unreliable
        if self._is_simulation:
            return True

        # Check OI data source from the agent output
        oi_out = outputs_dict.get("oi")
        if oi_out is None:
            return True  # OI agent not active this cycle — not a failure

        oi_abstained = oi_out.details.get("abstained", False)
        if not oi_abstained:
            self._oi_real_count += 1
        self._oi_total_count += 1

        # v3.8: Extended warmup grace period for SMALL_CAPITAL / live modes.
        # At startup, the OI API hasn't had time to populate the cache.
        # Forcing DEFENSIVE MPM on the first 10 cycles creates a dead zone
        # where the engine cannot trade at all. Extended to 30 samples.
        _oi_warmup = 30 if os.getenv("SYSTEM_MODE", "").upper() in ("SMALL_CAPITAL", "SCALED") else 10
        if self._oi_total_count < _oi_warmup:
            return True

        reliability = (self._oi_real_count / self._oi_total_count)

        # Reliable enough — no redistribution needed
        if reliability >= 0.80:
            return True

        # OI unreliable — redistribute its weight budget
        oi_base_weight = AGENT_WEIGHTS.get("oi", 0.08)
        oi_reliability_mult = AGENT_RELIABILITY.get("oi", 0.75)
        oi_budget = oi_base_weight * oi_reliability_mult  # ~0.06

        # Mark the OI output as neutral (zero-contribution) via details flag
        # so compute_weighted_score sees it as neutral and doesn't count it.
        # We can't mutate confidence directly, so we use a sentinel in details.
        oi_out.details["_oi_fallback_active"] = True

        # Redistribute to recipient agents that are present in outputs_dict
        for recipient, share in _OI_FALLBACK_RECIPIENTS.items():
            if recipient in outputs_dict:
                bonus = oi_budget * share
                existing_w = AGENT_WEIGHTS.get(recipient, 0.05)
                # Apply the bonus transiently in the agent details so
                # compute_weighted_score can pick it up via the fallback weight key.
                outputs_dict[recipient].details["_oi_fallback_weight_bonus"] = (
                    outputs_dict[recipient].details.get("_oi_fallback_weight_bonus", 0.0)
                    + bonus
                )

        if self._oi_total_count % 20 == 0:
            self.logger.warning(
                f"⚠️ [OI FALLBACK] OI reliability={reliability:.1%} < 80% — "
                f"weight redistributed to momentum/structure/price_action. "
                f"Strategy NOT degraded. (n={self._oi_total_count})"
            )
        return False

    def _compute_market_participation_mode(
        self,
        outputs_dict: Dict[str, "AgentOutput"],
        snapshot: "MarketSnapshot",
        gap_mult: float,
        oi_reliable: bool,
    ) -> "MarketParticipationMode":
        """
        Market Participation Mode (MPM) — v3.6 Three-state execution classifier.

        DEFENSIVE triggers if ANY of:
          1. OI is unreliable (live mode only) — data quality issue
          2. Gap shock active (gap_mult < 0.80) — opening chaos
          3. Memory is tilted (consecutive losses >= 3) — tilt protection
          4. Regime confidence very low (< 0.45) — structural uncertainty

        AGGRESSIVE triggers if ANY ONE of these qualifying conditions:
          A. STRONG_TREND (UP or DOWN) + ≥3/5 core agents aligned + gap_mult ≥ 0.85
          B. WEAK_TREND + ≥4/5 core agents aligned (tighter consensus requirement)
          C. BREAKOUT regime + momentum confirms breakout direction
          D. SQUEEZE + momentum expanding (ATR ≥ 1.3× min) + ≥3/5 core agents agree
             (squeeze breakouts are where intraday edge often exists)

        v3.7: Expanded AGGRESSIVE triggers so the engine can participate
        in WEAK_TREND, BREAKOUT, and momentum-driven SQUEEZE conditions
        — not just STRONG_TREND which is rare intraday.

        BALANCED: everything else (the safe default).
        """
        # ── DEFENSIVE checks (highest priority — capital protection) ──
        if not oi_reliable and not self._is_simulation:
            self._mpm_reason = "OI unreliable (live mode)"
            return MarketParticipationMode.DEFENSIVE

        # v3.8: Gap shock check now respects conviction override.
        # If _effective_gap_mult was boosted by the conviction exception,
        # the system can be BALANCED instead of hard DEFENSIVE.
        if gap_mult < 0.80:
            self._mpm_reason = f"Gap shock active (gap_mult={gap_mult:.3f})"
            return MarketParticipationMode.DEFENSIVE

        if self.memory.is_tilted or self.memory.current_streak <= -3:
            self._mpm_reason = "Memory tilted / loss cluster"
            return MarketParticipationMode.DEFENSIVE

        regime_out = outputs_dict.get("regime")
        reg_conf_val = regime_out.get_clamped_confidence() if regime_out else 1.0
        if reg_conf_val < 0.45:
            self._mpm_reason = f"Regime confidence too low ({reg_conf_val:.2f})"
            return MarketParticipationMode.DEFENSIVE

        # ── AGGRESSIVE checks ── (ANY one path qualifies) ──
        regime_val = regime_out.details.get("regime", "UNKNOWN") if regime_out else "UNKNOWN"
        core_agents = ["momentum", "structure", "price_action", "multi_timeframe", "level"]

        # Helper: count core agents agreeing with a direction
        def _core_agree(direction: Direction) -> int:
            return sum(
                1 for a in core_agents
                if a in outputs_dict and outputs_dict[a].direction == direction
            )

        # Path A: Strong trend + 3+/5 aligned
        if regime_val in ("STRONG_TREND_UP", "STRONG_TREND_DOWN") and gap_mult >= 0.85:
            trend_dir = Direction.BULLISH if "UP" in regime_val else Direction.BEARISH
            agree = _core_agree(trend_dir)
            if agree >= 3:
                self._mpm_reason = f"Path-A Strong trend ({regime_val}) + {agree}/5 core aligned"
                return MarketParticipationMode.AGGRESSIVE

        # Path B: Weak trend + tighter consensus (4+/5)
        if regime_val in ("WEAK_TREND_UP", "WEAK_TREND_DOWN") and gap_mult >= 0.85:
            trend_dir = Direction.BULLISH if "UP" in regime_val else Direction.BEARISH
            agree = _core_agree(trend_dir)
            if agree >= 4:  # Require higher bar for weaker trend
                self._mpm_reason = f"Path-B Weak trend ({regime_val}) + {agree}/5 core aligned (high bar)"
                return MarketParticipationMode.AGGRESSIVE

        # Path C: Breakout + momentum confirms
        if regime_val == "BREAKOUT" and gap_mult >= 0.85:
            mom_out = outputs_dict.get("momentum")
            struct_out = outputs_dict.get("structure")
            if mom_out is not None and mom_out.direction != Direction.NEUTRAL:
                breakout_dir = mom_out.direction
                agree = _core_agree(breakout_dir)
                if agree >= 3:
                    self._mpm_reason = f"Path-C BREAKOUT + momentum confirms + {agree}/5 core aligned"
                    return MarketParticipationMode.AGGRESSIVE

        # Path D: Squeeze with expanding momentum (breakout imminent)
        # ATR expanding means energy is releasing — directional conviction likely
        if regime_val == "SQUEEZE" and gap_mult >= 0.85:
            min_atr = getattr(self.settings.trade_filter, "min_atr_for_trade", 50)
            atr_expanding = snapshot.atr >= min_atr * 1.3
            if atr_expanding:
                mom_out = outputs_dict.get("momentum")
                if mom_out is not None and mom_out.direction != Direction.NEUTRAL:
                    squeeze_dir = mom_out.direction
                    agree = _core_agree(squeeze_dir)
                    if agree >= 3:
                        self._mpm_reason = (
                            f"Path-D SQUEEZE breakout: ATR={snapshot.atr:.0f} ≥ 1.3× min "
                            f"+ {agree}/5 core aligned {squeeze_dir.value}"
                        )
                        return MarketParticipationMode.AGGRESSIVE

        # ── Default ──
        self._mpm_reason = f"Normal conditions (regime={regime_val}, gap_mult={gap_mult:.3f})"
        return MarketParticipationMode.BALANCED

    def _check_trend_continuation(
        self,
        outputs_dict: Dict[str, "AgentOutput"],
        buy_prob: float,
        sell_prob: float,
        mpm: "MarketParticipationMode",
    ) -> bool:
        """
        Trend Continuation Mode gate (v3.6 Change C).

        When one side of the signal has collapsed (near zero), this function
        determines if the collapse is GENUINE directional conviction rather
        than broken/missing data.

        Returns True (allow continuation) only when ALL of:
          1. MPM is AGGRESSIVE (trend is confirmed from multiple angles)
          2. Momentum agent agrees with the dominant direction
          3. Structure agent agrees with the dominant direction (if active)

        In BALANCED or DEFENSIVE mode, this always returns False — the normal
        elevated-floor check applies unchanged.
        """
        # Trend continuation only makes sense in AGGRESSIVE mode
        if mpm != MarketParticipationMode.AGGRESSIVE:
            return False

        dominant_direction = Direction.BULLISH if buy_prob >= sell_prob else Direction.BEARISH

        # Momentum must agree
        mom_out = outputs_dict.get("momentum")
        if mom_out is None or mom_out.direction != dominant_direction:
            return False

        # Structure must agree if it was run this cycle
        struct_out = outputs_dict.get("structure")
        if struct_out is not None and struct_out.direction != dominant_direction:
            return False

        # Both momentum (and structure if present) confirm — allow continuation
        return True

    def _momentum_structure_alignment_bonus(
        self,
        outputs_dict: Dict[str, "AgentOutput"],
        direction: Direction,
    ) -> float:
        """
        Confidence gate bonus (v3.6 Change D).

        Returns an additional relaxation amount (0.0–0.05) for the confidence
        gate when momentum AND structure agents both confirm the dominant
        direction AND their confidence is high (>= 65%).

        This is a BONUS on top of the gap-decay and MPM relaxations.
        Maximum contribution: 0.05 (small, surgical, evidence-driven).
        """
        if direction == Direction.NEUTRAL:
            return 0.0

        bonus = 0.0

        mom_out = outputs_dict.get("momentum")
        struct_out = outputs_dict.get("structure")

        mom_confirms = (
            mom_out is not None
            and mom_out.direction == direction
            and mom_out.get_clamped_confidence() >= 0.65
        )
        struct_confirms = (
            struct_out is not None
            and struct_out.direction == direction
            and struct_out.get_clamped_confidence() >= 0.60
        )

        if mom_confirms and struct_confirms:
            bonus = 0.05   # Both agree with conviction — clear trend
        elif mom_confirms:
            bonus = 0.02   # Momentum alone confirms — partial credit
        elif struct_confirms:
            bonus = 0.02   # Structure alone confirms — partial credit

        return bonus

    def _check_high_conviction_exception(
        self,
        outputs_dict: Dict[str, "AgentOutput"],
        snapshot: "MarketSnapshot",
        gap_mult: float,
    ) -> bool:
        """
        v3.8 High Conviction Exception Path.

        Detects when gap suppression is blocking genuinely strong momentum
        that professional engines should trade (trend days, panic selloffs,
        runaway gap continuations).

        Returns True when ALL conditions are met:
          1. gap_mult < 0.85 (gap suppression is active)
          2. ≥3 directional agents agree on the same direction
          3. Momentum agent has STRONG confidence (≥ 0.70)
          4. ATR is expanding (≥ 1.5× min_atr threshold)
          5. Price action agent confirms the direction (if active)

        When True, the caller partially relaxes gap_mult by +0.12 (cap 0.85).
        This is NOT a full bypass — it's a targeted relaxation for elite setups.
        """
        # Only relevant when gap suppression is actually hurting
        if gap_mult >= 0.85:
            return False

        # Momentum must be STRONG and directional
        mom_out = outputs_dict.get("momentum")
        if mom_out is None or mom_out.direction == Direction.NEUTRAL:
            return False
        if mom_out.get_clamped_confidence() < 0.70:
            return False

        dominant_dir = mom_out.direction

        # ATR must be expanding (confirms real move, not noise)
        min_atr = getattr(self.settings.trade_filter, "min_atr_for_trade", 50)
        if snapshot.atr < min_atr * 1.5:
            return False

        # Count directional agents agreeing with momentum
        directional_agents = ["momentum", "structure", "price_action", "market", "level"]
        agree_count = sum(
            1 for name in directional_agents
            if name in outputs_dict and outputs_dict[name].direction == dominant_dir
        )

        if agree_count < 3:
            return False

        # Price action must not contradict (if active)
        pa_out = outputs_dict.get("price_action")
        if pa_out is not None and pa_out.direction != Direction.NEUTRAL:
            if pa_out.direction != dominant_dir:
                return False

        self.logger.info(
            f"🔥 [HIGH CONVICTION] Exception conditions met: "
            f"{agree_count}/5 agents agree {dominant_dir.value} | "
            f"momentum_conf={mom_out.get_clamped_confidence():.2f} | "
            f"ATR={snapshot.atr:.1f} (≥{min_atr*1.5:.1f}) | "
            f"gap_mult={gap_mult:.3f}"
        )
        return True

    def _is_opening_auction(self) -> bool:
        """
        v3.8 Opening Auction Mode detector.

        Returns True during 9:15–9:25 IST when:
          - EMAs/VWAP are contaminated (insufficient candles)
          - Oscillator signals (RSI, Stochastic) are meaningless
          - Mean reversion logic will produce false signals
          - Only momentum bursts and structural breaks are tradeable

        Used by the router to gate which agents contribute to scoring.
        """
        import pytz
        now = datetime.now(pytz.timezone('Asia/Kolkata'))
        current_time = now.time()
        from datetime import time as dt_time
        return dt_time(9, 15) <= current_time < dt_time(9, 25)

    def _get_dynamic_confirmation_route(
        self,
        outputs_dict: Dict[str, AgentOutput],
        snapshot: MarketSnapshot,
        core_confluence,
        opening_gap_session: bool = False,
        conviction_exception: bool = False,
    ) -> List[str]:
        """
        🧠 V4 DYNAMIC ROUTING ENGINE
        Context-Aware, Memory-Aware, Confidence-Driven, and Opening-Aware.

        opening_gap_session=True means:
          - Overnight gap created distorted indicator states
          - Opening candle structure is unreliable
          - Deep validation agents (institutional, order_flow, delta_gamma)
            run on contaminated data -- they add latency and noise, not signal.
          - ONLY allow them if an extraordinary momentum burst is visible.

        conviction_exception=True (v3.8):
          - High conviction override fired — 3+ agents agree + momentum STRONG
          - Allow targeted deep validation (OI + volatility) even during gap session
          - Still skip institutional / order_flow (contaminated at open)
        """
        route = set()

        # --- 1. CONTEXT EXTRACTION ---
        regime = outputs_dict.get("regime")
        regime_val = regime.details.get("regime", "UNKNOWN") if regime else "UNKNOWN"

        structure = outputs_dict.get("structure")
        is_bos = structure and structure.details.get("bos") is not None

        conf_score = core_confluence.confluence_ratio * 100 if core_confluence else 0.0

        # --- 2. OPENING GAP SESSION GUARD ------------------------------------
        # During opening volatility, deep validation adds latency not signal.
        # Only run lightweight agents.  Deep validation is blocked unless
        # we see an extreme momentum condition (ATR burst >= 3x normal)
        # OR the conviction exception has fired (v3.8).
        # ---------------------------------------------------------------------
        if opening_gap_session:
            self.logger.info(
                "[WARN]  [ROUTER] Opening gap session active -- deep validation SUPPRESSED. "
                "Indicators may be contaminated.  Routing to lightweight agents only."
            )
            # Only route to lightweight, time-independent tools
            route.update(["trap", "level"])

            # v3.8: Conviction exception allows targeted validation
            if conviction_exception:
                self.logger.info(
                    "[FIRE] [ROUTER] Conviction override active during gap session — "
                    "allowing OI + volatility for directional confirmation."
                )
                route.add("oi")
                route.add("volatility")

            # Extreme momentum burst exception: ATR >= 3x normal
            elif snapshot.atr > self.settings.trade_filter.min_atr_for_trade * 3.0:
                self.logger.info(
                    "[FIRE] [ROUTER] Exceptional ATR burst during opening gap -- "
                    "allowing targeted deep validation (momentum + OI only)."
                )
                route.add("volatility")
                # Do NOT add institutional/order_flow/delta_gamma -- still too noisy

            self.logger.debug(f"[ROUTE] V4 Opening-Gap Route: {list(route)}")
            return list(route)

        # --- 3. MEMORY-AWARE ROUTING (Survival Mode) ---
        if self.memory.is_tilted or self.memory.current_streak < 0:
            self.logger.info("[BRAIN] Memory State: TILTED/LOSING. Routing to heavy defense.")
            route.add("trap")
            route.add("level")
            route.add("institutional")  # See what big money is doing before risking more

        # --- 4. TIMEFRAME THROTTLING (The HFT Shift) ---
        now = datetime.now()
        minute = now.minute

        # Heavy tools only run on candle boundaries (5m/15m)
        is_5m_boundary  = (minute % 5  == 0)
        is_15m_boundary = (minute % 15 == 0)

        # Multi-Timeframe only on 5m boundary
        if is_5m_boundary:
            route.add("multi_timeframe")

        # Institutional only on 15m boundary
        if is_15m_boundary:
            route.add("institutional")

        # --- 5. VOLATILITY ROUTING ---
        # High ATR -> market is violent -> call volatility + trap agents
        if snapshot.atr > self.settings.trade_filter.min_atr_for_trade * 1.5:
            route.add("volatility")
            route.add("trap")

        # --- 6. QUALITY-GATED DEEP VALIDATION (3-Layer Confluence Check) ---
        # Replaces the old "if conf_score >= 85" single-threshold trigger.
        # Deep validation now requires ALL THREE conditions:
        #   1. Minimum active directional participants (breadth)
        #   2. Dominance ratio >= 0.75 of active agents (quality)
        #   3. Opposing score <= 0.15 (contradiction ceiling)
        if core_confluence:
            active   = core_confluence.bullish_agents + core_confluence.bearish_agents
            dominant = max(core_confluence.bullish_agents, core_confluence.bearish_agents)
            opposing = min(core_confluence.bullish_agents, core_confluence.bearish_agents)
            dominance_ratio = dominant / active if active > 0 else 0.0
            opposing_ratio  = opposing  / active if active > 0 else 1.0

            HIGH_CONF_ACTIVE_MIN    = 3
            HIGH_CONF_DOMINANCE_MIN = 0.75   # >=75% agents agree
            HIGH_CONF_OPPOSING_MAX  = 0.15   # <=15% agents contradict

            deep_validation_warranted = (
                active          >= HIGH_CONF_ACTIVE_MIN
                and dominance_ratio >= HIGH_CONF_DOMINANCE_MIN
                and opposing_ratio  <= HIGH_CONF_OPPOSING_MAX
            )

            if deep_validation_warranted:
                self.logger.info(
                    f"[FIRE] High Confluence Validated: {dominant}/{active} agents agree "
                    f"(dominance={dominance_ratio:.0%}, opposing={opposing_ratio:.0%}). "
                    f"Calling deep validation."
                )
                route.add("institutional")
                route.add("order_flow")
                route.add("delta_gamma")
            elif conf_score >= 85.0:
                self.logger.info(
                    f"[WARN] High conf_score ({conf_score:.0f}) but confluence fragmented "
                    f"({dominant}/{active} agree, {opposing} oppose). Skipping deep validation."
                )

        # --- 7. STRUCTURAL / REGIME ROUTING ---
        if regime_val == "BREAKOUT" or is_bos:
            route.add("trap")

        elif regime_val in ["STRONG_TREND_UP", "STRONG_TREND_DOWN"]:
            route.add("multi_timeframe")
            route.add("order_flow")

        elif regime_val == "SQUEEZE":
            route.add("oi")

        # Fallback for standard markets
        if not route:
            route.update(["oi", "multi_timeframe"])

        self.logger.debug(f"[ROUTE] V4 Dynamic Route Selected: {list(route)}")
        return list(route)

    def compute_weighted_score(self, agent_outputs: Dict[str, AgentOutput], regime_penalty: float = 1.0):
        """
        🧠 QUANT-GRADE WEIGHTED AGGREGATOR
        - Standardizes confidence to 0.1-0.95 clamping
        - Handles 'NO_TRADE' neutral pressure
        - Normalizes by total_weight_used for true probability
        - v3.6: Respects OI fallback weight suppression + redistribution
        - v3.7: Per-agent concentration cap (no single agent > MAX_SINGLE_WEIGHT_SHARE of budget)
        """
        # ── v3.7: Anti-concentration cap ──────────────────────────────────────
        # Prevents a single agent from holding >25% of the total weight budget.
        # First pass: compute raw weights so we can calculate total and apply cap.
        # This is a two-pass approach to avoid unbounded single-agent influence.
        # ------------------------------------------------------------------
        MAX_SINGLE_WEIGHT_SHARE = 0.25  # no agent may hold more than 25% of total

        buy_score = 0.0
        sell_score = 0.0
        total_weight_used = 0.0
        neutral_weight = 0.0
        directional_weight = 0.0
        
        agent_pfs = {}
        learning_ag = self.agents.get("learning")
        if learning_ag and hasattr(learning_ag, "get_agent_profit_factors"):
            agent_pfs = learning_ag.get_agent_profit_factors()

        # ── Pass 1: compute all raw weights ──
        raw_weights: Dict[str, float] = {}
        for name, output in agent_outputs.items():
            weight = AGENT_WEIGHTS.get(name, 0.02)
            reliability = AGENT_RELIABILITY.get(name, 1.0)
            weight *= reliability

            if output.details.get("_oi_fallback_active", False):
                weight = 0.0

            bonus = output.details.get("_oi_fallback_weight_bonus", 0.0)
            weight += bonus

            if name in agent_pfs and agent_pfs[name] < 1.0:
                weight = 0.0

            raw_weights[name] = max(weight, 0.0)

        raw_total = sum(raw_weights.values())

        # ── Pass 2: apply concentration cap + accumulate scores ──
        agent_contributions = []
        for name, output in agent_outputs.items():
            # Clean up fallback bonus (consumed in pass 1 check; pop here)
            output.details.pop("_oi_fallback_weight_bonus", None)

            weight = raw_weights[name]

            # Anti-concentration cap: if this agent holds > MAX_SINGLE_WEIGHT_SHARE of total,
            # trim it down. Excess weight is NOT redistributed (it simply lowers total).
            if raw_total > 0:
                share = weight / raw_total
                if share > MAX_SINGLE_WEIGHT_SHARE:
                    weight = raw_total * MAX_SINGLE_WEIGHT_SHARE
                    self.logger.debug(
                        f"[WEIGHT CAP] {name}: share={share:.1%} > {MAX_SINGLE_WEIGHT_SHARE:.0%} "
                        f"— capped from {raw_weights[name]:.4f} to {weight:.4f}"
                    )
            
            output.weight = weight

            total_weight_used += weight

            conf = output.get_clamped_confidence()
            
            is_squelched = (name in agent_pfs and agent_pfs[name] < 1.0 and raw_weights[name] == 0)

            if output.direction == Direction.BULLISH:
                buy_score += weight * conf
                directional_weight += weight
                agent_contributions.append({"name": name, "dir": "BUY", "contrib": weight * conf, "squelched": is_squelched})
            elif output.direction == Direction.BEARISH:
                sell_score += weight * conf
                directional_weight += weight
                agent_contributions.append({"name": name, "dir": "SELL", "contrib": weight * conf, "squelched": is_squelched})
            else:
                neutral_weight += weight
                agent_contributions.append({"name": name, "dir": "NEUTRAL", "contrib": weight * conf, "squelched": is_squelched})
            # Neutral/NO_TRADE agents act as TRUE ABSTENTIONS ("no opinion").
            # They do NOT dilute the directional probability denominator.

            # Log if a squelched agent is encountered during pass 2
            if is_squelched:
                self.logger.warning(f"🔇 Agent {name} squelched. PF < 1.0 ({agent_pfs[name]:.2f})")

        if directional_weight == 0:
            raw_buy = 0.0
            raw_sell = 0.0
        else:
            raw_buy = buy_score / directional_weight
            raw_sell = sell_score / directional_weight

        effective_participation_ratio = (directional_weight / total_weight_used) if total_weight_used > 0 else 0.0
        abstention_rate = (neutral_weight / total_weight_used) if total_weight_used > 0 else 0.0
        
        # ── Log Contribution Breakdown ──
        dominant_dir = "BUY" if raw_buy >= raw_sell else "SELL"
        dominant_score = raw_buy if dominant_dir == "BUY" else raw_sell
        
        pos_lines = []
        neg_lines = []
        pos_total = 0.0
        neg_total = 0.0
        
        for ac in agent_contributions:
            if ac["squelched"]:
                continue
            
            # Impact relative to active directional weight
            impact = (ac["contrib"] / directional_weight) if directional_weight > 0 else 0
            
            if ac["dir"] == "NEUTRAL" or impact == 0:
                continue
                
            if ac["dir"] == dominant_dir:
                pos_lines.append(f"{ac['name'].ljust(18)} +{impact:.3f}")
                pos_total += impact
            else:
                neg_lines.append(f"{ac['name'].ljust(18)} -{impact:.3f}")
                neg_total -= impact
                
        pos_str = "\n".join(pos_lines) if pos_lines else "None"
        neg_str = "\n".join(neg_lines) if neg_lines else "None"
        
        self.logger.info(
            f"📊 [{dominant_dir} Score Construction]\n\n"
            f"Positive Contributions\n----------------------\n{pos_str}\n\n"
            f"Negative Contributions\n----------------------\n{neg_str}\n\n"
            f"Contribution Summary\n----------------------\n"
            f"Positive Total : +{pos_total:.3f}\n"
            f"Negative Total : {neg_total:.3f}\n"
            f"Net Directional : {pos_total + neg_total:+.3f}\n\n"
            f"Net {dominant_dir} Raw = {dominant_score:.4f}"
        )
        
        adj_buy = raw_buy * regime_penalty
        adj_sell = raw_sell * regime_penalty

        import json
        self.logger.info(
            f"[WEIGHT DIAGNOSTICS] " + json.dumps({
                "buy_raw": round(raw_buy, 4),
                "sell_raw": round(raw_sell, 4),
                "adj_buy": round(adj_buy, 4),
                "adj_sell": round(adj_sell, 4),
                "total_weight": round(total_weight_used, 4),
                "neutral_weight": round(neutral_weight, 4),
                "directional_weight": round(directional_weight, 4),
                "effective_participation_ratio": round(effective_participation_ratio, 4),
                "abstention_rate": round(abstention_rate, 4),
                "regime_penalty": regime_penalty
            })
        )

        return adj_buy, adj_sell


    def _no_trade_signal(self, snapshot: MarketSnapshot, reasons: List[str], outputs: Dict[str, AgentOutput]) -> Signal:
        all_warnings = []
        for out in outputs.values():
            all_warnings.extend(out.warnings)
            
        blockers = [out.blocker_reason for out in outputs.values() if out.is_blocker]
        final_reasons = reasons + blockers

        sig_id = getattr(self, "current_signal_id", None) or str(uuid.uuid4())[:8]
        reason_str = final_reasons[0] if final_reasons else 'Unknown'
        
        # --- Trace Injection ---
        if hasattr(self, "current_trace") and self.current_trace and not self.current_trace._is_finalized:
            stage_name = "Agents"
            if "Phase 1" in reason_str or "Phase 2" in reason_str or "Bad Regime" in reason_str or "Opening" in reason_str: 
                stage_name = "Agents"
            elif "Market Acceptance Validator" in reason_str: 
                stage_name = "MAV"
            elif "Phase 4" in reason_str or "Low Confidence" in reason_str: 
                stage_name = "Signal Integrity"
            elif "EV " in reason_str or "Risk" in reason_str or "Drawdown" in reason_str or "Execution Halt" in reason_str or "Phase 5" in reason_str: 
                stage_name = "Risk Budget"
            elif "Not enough agreeing" in reason_str or "Momentum Alignment" in reason_str or "Core Agents Neutral" in reason_str: 
                stage_name = "Candidate Detection"
                
            pipeline_stages = ["Agents", "Candidate Detection", "MAV", "Signal Integrity", "Risk Budget"]
            try:
                fail_idx = pipeline_stages.index(stage_name)
            except ValueError:
                fail_idx = 0
                
            for i in range(fail_idx):
                st_name = pipeline_stages[i]
                if st_name == "MAV" and (not hasattr(self, 'experiment_config') or not self.experiment_config.enable_mav):
                    st_act = StageAction.SKIPPED
                else:
                    st_act = StageAction.PASSED
                    
                self.current_trace.add_stage(
                    stage_name=st_name,
                    entered_at=self.current_trace.timestamp,
                    exited_at=self.current_trace.timestamp,
                    action=st_act
                )
            # MAV Waiting state is not an ERROR/REJECTED for the candidate, it's WAITING.
            action = StageAction.WAITING if "waiting" in reason_str.lower() else StageAction.REJECTED
            
            self.current_trace.add_stage(
                stage_name=stage_name,
                entered_at=self.current_trace.timestamp,
                exited_at=datetime.now(),
                action=action,
                reason=reason_str
            )
        # -----------------------
        
        track = getattr(self, "_sim_track_data", {})
        if track:
            raw_buy = track.get('raw_buy', 0)
            raw_sell = track.get('raw_sell', 0)
            sig_buy = track.get('sig_buy', 0)
            sig_sell = track.get('sig_sell', 0)
            threshold = getattr(self, '_last_adaptive_threshold', 0)
            dominant = "BUY" if raw_buy >= raw_sell else "SELL"
            regime = self._classify_market(snapshot, outputs)
            mpm_str = getattr(self, '_current_mpm', MarketParticipationMode.BALANCED).value if hasattr(self, '_current_mpm') else "UNKNOWN"
            
            pipeline_log = (
                f"═══════════════════════════════════════════════\n"
                f"DECISION PIPELINE\n"
                f"═══════════════════════════════════════════════\n\n"
                f"Market Regime        : {regime.name if hasattr(regime, 'name') else regime}\n"
                f"MPM                  : {mpm_str}\n\n"
                f"BUY Raw              : {raw_buy:.4f}\n"
                f"SELL Raw             : {raw_sell:.4f}\n\n"
                f"BUY Sigmoid          : {sig_buy:.4f}\n"
                f"SELL Sigmoid         : {sig_sell:.4f}\n\n"
                f"Integrity Threshold  : {threshold:.3f}\n\n"
                f"Dominant             : {dominant}\n\n"
                f"Decision             : NO TRADE\n\n"
                f"Reject Reason\n"
                f"--------------\n"
                f"{reason_str}\n\n"
                f"═══════════════════════════════════════════════"
            )
            self.logger.info(pipeline_log)
        signal = Signal(
            id=sig_id,
            timestamp=datetime.now(),
            signal_type=SignalType.NO_TRADE,
            direction=Direction.NEUTRAL,
            confidence=0,
            strength=Strength.WEAK,
            entry_price=snapshot.price,
            regime=self._classify_market(snapshot, outputs),
            reasons=final_reasons[:5],
            warnings=all_warnings[:5],
            agent_votes={
                name: {"direction": out.direction.value, "confidence": out.confidence}
                for name, out in outputs.items()
            },
            metadata={
                "decision_path": getattr(self, "_last_decision_path", []),
                "sim_track_data": track
            }
        )
        self.logger.signal(f"⚪ NO TRADE | {reasons[0]}")
        return signal

    @staticmethod
    def _compute_rr_ratio(trade_params: dict) -> float:
        """
        Compute Risk:Reward ratio from trade parameters.
        Uses T1 as the primary reward target (conservative estimate).
        Falls back to 0.0 if entry/SL/T1 are missing or invalid.
        """
        entry = trade_params.get("entry", 0)
        sl = trade_params.get("stop_loss", 0)
        t1 = trade_params.get("target_1", 0)

        if entry <= 0 or sl <= 0 or t1 <= 0:
            return 0.0

        risk = abs(entry - sl)
        if risk < 0.01:  # avoid div by zero
            return 0.0

        reward = abs(t1 - entry)
        return round(reward / risk, 1)

    def _classify_market(self, snapshot: MarketSnapshot, outputs: Dict[str, AgentOutput]) -> MarketRegime:
        """
        🧠 Market State Classifier
        Converts raw indicators into human-readable canonical market archetypes.
        """
        if hasattr(snapshot, 'bb_width') and snapshot.bb_width > 0 and snapshot.bb_width < self.settings.thresholds.squeeze_threshold:
            return MarketRegime.SQUEEZE
            
        bulls = sum(1 for o in outputs.values() if o.direction == Direction.BULLISH)
        bears = sum(1 for o in outputs.values() if o.direction == Direction.BEARISH)
        if bulls > 2 and bears > 2:
            return MarketRegime.VOLATILE_CHOPPY
            
        regime_agent = outputs.get("regime")
        if regime_agent:
            reg_val = regime_agent.details.get("regime", "")
            if reg_val == "STRONG_TREND_UP":
                return MarketRegime.STRONG_TREND_UP
            elif reg_val == "WEAK_TREND_UP":
                return MarketRegime.WEAK_TREND_UP
            elif reg_val == "STRONG_TREND_DOWN":
                return MarketRegime.STRONG_TREND_DOWN
            elif reg_val == "WEAK_TREND_DOWN":
                return MarketRegime.WEAK_TREND_DOWN
            elif reg_val == "VOLATILE_CHOPPY":
                return MarketRegime.VOLATILE_CHOPPY
            elif reg_val == "SQUEEZE":
                return MarketRegime.SQUEEZE
            elif reg_val == "BREAKOUT":
                return MarketRegime.BREAKOUT
            elif reg_val == "RANGING":
                return MarketRegime.RANGING
            elif "TREND" in reg_val:
                return MarketRegime.STRONG_TREND_UP if "UP" in reg_val else MarketRegime.STRONG_TREND_DOWN
                
        if hasattr(snapshot, 'bb_upper') and (snapshot.price > snapshot.bb_upper or snapshot.price < snapshot.bb_lower):
            return MarketRegime.BREAKOUT
            
        return MarketRegime.RANGING

    def _record_signal(self, signal: Signal):
        self.signal_count += 1
        self.last_signal = signal
        self.signal_history.append(signal)

        if len(self.signal_history) > 100:
            self.signal_history = self.signal_history[-100:]

        try:
            if signal.signal_type.value != "NO_TRADE":
                analytics_bus.publish("signal_generated", {
                    "signal_id": getattr(signal, "id", None) or getattr(signal, "intent_id", None),
                    "expected_edge_pts": getattr(signal, "expected_profit_pts", 0.0),
                    "snapshot": getattr(signal, "metadata", {}).get("snapshot_dict", {}),
                    "metadata": getattr(signal, "metadata", {})
                })
        except Exception as e:
            self.logger.error(f"Analytics signal publish failed: {e}")

    def _record_opportunity(
        self,
        blocked_by: str,
        buy_prob: float,
        sell_prob: float,
        dominant: float,
        threshold: float,
        snapshot: "MarketSnapshot",
        outputs_dict: Dict[str, "AgentOutput"] = None,
    ) -> None:
        """
        📓 Trade Opportunity Analytics — Shadow Journal

        Records every blocked setup to:
          1. In-memory rolling list (for fast report queries)
          2. data/opportunity_journal.jsonl (crash-safe, append-only, stream-processable)
          3. Pending outcome queue (to label future_move_5m/15m/30m on later cycles)

        Does NOT affect execution. Negligible I/O overhead (one line append per block).
        """
        import json as _json
        now = datetime.now()
        entry_id = f"{now.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

        try:
            analytics_bus.publish("signal_blocked", {
                "signal_id": entry_id,
                "reason": blocked_by,
                "theoretical_entry": snapshot.price if snapshot else 0.0,
            })
        except Exception as e:
            self.logger.error(f"Analytics block publish failed: {e}")

        # ── 1. Agent Attribution ────────────────────────────────────────────────
        # Compute which agent dragged down the dominant score the most.
        # Compare each agent's weighted contribution against the group average.
        agent_attribution = {}
        if outputs_dict:
            total_w = 0.0
            for name, out in outputs_dict.items():
                w = AGENT_WEIGHTS.get(name, 0.02) * AGENT_RELIABILITY.get(name, 1.0)
                total_w += w
            if total_w > 0:
                for name, out in outputs_dict.items():
                    w = AGENT_WEIGHTS.get(name, 0.02) * AGENT_RELIABILITY.get(name, 1.0)
                    conf = out.get_clamped_confidence()
                    direction = out.direction.value
                    # Negative attribution = agent pushed AGAINST dominant direction
                    contrib = (w / total_w) * conf
                    if out.direction == Direction.BULLISH:
                        agent_attribution[name] = {"direction": direction, "effect": round(contrib, 4)}
                    elif out.direction == Direction.BEARISH:
                        agent_attribution[name] = {"direction": direction, "effect": round(-contrib, 4)}
                    else:
                        agent_attribution[name] = {"direction": direction, "effect": 0.0}

            # Identify biggest drag: agent with most negative effect relative to dominant side
            if buy_prob >= sell_prob:
                biggest_drag = min(agent_attribution.items(), key=lambda x: x[1]["effect"], default=(None, {}))
            else:
                biggest_drag = max(agent_attribution.items(), key=lambda x: x[1]["effect"], default=(None, {}))
            top_drag_agent = biggest_drag[0] if biggest_drag[0] else "unknown"
            top_drag_effect = biggest_drag[1].get("effect", 0.0) if biggest_drag[0] else 0.0
        else:
            top_drag_agent = "unknown"
            top_drag_effect = 0.0
            
        if hasattr(self, "_sim_track_data"):
            self._sim_track_data["top_drag_agent"] = top_drag_agent
            self._sim_track_data["top_drag_effect"] = round(top_drag_effect, 4)
            self._sim_track_data["shortfall"] = round(threshold - dominant, 4)

        # ── 2. Regime Context (for regime-conditioned calibration) ─────────────
        # Captured at write-time — cannot be reconstructed later.
        # These fields enable: "Trap agent suppresses alpha ONLY in trend regimes"
        # and confidence calibration curves segmented by market condition.
        _gap_status     = self.gap_penalty_mgr.get_status()
        _gap_severity   = _gap_status.get("severity", "NONE")
        _gap_mins       = _gap_status.get("minutes_since_open", 0)
        _vix            = round(getattr(snapshot, 'india_vix', 0), 2)
        _vix_bucket     = "low" if _vix < 14 else ("high" if _vix > 20 else "medium")
        _hour           = now.hour
        _minute         = now.minute
        # Session: opening (9:15–10:00), midday (10:00–14:00), closing (14:00–15:30)
        _total_min      = _hour * 60 + _minute
        _session        = ("opening"  if _total_min < 10*60
                           else ("closing" if _total_min >= 14*60 else "midday"))
        # Regime from outputs_dict if available
        _regime_val = "UNKNOWN"
        if outputs_dict and "regime" in outputs_dict:
            _regime_val = outputs_dict["regime"].details.get("regime", "UNKNOWN")

        # ── 3. Build entry ──────────────────────────────────────────────────────
        entry = {
            "id": entry_id,
            "timestamp": now.isoformat(),
            "day_of_week": now.strftime("%A"),         # Monday … Friday
            "session": _session,                        # opening / midday / closing
            "blocked_by": blocked_by,
            "buy_prob": round(buy_prob, 4),
            "sell_prob": round(sell_prob, 4),
            "dominant": round(dominant, 4),
            "threshold": round(threshold, 4),
            "shortfall": round(threshold - dominant, 4),
            "dominant_direction": "BUY" if buy_prob >= sell_prob else "SELL",
            "price": snapshot.price,
            "atr": round(getattr(snapshot, 'atr', 0), 2),
            # ── Regime context ──────────────────────────────────────────────────
            "regime": _regime_val,                      # RANGING / STRONG_TREND_UP / etc.
            "gap_severity": _gap_severity,              # NONE / MINOR / MODERATE / CRITICAL
            "gap_minutes_elapsed": round(_gap_mins, 1),
            "india_vix": _vix,
            "vix_bucket": _vix_bucket,                  # low / medium / high
            # ── Agent attribution ───────────────────────────────────────────────
            "top_drag_agent": top_drag_agent,
            "top_drag_effect": round(top_drag_effect, 4),
            # ── Future outcome fields (filled by _resolve_pending_outcomes) ─────
            "future_move_5m":  None,
            "future_move_15m": None,
            "future_move_30m": None,
            "mode": "SIM" if self._is_simulation else "LIVE",
        }

        # ── 3. Write to JSONL (append-only, crash-safe) ─────────────────────────
        try:
            with open(self._opp_journal_path, "a", encoding="utf-8") as fh:
                fh.write(_json.dumps(entry) + "\n")
        except Exception as exc:
            self.logger.warning(f"[OPPORTUNITY] JSONL write failed: {exc}")

        # ── 4. Update in-memory rolling cache ──────────────────────────────────
        self.opportunity_journal.append(entry)
        if len(self.opportunity_journal) > self._opportunity_journal_limit:
            self.opportunity_journal = self.opportunity_journal[-self._opportunity_journal_limit:]

        # ── 5. Enqueue for future outcome labeling ─────────────────────────────
        self._pending_outcomes.append({
            "id": entry_id,
            "block_ts": now.timestamp(),
            "block_price": snapshot.price,
            "dominant_direction": entry["dominant_direction"],
            "resolved_5m": False,
            "resolved_15m": False,
            "resolved_30m": False,
        })
        # Prevent unbounded growth — max 200 pending
        if len(self._pending_outcomes) > 200:
            self._pending_outcomes = self._pending_outcomes[-200:]

        self.logger.info(
            f"📓 [OPPORTUNITY] Blocked='{blocked_by}' | "
            f"dominant={dominant:.3f} (need {threshold:.3f}, -shortfall {threshold - dominant:.3f}) | "
            f"B={buy_prob:.3f} S={sell_prob:.3f} | drag_agent={top_drag_agent} ({top_drag_effect:+.3f})"
        )

    def _resolve_pending_outcomes(self, current_price: float) -> None:
        """
        ⏳ Future Outcome Labeler

        Called at the start of every process() cycle with the current price.
        For each pending blocked setup, check if 5m / 15m / 30m have elapsed
        since the block timestamp. When they have, calculate the price move
        and patch the JSONL record with the result.

        Price move = current_price - block_price, signed relative to dominant_direction:
          - Positive = market moved in the direction that was blocked (alpha suppression candidate)
          - Negative = market moved against it (filter saved money)
        """
        import json as _json

        now_ts = time.time()
        windows = [("5m", 300), ("15m", 900), ("30m", 1800)]
        still_pending = []

        for pending in self._pending_outcomes:
            elapsed = now_ts - pending["block_ts"]
            raw_move = current_price - pending["block_price"]
            # Sign the move relative to dominant direction
            signed_move = raw_move if pending["dominant_direction"] == "BUY" else -raw_move

            updated = False
            for label, secs in windows:
                key = f"resolved_{label.replace('m', 'm')}"
                if elapsed >= secs and not pending.get(key, False):
                    pending[key] = True
                    # Update the in-memory journal entry
                    for mem_entry in self.opportunity_journal:
                        if mem_entry.get("id") == pending["id"]:
                            mem_entry[f"future_move_{label}"] = round(signed_move, 2)
                            break
                    # Append an outcome patch record to JSONL
                    patch = {
                        "_type": "outcome_patch",
                        "id": pending["id"],
                        f"future_move_{label}": round(signed_move, 2),
                        "resolved_at": datetime.now().isoformat(),
                    }
                    try:
                        with open(self._opp_journal_path, "a", encoding="utf-8") as fh:
                            fh.write(_json.dumps(patch) + "\n")
                    except Exception:
                        pass
                    updated = True

            # Keep pending if not all 30m resolved yet
            if not pending.get("resolved_30m", False):
                still_pending.append(pending)
            elif updated:
                self.logger.info(
                    f"📓 [OUTCOME] id={pending['id']} fully resolved | "
                    f"dir={pending['dominant_direction']} | "
                    f"block_price={pending['block_price']} → now={current_price} | "
                    f"30m_move={round(signed_move, 2)}"
                )

        self._pending_outcomes = still_pending

    def get_opportunity_report(self) -> dict:
        """
        Summarise the shadow journal.

        Reads from the in-memory cache (fast). For full historical analysis
        across sessions, read data/opportunity_journal.jsonl directly.

        Returns:
          - total_blocked: total suppressed setups this session
          - breakdown: per-filter stats sorted by frequency
          - agent_drag: which agents most frequently top the drag list
          - outcome_stats: average future moves for resolved setups
        """
        from collections import defaultdict
        if not self.opportunity_journal:
            return {"total_blocked": 0, "breakdown": {}, "agent_drag": {}, "outcome_stats": {}}

        breakdown: dict = defaultdict(lambda: {"count": 0, "shortfalls": []})
        drag_counts: dict = defaultdict(int)
        moves_5m, moves_15m, moves_30m = [], [], []

        for entry in self.opportunity_journal:
            key = entry["blocked_by"]
            breakdown[key]["count"] += 1
            breakdown[key]["shortfalls"].append(entry["shortfall"])
            drag_counts[entry.get("top_drag_agent", "unknown")] += 1
            if entry.get("future_move_5m") is not None:
                moves_5m.append(entry["future_move_5m"])
            if entry.get("future_move_15m") is not None:
                moves_15m.append(entry["future_move_15m"])
            if entry.get("future_move_30m") is not None:
                moves_30m.append(entry["future_move_30m"])

        summary = {}
        for key, data in breakdown.items():
            sfalls = data["shortfalls"]
            summary[key] = {
                "count": data["count"],
                "avg_shortfall": round(sum(sfalls) / len(sfalls), 4),
                "min_shortfall": round(min(sfalls), 4),
                "pct_of_total": round(data["count"] / len(self.opportunity_journal) * 100, 1),
            }

        def _avg(lst): return round(sum(lst) / len(lst), 2) if lst else None
        def _pos_pct(lst): return round(sum(1 for x in lst if x > 0) / len(lst) * 100, 1) if lst else None

        return {
            "total_blocked": len(self.opportunity_journal),
            "breakdown": dict(sorted(summary.items(), key=lambda x: -x[1]["count"])),
            "agent_drag": dict(sorted(drag_counts.items(), key=lambda x: -x[1])),
            "outcome_stats": {
                "5m":  {"avg_move": _avg(moves_5m),  "pct_positive": _pos_pct(moves_5m),  "n": len(moves_5m)},
                "15m": {"avg_move": _avg(moves_15m), "pct_positive": _pos_pct(moves_15m), "n": len(moves_15m)},
                "30m": {"avg_move": _avg(moves_30m), "pct_positive": _pos_pct(moves_30m), "n": len(moves_30m)},
            },
        }

    def get_status(self) -> dict:
        agents_status = {name: agent.get_status() for name, agent in self.agents.items()}
        return {
            "total_signals": self.signal_count,
            "last_signal": self.last_signal.to_dict() if self.last_signal else None,
            "agents": agents_status,
        }
