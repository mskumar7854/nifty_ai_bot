import asyncio
from datetime import datetime
import logging
import sys

# Configure logging to console
logging.basicConfig(level=logging.WARNING, format='%(message)s', stream=sys.stdout)

from core.trade_filter import TradeFilter
from config.settings import Settings
from models.signal import Signal, SignalType, Direction, Strength

settings = Settings()
# Force log explicitly for demo
settings.system_mode.log_filter_kills = True

tf = TradeFilter(settings)

# Mocked signal for PEV drop trap
signal = Signal(
    id="sim-test-1",
    timestamp=datetime.now(),
    signal_type=SignalType.BUY_CE,
    direction=Direction.BULLISH,
    confidence=50.0,  # 50% chance
    strength=Strength.MODERATE,
    entry_price=100.0,
    stop_loss=90.0,   # Risk = 10 pts
    target_1=110.0,   # Target = 10 pts (Horrible PEV)
    target_2=120.0,
    position_size=50,
    reasons=["test setup"],
    warnings=[]
)

print("--- RUNNING SIMULATION TEST FOR PEV ---")
tf.evaluate(
    signal=signal,
    snapshot=None,
    agent_outputs={},
    regime_info={"regime": "RANGING"},
    structure_info={"structure": "OK"},
    learning_info={"confidence": 80, "current_streak": 2},
    decay_info={"theta_pct_per_hour": 1.0, "iv_crushing": False},
    cost_info={"total_costs": 150},
    position_manager_status={"today_trades": 2},
    confluence_score=80.0
)

# Mock Chop Zone trap
# Force a spoofed datetime by directly attacking the object logic internally just for output test, or simply passing parameters.
print("\n--- RUNNING SIMULATION TEST FOR DAILY LIMIT ---")
tf.evaluate(
    signal=signal,
    snapshot=None,
    agent_outputs={},
    regime_info={"regime": "RANGING"},
    structure_info={"structure": "OK"},
    learning_info={"confidence": 80, "current_streak": 2},
    decay_info={"theta_pct_per_hour": 1.0, "iv_crushing": False},
    cost_info={"total_costs": 150},
    position_manager_status={"today_trades": 6},  # Cap is 5
    confluence_score=80.0
)
