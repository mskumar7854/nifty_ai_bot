"""
============================================
🔒 TRADE FILTER — 10-GATE PRO MODE

The bouncer between raw signals and real trades.
Only the highest quality setups pass all 10 gates.

Gates:
  1. Confidence Gate
  2. Confluence Gate
  3. Agent Agreement Gate
  4. Regime Gate
  5. Structure Gate
  6. Cost/Breakeven Gate
  7. Daily Limit Gate
  8. Learning Gate
  9. Decay/Theta Gate
  10. Quality Grade Gate
============================================
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime

from models.signals import Signal, SignalType, Direction
from utils.logger import get_logger
from utils.helpers import safe_divide
from config.settings import Settings


@dataclass
class FilterResult:
    """Result from the 10-gate filter evaluation"""
    passed: bool
    final_score: float
    grade: str
    filters_passed: int
    filters_total: int
    kill_reason: str = ""
    gate_details: List[Dict] = field(default_factory=list)


class TradeFilter:
    """
    10-Gate Pro Filter.

    Apply strict gates to every signal.
    Kill bad trades before they cost money.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.cfg = settings.trade_filter
        self.logger = get_logger("trade_filter")

        # Stats
        self.total_received = 0
        self.killed = 0
        self.passed_ = 0
        self.kill_reasons: Dict[str, int] = {}

    def evaluate(
        self,
        signal: Signal,
        snapshot,
        agent_outputs: Dict,
        regime_info: Dict,
        structure_info: Dict,
        learning_info: Dict,
        decay_info: Dict,
        cost_info: Dict,
        position_manager_status: Dict,
        confluence_score: float,
    ) -> FilterResult:
        """
        Run signal through all 10 gates.
        Returns FilterResult with pass/fail and details.
        """

        self.total_received += 1
        gates = []
        total_score = 0.0
        max_score = 0.0

        # ──────────────────────────────────────────────────────────
        # P2-C: GATE ORDERING RATIONALE (DO NOT REORDER without updating)
        #
        # 1. Cheapest-to-compute and highest-rejection-rate filters first.
        # 2. This minimizes CPU time on signals that will be rejected anyway.
        # 3. Expensive agent-based gates (confluence, agreement) run last.
        # 4. Daily limit first: if we've hit the day's limit, nothing else matters.
        # 5. Chop zone second: time-based block, zero computation.
        # 6. Confidence third: cheap scalar check.
        # 7. Cost fourth: no point evaluating a trade that can't cover transaction costs.
        # ──────────────────────────────────────────────────────────

        # ── GATE 0: Daily Limits (cheapest — instant rejection) ──
        today_trades = position_manager_status.get("today_trades", 0)
        g0_pass = today_trades < 5  # Phase 5 hard cap
        g0_score = 100 if g0_pass else 0
        gates.append({
            "gate": "Daily Limit",
            "pass": g0_pass,
            "score": g0_score,
            "detail": f"{today_trades}/5 trades today",
        })
        total_score += g0_score * 0.05
        max_score += 5.0

        if not g0_pass:
            return self._kill(signal, gates, "DAILY_LIMIT_REACHED", 1, 10)

        # ── CHOP ZONE FILTER (Phase 5 — with P2-F override support) ──
        current_time = datetime.now()
        chop_start = current_time.replace(hour=11, minute=30, second=0, microsecond=0)
        chop_end = current_time.replace(hour=13, minute=30, second=0, microsecond=0)
        if chop_start <= current_time <= chop_end:
            # P2-F: Check override conditions before blocking
            chop_blocked = True

            # Override 1: Scheduled event date (RBI day, budget, etc.)
            import os
            disable_chop_date = os.getenv("DISABLE_CHOP_BLOCK_DATE")
            today_str = current_time.date().isoformat()
            if disable_chop_date and today_str == disable_chop_date:
                self.logger.info("Chop zone disabled for scheduled event on %s", today_str)
                chop_blocked = False

            # Override 2: Exceptional signal quality (A+ grade, 92%+ confidence)
            CHOP_OVERRIDE_MIN_CONFIDENCE = 92.0
            CHOP_OVERRIDE_MIN_GRADE = "A+"
            signal_grade_str = signal.grade.value if hasattr(signal.grade, 'value') else str(signal.grade)
            if (signal.confidence >= CHOP_OVERRIDE_MIN_CONFIDENCE
                    and signal_grade_str == CHOP_OVERRIDE_MIN_GRADE):
                self.logger.info(
                    "Chop zone override: confidence=%.2f grade=%s",
                    signal.confidence, signal_grade_str
                )
                chop_blocked = False

            if chop_blocked:
                gates.append({
                    "gate": "Chop Zone",
                    "pass": False,
                    "score": 0,
                    "detail": "11:30 to 1:30 IST Chop Zone blocking entries.",
                })
                return self._kill(signal, gates, "CHOP_ZONE_ACTIVE", 1, 10)

        # ── GATE 1: Confidence ──
        conf = signal.confidence
        g1_pass = conf >= self.cfg.min_signal_confidence
        g1_score = min(100, conf)
        gates.append({
            "gate": "Confidence",
            "pass": g1_pass,
            "score": g1_score,
            "detail": f"{conf:.1f}% (need {self.cfg.min_signal_confidence}%)",
        })
        total_score += g1_score * 0.20
        max_score += 20.0

        if not g1_pass:
            return self._kill(signal, gates, "LOW_CONFIDENCE", 1, 10)

        # ── GATE 2: Confluence ──
        conf_score = 0.0
        if signal.confluence:
            conf_score = signal.confluence.confluence_ratio * 100
        g2_pass = conf_score >= self.cfg.min_confluence_score
        g2_score = min(100, conf_score)
        gates.append({
            "gate": "Confluence",
            "pass": g2_pass,
            "score": g2_score,
            "detail": f"{conf_score:.1f}% (need {self.cfg.min_confluence_score}%)",
        })
        total_score += g2_score * 0.15
        max_score += 15.0

        if not g2_pass:
            return self._kill(signal, gates, "LOW_CONFLUENCE", 2, 10)

        # ── GATE 3: Agent Agreement ──
        # Compute agreement from confluence data
        agreement_pct = 0.0
        if signal.confluence:
            total_agents = signal.confluence.total_agents
            bullish = signal.confluence.bullish_agents
            bearish = signal.confluence.bearish_agents
            direction_agents = (
                bullish if signal.direction == Direction.BULLISH
                else bearish
            )
            agreement_pct = safe_divide(direction_agents * 100, total_agents)
        g3_pass = agreement_pct >= self.cfg.min_agent_agreement_pct
        g3_score = min(100, agreement_pct)
        gates.append({
            "gate": "Agent Agreement",
            "pass": g3_pass,
            "score": g3_score,
            "detail": f"{agreement_pct:.1f}% agree (need {self.cfg.min_agent_agreement_pct}%)",
        })
        total_score += g3_score * 0.10
        max_score += 10.0

        if not g3_pass:
            return self._kill(signal, gates, "LOW_AGENT_AGREEMENT", 3, 10)

        # ── GATE 4: Regime ──
        regime_str = regime_info.get("regime", "UNKNOWN")
        blocked_regime = regime_str in self.cfg.blocked_regimes
        g4_pass = not blocked_regime
        g4_score = 0 if blocked_regime else 100
        gates.append({
            "gate": "Regime",
            "pass": g4_pass,
            "score": g4_score,
            "detail": f"Regime: {regime_str}",
        })
        total_score += g4_score * 0.10
        max_score += 10.0

        if not g4_pass:
            return self._kill(signal, gates, f"BLOCKED_REGIME_{regime_str}", 4, 10)

        # ── GATE 5: Structure ──
        structure_type = structure_info.get("structure", "OK")
        blocked_structure = structure_type in self.cfg.blocked_structures
        g5_pass = not blocked_structure
        g5_score = 0 if blocked_structure else 100
        gates.append({
            "gate": "Structure",
            "pass": g5_pass,
            "score": g5_score,
            "detail": f"Structure: {structure_type}",
        })
        total_score += g5_score * 0.10
        max_score += 10.0

        if not g5_pass:
            return self._kill(signal, gates, f"BAD_STRUCTURE_{structure_type}", 5, 10)

        # ── GATE 6: Cost vs Breakeven (Premium Edge PEV) ──
        total_costs = cost_info.get("total_costs", 100) # Baseline costs
        p_win = signal.confidence / 100.0 if signal.confidence > 1 else signal.confidence
        p_loss = 1.0 - p_win

        target_pts = abs(signal.target_1 - signal.entry_price)
        stop_pts = abs(signal.entry_price - signal.stop_loss)
        qty = max(signal.position_size, 50)

        pev_rupees = ((p_win * target_pts) - (p_loss * stop_pts)) * qty
        risk_rupees = stop_pts * qty

        # Institutional Block: Trade is blocked unless PEV >= 1.2 * (Risk + Brokerage + Slippage)
        g6_pass = pev_rupees >= 1.2 * (risk_rupees + total_costs)
        g6_score = min(100, (pev_rupees / (risk_rupees + total_costs)) * 50 if (risk_rupees + total_costs) > 0 else 0)
        
        gates.append({
            "gate": "Cost/Breakeven (PEV)",
            "pass": g6_pass,
            "score": g6_score,
            "detail": f"PEV: ₹{pev_rupees:.0f} vs req ₹{1.2*(risk_rupees+total_costs):.0f}",
        })
        total_score += g6_score * 0.10
        max_score += 10.0

        if not g6_pass:
            return self._kill(signal, gates, "PEV_TOO_LOW", 6, 10)

        # P2-C: Daily Limit was moved to Gate 0 (first check) to save compute.
        # The old Gate 7 location is removed to avoid duplicate scoring.


        # ── GATE 8: Learning Approval ──
        learning_conf = learning_info.get("confidence", 50)
        streak = learning_info.get("current_streak", 0)
        g8_pass = (
            learning_conf >= self.cfg.learning_min_confidence
            and streak > self.cfg.learning_block_on_streak
        )
        g8_score = min(100, learning_conf)
        gates.append({
            "gate": "Learning Gate",
            "pass": g8_pass,
            "score": g8_score,
            "detail": (
                f"Learning conf: {learning_conf:.0f}% | "
                f"Streak: {streak}"
            ),
        })
        total_score += g8_score * 0.05
        max_score += 5.0

        if not g8_pass:
            return self._kill(signal, gates, "LEARNING_BLOCK", 8, 10)

        # ── GATE 9: Decay/Theta ──
        theta_pct = decay_info.get("theta_pct_per_hour", 0)
        iv_crushing = decay_info.get("iv_crushing", False)
        g9_pass = (
            theta_pct <= self.cfg.max_theta_pct_per_hour
            and not iv_crushing
        )
        g9_score = max(0, 100 - theta_pct * 10)
        gates.append({
            "gate": "Decay/Theta",
            "pass": g9_pass,
            "score": g9_score,
            "detail": (
                f"Theta: {theta_pct:.1f}%/hr | "
                f"IV Crush: {iv_crushing}"
            ),
        })
        total_score += g9_score * 0.05
        max_score += 5.0

        if not g9_pass:
            return self._kill(signal, gates, "HIGH_DECAY", 9, 10)

        # ── GATE 10: Quality Grade ──
        grade_map = {"A+": 5, "A": 4, "B+": 3.5, "B": 3, "C": 2, "D": 1}
        signal_grade_val = grade_map.get(signal.grade.value if hasattr(signal.grade, 'value') else str(signal.grade), 1)
        min_grade_val = grade_map.get(self.cfg.min_grade_to_trade, 4)
        g10_pass = signal_grade_val >= min_grade_val
        g10_score = min(100, signal_grade_val / 5 * 100)
        grade_str = signal.grade.value if hasattr(signal.grade, 'value') else str(signal.grade)
        gates.append({
            "gate": "Quality Grade",
            "pass": g10_pass,
            "score": g10_score,
            "detail": (
                f"Grade: {grade_str} "
                f"(need {self.cfg.min_grade_to_trade}+)"
            ),
        })
        total_score += g10_score * 0.10
        max_score += 10.0

        if not g10_pass:
            return self._kill(signal, gates, f"LOW_GRADE_{grade_str}", 10, 10)

        # ── ALL GATES PASSED ──
        final_score = safe_divide(total_score, max_score) * 100

        # Determine final grade
        if final_score >= 92:
            final_grade = "A+"
        elif final_score >= 82:
            final_grade = "A"
        elif final_score >= 72:
            final_grade = "B+"
        elif final_score >= 62:
            final_grade = "B"
        else:
            final_grade = "C"

        self.passed_ += 1

        self.logger.info(
            f"✅ Filter PASSED | Grade: {final_grade} | "
            f"Score: {final_score:.0f} | "
            f"Gates: 10/10"
        )

        return FilterResult(
            passed=True,
            final_score=final_score,
            grade=final_grade,
            filters_passed=10,
            filters_total=10,
            gate_details=gates,
        )

    def _kill(
        self,
        signal: Signal,
        gates: List[Dict],
        reason: str,
        gates_passed: int,
        gates_total: int,
    ) -> FilterResult:
        """Record a filter kill and return failure result"""

        self.killed += 1
        self.kill_reasons[reason] = self.kill_reasons.get(reason, 0) + 1

        if self.settings.system_mode.log_filter_kills:
            self.logger.warning(
                f"TRADE BLOCKED -> Reason: {reason}"
            )

        return FilterResult(
            passed=False,
            final_score=0.0,
            grade="D",
            filters_passed=gates_passed,
            filters_total=gates_total,
            kill_reason=reason,
            gate_details=gates,
        )

    def get_filter_stats(self) -> Dict:
        total = max(self.total_received, 1)
        return {
            "total_received": self.total_received,
            "killed": self.killed,
            "passed": self.passed_,
            "kill_rate": f"{safe_divide(self.killed * 100, total):.0f}%",
            "pass_rate": f"{safe_divide(self.passed_ * 100, total):.0f}%",
            "top_kill_reasons": dict(
                sorted(
                    self.kill_reasons.items(),
                    key=lambda x: x[1],
                    reverse=True,
                )[:5]
            ),
        }
