from datetime import datetime
from config.settings import Settings

class SessionGuard:
    """
    Single source of truth for market session gating.
    Ensures that data layer and strategy layer synchronize on the same unblock time.
    """
    
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
            return False, f"Market session start protection — waiting until {safe_time_str}"
            
        return True, "Session OK"
