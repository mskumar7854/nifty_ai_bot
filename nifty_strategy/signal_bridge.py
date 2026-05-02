"""
╔══════════════════════════════════════════════════════════════╗
║         SIGNAL BRIDGE  v2  —  PRO INTEGRATION LAYER         ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  AI Engine (23 agents)                                       ║
║       ↓                                                      ║
║  Layer 1 : Core Alignment Filter   (confluence ≥ 65%)        ║
║       ↓                                                      ║
║  Layer 2 : Primary Agent Consensus  (≥2 primaries agree)     ║
║       ↓                                                      ║
║  Layer 3 : Warning Intelligence     (critical words → WAIT)  ║
║       ↓                                                      ║
║  Layer 4 : Grade × Regime Matrix    (only valid combos)      ║
║       ↓                                                      ║
║  Layer 5 : Strategy 7-Gate Check   (EMA/RSI/breakout + SFs) ║
║       ↓                                                      ║
║  Layer 6 : Entry Quality Filter    (not chasing price)       ║
║       ↓                                                      ║
║  Layer 7 : Scoring Engine          (weighted 0-140 pts)      ║
║       ↓                                                      ║
║  FINAL OUTPUT (5 types):                                     ║
║    🟢 STRONG_TRADE   ≥ 110 pts  → execute immediately        ║
║    🟡 CONDITIONAL    ≥  80 pts  → execute with caution       ║
║    ⏳ WAIT           warning    → re-check next candle        ║
║    🔴 NO_TRADE       blocked    → hard skip                   ║
║    ❌ SKIP           regime/grade mismatch                    ║
╚══════════════════════════════════════════════════════════════╝
"""

import sys
import os
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Tuple
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from .config import Config
from models.trade_record import RejectionRecord

logger = logging.getLogger("signal_bridge")


# ══════════════════════════════════════════════════════════════
# CONSTANTS  —  every threshold in one visible place
# ══════════════════════════════════════════════════════════════

# ── Layer 1: Core Alignment ───────────────────────────────────
MIN_CONFLUENCE_RATIO     = 0.65   # ≥ 65% of agents must agree

# ── Layer 2: Primary Agents ───────────────────────────────────
PRIMARY_AGENTS           = {"market", "multi_timeframe", "oi"}
MIN_PRIMARY_VOTES        = 2      # at least 2 of 3 primaries must agree

# ── Layer 3: Warning Intelligence ─────────────────────────────
CRITICAL_WARNINGS = [
    "large wick", "stop hunt", "liquidity sweep", "max pain",
    "fake breakout", "rejection", "divergence", "trap",
    "iv crush", "pin risk",
]

# ── Layer 4: Grade × Regime Matrix ────────────────────────────
# Only these (grade, regime) combos are allowed.
# Everything else → SKIP
GRADE_REGIME_MATRIX = {
    "A+" : {"TRENDING_UP", "TRENDING_DOWN", "BREAKOUT"},
    "A"  : {"TRENDING_UP", "TRENDING_DOWN", "BREAKOUT"},
    "B+" : {"TRENDING_UP", "TRENDING_DOWN", "BREAKOUT"},
    "B"  : {"BREAKOUT"},           # B grade only on confirmed breakouts
    # C, D → always SKIP (never trade low-grade signals)
}

GRADE_VALUES = {"A+": 5, "A": 4, "B+": 3.5, "B": 3, "C": 2, "D": 1}
MIN_GRADE    = 3  # B = minimum (C and D are always skipped)

# ── Layer 6: Entry Quality ────────────────────────────────────
MAX_ENTRY_DISTANCE_PCT   = 0.20   # 0.20% — not chasing price

# ── Layer 7: Scoring thresholds ───────────────────────────────
SCORE_STRONG_TRADE  = 110
SCORE_CONDITIONAL   = 80


# ══════════════════════════════════════════════════════════════
# DATA CONTRACTS
# ══════════════════════════════════════════════════════════════

