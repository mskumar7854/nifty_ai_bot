import logging
from datetime import datetime
from config.settings import Settings

logger = logging.getLogger("session_guard")

class SessionGuard:
    """
    Single source of truth for market session gating.
    Ensures that data layer and strategy layer synchronize on the same unblock time.

    Transition logging: emits a log ONLY when entering or leaving protection,
    completely silencing the steady-state wait period.
    """

    # ── Class-level state (singleton via Python import cache) ──
    _in_protection: bool = False
    _last_safe_time_str: str | None = None
    
    @staticmethod
    def can_trade(settings: Settings) -> tuple[bool, str]:
        """
        Returns (True, reason) if we are clear to trade.
        Returns (False, reason) if we are in market open protection.
        """
        now = datetime.now()
        safe_time_str = settings.trade_filter.market_open_safe_time
        try:
            safe_h, safe_m = map(int, safe_time_str.split(':'))
        except ValueError:
            safe_h, safe_m = 9, 20
            
        safe_time = now.replace(hour=safe_h, minute=safe_m, second=0, microsecond=0)

        if now < safe_time:
            # ── Entering or continuing protection ──
            if not SessionGuard._in_protection or SessionGuard._last_safe_time_str != safe_time_str:
                logger.info(
                    f"🛡️ Entering opening-session protection until {safe_time_str}"
                )
                SessionGuard._in_protection = True
                SessionGuard._last_safe_time_str = safe_time_str
            # Steady state: completely silent
            return False, f"Market session start protection — waiting until {safe_time_str}"

        # ── Protection lifted ──
        if SessionGuard._in_protection:
            logger.info("✅ Opening-session protection lifted — trading eligible")
            SessionGuard._in_protection = False
            
        return True, "Session OK"
