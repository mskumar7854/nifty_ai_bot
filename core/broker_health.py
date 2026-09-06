from typing import Optional
from utils.logger import get_logger

logger = get_logger("broker_health")

class BrokerHealthMonitor:
    """
    Continuously probes broker API health and blocks trading
    if connectivity degrades.
    
    Tracks:
        - api_latency_ms:         round-trip time of last API call
        - last_successful_order:  timestamp of last confirmed order
        - feed_delay_s:           age of the most recent market data tick
        - is_healthy:             computed gate — False blocks new orders
    """
    def __init__(self, settings):
        self.settings = settings
        self._warn_ms  = getattr(settings.alerts, "broker_latency_warn_ms",  1500.0)
        self._halt_ms  = getattr(settings.alerts, "broker_latency_halt_ms",  3000.0)
        self.poll_interval_s: float = 15.0

        self.api_latency_ms: float = 0.0
        self.last_successful_order: Optional[float] = None
        self.feed_delay_s: float = 0.0
        self.consecutive_degraded: int = 0

        self.is_healthy: bool = True
        self.degraded_reason: str = ""

    def record_order_success(self):
        """Call this after every successful broker order placement."""
        import time as _time
        self.last_successful_order = _time.time()

    def record_api_latency(self, latency_ms: float):
        """Call this after every broker API round-trip."""
        self.api_latency_ms = latency_ms

        if latency_ms >= self._halt_ms:
            self.consecutive_degraded += 1
            self.degraded_reason = f"API latency {latency_ms:.0f}ms ≥ halt threshold {self._halt_ms:.0f}ms"
            if self.consecutive_degraded >= 3:
                self.is_healthy = False
                logger.critical(
                    "🔴 [BROKER HEALTH] DEGRADED — latency=%.0fms (×%d consecutive). "
                    "New trades BLOCKED.", latency_ms, self.consecutive_degraded
                )
        elif latency_ms >= self._warn_ms:
            logger.warning(
                "⚠️ [BROKER HEALTH] High latency: %.0fms", latency_ms
            )
            self.consecutive_degraded = 0  # warn-only; don't count as halt
        else:
            # Healthy: reset counter and re-enable
            if not self.is_healthy:
                logger.info("✅ [BROKER HEALTH] Latency normalised (%.0fms). Trades re-enabled.", latency_ms)
            self.consecutive_degraded = 0
            self.is_healthy = True
            self.degraded_reason = ""

    def get_status(self) -> dict:
        import time as _time
        last_order_age = (
            f"{_time.time() - self.last_successful_order:.0f}s ago"
            if self.last_successful_order else "never"
        )
        return {
            "healthy":             self.is_healthy,
            "api_latency_ms":      round(self.api_latency_ms, 1),
            "last_order":          last_order_age,
            "feed_delay_s":        round(self.feed_delay_s, 1),
            "consecutive_degraded": self.consecutive_degraded,
            "degraded_reason":     self.degraded_reason,
        }