@dataclass
class AISignalPacket:
    """
    Everything extracted from a live Signal object.
    Populate via AISignalPacket.from_signal(signal, snapshot).
    """
    direction:        str           # BULLISH | BEARISH | NEUTRAL
    confidence:       float         # 0-100
    grade:            str           # A+ | A | B+ | B | C | D
    signal_type:      str           # BUY_CE | BUY_PE | NO_TRADE
    regime:           str           # TRENDING_UP | RANGING | …
    confluence_ratio: float         # 0-1
    agreeing_agents:  List[str] = field(default_factory=list)
    warnings:         List[str] = field(default_factory=list)
    entry_type:       str  = "AI"      # AI | TELEGRAM | MANUAL
    entry_price:      float  = 0.0
    stop_loss:        float  = 0.0
    target_1:         float  = 0.0
    snapshot_price:   float  = 0.0  # current LTP for chase check
    timestamp:        datetime = field(default_factory=datetime.now)

    @classmethod
    def from_signal(cls, signal, snapshot=None) -> "AISignalPacket":
        """
        Build from a live Signal + MarketSnapshot.
        Handles both enum values and plain strings gracefully.
        """
        def _str(v):
            return v.value if hasattr(v, 'value') else str(v)

        confluence = signal.confluence
        agreeing   = list(confluence.agreeing_agents) if confluence else []
        conf_ratio = confluence.confluence_ratio       if confluence else 0.0

        return cls(
            direction        = _str(signal.direction),
            confidence       = signal.confidence,
            grade            = _str(signal.grade),
            signal_type      = _str(signal.signal_type),
            regime           = _str(signal.regime),
            confluence_ratio = conf_ratio,
            agreeing_agents  = agreeing,
            warnings         = list(signal.warnings),
            entry_type       = signal.metadata.get('entry_type', 'AI'),
            entry_price      = signal.entry_price,
            stop_loss        = signal.stop_loss,
            target_1         = signal.target_1,
            snapshot_price   = snapshot.price if snapshot else signal.entry_price,
        )


# ── Output types ──────────────────────────────────────────────
class TradeAction:
    STRONG_TRADE = "STRONG_TRADE"   # 🟢 — execute full size
    CONDITIONAL  = "CONDITIONAL"    # 🟡 — execute half size / wait 1 candle
    WAIT         = "WAIT"           # ⏳ — critical warning, re-check next bar
    NO_TRADE     = "NO_TRADE"       # 🔴 — hard block
    SKIP         = "SKIP"           # ❌ — regime/grade mismatch

    _ICONS = {
        "STRONG_TRADE": "🟢",
        "CONDITIONAL":  "🟡",
        "WAIT":         "⏳",
        "NO_TRADE":     "🔴",
        "SKIP":         "❌",
    }

    @classmethod
    def icon(cls, action: str) -> str:
        return cls._ICONS.get(action, "⚪")

    @classmethod
    def is_tradeable(cls, action: str) -> bool:
        return action in {cls.STRONG_TRADE, cls.CONDITIONAL}


@dataclass
class LayerResult:
    """Trace of one layer's decision."""
    layer:   int
    name:    str
    passed:  bool
    score:   float = 0.0
    detail:  str   = ""


@dataclass
class BridgeDecision:
    """Final output of the signal bridge."""
    action:      str     # TradeAction constant
    signal:      str     # BUY_CE | BUY_PE | NO_TRADE
    can_trade:   bool
    score:       float   = 0.0
    confidence:  float   = 0.0
    reason:      str     = ""
    layers:      List[LayerResult] = field(default_factory=list)
    ai_details:  dict    = field(default_factory=dict)
    strategy_details: dict = field(default_factory=dict)
    position_size_pct: float = 1.0  # 1.0 = full, 0.5 = half
    entry_type:  str = "AI"
    agreeing_agents: List[str] = field(default_factory=list)
    warnings:    List[str] = field(default_factory=list)
    timestamp:   datetime = field(default_factory=datetime.now)

    def summary(self) -> str:
        icon = TradeAction.icon(self.action)
        return (
            f"{icon} {self.action:<14} | "
            f"Signal:{self.signal:<8} | "
            f"Score:{self.score:.0f}/140 | "
            f"Conf:{self.confidence:.0f}% | "
            f"{self.reason}"
        )

    def print_layers(self):
        """Debug: print every layer's pass/fail."""
        print(f"\n{'─'*52}")
        print(f"  BRIDGE DECISION: {TradeAction.icon(self.action)} {self.action}")
        print(f"  Score: {self.score:.0f}/140 | Signal: {self.signal}")
        print(f"{'─'*52}")
        for lr in self.layers:
            icon = "✅" if lr.passed else "❌"
            print(f"  {icon} L{lr.layer} {lr.name:<28} | {lr.detail}")
        print(f"{'─'*52}\n")


