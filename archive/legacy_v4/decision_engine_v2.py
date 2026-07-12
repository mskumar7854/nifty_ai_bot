"""
============================================
🧠 DECISION ENGINE v2
Why: The brain of the operation. Takes inputs
     from 18 agents, calculates confluence,
     adjusts for regime, checks blockers,
     and grades the final signal.
============================================
"""

from typing import List, Optional, Dict
from datetime import datetime

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
from utils.logger import AgentLogger
from config.settings import Settings
from models.signals import MarketRegime

class DecisionEngineV2:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.logger = AgentLogger("decision_v2")
        self.scorer = ConfluenceScorer(settings)
        self.quality_grader = SignalQualityGrader(settings)
        
        # 1. Define Agent Registry
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
        
        # 2. Dynamically load all registered agents
        self.agents = {
            name: agent_class(settings)
            for name, agent_class in AGENT_REGISTRY.items()
        }

        self.signal_history: List[Signal] = []
        self.last_signal: Optional[Signal] = None
        self.signal_count = 0

    @property
    def learning_agent(self):
        return self.agents.get("learning")

    def process(self, df, snapshot: MarketSnapshot) -> Signal:
        # 0. Market Open Filter (PRO safeguard)
        current_time = datetime.now().strftime("%H:%M")
        if current_time < self.settings.trade_filter.market_open_safe_time:
            signal = self._no_trade_signal(
                snapshot, 
                [f"Market Opening Chaos (Wait until {self.settings.trade_filter.market_open_safe_time})"],
                {}
            )
            return signal

        # 1. Collect outputs from all agents
        outputs = []
        outputs_dict = {}
        for name, agent in self.agents.items():
            out = agent.run(df, snapshot)
            outputs.append(out)
            outputs_dict[name] = out

        # 2. Check Blockers
        blockers = [o for o in outputs if o.is_blocker]
        if blockers:
            reasons = [b.blocker_reason for b in blockers]
            signal = self._no_trade_signal(snapshot, reasons, outputs_dict)
            self._record_signal(signal)
            return signal

        # Risk check using risk agent
        risk_out = outputs_dict.get("risk")
        if risk_out and risk_out.confidence == 0:
            signal = self._no_trade_signal(snapshot, ["Risk limits reached"], outputs_dict)
            self._record_signal(signal)
            return signal

        # 3. Calculate Confluence
        confluence = self.scorer.score(outputs)

        # 4. Detect Regime (Using RegimeAgent)
        regime_out = outputs_dict.get("regime")
        if regime_out:
            regime_val = regime_out.details.get("regime", "RANGING")
            # Map DetailedRegime string to MarketRegime enum
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
        else:
            regime = MarketRegime.UNKNOWN

        # 5. Check Confluence Thresholds
        if confluence.dominant_direction == Direction.NEUTRAL:
            signal = self._no_trade_signal(snapshot, ["Neutral confluence"], outputs_dict)
            self._record_signal(signal)
            return signal
            
        conf_ratio = confluence.confluence_ratio * 100
        if conf_ratio < self.settings.thresholds.min_confidence:
            signal = self._no_trade_signal(snapshot, [f"Low confluence ratio ({conf_ratio:.1f}%)"], outputs_dict)
            self._record_signal(signal)
            return signal
            
        direction_agents = confluence.bullish_agents if confluence.dominant_direction == Direction.BULLISH else confluence.bearish_agents
        if direction_agents < self.settings.thresholds.min_confluence_agents:
            signal = self._no_trade_signal(snapshot, [f"Not enough agreeing agents ({direction_agents})"], outputs_dict)
            self._record_signal(signal)
            return signal

        # 6. Build Base Signal
        direction = confluence.dominant_direction
        signal_type = SignalType.BUY_CE if direction == Direction.BULLISH else SignalType.BUY_PE
        confidence = conf_ratio

        strength = Strength.STRONG if confidence >= 80 else (Strength.MODERATE if confidence >= 65 else Strength.WEAK)

        reasons = []
        warnings = []
        for out in outputs:
            if out.direction == direction and out.details:
                reasons.append(f"{out.agent_name}: {out.strength.value}")
            if out.warnings:
                warnings.extend(out.warnings)

        # Meta Decision Filter
        decay_out = outputs_dict.get("decay")
        if decay_out and decay_out.is_blocker:
            # Although standard blocker loop catches it, this explicitly handles decay blocking logic
            signal = self._no_trade_signal(snapshot, [decay_out.blocker_reason], outputs_dict)
            self._record_signal(signal)
            return signal

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
            if structure_out.details.get("ob_verdict"):
                reasons.append(f"Structure: {structure_out.details['ob_verdict']}")
                confidence = min(100.0, confidence + 5.0)

        # Get trade parameters from risk agent
        trade_params = self.agents["risk"].get_trade_params(direction, snapshot.price, snapshot.atr)
        
        agent_votes = {
            name: {
                "direction": out.direction.value,
                "confidence": out.confidence,
            }
            for name, out in outputs_dict.items()
        }

        signal = Signal(
            timestamp=datetime.now(),
            signal_type=signal_type,
            direction=direction,
            confidence=round(confidence, 1),
            strength=strength,
            entry_price=trade_params.get("entry", snapshot.price),
            stop_loss=trade_params.get("stop_loss", 0),
            target_1=trade_params.get("target_1", 0),
            target_2=trade_params.get("target_2", 0),
            target_3=trade_params.get("target_3", 0),
            position_size=trade_params.get("position_size", 0),
            regime=regime,
            confluence=confluence,
            risk_reward_ratio=3.0, # Approximate
            agent_votes=agent_votes,
            reasons=reasons[:5],
            warnings=warnings[:5]
        )

        # 7. Grade the Signal
        signal.grade = self.quality_grader.grade(signal)

        # 8. Check Minimum Quality
        min_grade = self.settings.thresholds.signal_quality_min
        grade_map = {"A+": 5, "A": 4, "B": 3, "C": 2, "D": 1}
        
        if grade_map.get(signal.grade.value, 1) < grade_map.get(min_grade, 2):
            signal = self._no_trade_signal(snapshot, [f"Signal Quality too low ({signal.grade.value})"], outputs_dict)
            self._record_signal(signal)
            return signal

        self._record_signal(signal)
        self.logger.signal(f"\n{signal}")

        return signal

    def _no_trade_signal(self, snapshot: MarketSnapshot, reasons: List[str], outputs: Dict[str, AgentOutput]) -> Signal:
        all_warnings = []
        for out in outputs.values():
            all_warnings.extend(out.warnings)

        signal = Signal(
            timestamp=datetime.now(),
            signal_type=SignalType.NO_TRADE,
            direction=Direction.NEUTRAL,
            confidence=0,
            strength=Strength.WEAK,
            entry_price=snapshot.price,
            reasons=reasons,
            warnings=all_warnings[:5],
            agent_votes={
                name: {
                    "direction": out.direction.value,
                    "confidence": out.confidence,
                }
                for name, out in outputs.items()
            },
        )
        self.logger.signal(f"⚪ NO TRADE | Reasons: {reasons}")
        return signal

    def _record_signal(self, signal: Signal):
        self.signal_count += 1
        self.last_signal = signal
        self.signal_history.append(signal)

        if len(self.signal_history) > 100:
            self.signal_history = self.signal_history[-100:]

    def get_status(self) -> dict:
        agents_status = {}
        for name, agent in self.agents.items():
            agents_status[name] = agent.get_status()
            
        return {
            "total_signals": self.signal_count,
            "last_signal": self.last_signal.to_dict() if self.last_signal else None,
            "agents": agents_status,
        }
