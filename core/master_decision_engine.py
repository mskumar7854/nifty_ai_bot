"""
╔══════════════════════════════════════════════════════════════════════════╗
║          🧠 MASTER DECISION ENGINE — SINGLE POINT OF TRUTH              ║
╠══════════════════════════════════════════════════════════════════════════╣
║                                                                          ║
║  ONE question.  ONE place.  ONE answer.                                  ║
║                                                                          ║
║  ❓ "Should we trade right now?"                                          ║
║                                                                          ║
║  Every execution path (Architecture 1 + Architecture 2) MUST call       ║
║  MasterDecisionEngine.approve() before placing ANY real-money order.     ║
║                                                                          ║
║  This was designed after a Graphify analysis of the full codebase        ║
║  (2026-04-09) that revealed:                                             ║
║    • 2 separate execution architectures with different pre-trade checks  ║
║    • 1 gap where _live_execute() skipped the risk re-check               ║
║    • 1 NameError in core/risk_manager.py is_within_trading_hours()       ║
║                                                                          ║
║  ⚠️ AI WARNING:                                                          ║
║  Removing or weakening ANY gate can cause UNLIMITED CAPITAL LOSS.        ║
║  ApprovalResult.__bool__ raises TypeError — use .approved explicitly.    ║
║                                                                          ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, time as dt_time
from typing import List, Optional, Tuple, Any
from config.signal_weights import MIN_CONFIDENCE, MIN_DIRECTION_GAP

logger = logging.getLogger("master_decision")


# ══════════════════════════════════════════════════════════════════
# RESULT CONTRACT
# ══════════════════════════════════════════════════════════════════

@dataclass
class ApprovalResult:
    """Every trade must receive an ApprovalResult with .approved=True before execution.
    
    P1-A: __bool__ intentionally raises TypeError.
    This prevents silent bugs where `if engine.approve(signal):` passes
    because a non-empty object is truthy in Python.
    
    CORRECT:   result = engine.approve(signal); if result.approved:
    WRONG:     if engine.approve(signal):  # <-- raises TypeError
    """

    approved: bool
    reason: str
    timestamp: datetime = field(default_factory=datetime.now)
    gates_failed: List[str] = field(default_factory=list)
    gates_passed: List[str] = field(default_factory=list)

    @property
    def gate_failed(self) -> str | None:
        """Returns the first failed gate name, or None if all passed."""
        return self.gates_failed[0] if self.gates_failed else None

    def __bool__(self):
        """P1-A: Raise on bool usage to make wrong usage impossible.
        
        Forces callers to use `.approved` explicitly:
            result = engine.approve(signal)
            if result.approved:  # ← correct
        """
        raise TypeError(
            "ApprovalResult cannot be used directly as bool. "
            "Use result.approved explicitly: `if result.approved:`"
        )

    def __str__(self):
        icon = "✅" if self.approved else "❌"
        return (
            f"{icon} MasterDecision: {'APPROVED' if self.approved else 'BLOCKED'} | "
            f"{self.reason}"
        )


# ══════════════════════════════════════════════════════════════════
# MASTER DECISION ENGINE
# ══════════════════════════════════════════════════════════════════

class MasterDecisionEngine:
    """
    The single mandatory gate that sits between any signal and any order.

    Design principle:
        If you cannot call this and get APPROVED → you cannot trade. Period.

    Usage (both architectures — P1-A safe pattern):
        result = master.approve(signal_type, context)
        if not result.approved:  # ← MUST use .approved, NOT bare `if not result:`
            logger.warning(f"Trade blocked at gate '{result.gate_failed}': {result.reason}")
            return None
        # Only here: place the actual order
    """

    # ── Trading hours (IST) ───────────────────────────────────────
    MARKET_OPEN   = dt_time(9, 15)
    MARKET_CLOSE  = dt_time(15, 20)   # hard close — no new trades after this
    FRIDAY_CUTOFF = dt_time(15, 10)   # weekend buffer on Fridays

    def __init__(
        self,
        risk_manager=None,          # core.risk_manager.RiskManager  (v4.6.1)
        nifty_risk=None,            # nifty_strategy.risk_manager.RiskManager
        position_manager=None,      # core.position_manager.PositionManager
        discipline_engine=None,     # core.discipline_engine.DisciplineEngine
        exit_engine=None,           # core.exit_engine.ExitEngine
        session_strategy=None,      # core.session_strategy.SessionStrategy
    ):
        self.risk_manager     = risk_manager
        self.nifty_risk       = nifty_risk
        self.position_manager = position_manager
        self.discipline       = discipline_engine
        self.exit_engine      = exit_engine
        self.session_strategy = session_strategy

        # Internal state
        self._total_approvals = 0
        self._total_blocks    = 0
        self._last_result: Optional[ApprovalResult] = None
        
        from collections import defaultdict
        self.gate_rejections = defaultdict(int)
        
        # ── Log throttle: suppress repetitive steady-state messages ──
        # key = gate_id, value = last reason logged
        # A message is only logged again if the REASON changes (e.g. time advances)
        self._throttled_log: dict = {}

    # ── PUBLIC API ────────────────────────────────────────────────
    def approve(
        self,
        signal_type: str,           # "BUY_CE" | "BUY_PE" | "NO_TRADE"
        context: Optional[dict] = None,
    ) -> ApprovalResult:
        """
        Run every safety gate in order.
        Return ApprovalResult — caller checks `.approved` before placing order.

        Gates (in order, first failure stops the chain):
          G1  Signal type whitelist
          G2  Trading hours
          G3  Daily loss kill switch   (core risk_manager)
          G4  Daily loss limit         (nifty_strategy risk_manager, if present)
          G5  Daily target hit         (exit_engine)
          G6  Position capacity        (position_manager)
          G7  Session rules            (session_strategy)
          G8  Discipline rules         (discipline_engine)
          G9  No NEUTRAL/NO_TRADE      (final sanity)
        """
        ctx = context or {}
        passed: List[str] = []
        now = datetime.now()

        def _block(gate: str, reason: str, throttle: bool = False) -> ApprovalResult:
            self._total_blocks += 1
            self.gate_rejections[gate] += 1
            result = ApprovalResult(
                approved=False,
                reason=reason,
                gates_passed=list(passed),
                gates_failed=[gate],
            )
            self._last_result = result
            # Throttled gates only log when the reason changes (prevents log spam)
            if throttle:
                if self._throttled_log.get(gate) != reason:
                    logger.warning(f"🚫 [{gate}] {reason}")
                    self._throttled_log[gate] = reason
            else:
                logger.warning(f"🚫 [{gate}] {reason}")
            return result

        def _ok(gate: str):
            passed.append(gate)

        # ── G0: Probabilistic Intelligence Gate (2026-04-09) ───────
        # When a CRITICAL or MAJOR gap is active, indicators (EMA, VWAP,
        # momentum) are contaminated by overnight distortion. We respond by
        # raising the minimum confidence threshold, NOT by blocking trading
        # outright. This forces the engine to require stronger conviction
        # before entering during indicator-contaminated market opens.
        sig_obj = ctx.get("signal_obj")
        score = sig_obj.weighted_score if sig_obj else ctx.get("weighted_score", 1.0)
        
        effective_min_confidence = MIN_CONFIDENCE
        gap_mgr = ctx.get("gap_manager")
        if gap_mgr is not None:
            status = gap_mgr.get_status()
            severity = status.get("severity", "NONE")
            current_penalty_pct = status.get("current_penalty_pct", 0.0)
            if severity == "CRITICAL" and current_penalty_pct > 5.0:
                # CRITICAL gap (>1 ATR): require 25% more confidence
                # Decays naturally as the gap penalty melts away
                boost = MIN_CONFIDENCE * 0.25 * (current_penalty_pct / 40.0)
                effective_min_confidence = round(MIN_CONFIDENCE + boost, 3)
                logger.debug(
                    f"[G0] CRITICAL gap active ({current_penalty_pct:.1f}% penalty) — "
                    f"confidence threshold raised: {MIN_CONFIDENCE:.3f} → {effective_min_confidence:.3f}"
                )
            elif severity == "MAJOR" and current_penalty_pct > 10.0:
                # MAJOR gap (>0.95 ATR): require 15% more confidence
                boost = MIN_CONFIDENCE * 0.15 * (current_penalty_pct / 30.0)
                effective_min_confidence = round(MIN_CONFIDENCE + boost, 3)
                logger.debug(
                    f"[G0] MAJOR gap active ({current_penalty_pct:.1f}% penalty) — "
                    f"confidence threshold raised: {MIN_CONFIDENCE:.3f} → {effective_min_confidence:.3f}"
                )

        if score < effective_min_confidence:
            return _block(
                "G0_PROBABILITY",
                f"Scored {score:.2f} < {effective_min_confidence:.3f} "
                f"(gap-adjusted threshold, severity={ctx.get('gap_manager', None) and gap_mgr.get_status().get('severity', 'NONE')})"
                if effective_min_confidence > MIN_CONFIDENCE
                else f"Scored {score:.2f} < {MIN_CONFIDENCE} (Insufficient probabilistic edge)"
            )
        _ok("G0_PROBABILITY")

        # ── G1: Signal whitelist ──────────────────────────────────
        ALLOWED = {"BUY_CE", "BUY_PE"}
        if signal_type not in ALLOWED:
            return _block("G1_SIGNAL", f"'{signal_type}' is not a tradeable signal")
        _ok("G1_SIGNAL")

        # ── G2: Trading hours ─────────────────────────────────────
        time_ok, time_msg = self._check_trading_hours(now)
        if not time_ok:
            # Throttle: market-close, pre-open, and weekend messages repeat
            # every single cycle and bury real log events. Log once per message.
            return _block("G2_HOURS", time_msg, throttle=True)
        else:
            # Clear throttle when market reopens so next close logs fresh
            self._throttled_log.pop("G2_HOURS", None)
        _ok("G2_HOURS")

        # ── G3: Core risk_manager kill switch (v4.6.1) ───────────
        if self.risk_manager is not None:
            ok, msg = self.risk_manager.can_take_new_trade(
                type("_Sig", (), {"signal_type": type("_T", (), {"value": signal_type})()})()
            )
            if not ok:
                return _block("G3_RISK_CORE", msg)
        _ok("G3_RISK_CORE")

        # ── G4: nifty_strategy risk_manager ──────────────────────
        if self.nifty_risk is not None:
            ok, msg = self.nifty_risk.can_take_trade(signal_type)
            if not ok:
                return _block("G4_RISK_NIFTY", msg)
        _ok("G4_RISK_NIFTY")

        # ── G5: Daily profit target ───────────────────────────────
        if self.exit_engine is not None and self.exit_engine.daily_target_hit:
            return _block("G5_DAILY_TARGET", "Daily profit target already hit — no new trades")
        _ok("G5_DAILY_TARGET")

        # ── G6: Position capacity ─────────────────────────────────
        if self.position_manager is not None:
            can_trade, pm_reason = self.position_manager.can_trade()
            if not can_trade:
                return _block("G6_POSITIONS", pm_reason)
        _ok("G6_POSITIONS")

        # ── G7: Session rules ─────────────────────────────────────
        session_is_approved = True
        if self.session_strategy is not None:
            rules = self.session_strategy.get_current_rules()
            if not rules.get("can_trade", True):
                session_is_approved = False
                return _block("G7_SESSION", rules.get("reason", "Session blocked"))
        _ok("G7_SESSION")

        # ── G8: Discipline rules ──────────────────────────────────
        if self.discipline is not None:
            disc_ctx = ctx.get("discipline_context", {})
            if "session_approved" not in disc_ctx:
                disc_ctx["session_approved"] = session_is_approved
            
            disc_ok, disc_msg = self.discipline.check_discipline(
                "TRADE", disc_ctx
            )
            if not disc_ok:
                return _block("G8_DISCIPLINE", disc_msg)
        _ok("G8_DISCIPLINE")

        # ── ALL GATES PASSED ──────────────────────────────────────
        self._total_approvals += 1
        result = ApprovalResult(
            approved=True,
            reason=f"All {len(passed)} gates passed | {signal_type} approved",
            gates_passed=passed,
        )
        self._last_result = result
        logger.info(f"✅ MasterDecision APPROVED | {signal_type} | {len(passed)} gates passed")
        return result

    # ── Trading hours (fixes the NameError bug in core/risk_manager.py) ──
    def _check_trading_hours(self, now: datetime) -> Tuple[bool, str]:
        """
        Centralised, bug-free trading-hours check.

        Fixes: core/risk_manager.py is_within_trading_hours() had a NameError
               (`weekday` and `current_time` were used before being defined).
        """
        current_time = now.time()
        weekday      = now.weekday()   # 0=Mon … 4=Fri … 6=Sun

        # Before market open
        if current_time < self.MARKET_OPEN:
            return False, f"Market not open yet (opens {self.MARKET_OPEN})"

        # Weekend buffer: no new trades after 15:10 on Friday
        if weekday == 4 and current_time >= self.FRIDAY_CUTOFF:
            return False, f"Weekend Buffer: no new trades after {self.FRIDAY_CUTOFF} on Friday"

        # Hard market close
        if current_time >= self.MARKET_CLOSE:
            return False, f"Market closing buffer: no new trades after {self.MARKET_CLOSE}"

        # Weekend — should never happen if bot is correctly scheduled
        if weekday >= 5:
            return False, f"Market closed (weekend — day {weekday})"

        return True, "OK"

    # ── Status ────────────────────────────────────────────────────
    def get_stats(self) -> dict:
        return {
            "total_approvals": self._total_approvals,
            "total_blocks":    self._total_blocks,
            "approval_rate":   (
                round(self._total_approvals /
                      max(1, self._total_approvals + self._total_blocks) * 100, 1)
            ),
            "gate_rejections": dict(self.gate_rejections),
            "last_result": str(self._last_result) if self._last_result else None,
        }

    def explain_last(self) -> str:
        """Human-readable explanation of the last decision — useful for Telegram /status."""
        if not self._last_result:
            return "No decisions made yet."
        r = self._last_result
        lines = [str(r)]
        if r.gates_passed:
            lines.append(f"  Passed : {', '.join(r.gates_passed)}")
        if r.gates_failed:
            lines.append(f"  Failed : {', '.join(r.gates_failed)}")
        return "\n".join(lines)
