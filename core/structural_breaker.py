import time
import logging
from typing import Dict, Tuple

logger = logging.getLogger("system.breakers")

class StructuralBreaker:
    def __init__(self, state_manager):
        self.state_manager = state_manager
        # (instrument, direction) -> timestamp
        self._last_orders: Dict[Tuple[str, str], float] = {}

    def check_duplicate_order(self, instrument: str, direction: str, window_sec: float = 60.0) -> bool:
        """
        1. Duplicate Order Guard
        Blocks duplicate orders sent within the specified time window.
        """
        key = (instrument, direction)
        now = time.time()
        if key in self._last_orders:
            elapsed = now - self._last_orders[key]
            if elapsed < window_sec:
                reason = f"Duplicate order protection triggered for {instrument} {direction} ({elapsed:.1f}s < {window_sec}s)"
                self.state_manager.trigger_structural_halt(reason)
                return False
        self._last_orders[key] = now
        return True

    def check_broker_ack(self, order_id: str, elapsed_sec: float, timeout_sec: float = 5.0) -> bool:
        """
        2. Broker ACK Timeout Breaker
        Triggers a halt if the broker fails to acknowledge a sent order within timeout.
        """
        if elapsed_sec > timeout_sec:
            reason = f"Broker ACK missing for order {order_id} after {elapsed_sec:.1f}s (timeout: {timeout_sec}s)"
            self.state_manager.trigger_structural_halt(reason)
            return False
        elif elapsed_sec > 3.0:
            logger.warning(f"⚠️ High Broker ACK latency detected: {elapsed_sec:.1f}s (threshold: 3.0s)")
        return True

    def check_stop_loss_attached(self, order_id: str, stop_loss: float) -> bool:
        """
        3. Attached Stop Loss Breaker
        Ensures that every order placed has a valid Stop Loss.
        """
        if stop_loss <= 0.01:
            reason = f"Safety Violation: Order {order_id} sent without a valid Stop Loss ({stop_loss:.2f})"
            self.state_manager.trigger_structural_halt(reason)
            return False
        return True

    def check_position_mismatch(self, internal_count: int, broker_count: int) -> bool:
        """
        4. Position Reconciliation Breaker
        Halts trading immediately if the internal open position count differs from the broker count.
        """
        if internal_count != broker_count:
            reason = f"Position Reconciliation Mismatch! Internal Count: {internal_count} | Broker Count: {broker_count}"
            self.state_manager.trigger_structural_halt(reason)
            return False
        return True

    def check_telegram_execution_sync(
        self,
        signal_id: str,
        sent_time: float,
        current_time: float,
        current_price: float,
        signal_price: float,
        threshold_sec: float = 30.0,
        max_drift_pct: float = 0.3
    ) -> Tuple[bool, bool]:
        """
        5. Telegram Execution Sync Breaker (Price-Aware)
        Returns (is_valid, should_halt).
        
        - If delay > threshold_sec AND price drift > max_drift_pct -> reject signal (is_valid=False, should_halt=False).
        - If delay is within threshold OR drift is safe -> allow signal (is_valid=True, should_halt=False).
        - If delay is critically high (> 300s) -> queue desync halt (is_valid=False, should_halt=True).
        """
        delay = current_time - sent_time
        
        # Hard queue stall protection
        if delay > 300.0:
            reason = f"System Queue Stall: Signal {signal_id} executed {delay:.1f}s after generation (desync limit: 300s)"
            self.state_manager.trigger_structural_halt(reason)
            return False, True

        drift = abs(current_price - signal_price) / signal_price * 100 if signal_price > 0 else 0.0
        if delay > threshold_sec:
            if drift > max_drift_pct:
                logger.warning(
                    f"⚠️ Stale Signal Rejected: Signal {signal_id} approved {delay:.1f}s after birth "
                    f"and Nifty drifted {drift:.2f}% (max allowed: {max_drift_pct}%)"
                )
                return False, False
            else:
                logger.info(
                    f"ℹ️ Signal {signal_id} delay is {delay:.1f}s, but Nifty price drift is safe "
                    f"({drift:.2f}% <= {max_drift_pct}%). Execution allowed."
                )
        return True, False
