import asyncio
import os
from config.settings import Settings
from core.trend_structure_tracker import TrendStructureTracker
from core.data_manager import MarketSnapshot
from models.signal import Signal, SignalType, Direction
from models.regime import MarketRegime as Regime

def verify_structural_leg():
    settings = Settings()
    tracker = TrendStructureTracker(max_reentry_per_trend=2)
    
    print("Testing Monotonic Leg Sequence...")
    # Leg 1 / 1
    auth1, reason1, _ = tracker.check_reentry_allowed("BULLISH")
    assert auth1 is True
    tracker.record_trade_execution("BULLISH", 24500, timestamp="2026-08-18T10:00:00")
    print(f"Trade 1 -> Leg {tracker.leg_id} / {tracker.entries_in_leg}")
    assert tracker.leg_id == 1 and tracker.entries_in_leg == 1

    # Leg 1 / 2
    auth2, reason2, _ = tracker.check_reentry_allowed("BULLISH")
    assert auth2 is True
    tracker.record_trade_execution("BULLISH", 24500, timestamp="2026-08-18T10:05:00")
    print(f"Trade 2 -> Leg {tracker.leg_id} / {tracker.entries_in_leg}")
    assert tracker.leg_id == 1 and tracker.entries_in_leg == 2

    # REJECT
    auth3, reason3, _ = tracker.check_reentry_allowed("BULLISH")
    print(f"Trade 3 -> REJECT ({reason3})")
    assert auth3 is False
    
    # BOS (Break of Structure)
    print("\nBOS detected...")
    tracker.register_structural_event(event_type="BOS", details={"direction": "BULLISH"})
    assert tracker.leg_id == 1 # Still 1 because no trade executed yet
    
    # Leg 2 / 1
    auth4, reason4, _ = tracker.check_reentry_allowed("BULLISH")
    assert auth4 is True
    tracker.record_trade_execution("BULLISH", 24500, timestamp="2026-08-18T10:20:00", reset_event="BOS")
    print(f"Trade 4 -> Leg {tracker.leg_id} / {tracker.entries_in_leg}")
    assert tracker.leg_id == 2 and tracker.entries_in_leg == 1

    # Leg 2 / 2
    auth5, reason5, _ = tracker.check_reentry_allowed("BULLISH")
    assert auth5 is True
    tracker.record_trade_execution("BULLISH", 24500, timestamp="2026-08-18T10:25:00")
    print(f"Trade 5 -> Leg {tracker.leg_id} / {tracker.entries_in_leg}")
    assert tracker.leg_id == 2 and tracker.entries_in_leg == 2

    # REJECT
    auth6, reason6, _ = tracker.check_reentry_allowed("BULLISH")
    print(f"Trade 6 -> REJECT ({reason6})")
    assert auth6 is False

    # Direction change
    print("\nDirection change detected...")
    # Leg 3 / 1
    auth7, reason7, _ = tracker.check_reentry_allowed("BEARISH")
    assert auth7 is True
    tracker.record_trade_execution("BEARISH", 24500, timestamp="2026-08-18T10:35:00")
    print(f"Trade 7 (Direction Change) -> Leg {tracker.leg_id} / {tracker.entries_in_leg}")
    assert tracker.leg_id == 3 and tracker.entries_in_leg == 1

    print("\nAll invariants and behaviors verified successfully.")

if __name__ == "__main__":
    verify_structural_leg()
