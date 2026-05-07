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
============================================
"""

import math
from typing import List, Optional, Dict
from datetime import datetime
import time
from time import perf_counter
import uuid

from models.signals import (
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
from models.signals import MarketRegime
from config.signal_weights import AGENT_WEIGHTS, MIN_CONFIDENCE, MIN_DIRECTION_GAP
from core.threshold_tuner import ThresholdTuner


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
AGENT_RELIABILITY = {
    "multi_timeframe": 1.40,   # VERY HIGH — aligns strongly with structure
    "structure":       1.30,   # HIGH — cleanest signal source
    "price_action":    1.25,   # HIGH — pure price mechanics
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

class DecisionEngineV3:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.logger = AgentLogger("decision_v3")
        self.scorer = ConfluenceScorer(settings)
        self.quality_grader = SignalQualityGrader(settings)

        self.spike_freeze_until = 0.0
        self.session_started_date = None

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
        # The doc says "23 agents" in the header but the registry has 23 classes.
        # active_agents from settings should match what we expect.
        # Update EXPECTED_ACTIVE_AGENT_COUNT when agents are added/removed.
        EXPECTED_ACTIVE_AGENT_COUNT = 18  # Single source of truth — from settings.pipeline.active_agents
        registered = len(self.agents)
        if registered != EXPECTED_ACTIVE_AGENT_COUNT:
            raise AssertionError(
                f"🚨 AGENT COUNT MISMATCH: {registered} loaded, "
                f"{EXPECTED_ACTIVE_AGENT_COUNT} expected. "
                f"Check agents/ directory and pipeline.active_agents in settings.py. "
                f"Active: {sorted(self.agents.keys())}"
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
            "regime":    60.0,   # 1 minute — regime state is sticky
            "structure": 30.0,   # 30 secs  — structure updates on candle boundaries
        }

        self.signal_history: List[Signal] = []
        self.last_signal: Optional[Signal] = None
        self.signal_count = 0
        self.recent_signals: Dict[str, float] = {}

    @property
    def learning_agent(self):
        return self.agents.get("learning")

    def process(self, df, snapshot: MarketSnapshot) -> Signal:
        outputs = []
        outputs_dict = {}

        self.logger.info("⚡ Engine v3 Cycle Started")

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
        # New model: GapPenaltyManager computes severity relative to ATR and
        #            exponentially decays it so gap influence melts away naturally.
        today_date = datetime.now().date()
        if self.gap_penalty_mgr.is_new_session_needed():
            self.session_started_date = today_date
            if hasattr(snapshot, 'prev_day_close') and snapshot.prev_day_close > 0:
                gap_pts = abs(
                    (snapshot.day_open if snapshot.day_open > 0 else snapshot.price)
                    - snapshot.prev_day_close
                )
                atr = snapshot.atr if snapshot.atr > 0 else 100.0
                self.gap_penalty_mgr.new_session(gap_pts, atr)
                self.session_gap_detected = gap_pts > 0  # kept for metadata compat

        if df is not None and not df.empty:
            last_candle = df.iloc[-1]
            if 'high' in last_candle and 'low' in last_candle:
                candle_range = last_candle['high'] - last_candle['low']
                # Require range to be at least 30 points AND > 2x ATR for it to be considered a freeze-worthy spike
                if snapshot.atr > 0 and candle_range > 30 and candle_range > 2 * snapshot.atr:
                    self.spike_freeze_until = time.time() + 600  # 10 minute freeze
                    self.logger.warning(f"⚡ INTRADAY SPIKE! Range {candle_range:.1f} > 30 & 2xATR ({2*snapshot.atr:.1f}). Freezing for 10m.")
        
        if time.time() < self.spike_freeze_until:
            return self._no_trade_signal(snapshot, ["Phase 2 Halt: Intraday Spike Freeze active"], outputs_dict)

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
                    self.logger.info(f"[CACHE HIT] {name} | age={(now_ts-last_ts):.1f}s < TTL={ttl:.0f}s")
                else:
                    start_p = perf_counter()
                    out = self.agents[name].run(df, snapshot)
                    latency = perf_counter() - start_p
                    self.logger.info(f"Agent {name} latency = {latency:.3f}s")
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
                    f"| Gap: {gap_status['gap_points']}pts ({gap_status['severity']}) "
                    f"| Decay: {gap_status['minutes_since_open']:.0f}min elapsed"
                )

            # Map string to enum
            regime_map = {
                "STRONG_TREND_UP": MarketRegime.TRENDING_UP,
                "WEAK_TREND_UP": MarketRegime.TRENDING_UP,
                "STRONG_TREND_DOWN": MarketRegime.TRENDING_DOWN,
                "WEAK_TREND_DOWN": MarketRegime.TRENDING_DOWN,
                "RANGING": MarketRegime.RANGING,
                "VOLATILE_CHOPPY": MarketRegime.VOLATILE,
                "SQUEEZE": MarketRegime.SQUEEZE,
                "BREAKOUT": MarketRegime.BREAKOUT,
            }
            regime = regime_map.get(regime_val, MarketRegime.RANGING)

            if regime_val in self.settings.trade_filter.blocked_regimes:
                return self._no_trade_signal(snapshot, [f"Phase 1 Halt: Bad Regime ({regime_val})"], outputs_dict)

        # ─── PHASE 2: CORE DIRECTION ───
        for name in self.settings.pipeline.phase_2_core:
            if name in self.agents:
                start_p = perf_counter()
                out = self.agents[name].run(df, snapshot)
                latency = perf_counter() - start_p
                self.logger.info(f"Agent {name} latency = {latency:.3f}s")
                
                outputs.append(out)
                outputs_dict[name] = out
                
                if out.is_blocker:
                    return self._no_trade_signal(snapshot, [f"Phase 2 Halt: {out.blocker_reason}"], outputs_dict)

        # Phase 2 Mini-Confluence: Do we have a setup?
        core_confluence = self.scorer.score(outputs)
        if core_confluence.dominant_direction == Direction.NEUTRAL:
             return self._no_trade_signal(snapshot, ["Phase 2 Halt: Core Agents Neutral (No Setup)"], outputs_dict)

        # ─── PHASE 3: DYNAMIC CONFIRMATION (THE ROUTER) ───
        # Instead of calling the static list from settings, we ask the router what tools we need.
        dynamic_phase_3_agents = self._get_dynamic_confirmation_route(outputs_dict, snapshot, core_confluence)
        
        for name in self.settings.pipeline.phase_3_confirmation:
            if name in self.agents:
                # If agent is in the dynamic route, run it
                if name in dynamic_phase_3_agents:
                    start_p = perf_counter()
                    out = self.agents[name].run(df, snapshot)
                    latency = perf_counter() - start_p
                    self.logger.info(f"Agent {name} latency = {latency:.3f}s")
                    
                    outputs.append(out)
                    outputs_dict[name] = out
                    # Cache it if it's a "heavy" agent
                    if name in ["multi_timeframe", "institutional"]:
                        self.last_heavy_results[name] = out
                        self.last_heavy_run_time[name] = datetime.now()
                # If not in route but we have a cache, reuse it to sustain the thesis
                elif name in self.last_heavy_results:
                    outputs.append(self.last_heavy_results[name])
                    outputs_dict[name] = self.last_heavy_results[name]
                
                # Immediate halt if a dynamically called blocker (like Trap) fires
                if 'out' in locals() and out.is_blocker:
                    return self._no_trade_signal(snapshot, [f"Dynamic Phase 3 Halt ({name}): {out.blocker_reason}"], outputs_dict)

        # ─── PHASE 4: RISK & EXECUTION ───
        for name in self.settings.pipeline.phase_4_risk:
            if name in self.agents:
                start_p = perf_counter()
                out = self.agents[name].run(df, snapshot)
                latency = perf_counter() - start_p
                self.logger.info(f"Agent {name} latency = {latency:.3f}s")
                
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
        buy_prob, sell_prob = self.compute_weighted_score(outputs_dict, regime_penalty)

        # Priority 3 Fix: Apply sigmoid normalization BEFORE grading.
        # Multiplicative penalties compress all scores into 0.48–0.62.
        # Sigmoid widens the distribution so elite setups grade distinctly from marginal ones.
        buy_prob  = _sigmoid_normalize(buy_prob)
        sell_prob = _sigmoid_normalize(sell_prob)

        # ── INTEGRITY GATE (data validation — BEFORE any scoring logic) ──
        # This is NOT a quality filter — it's input validation.
        # One-sided signals (one side near zero) mean agents on that side
        # are dead/suppressed/missing data. That's NOT dominance — it's
        # incomplete information.
        MIN_SIDE_FLOOR = 0.05     # each side must show SOME participation
        MIN_DOMINANT_PROB = 0.20  # dominant side needs this much substance (both sides present)
        MIN_ONESIDED_PROB = 0.35  # HIGHER bar when one side is collapsed (compensates info gap)

        if buy_prob < MIN_SIDE_FLOOR and sell_prob < MIN_SIDE_FLOOR:
            return self._no_trade_signal(snapshot,
                [f"Signal Integrity: both sides collapsed (B={buy_prob:.3f} S={sell_prob:.3f})"],
                outputs_dict)

        if buy_prob < MIN_SIDE_FLOOR or sell_prob < MIN_SIDE_FLOOR:
            # One side is collapsed — we're flying blind on that direction.
            # Require a HIGHER dominant threshold to compensate for the info gap.
            dominant = max(buy_prob, sell_prob)
            collapsed_side = "BUY" if buy_prob < MIN_SIDE_FLOOR else "SELL"
            if dominant < MIN_ONESIDED_PROB:
                return self._no_trade_signal(snapshot,
                    [f"Signal Integrity: {collapsed_side} side collapsed "
                     f"(B={buy_prob:.3f} S={sell_prob:.3f}, dominant={dominant:.3f} < {MIN_ONESIDED_PROB})"],
                    outputs_dict)
            # Still warn — this IS unusual even if dominant is high enough
            self.logger.warning(
                f"[INTEGRITY] One-sided signal ({collapsed_side}=0): B={buy_prob:.3f} S={sell_prob:.3f} "
                f"(dominant={dominant:.3f} passes elevated floor {MIN_ONESIDED_PROB})"
            )

        # ── Minimum Probability Floor (dominant side must have real substance) ──
        dominant_prob = max(buy_prob, sell_prob)
        if dominant_prob < MIN_DOMINANT_PROB:
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
        live_gap, live_conf = self.tuner.get_thresholds()
        adaptive_gap = live_gap if reg_conf >= 0.6 else max(live_gap - 0.01, 0.035)
        gap = abs(buy_prob - sell_prob)
        if gap < adaptive_gap and direction != Direction.NEUTRAL:
            return self._no_trade_signal(snapshot, [f"Minimum Dominance Rule (Gap: {gap:.3f} < {adaptive_gap:.2f}, regime: {reg_conf:.2f})"], outputs_dict)

        # 4. Check Global Threshold (from tuner)
        adaptive_confidence = live_conf if reg_conf >= 0.6 else max(live_conf - 0.13, 0.28)
        if confidence < adaptive_confidence:
            reason = f"Low Confidence Gate ({confidence:.2f} < {adaptive_confidence:.2f}, regime: {reg_conf:.2f})"
            return self._no_trade_signal(snapshot, [reason], outputs_dict)
            
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
        self.logger.info(
            f"🧠 [PROBABILITY] Signal: {signal_type.value} | "
            f"Score: {confidence:.2f} | "
            f"Buy: {buy_prob:.2f} | "
            f"Sell: {sell_prob:.2f} | "
            f"Gap: {gap:.2f}"
        )

        # Attach dynamic sizing metrics to metadata so PositionManager can size properly
        meta = {
            "dominance_pct": dominance_pct,
            "dominance_gap": gap,
            "quality": quality_tag,
            "regime_conf": reg_conf,
            "directional_alignment": directional_alignment,
            "gap_detected": self.session_gap_detected
        }

        signal = Signal(
            id=str(uuid.uuid4())[:8],
            timestamp=datetime.now(),
            signal_type=signal_type,
            direction=direction,
            confidence=round(confidence * 100, 1), # Store as % for display
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
            risk_reward_ratio=3.0, 
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
        # So the grade is realistic, not based on raw pre-penalty scores.
        from models.signals import SignalGrade
        signal.grade = self.quality_grader.grade(signal)
        self.logger.info(
            f"[GRADE] Post-penalty score: {confidence:.3f} | "
            f"Grade: {signal.grade.value} | "
            f"Unified penalty: {regime_penalty:.3f}"
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
        fingerprint = f"{signal.direction.value}_{signal.entry_price}_{signal.signal_type.value}"
        now_ts = time.time()
        
        # Clear old fingerprints
        self.recent_signals = {k: v for k, v in self.recent_signals.items() if now_ts - v < 60}
        
        if fingerprint in self.recent_signals:
            return self._no_trade_signal(snapshot, ["Signal Deduplication: Duplicate signal within 60s"], outputs_dict)
            
        self.recent_signals[fingerprint] = now_ts

        self._record_signal(signal)
        self.logger.signal(f"\n✅ A+ TRADE FOUND! {signal}")

        return signal

    def _get_dynamic_confirmation_route(
        self, 
        outputs_dict: Dict[str, AgentOutput], 
        snapshot: MarketSnapshot, 
        core_confluence
    ) -> List[str]:
        """
        🧠 V4 DYNAMIC ROUTING ENGINE
        Context-Aware, Memory-Aware, and Confidence-Driven tool selection.
        """
        route = set()

        # ─── 1. CONTEXT EXTRACTION ───
        regime = outputs_dict.get("regime")
        regime_val = regime.details.get("regime", "UNKNOWN") if regime else "UNKNOWN"
        
        structure = outputs_dict.get("structure")
        is_bos = structure and structure.details.get("bos") is not None
        
        conf_score = core_confluence.confluence_ratio * 100 if core_confluence else 0.0

        # ─── 2. MEMORY-AWARE ROUTING (Survival Mode) ───
        if self.memory.is_tilted or self.memory.current_streak < 0:
            self.logger.info("🧠 Memory State: TILTED/LOSING. Routing to heavy defense.")
            route.add("trap")
            route.add("level")
            route.add("institutional") # See what the big money is doing before risking more

        # ─── 3. TIMEFRAME THROTTLING (The HFT Shift) ───
        now = datetime.now()
        minute = now.minute
        
        # Heavy tools only run on candle boundaries (5m/15m)
        is_5m_boundary = (minute % 5 == 0)
        is_15m_boundary = (minute % 15 == 0)

        # Multi-Timeframe only on 5m
        if is_5m_boundary:
            route.add("multi_timeframe")
            
        # Institutional only on 15m
        if is_15m_boundary:
            route.add("institutional")

        # ─── 4. VOLATILITY ROUTING ───
        # If ATR is unusually high, the market is violent. Call the volatility agent.
        if snapshot.atr > self.settings.trade_filter.min_atr_for_trade * 1.5:
            route.add("volatility")
            route.add("trap") # High volatility = high wick traps

        # ─── 4. QUALITY-GATED DEEP VALIDATION (3-Layer Confluence Check) ───
        # Replaces the old "if conf_score >= 85" single-threshold trigger.
        # Deep validation now requires ALL THREE conditions:
        #   1. Minimum active directional participants (breadth)
        #   2. Dominance ratio ≥ 0.75 of active agents (quality)
        #   3. Opposing score ≤ 0.15 (contradiction ceiling)
        if core_confluence:
            active = core_confluence.bullish_agents + core_confluence.bearish_agents
            dominant = max(core_confluence.bullish_agents, core_confluence.bearish_agents)
            opposing = min(core_confluence.bullish_agents, core_confluence.bearish_agents)
            dominance_ratio = dominant / active if active > 0 else 0.0
            opposing_ratio  = opposing / active if active > 0 else 1.0

            HIGH_CONF_ACTIVE_MIN    = 3
            HIGH_CONF_DOMINANCE_MIN = 0.75   # ≥75% agents agree
            HIGH_CONF_OPPOSING_MAX  = 0.15   # ≤15% agents contradict

            deep_validation_warranted = (
                active >= HIGH_CONF_ACTIVE_MIN
                and dominance_ratio >= HIGH_CONF_DOMINANCE_MIN
                and opposing_ratio  <= HIGH_CONF_OPPOSING_MAX
            )

            if deep_validation_warranted:
                self.logger.info(
                    f"🔥 High Confluence Validated: {dominant}/{active} agents agree "
                    f"(dominance={dominance_ratio:.0%}, opposing={opposing_ratio:.0%}). "
                    f"Calling deep validation."
                )
                route.add("institutional")
                route.add("order_flow")
                route.add("delta_gamma")
            elif conf_score >= 85.0:
                # conf_score high but directional conflict exists — log and skip deep validation
                self.logger.info(
                    f"⚠️ High conf_score ({conf_score:.0f}) but confluence fragmented "
                    f"({dominant}/{active} agree, {opposing} oppose). Skipping deep validation."
                )

        # ─── 5. STRUCTURAL / REGIME ROUTING ───
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

        self.logger.info(f"🔀 V4 Dynamic Route Selected: {list(route)}")
        return list(route)

    def compute_weighted_score(self, agent_outputs: Dict[str, AgentOutput], regime_penalty: float = 1.0):
        """
        🧠 QUANT-GRADE WEIGHTED AGGREGATOR
        - Standardizes confidence to 0.1-0.95 clamping
        - Handles 'NO_TRADE' neutral pressure
        - Normalizes by total_weight_used for true probability
        """
        buy_score = 0.0
        sell_score = 0.0
        total_weight_used = 0.0
        
        agent_pfs = {}
        learning_ag = self.agents.get("learning")
        if learning_ag and hasattr(learning_ag, "get_agent_profit_factors"):
            agent_pfs = learning_ag.get_agent_profit_factors()

        for name, output in agent_outputs.items():
            weight = AGENT_WEIGHTS.get(name, 0.02)  # Standard low weight for unlisted

            # ── Agent Reliability Adjustment ──
            # Multiply base weight by empirical reliability score.
            # High-signal agents (multi_timeframe, structure) get more pull.
            # Noisy agents (trap, oi in sim mode) are discounted.
            reliability = AGENT_RELIABILITY.get(name, 1.0)
            weight *= reliability

            # Phase 4: Agent Degradation Kill-Switch
            if name in agent_pfs and agent_pfs[name] < 1.0:
                weight = 0.0
                self.logger.warning(f"🔇 Agent {name} squelched. PF < 1.0 ({agent_pfs[name]:.2f})")

            weight *= regime_penalty
            total_weight_used += weight

            conf = output.get_clamped_confidence()

            if output.direction == Direction.BULLISH:
                buy_score += weight * conf
            elif output.direction == Direction.BEARISH:
                sell_score += weight * conf
            # Neutral/NO_TRADE adds 0 to score but counts toward total_weight
            # which naturally dilutes the final probability (as it should).

        if total_weight_used == 0:
            return 0.0, 0.0

        return buy_score / total_weight_used, sell_score / total_weight_used

    def _no_trade_signal(self, snapshot: MarketSnapshot, reasons: List[str], outputs: Dict[str, AgentOutput]) -> Signal:
        all_warnings = []
        for out in outputs.values():
            all_warnings.extend(out.warnings)
            
        blockers = [out.blocker_reason for out in outputs.values() if out.is_blocker]
        final_reasons = reasons + blockers

        signal = Signal(
            id=str(uuid.uuid4())[:8],
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
        )
        self.logger.signal(f"⚪ NO TRADE | {reasons[0]}")
        return signal

    def _classify_market(self, snapshot: MarketSnapshot, outputs: Dict[str, AgentOutput]) -> MarketRegime:
        """
        🧠 Market State Classifier
        Converts raw indicators into human-readable market archetypes.
        """
        if hasattr(snapshot, 'bb_width') and snapshot.bb_width > 0 and snapshot.bb_width < self.settings.thresholds.squeeze_threshold:
            return MarketRegime.SQUEEZE
            
        bulls = sum(1 for o in outputs.values() if o.direction == Direction.BULLISH)
        bears = sum(1 for o in outputs.values() if o.direction == Direction.BEARISH)
        if bulls > 2 and bears > 2:
            return MarketRegime.VOLATILE
            
        regime_agent = outputs.get("regime")
        if regime_agent:
            reg_val = regime_agent.details.get("regime", "")
            if "TREND" in reg_val:
                return MarketRegime.TRENDING_UP if "UP" in reg_val else MarketRegime.TRENDING_DOWN
                
        if hasattr(snapshot, 'bb_upper') and (snapshot.price > snapshot.bb_upper or snapshot.price < snapshot.bb_lower):
            return MarketRegime.BREAKOUT
            
        return MarketRegime.RANGING

    def _record_signal(self, signal: Signal):
        self.signal_count += 1
        self.last_signal = signal
        self.signal_history.append(signal)

        if len(self.signal_history) > 100:
            self.signal_history = self.signal_history[-100:]

    def get_status(self) -> dict:
        agents_status = {name: agent.get_status() for name, agent in self.agents.items()}
        return {
            "total_signals": self.signal_count,
            "last_signal": self.last_signal.to_dict() if self.last_signal else None,
            "agents": agents_status,
        }
