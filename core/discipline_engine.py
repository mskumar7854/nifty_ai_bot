"""
============================================
🛡️ DISCIPLINE ENGINE

The system that prevents YOU from
destroying your own edge.

Monitors for:
- Rule violations
- Override attempts
- Emotional trading patterns
- Revenge trading
- Overtrading
- Ignoring the system

The HARDEST part of trading isn't the system.
It's following the system.
============================================
"""

from datetime import datetime, date, timedelta
from typing import Dict, List, Tuple
from collections import deque

from utils.logger import get_logger


class DisciplineEngine:
    """
    Monitors trader behavior and enforces discipline.

    This is the agent that watches YOU,
    not the market.
    """

    def __init__(self):
        self.logger = get_logger("discipline")

        # ── Violation Tracking ──
        self.violations: List[Dict] = []
        self.daily_violations = 0
        self.total_violations = 0

        # ── Pattern Detection ──
        self.trade_intervals: deque = deque(maxlen=50)
        self.loss_reactions: deque = deque(maxlen=20)
        self.override_attempts = 0

        # ── Session Tracking ──
        self.current_date = date.today()
        self.rules_followed = 0
        self.rules_total = 0

    def check_discipline(
        self,
        action: str,
        context: Dict,
    ) -> Tuple[bool, str]:
        """
        Check if an action violates discipline rules.
        Returns (allowed, reason).
        """

        self._check_daily_reset()

        # ── RULE 1: No trading outside session ──
        if action == "TRADE" and not context.get(
            "session_approved", False
        ):
            self._record_violation(
                "SESSION_VIOLATION",
                "Attempted trade outside approved session"
            )
            return False, "Trading outside approved session"

        # ── RULE 2: No trading after daily target ──
        if action == "TRADE" and context.get(
            "daily_target_hit", False
        ):
            self._record_violation(
                "TARGET_VIOLATION",
                "Attempted trade after daily target"
            )
            return False, "Daily target already hit — stop trading"

        # ── RULE 3: No revenge trading ──
        if action == "TRADE":
            recent_losses = context.get("consecutive_losses", 0)
            last_trade_ago = context.get(
                "seconds_since_last_trade", 999
            )

            if recent_losses >= 2 and last_trade_ago < 120:
                self._record_violation(
                    "REVENGE_TRADING",
                    f"Quick trade after {recent_losses} losses"
                )
                return False, (
                    "Possible revenge trading detected — "
                    "wait at least 2 minutes"
                )

        # ── RULE 4: Respect position limits ──
        if action == "TRADE":
            open_positions = context.get("open_positions", 0)
            max_positions = context.get("max_positions", 1)

            if open_positions >= max_positions:
                return False, (
                    f"Max positions ({max_positions}) reached"
                )

        # ── RULE 5: Don't override the filter ──
        if action == "OVERRIDE_FILTER":
            self.override_attempts += 1
            self._record_violation(
                "FILTER_OVERRIDE",
                "Attempted to override trade filter"
            )
            return False, (
                "Filter overrides are not allowed — "
                "trust the system"
            )

        # ── RULE 6: No manual trades outside system ──
        if action == "MANUAL_TRADE":
            self._record_violation(
                "MANUAL_TRADE",
                "Manual trade outside system"
            )
            return False, (
                "Manual trading is disabled — "
                "use the system"
            )

        self.rules_followed += 1
        self.rules_total += 1

        return True, "OK"

    def post_trade_review(
        self,
        trade_result: Dict,
    ) -> Dict:
        """
        Generate a post-trade review.
        Forces reflection on every trade.
        """

        review = {
            "timestamp": datetime.now().isoformat(),
            "result": trade_result.get("result", ""),
            "pnl": trade_result.get("net_pnl", 0),
        }

        questions = []

        # Standard questions
        questions.append({
            "question": "Did you follow the system signal?",
            "expected": "YES",
        })
        questions.append({
            "question": "Was the entry at the right level?",
            "expected": "Filter-approved entry",
        })
        questions.append({
            "question": "Did you follow the exit rules?",
            "expected": "YES — system exit",
        })

        # Result-specific questions
        if trade_result.get("result") == "LOSS":
            questions.append({
                "question": "Was the stop loss appropriate?",
                "expected": "ATR-based, not emotional",
            })
            questions.append({
                "question": (
                    "Would you take this trade again "
                    "with the same setup?"
                ),
                "expected": "YES if system-approved",
            })
            questions.append({
                "question": (
                    "Are you emotionally stable to "
                    "continue trading?"
                ),
                "expected": "YES — or take a break",
            })

        if trade_result.get("result") == "WIN":
            questions.append({
                "question": (
                    "Did you let the winner run "
                    "or exit too early?"
                ),
                "expected": "Followed system targets",
            })

        review["questions"] = questions
        review["discipline_score"] = self._calculate_discipline_score()

        return review

    def generate_weekly_journal(self) -> Dict:
        """Generate weekly discipline and performance journal"""

        return {
            "week_ending": date.today().isoformat(),
            "discipline": {
                "rules_followed": self.rules_followed,
                "rules_total": self.rules_total,
                "compliance_rate": (
                    f"{(self.rules_followed / max(self.rules_total, 1) * 100):.1f}%"
                ),
                "violations": self.total_violations,
                "override_attempts": self.override_attempts,
            },
            "violations_breakdown": self._get_violation_summary(),
            "improvement_areas": self._identify_improvements(),
        }

    def _record_violation(self, violation_type: str, detail: str):
        self.violations.append({
            "time": datetime.now().isoformat(),
            "type": violation_type,
            "detail": detail,
        })
        self.daily_violations += 1
        self.total_violations += 1
        self.rules_total += 1

        self.logger.warning(
            f"⚠️ DISCIPLINE VIOLATION: {violation_type} — "
            f"{detail}"
        )

    def _calculate_discipline_score(self) -> float:
        if self.rules_total == 0:
            return 100.0
        return self.rules_followed / self.rules_total * 100

    def _get_violation_summary(self) -> Dict:
        from collections import Counter
        types = [v["type"] for v in self.violations]
        return dict(Counter(types))

    def _identify_improvements(self) -> List[str]:
        improvements = []
        summary = self._get_violation_summary()

        if summary.get("REVENGE_TRADING", 0) > 0:
            improvements.append(
                "⚠️ Revenge trading detected — "
                "implement mandatory cooldown after losses"
            )

        if summary.get("SESSION_VIOLATION", 0) > 0:
            improvements.append(
                "⚠️ Trading outside sessions — "
                "respect the session schedule"
            )

        if summary.get("FILTER_OVERRIDE", 0) > 0:
            improvements.append(
                "⚠️ Attempted filter overrides — "
                "trust the system, don't override"
            )

        if self.override_attempts > 3:
            improvements.append(
                "🚨 Multiple override attempts — "
                "if you can't trust the system, "
                "fix the system, don't bypass it"
            )

        if not improvements:
            improvements.append(
                "✅ Good discipline — keep it up!"
            )

        return improvements

    def _check_daily_reset(self):
        today = date.today()
        if self.current_date != today:
            self.current_date = today
            self.daily_violations = 0

    def get_status(self) -> Dict:
        return {
            "discipline_score": f"{self._calculate_discipline_score():.1f}%",
            "violations_today": self.daily_violations,
            "total_violations": self.total_violations,
            "override_attempts": self.override_attempts,
            "rules_compliance": f"{self.rules_followed}/{self.rules_total}",
        }