# ══════════════════════════════════════════════════════════════
# SIGNAL BRIDGE  v2
# ══════════════════════════════════════════════════════════════

class SignalBridge:
    """
    7-layer weighted + context-aware decision engine.

    Usage:
        bridge = SignalBridge(strategy=strategy, risk_manager=rm)
        packet = AISignalPacket.from_signal(signal, snapshot)
        decision = bridge.evaluate(packet, trend_df, momentum_df, entry_df)

        if TradeAction.is_tradeable(decision.action):
            executor.execute_signal(...)
    """

    def __init__(self, strategy=None, risk_manager=None, trade_logger=None):
        self.strategy     = strategy
        self.risk_manager = risk_manager
        self.trade_logger = trade_logger

    # ── PUBLIC API ─────────────────────────────────────────────
    def evaluate(
        self,
        packet:      AISignalPacket,
        trend_df:    pd.DataFrame,
        momentum_df: pd.DataFrame,
        entry_df:    pd.DataFrame,
        volume_df:   Optional[pd.DataFrame] = None,
        dt:          Optional[datetime]     = None,
    ) -> BridgeDecision:
        """
        Run all 7 layers in sequence.
        Returns BridgeDecision with action, score, and full layer trace.
        """
        now    = dt or datetime.now()
        layers: List[LayerResult] = []
        score  = 0.0

        # ── LAYER 1: Core Alignment ───────────────────────────
        lr1 = self._layer_core_alignment(packet)
        layers.append(lr1)
        if not lr1.passed:
            return self._no_trade(packet, layers, "NO_TRADE",
                                  lr1.detail, score)
        score += lr1.score

        # ── LAYER 2: Primary Agent Consensus ──────────────────
        lr2 = self._layer_primary_agents(packet)
        layers.append(lr2)
        if not lr2.passed:
            return self._no_trade(packet, layers, "NO_TRADE",
                                  lr2.detail, score)
        score += lr2.score

        # ── LAYER 3: Warning Intelligence ─────────────────────
        lr3 = self._layer_warnings(packet)
        layers.append(lr3)
        if not lr3.passed:
            # Not a hard NO — emit WAIT so caller re-checks next bar
            return self._build(
                action   = TradeAction.WAIT,
                signal   = packet.signal_type,
                can_trade= False,
                score    = score,
                conf     = packet.confidence,
                reason   = f"⏳ {lr3.detail}",
                layers   = layers,
                packet   = packet,
            )
        score += lr3.score

        # ── LAYER 4: Grade × Regime Matrix ────────────────────
        lr4 = self._layer_grade_regime(packet)
        layers.append(lr4)
        if not lr4.passed:
            return self._no_trade(packet, layers, "SKIP",
                                  lr4.detail, score)
        score += lr4.score

        # ── LAYER 5: Strategy 7-Gate Check ────────────────────
        strategy_result = {}
        lr5, strategy_result = self._layer_strategy(
            packet, trend_df, momentum_df, entry_df, volume_df, now
        )
        layers.append(lr5)
        if not lr5.passed:
            return self._no_trade(packet, layers, "NO_TRADE",
                                  lr5.detail, score,
                                  strategy_details=strategy_result)
        score += lr5.score

        # Direction must match strategy
        lr5b = self._layer_direction_match(packet, strategy_result)
        layers.append(lr5b)
        if not lr5b.passed:
            return self._no_trade(packet, layers, "NO_TRADE",
                                  lr5b.detail, score,
                                  strategy_details=strategy_result)
        # No extra score — just a gate

        # ── LAYER 6: Entry Quality ────────────────────────────
        lr6 = self._layer_entry_quality(packet)
        layers.append(lr6)
        if not lr6.passed:
            return self._no_trade(packet, layers, "NO_TRADE",
                                  lr6.detail, score,
                                  strategy_details=strategy_result)
        score += lr6.score

        # ── LAYER 7: Scoring Engine ───────────────────────────
        lr7, bonus_score = self._layer_scoring(packet, strategy_result)
        layers.append(lr7)
        score += bonus_score

        # ── Refinement: Telegram Strict Mode Gate ──────────
        if packet.entry_type == "TELEGRAM":
            threshold = (Config.TELEGRAM_STRICT_THRESHOLD 
                         if Config.TELEGRAM_MODE == "STRICT" 
                         else Config.TELEGRAM_TEST_THRESHOLD)
            
            # Normalize threshold (v5.0 uses 0-140 total score)
            # 0.85 normalized to 140 scale = 119
            normalized_threshold = threshold if threshold > 1 else (threshold * 140)
            
            if score < normalized_threshold:
                lr_tele = LayerResult(7.5, "Telegram Strict Gate", False,
                                     detail=f"Score {score:.1f} < {normalized_threshold} (Mode:{Config.TELEGRAM_MODE})")
                layers.append(lr_tele)
                return self._no_trade(packet, layers, "NO_TRADE",
                                      f"Telegram signal below strict {threshold} threshold", score,
                                      strategy_details=strategy_result)

        # ── Risk gate ─────────────────────────────────────────
        final_signal = strategy_result.get('signal', packet.signal_type)
        if self.risk_manager:
            risk_ok, risk_reason = self.risk_manager.can_take_trade(final_signal)
            if not risk_ok:
                lr_risk = LayerResult(8, "Risk Manager", False,
                                      detail=risk_reason)
                layers.append(lr_risk)
                return self._no_trade(packet, layers, "NO_TRADE",
                                      f"Risk: {risk_reason}", score,
                                      strategy_details=strategy_result)

        # ── Final classification ──────────────────────────────
        combined_conf = self._combined_confidence(packet, strategy_result)

        if score >= SCORE_STRONG_TRADE:
            action         = TradeAction.STRONG_TRADE
            position_pct   = 1.0
        elif score >= SCORE_CONDITIONAL:
            action         = TradeAction.CONDITIONAL
            position_pct   = 0.5   # half size on conditional trades
        else:
            action         = TradeAction.NO_TRADE
            position_pct   = 0.0

        if not TradeAction.is_tradeable(action):
            return self._no_trade(packet, layers, action,
                                  f"Score {score:.0f} < {SCORE_CONDITIONAL}",
                                  score, strategy_details=strategy_result)

        logger.info(
            f"{'🟢' if action==TradeAction.STRONG_TRADE else '🟡'} "
            f"BRIDGE {action} | {final_signal} | "
            f"Score:{score:.0f}/140 | "
            f"Grade:{packet.grade} | Regime:{packet.regime} | "
            f"Conf:{combined_conf:.0f}%"
        )

        return self._build(
            action        = action,
            signal        = final_signal,
            can_trade     = True,
            score         = score,
            conf          = combined_conf,
            reason        = (
                f"Score {score:.0f}/140 | "
                f"AI {packet.grade} {packet.confidence:.0f}% | "
                f"Regime:{packet.regime}"
            ),
            layers        = layers,
            packet        = packet,
            strategy_details = strategy_result,
            position_pct  = position_pct,
        )

    # ══════════════════════════════════════════════════════════
    # LAYER IMPLEMENTATIONS
    # ══════════════════════════════════════════════════════════

    # ── Layer 1 ───────────────────────────────────────────────
    def _layer_core_alignment(self, p: AISignalPacket) -> LayerResult:
        """
        Confluence ratio ≥ 65%.
        Below this threshold the agents are divided — skip.
        """
        if p.signal_type == "NO_TRADE":
            return LayerResult(1, "Core Alignment", False,
                               detail="AI engine: NO_TRADE")

        ratio = p.confluence_ratio
        passed = ratio >= MIN_CONFLUENCE_RATIO

        # Bonus score scales with how well agents agree (0-30 pts)
        score = min(30.0, ratio * 40) if passed else 0.0

        return LayerResult(
            1, "Core Alignment", passed, score=score,
            detail=(
                f"Confluence {ratio:.0%} "
                f"{'≥' if passed else '<'} {MIN_CONFLUENCE_RATIO:.0%}"
            ),
        )

    # ── Layer 2 ───────────────────────────────────────────────
    def _layer_primary_agents(self, p: AISignalPacket) -> LayerResult:
        """
        At least MIN_PRIMARY_VOTES primary agents must be in agreeing_agents.
        Primary agents are the market's core reads — if they disagree, skip.
        """
        agreeing  = {a.lower() for a in p.agreeing_agents}
        primaries = PRIMARY_AGENTS

        votes = agreeing & primaries
        count = len(votes)
        passed = count >= MIN_PRIMARY_VOTES

        # Score: 0-20 pts
        score = count / len(primaries) * 20 if passed else 0.0

        return LayerResult(
            2, "Primary Agent Consensus", passed, score=score,
            detail=(
                f"{count}/{len(primaries)} primaries agree "
                f"({', '.join(votes) or 'none'})"
            ),
        )

    # ── Layer 3 ───────────────────────────────────────────────
    def _layer_warnings(self, p: AISignalPacket) -> LayerResult:
        """
        Check signal.warnings for critical danger phrases.
        One match → WAIT (not hard NO — re-evaluate next candle).
        No warnings → bonus 10 pts (clean setup).
        """
        all_warnings = " ".join(p.warnings).lower()
        hits = [kw for kw in CRITICAL_WARNINGS if kw in all_warnings]

        if hits:
            return LayerResult(
                3, "Warning Intelligence", False, score=0.0,
                detail=f"Critical warning(s): {', '.join(hits[:3])}",
            )

        # Clean — bonus 10 pts
        return LayerResult(
            3, "Warning Intelligence", True, score=10.0,
            detail=f"No critical warnings | {len(p.warnings)} minor",
        )

    # ── Layer 4 ───────────────────────────────────────────────
    def _layer_grade_regime(self, p: AISignalPacket) -> LayerResult:
        """
        Grade × Regime matrix:
          A+/A/B+  → TRENDING_UP, TRENDING_DOWN, BREAKOUT
          B        → BREAKOUT only
          C / D    → always skip

        Grade B+ is handled here even if SignalGrade enum only has A/B.
        """
        grade  = p.grade
        regime = p.regime

        grade_val = GRADE_VALUES.get(grade, 1)
        if grade_val < MIN_GRADE:
            return LayerResult(
                4, "Grade × Regime Matrix", False,
                detail=f"Grade {grade} below minimum B — skip",
            )

        allowed_regimes = GRADE_REGIME_MATRIX.get(grade, set())
        passed = regime in allowed_regimes

        # Score: A+=30, A=25, B+=20, B=15
        grade_score = {5: 30, 4: 25, 3.5: 20, 3: 15}.get(grade_val, 0)
        score = float(grade_score) if passed else 0.0

        return LayerResult(
            4, "Grade × Regime Matrix", passed, score=score,
            detail=(
                f"Grade:{grade} + Regime:{regime} → "
                f"{'ALLOWED ✓' if passed else 'NOT in matrix ✗'}"
            ),
        )

    # ── Layer 5 ───────────────────────────────────────────────
    def _layer_strategy(
        self, p, trend_df, momentum_df, entry_df, volume_df, now
    ) -> Tuple[LayerResult, dict]:
        """Run the 7-gate strategy and return its full result dict."""
        if self.strategy is None:
            return (
                LayerResult(5, "Strategy 7-Gate", True, score=20.0,
                            detail="Strategy not loaded — auto-pass"),
                {},
            )

        result = self.strategy.analyze(
            trend_df    = trend_df,
            momentum_df = momentum_df,
            entry_df    = entry_df,
            volume_df   = volume_df,
            dt          = now,
        )
        passed = result['can_trade']

        # Score: 0-30 pts (pass = 30, fail = 0)
        score = 30.0 if passed else 0.0

        return (
            LayerResult(
                5, "Strategy 7-Gate", passed, score=score,
                detail=(
                    f"Strategy: {result['signal']} | "
                    f"{result.get('no_trade_reason') or 'All gates passed'}"
                ),
            ),
            result,
        )

    def _layer_direction_match(
        self, p: AISignalPacket, strategy_result: dict
    ) -> LayerResult:
        """AI direction and strategy signal direction must agree."""
        ai_dir  = p.direction
        s_sig   = strategy_result.get('signal', 'NO_TRADE')

        match = (
            (ai_dir == "BULLISH" and s_sig == "BUY_CE") or
            (ai_dir == "BEARISH" and s_sig == "BUY_PE")
        )
        return LayerResult(
            "5b", "Direction Match", match, score=0.0,
            detail=(
                f"AI={ai_dir} ↔ Strategy={s_sig} → "
                f"{'MATCH ✓' if match else 'MISMATCH ✗'}"
            ),
        )

    # ── Layer 6 ───────────────────────────────────────────────
    def _layer_entry_quality(self, p: AISignalPacket) -> LayerResult:
        """
        Current price must be within MAX_ENTRY_DISTANCE_PCT% of
        signal entry_price — prevents chasing stale entries.
        """
        entry   = p.entry_price
        current = p.snapshot_price or entry

        if entry <= 0 or current <= 0:
            return LayerResult(6, "Entry Quality", True, score=10.0,
                               detail="No price context — auto-pass")

        dist_pct = abs(current - entry) / entry * 100

        passed = dist_pct <= MAX_ENTRY_DISTANCE_PCT
        # Score: 0-10 pts inversely proportional to distance
        score = max(0.0, 10.0 - dist_pct * 30) if passed else 0.0

        return LayerResult(
            6, "Entry Quality", passed, score=score,
            detail=(
                f"Price ₹{current:.1f} vs Entry ₹{entry:.1f} "
                f"= {dist_pct:.3f}% "
                f"({'OK' if passed else 'CHASING ✗'})"
            ),
        )

    # ── Layer 7 ───────────────────────────────────────────────
    def _layer_scoring(
        self, p: AISignalPacket, strategy_result: dict
    ) -> Tuple[LayerResult, float]:
        """
        Additive bonus scoring on top of layer scores.

        Component         Max pts  Condition
        ─────────────────────────────────────
        AI confidence      20      ≥ 80%
        Grade bonus        20      A or A+
        High confluence    20      ≥ 75%
        Clean warnings     10      already given in L3
        Strong regime      10      trending + grade match
        ─────────────────────────────────────
        Total bonus max    70  (base from L1-L6 = 70 → total 140)
        """
        bonus = 0.0
        notes = []

        # AI confidence bonus (0-20)
        if p.confidence >= 90:
            bonus += 20; notes.append("Conf≥90+20")
        elif p.confidence >= 80:
            bonus += 15; notes.append("Conf≥80+15")
        elif p.confidence >= 70:
            bonus += 10; notes.append("Conf≥70+10")

        # Grade bonus (0-20)
        if p.grade == "A+":
            bonus += 20; notes.append("A++20")
        elif p.grade == "A":
            bonus += 15; notes.append("A+15")
        elif p.grade in ("B+", "B"):
            bonus += 8;  notes.append("B/B++8")

        # Confluence bonus (0-20)
        if p.confluence_ratio >= 0.80:
            bonus += 20; notes.append("Conf≥80%+20")
        elif p.confluence_ratio >= 0.75:
            bonus += 12; notes.append("Conf≥75%+12")
        elif p.confluence_ratio >= 0.65:
            bonus += 5;  notes.append("Conf≥65%+5")

        # Strong regime bonus (0-10)
        if p.regime in {"TRENDING_UP", "TRENDING_DOWN"} and \
                GRADE_VALUES.get(p.grade, 0) >= 4:
            bonus += 10; notes.append("Trending+Grade+10")
        elif p.regime == "BREAKOUT":
            bonus += 5;  notes.append("Breakout+5")

        # RSI from strategy details (bonus 0-5)
        rsi_d = strategy_result.get('details', {}).get('rsi_details', {})
        rsi   = rsi_d.get('rsi', 50)
        if rsi > 65 or rsi < 35:
            bonus += 5; notes.append(f"RSI={rsi:.0f}+5")

        detail = f"Bonus {bonus:.0f}pts | " + " | ".join(notes) if notes else \
                 f"Bonus {bonus:.0f}pts"

        return (
            LayerResult(7, "Scoring Engine", True, score=bonus,
                        detail=detail),
            bonus,
        )

    # ══════════════════════════════════════════════════════════
    # HELPERS
    # ══════════════════════════════════════════════════════════

    def _combined_confidence(
        self, p: AISignalPacket, strategy_result: dict
    ) -> float:
        rsi = (strategy_result.get('details', {})
               .get('rsi_details', {})
               .get('rsi', 50))
        # AI confidence (70%) + RSI normalised (30%)
        rsi_conf = min(100, abs(rsi - 50) * 2 + 50)
        return round(p.confidence * 0.70 + rsi_conf * 0.30, 1)

    def _no_trade(
        self,
        packet:           AISignalPacket,
        layers:           list,
        action:           str,
        reason:           str,
        score:            float,
        strategy_details: dict = None,
        position_pct:     float = 0.0,
    ) -> BridgeDecision:
        logger.debug(
            f"{TradeAction.icon(action)} BRIDGE {action} | "
            f"Score:{score:.0f} | {reason}"
        )
        
        # ── Refinement 5: Rejection Logging ──────────────────
        if self.trade_logger and action in {TradeAction.NO_TRADE, TradeAction.SKIP}:
            rejection = RejectionRecord(
                signal_type = packet.signal_type,
                score       = score,
                reason      = reason,
                gate        = layers[-1].name if layers else "MasterDecisionEngine",
                market_regime = packet.regime
            )
            self.trade_logger.log_rejection(rejection)
        return self._build(
            action           = action,
            signal           = "NO_TRADE",
            can_trade        = False,
            score            = score,
            conf             = packet.confidence,
            reason           = reason,
            layers           = layers,
            packet           = packet,
            strategy_details = strategy_details or {},
            position_pct     = position_pct,
        )

    @staticmethod
    def _build(
        action, signal, can_trade, score, conf,
        reason, layers, packet, strategy_details=None, position_pct=0.0,
    ) -> BridgeDecision:
        return BridgeDecision(
            action     = action,
            signal     = signal,
            can_trade  = can_trade,
            score      = score,
            confidence = conf,
            reason     = reason,
            layers     = layers,
            ai_details = {
                'signal_type':      packet.signal_type,
                'direction':        packet.direction,
                'confidence':       packet.confidence,
                'grade':            packet.grade,
                'regime':           packet.regime,
                'confluence_ratio': packet.confluence_ratio,
                'warnings':         packet.warnings,
                'agreeing_agents':  packet.agreeing_agents,
            },
            strategy_details   = strategy_details or {},
            position_size_pct  = position_pct,
            entry_type         = packet.entry_type,
            agreeing_agents    = packet.agreeing_agents,
            warnings           = packet.warnings
        )
