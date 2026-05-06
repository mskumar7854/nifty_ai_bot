"""
============================================
🧠 DECISION ENGINE v3 (CLAUDE-STYLE ROUTING)
Why: Transforms the system from a linear 
     pipeline to a dynamic, phase-based 
     agentic loop. Saves compute, reduces 
     latency, and stops bad trades early.
============================================
"""

from typing import List, Optional, Dict
from datetime import datetime
import time
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
from utils.logger import AgentLogger
from config.settings import Settings
from models.signals import MarketRegime
from config.signal_weights import AGENT_WEIGHTS, MIN_CONFIDENCE, MIN_DIRECTION_GAP

class DecisionEngineV3:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.logger = AgentLogger("decision_v3")
        self.scorer = ConfluenceScorer(settings)
        self.quality_grader = SignalQualityGrader(settings)

        self.spike_freeze_until = 0.0
        self.session_started_date = None
        self.session_gap_detected = False

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

        # ── ⚡ HFT HEAVY CACHE ──
        self.last_heavy_results: Dict[str, AgentOutput] = {}
        self.last_heavy_run_time: Dict[str, datetime] = {}

        self.signal_history: List[Signal] = []
        self.last_signal: Optional[Signal] = None
        self.signal_count = 0

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
        today_date = datetime.now().date()
        if self.session_started_date != today_date:
            self.session_started_date = today_date
            self.session_gap_detected = False
            if hasattr(snapshot, 'prev_day_close') and snapshot.prev_day_close > 0:
                gap_pct = abs(snapshot.open - snapshot.prev_day_close) / snapshot.prev_day_close * 100
                if gap_pct > 0.7:
                    self.session_gap_detected = True
                    self.logger.warning(f"⚠️ GAP DETECTED: {gap_pct:.2f}% > 0.7%. Halving risk for the session.")

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
                out = self.agents[name].run(df, snapshot)
                outputs.append(out)
                outputs_dict[name] = out
                
                if out.is_blocker:
                    return self._no_trade_signal(snapshot, [f"Phase 1 Halt: {out.blocker_reason}"], outputs_dict)

        # Explicit Regime Verification
        regime = MarketRegime.UNKNOWN
        regime_penalty = 1.0
        reg_conf = 1.0  # Default — no regime agent means full confidence
        if "regime" in outputs_dict:
            regime_agent_output = outputs_dict["regime"]
            regime_val = regime_agent_output.details.get("regime", "RANGING")

            # ── FIX #1: SMOOTH REGIME SCALING (replaces hard 0.5 halving) ──
            # Old: reg_conf < 0.6 → weights *= 0.5  (cliff edge, causes suffocation)
            # New: smooth proportional scale, clamped to never go below 0.70
            #      At 0.55 conf: penalty = max(0.70, 0.55) = 0.70  (was 0.50)
            #      At 0.40 conf: hard block (unchanged)
            #      At 0.60+ conf: penalty = 1.0 (unchanged)
            reg_conf = regime_agent_output.get_clamped_confidence()
            if reg_conf < 0.4:
                return self._no_trade_signal(snapshot, [f"Phase 4 Halt: Regime Confidence Too Low ({reg_conf:.2f})"], outputs_dict)
            elif reg_conf < 0.6:
                regime_penalty = max(0.70, reg_conf)  # smooth scale, floor at 0.70
                self.logger.warning(f"⚠️ Regime confidence low ({reg_conf:.2f}). Applying scaled penalty ({regime_penalty:.2f}x).")

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
                out = self.agents[name].run(df, snapshot)
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
                    out = self.agents[name].run(df, snapshot)
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
                if out.is_blocker:
                    return self._no_trade_signal(snapshot, [f"Dynamic Phase 3 Halt ({name}): {out.blocker_reason}"], outputs_dict)

        # ─── PHASE 4: RISK & EXECUTION ───
        for name in self.settings.pipeline.phase_4_risk:
            if name in self.agents:
                out = self.agents[name].run(df, snapshot)
                outputs.append(out)
                outputs_dict[name] = out
                
                if out.is_blocker:
                    return self._no_trade_signal(snapshot, [f"Phase 4 Halt: {out.blocker_reason}"], outputs_dict)

        # Double check Risk confidence
        if "risk" in outputs_dict and outputs_dict["risk"].confidence == 0:
            return self._no_trade_signal(snapshot, ["Phase 4 Halt: Risk limits reached"], outputs_dict)

        # ─── PHASE 5: FINAL SYNTHESIS & PROBABILISTIC GRADING ───
        # 1. Compute Weighted Probability Matrix
        buy_prob, sell_prob = self.compute_weighted_score(outputs_dict, regime_penalty)
        
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

        # 3. Minimum Dominance Rule (Adaptive Edge Guard)
        # ── Prevents overtrading chop by requiring a minimum buy/sell score gap.
        # Two-tier threshold — tighter in clear regime, relaxed (but not noise) in uncertain:
        #   reg_conf >= 0.6: require gap >= 0.05 (MIN_DIRECTION_GAP)  — full selectivity
        #   reg_conf <  0.6: require gap >= 0.04  — allows real edges, blocks 0.01-0.03 noise
        # NOTE: 0.03 (previous) was too close to noise floor — risk of chop trades.
        #       0.04 is the measured minimum for a signal to have intraday substance.
        adaptive_gap = MIN_DIRECTION_GAP if reg_conf >= 0.6 else 0.04
        gap = abs(buy_prob - sell_prob)
        if gap < adaptive_gap and direction != Direction.NEUTRAL:
            return self._no_trade_signal(snapshot, [f"Minimum Dominance Rule (Gap: {gap:.3f} < {adaptive_gap:.2f}, regime: {reg_conf:.2f})"], outputs_dict)

        # 4. Check Global Threshold
        # ── FIX #3: ADAPTIVE CONFIDENCE GATE ──
        # When regime penalty is active, the max achievable confidence is
        # ~0.70 * original_score. With 0.55 regime, ceiling drops to ~0.38.
        # Static gate of 0.45 is unreachable — permanent lock.
        # Solution: lower gate to 0.32 when regime is uncertain.
        #   reg_conf >= 0.6: gate = MIN_CONFIDENCE (0.45)
        #   reg_conf < 0.6:  gate = 0.32 — still filters weak signals but is reachable
        adaptive_confidence = MIN_CONFIDENCE if reg_conf >= 0.6 else 0.32
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
            confidence = max(0.0, confidence - 10.0)
            warnings.append("MetaFilter: Expiry Risk HIGH -> Reduced Confidence")

        learning_out = outputs_dict.get("learning")
        if learning_out and learning_out.strength == Strength.STRONG:
            confidence = min(100.0, confidence + 10.0)
            reasons.append("MetaFilter: Learning Agent Confirms -> Boosted Confidence")

        structure_out = outputs_dict.get("structure")
        if structure_out:
            if structure_out.details.get("bos"):
                reasons.append(f"Structure: BOS {structure_out.details['bos']['direction']}")
                confidence = min(100.0, confidence + 5.0)
            if structure_out.details.get("choch"):
                reasons.append(f"Structure: CHoCH to {structure_out.details['choch']['to']}")
                confidence = min(100.0, confidence + 10.0)

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

        # Grade the Signal
        signal.grade = self.quality_grader.grade(signal)

        # Check Minimum Quality standard
        min_grade = self.settings.trade_filter.min_grade_to_trade
        grade_map = {"A+": 5, "A": 4, "B+": 3, "B": 2, "C": 1}
        
        if grade_map.get(signal.grade.value, 1) < grade_map.get(min_grade, 2):
            signal = self._no_trade_signal(snapshot, [f"Signal Quality too low ({signal.grade.value})"], outputs_dict)
            self._record_signal(signal)
            return signal

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

        # ─── 4. CONFIDENCE-BASED ROUTING (Deep Dive on A+ Setups) ───
        if conf_score >= 85.0:
            self.logger.info("🔥 High Confluence Detected. Calling deep validation.")
            route.add("institutional")
            route.add("order_flow")
            route.add("delta_gamma")

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
            weight = AGENT_WEIGHTS.get(name, 0.02) # Standard low weight for unlisted
            
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
