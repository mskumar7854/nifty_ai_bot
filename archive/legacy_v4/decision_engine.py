"""
============================================
🧠 DECISION ENGINE — THE MASTER AI BRAIN
Combines all agent outputs into a final
trading signal with confidence scoring
============================================
"""

from datetime import datetime
from typing import Dict, List, Optional

from models.signals import (
    AgentOutput, Signal, SignalType, Direction, Strength, MarketSnapshot
)
from agents import (
    MarketAgent, MomentumAgent, OIAgent,
    TrapAgent, SentimentAgent, RiskAgent,
    LearningAgent, ExpiryDayAgent, DecayAgent
)
from utils.logger import AgentLogger
from config.settings import Settings


class DecisionEngine:
    """
    The brain that makes the final call.

    Flow:
    1. Collect all agent outputs
    2. Check for BLOCKERS (risk, trap)
    3. Calculate weighted consensus
    4. Generate final signal with trade params
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.logger = AgentLogger("decision")
        self.weights = settings.thresholds.agent_weights
        self.min_confidence = settings.thresholds.min_confidence

        # Initialize all agents
        self.market_agent = MarketAgent(settings)
        self.momentum_agent = MomentumAgent(settings)
        self.oi_agent = OIAgent(settings)
        self.trap_agent = TrapAgent(settings)
        self.sentiment_agent = SentimentAgent(settings)
        self.risk_agent = RiskAgent(settings)

        # Advanced Intelligence Agents
        self.learning_agent = LearningAgent(settings)
        self.expiry_day_agent = ExpiryDayAgent(settings)
        self.decay_agent = DecayAgent(settings)

        # Signal history
        self.signal_history: List[Signal] = []
        self.last_signal: Optional[Signal] = None
        self.signal_count = 0

    def process(
        self, df, snapshot: MarketSnapshot
    ) -> Signal:
        """
        MAIN PROCESSING PIPELINE

        Steps:
        1. Run all agents
        2. Check blockers
        3. Calculate consensus
        4. Build final signal
        """

        self.logger.signal("━━━ Processing cycle started ━━━")

        # ── STEP 1: RUN ALL AGENTS ──
        outputs: Dict[str, AgentOutput] = {}

        outputs["market"] = self.market_agent.run(df, snapshot)
        outputs["momentum"] = self.momentum_agent.run(df, snapshot)
        outputs["oi"] = self.oi_agent.run(df, snapshot)
        outputs["trap"] = self.trap_agent.run(df, snapshot)
        outputs["sentiment"] = self.sentiment_agent.run(df, snapshot)
        outputs["risk"] = self.risk_agent.run(df, snapshot)

        # Advanced Intelligence Agents
        outputs["learning"] = self.learning_agent.run(df, snapshot)
        outputs["expiry_day"] = self.expiry_day_agent.run(df, snapshot)
        outputs["decay"] = self.decay_agent.run(df, snapshot)

        # ── STEP 2: CHECK BLOCKERS ──
        blockers = self._check_blockers(outputs)

        if blockers:
            signal = self._no_trade_signal(
                snapshot, blockers, outputs
            )
            self._record_signal(signal)
            return signal

        # ── STEP 3: CALCULATE CONSENSUS ──
        direction, confidence, reasons = self._calculate_consensus(outputs)

        # ── STEP 4: CONFIDENCE CHECK ──
        if confidence < self.min_confidence:
            signal = self._no_trade_signal(
                snapshot,
                [f"Confidence too low ({confidence:.1f}% < {self.min_confidence}%)"],
                outputs
            )
            self._record_signal(signal)
            return signal

        # ── STEP 5: BUILD FINAL SIGNAL ──
        signal = self._build_signal(
            direction, confidence, reasons, snapshot, outputs
        )

        self._record_signal(signal)

        # ── STRUCTURED LOGGING FOR PRO DEBUGGING ──
        self.logger.info({
            "price": snapshot.price,
            "rsi": round(snapshot.rsi, 1),
            "vix": round(snapshot.india_vix, 2),
            "bbw": round(snapshot.bb_width, 2),
            "regime": signal.regime.value if hasattr(signal.regime, 'value') else str(signal.regime),
            "decision": signal.signal_type.value,
            "confidence": signal.confidence,
            "grade": signal.grade.value if hasattr(signal.grade, 'value') else str(signal.grade),
        })

        return signal

    def _check_blockers(self, outputs: Dict[str, AgentOutput]) -> List[str]:
        """
        Check for conditions that BLOCK trading entirely.
        Returns list of blocker reasons (empty = OK to trade)
        """
        blockers = []

        # BLOCKER 1: Risk agent says NO
        risk_output = outputs["risk"]
        if risk_output.confidence == 0:
            blockers.append("Risk limits reached")

        if risk_output.strength == Strength.WEAK and risk_output.confidence < 30:
            blockers.append("Risk conditions unfavorable")

        # BLOCKER 2: Trap detected with high confidence
        trap_output = outputs["trap"]
        if trap_output.confidence >= 70:
            blockers.append(
                f"Trap detected: {trap_output.details.get('trap_types', [])}"
            )

        # BLOCKER 3: Sentiment extremely poor
        sentiment_output = outputs["sentiment"]
        if sentiment_output.confidence < 25:
            blockers.append("Market conditions extremely unfavorable")

        # BLOCKER 4: Market + Momentum conflict
        market_dir = outputs["market"].direction
        momentum_dir = outputs["momentum"].direction

        if (market_dir == Direction.BULLISH and
            momentum_dir == Direction.BEARISH) or \
           (market_dir == Direction.BEARISH and
            momentum_dir == Direction.BULLISH):
            if (outputs["market"].confidence > 60 and
                outputs["momentum"].confidence > 60):
                blockers.append("Market and Momentum agents in conflict")

        # ── ADVANCED BLOCKERS ──
        # BLOCKER 5: Expiry Day Agent
        if "expiry_day" in outputs:
            exp_out = outputs["expiry_day"]
            if exp_out.confidence <= self.settings.thresholds.blocker_agents.get("expiry_day", 15.0) and exp_out.direction == Direction.NEUTRAL:
                blockers.append(f"Expiry Block: {exp_out.details.get('verdict', 'Blocked')}")

        # BLOCKER 6: Decay Agent
        if "decay" in outputs:
            dec_out = outputs["decay"]
            if dec_out.confidence <= self.settings.thresholds.blocker_agents.get("decay", 20.0):
                blockers.append(f"Decay Block: {dec_out.details.get('verdict', 'Blocked')}")

        # BLOCKER 7: Learning Agent
        if "learning" in outputs:
            lrn_out = outputs["learning"]
            if lrn_out.confidence <= self.settings.thresholds.blocker_agents.get("learning", 25.0):
                blockers.append(f"Learning Block: {lrn_out.details.get('verdict', 'Blocked')}")

        if blockers:
            self.logger.warning(f"BLOCKED: {blockers}")

        return blockers

    def _calculate_consensus(
        self, outputs: Dict[str, AgentOutput]
    ) -> tuple:
        """
        Calculate weighted consensus from all agents.
        Returns: (direction, confidence, reasons)
        """

        bull_score = 0
        bear_score = 0
        total_weight = 0
        reasons = []

        # Directional agents (market, momentum, oi)
        directional_agents = ["market", "momentum", "oi", "expiry_day"]

        for agent_name in directional_agents:
            output = outputs.get(agent_name)
            if not output: continue
            weight = self.weights.get(agent_name, 0.2)

            if output.direction == Direction.BULLISH:
                bull_score += output.confidence * weight
                reasons.append(
                    f"{agent_name.upper()}: BULLISH ({output.confidence:.0f}%)"
                )
            elif output.direction == Direction.BEARISH:
                bear_score += output.confidence * weight
                reasons.append(
                    f"{agent_name.upper()}: BEARISH ({output.confidence:.0f}%)"
                )
            else:
                reasons.append(
                    f"{agent_name.upper()}: NEUTRAL ({output.confidence:.0f}%)"
                )

            total_weight += weight

        # Trap agent adjusts confidence DOWN
        trap_output = outputs["trap"]
        trap_penalty = 0
        if trap_output.confidence > 40:
            trap_penalty = trap_output.confidence * self.weights.get("trap", 0.15)
            reasons.append(f"TRAP: Penalty -{trap_penalty:.0f}")

        # Sentiment agent adjusts confidence
        sentiment_output = outputs["sentiment"]
        sentiment_modifier = (sentiment_output.confidence / 100) * \
                             self.weights.get("sentiment", 0.1) * 100

        # Calculate final scores
        if total_weight > 0:
            bull_score = bull_score / total_weight
            bear_score = bear_score / total_weight

        # Apply modifiers
        if bull_score > bear_score:
            direction = Direction.BULLISH
            raw_confidence = bull_score
        elif bear_score > bull_score:
            direction = Direction.BEARISH
            raw_confidence = bear_score
        else:
            direction = Direction.NEUTRAL
            raw_confidence = 0

        # Apply trap penalty and sentiment modifier
        final_confidence = raw_confidence - trap_penalty + \
                          (sentiment_modifier * 0.5)
        final_confidence = max(0, min(100, final_confidence))

        return direction, final_confidence, reasons

    def _build_signal(
        self,
        direction: Direction,
        confidence: float,
        reasons: List[str],
        snapshot: MarketSnapshot,
        outputs: Dict[str, AgentOutput],
    ) -> Signal:
        """Build the final trading signal with parameters"""

        # Determine signal type
        if direction == Direction.BULLISH:
            signal_type = SignalType.BUY_CE
        elif direction == Direction.BEARISH:
            signal_type = SignalType.BUY_PE
        else:
            signal_type = SignalType.NO_TRADE

        # Get trade parameters from risk agent
        trade_params = self.risk_agent.get_trade_params(
            direction, snapshot.price, snapshot.atr
        )

        # Determine strength
        if confidence >= 85:
            strength = Strength.STRONG
        elif confidence >= 65:
            strength = Strength.MODERATE
        else:
            strength = Strength.WEAK

        # Collect all warnings
        all_warnings = []
        for output in outputs.values():
            all_warnings.extend(output.warnings)

        # Build vote summary
        agent_votes = {
            name: {
                "direction": output.direction.value,
                "confidence": output.confidence,
            }
            for name, output in outputs.items()
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
            position_size=trade_params.get("position_size", 0),
            agent_votes=agent_votes,
            reasons=reasons,
            warnings=all_warnings[:5],  # Limit warnings
        )

        self.logger.signal(f"\n{signal}")

        return signal

    def _no_trade_signal(
        self,
        snapshot: MarketSnapshot,
        reasons: List[str],
        outputs: Dict[str, AgentOutput],
    ) -> Signal:
        """Build a NO TRADE signal"""

        all_warnings = []
        for output in outputs.values():
            all_warnings.extend(output.warnings)

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
                    "direction": output.direction.value,
                    "confidence": output.confidence,
                }
                for name, output in outputs.items()
            },
        )

        self.logger.signal(f"⚪ NO TRADE | Reasons: {reasons}")

        return signal

    def _record_signal(self, signal: Signal):
        """Store signal in history"""
        self.signal_count += 1
        self.last_signal = signal
        self.signal_history.append(signal)

        # Keep only last 100 signals
        if len(self.signal_history) > 100:
            self.signal_history = self.signal_history[-100:]

    def get_status(self) -> dict:
        """Get engine status for dashboard"""
        return {
            "total_signals": self.signal_count,
            "last_signal": self.last_signal.to_dict() if self.last_signal else None,
            "agents": {
                "market": self.market_agent.get_status(),
                "momentum": self.momentum_agent.get_status(),
                "oi": self.oi_agent.get_status(),
                "trap": self.trap_agent.get_status(),
                "sentiment": self.sentiment_agent.get_status(),
                "risk": self.risk_agent.get_status(),
                "learning": self.learning_agent.get_status(),
                "expiry_day": self.expiry_day_agent.get_status(),
                "decay": self.decay_agent.get_status(),
            },
        }
