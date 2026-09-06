import pytest
import pandas as pd
from datetime import datetime
from models.lrm_models import LRMSignal
from core.lrm_engine import LRMEngine

class MockSnapshot:
    def __init__(self, price, atr, vwap):
        self.price = price
        self.atr = atr
        self.vwap = vwap
        self.regime_state = {"regime": "TRENDING"}
        self.bid_volume = 1000
        self.ask_volume = 500
        self.large_buy_orders = 10
        self.large_sell_orders = 5

class MockSettings:
    pass

def test_lrm_engine_basic_cycle():
    engine = LRMEngine(MockSettings())
    
    # Create fake dataframe
    df = pd.DataFrame({
        "open": [100, 101, 102, 103, 104],
        "high": [101, 102, 103, 104, 105],
        "low": [99, 100, 101, 102, 103],
        "close": [100.5, 101.5, 102.5, 103.5, 104.5],
        "volume": [1000, 1100, 1200, 1300, 1400]
    })
    
    snapshot = MockSnapshot(price=104.5, atr=1.5, vwap=102.0)
    
    # Run a cycle without any zones (should return NO_TRADE, not at zone)
    snap_result = engine.update(
        df=df,
        snapshot=snapshot,
        sr_state=None,
        oi_analysis=None,
        amd_state=None,
        structure_tracker_state=None,
        v2_decision="NO_SIGNAL",
        v2_kill_reason=""
    )
    
    assert snap_result.at_zone is False
    assert snap_result.lrm_signal == LRMSignal.NO_TRADE
    assert snap_result.v2_decision == "NO_SIGNAL"
    assert snap_result.lrm_schema_version == "v1.0"
    assert "unknown" in snap_result.git_commit or len(snap_result.git_commit) > 0

    print("Test passed.")
    
if __name__ == "__main__":
    test_lrm_engine_basic_cycle()
