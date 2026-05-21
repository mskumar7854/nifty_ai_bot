from models.signals import Signal, MarketRegime, ExecutionPolicy, SignalType
from utils.logger import get_logger

logger = get_logger("regime_adapter")

class RegimeAdapter:
    """
    Applies Regime-Specific Execution Policies without mutating the agent's original intent.
    Creates an ExecutionPolicy overlay on the Signal that the Simulation/Execution engine respects.
    """

    def apply_policy(self, signal: Signal) -> Signal:
        # Initialize an empty policy
        policy = ExecutionPolicy(
            original_sl=signal.stop_loss,
            adapted_sl=signal.stop_loss,
            original_qty=signal.position_size,
            adapted_qty=signal.position_size,
        )

        regime = signal.regime

        if regime == MarketRegime.CHOPPY or regime == MarketRegime.RANGING:
            # CHOPPY: Suppress BREAKOUT trades
            # Since we don't have a specific "BREAKOUT" trade type in SignalType, we rely on the agent name
            # or reasons to detect breakout trades. But we can also check if the system regime is choppy,
            # we should suppress signals that are meant for breakouts.
            # Let's check reasons for "breakout"
            is_breakout = any("breakout" in r.lower() for r in signal.reasons)
            if is_breakout:
                policy.suppressed = True
                policy.reason = "Regime Mismatch: Suppressed BREAKOUT signal in CHOPPY regime"

        elif regime == MarketRegime.VOLATILE:
            # VOLATILE: Widen SL by 1.5x, maintain constant risk budget
            original_sl_dist = abs(signal.entry_price - signal.stop_loss)
            if original_sl_dist > 0:
                policy.sl_multiplier = 1.5
                widened_sl_dist = original_sl_dist * 1.5
                
                # Determine direction to widen SL
                if signal.stop_loss < signal.entry_price:
                    policy.adapted_sl = signal.entry_price - widened_sl_dist
                else:
                    policy.adapted_sl = signal.entry_price + widened_sl_dist
                
                # Constant risk budget: new_qty = original_risk / widened_sl_dist
                original_risk = original_sl_dist * signal.position_size
                new_qty = max(1, int(original_risk / widened_sl_dist))
                policy.adapted_qty = new_qty
                
                policy.reason = "VOLATILE Regime: Widened SL (1.5x) and adjusted size for constant risk"

        elif regime == MarketRegime.TRENDING_UP or regime == MarketRegime.TRENDING_DOWN:
            # TRENDING: Extend TP2 by 1.5x
            policy.tp2_multiplier = 1.5
            policy.reason = "TRENDING Regime: Extended TP2 (1.5x) to allow runners"

        elif regime == MarketRegime.BREAKOUT:
            # BREAKOUT: Reduce position size by 50%
            policy.position_scale = 0.5
            new_qty = max(1, int(signal.position_size * 0.5))
            policy.adapted_qty = new_qty
            policy.reason = "BREAKOUT Regime: Reduced size by 50% (High risk of false breakouts)"

        if policy.reason:
            logger.info(f"🛡️ RegimeAdapter Applied: {policy.reason} "
                        f"(Orig Qty: {policy.original_qty} -> {policy.adapted_qty}, "
                        f"Orig SL: {policy.original_sl} -> {policy.adapted_sl})")
            
        signal.execution_policy = policy
        return signal
