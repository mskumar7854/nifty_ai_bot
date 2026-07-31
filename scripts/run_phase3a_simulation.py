import sqlite3
import json
import uuid
import sys
import os
from datetime import datetime

# Add root path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from models.signal import Signal, SignalType, Direction
from core.pipelines.decision_pipeline import DecisionPipeline
from config.settings import Settings
from core.context import RuntimeContext

class MockSnapshot:
    def __init__(self, price, vix, atr):
        self.price = price
        self.vix = vix
        self.atr = atr
        self.spread_pct = 0.5

class MockAgentOutput:
    def __init__(self, direction, confidence, details):
        self.direction = direction
        self.confidence = confidence
        self.details = details

class MockEvEngine:
    def evaluate(self, **kwargs):
        return {"ev_r": 1.2, "normalized_score": 85, "grade": "A"}

class MockCalibrator:
    def calibrate(self, conf, regime):
        return conf, {"regime": regime, "raw": conf, "calibrated": conf}

class MockContext:
    def __init__(self):
        self.simulation = None
        self.telemetry = type('obj', (object,), {'metrics_logger': type('obj', (object,), {'log_cycle': lambda x: None, 'log_execution_truth': lambda x: None})})
        self.system = type('obj', (object,), {'_update_dashboard': lambda x, y: None})
        self.data_manager = type('obj', (object,), {})

def simulate():
    print("Running Phase 3A Controlled Simulation over historical snapshots...")
    
    conn = sqlite3.connect("data/trading_v4_sim.db")
    conn.row_factory = sqlite3.Row
    # Fetch 1000 snapshots, we'll process ones that had signals
    rows = conn.execute("SELECT * FROM decision_snapshots WHERE confidence > 0 LIMIT 1000").fetchall()
    
    settings = Settings()
    settings.system_mode.mode = "SIMULATION"
    ctx = RuntimeContext(settings=settings, mode="SIMULATION", is_simulation=True, telegram_enabled=False, event_manager=None, broker_health=None)
    
    pipeline = DecisionPipeline(ctx)
    pipeline.ev_engine = MockEvEngine()
    pipeline.calibrator = MockCalibrator()
    
    count = 0
    executed = 0
    shadow = 0
    
    for row in rows:
        meta = json.loads(row["market_context_json"]) if row["market_context_json"] else {}
        snap = MockSnapshot(price=row["spot_price"], vix=meta.get("vix", 15.0), atr=meta.get("atr", 100.0))
        
        from models.enums import Strength
        from datetime import datetime
        try:
            ts = datetime.fromisoformat(row["timestamp"])
        except:
            ts = datetime.now()
        # Ensure direction exists in row or default to BULLISH
        direction_str = row["direction"] if "direction" in row.keys() else "BULLISH"
        sig = Signal(
            id=f"{row['timestamp'].replace(':', '').replace('-', '').replace('T', '-')}-{uuid.uuid4().hex[:4].upper()}",
            timestamp=ts,
            signal_type=SignalType.BUY_CE if direction_str == "BULLISH" else SignalType.BUY_PE,
            direction=Direction.BULLISH if direction_str == "BULLISH" else Direction.BEARISH,
            confidence=row["confidence"],
            strength=Strength.MODERATE
        )
        sig.metadata = {"calibrated_pwin": sig.confidence, "ev_r": 1.2, "ev_score": 85}
        sig.ev_info = {"ev_r": 1.2, "normalized_score": 85, "grade": "A", "probability": sig.confidence}
        
        class MockConfluence:
            confluence_ratio = 80
            bullish_agents = 4
            bearish_agents = 1
            total_agents = 5
            concurring_agents = 4
        sig.confluence = MockConfluence()
        
        # mock outputs
        agents_data = json.loads(row.get("agents_json", "{}")) if "agents_json" in row.keys() else {}
        outputs = {}
        for k in ["trend", "momentum", "volatility", "regime", "structure", "learning", "decay"]:
            outputs[k] = MockAgentOutput(sig.direction, sig.confidence, agents_data.get(k, {}))
            
        # Instead of calling evaluate() which needs df, we will call trade_filter directly then _record_v2_snapshot
        
        _regime_info = {"regime": "TRENDING"}
        _structure_info = {"structure": "OK", "trend_alignment": True}
        _learning_info = {"confidence": 60, "current_streak": 0}
        _decay_info = {}
        _cost_info = {"total_costs": 60, "break_even_points": 2.0}
        pm_status = {"daily_trades_taken": 0, "today_trades": 0, "open_positions": 0}
        
        filter_result = pipeline.trade_filter.evaluate(
            signal=sig, snapshot=snap, agent_outputs=outputs,
            regime_info=_regime_info, structure_info=_structure_info,
            learning_info=_learning_info, decay_info=_decay_info,
            cost_info=_cost_info, position_manager_status=pm_status,
            confluence_score=70
        )
        
        # Manually add risk to signal for snapshot extraction
        sig.risk_info = {"position_size": 50, "stop_loss": 22650, "target": 22800, "risk_amount": 500}
        sig.structure_info = {"structure": "OK", "trend_alignment": True}
        
        from models.snapshot_v2 import Outcome
        sig.outcome = Outcome(
            status="EXECUTED", trade_id=sig.id, entry_time="10:05", exit_time="10:15",
            entry_price=22700, exit_price=22750, realized_r=1.5,
            max_favorable_excursion_r=2.0, max_adverse_excursion_r=-0.5, exit_reason="TARGET"
        )        
        timeline = {
            "Market Snapshot Created": "10:00:00.000",
            "Agents Completed": "10:00:00.010",
            "Confidence Calibrated": "10:00:00.015",
            "EV Calculated": "10:00:00.020",
            "TradeFilter Decision": "10:00:00.025",
            "OMS Intent Generated": "10:00:00.030"
        }
        
        if filter_result.passed:
            final_decision = "EXECUTE"
            rejection_reason = "Passed all gates"
            executed += 1
        else:
            final_decision = "REJECTED"
            rejection_reason = "Failed trade filter"
            
        pipeline._record_v2_snapshot(sig, snap, outputs, filter_result, final_decision, rejection_reason, timeline)
        
        # Manually verify if shadow trade was created (requires re-querying the DB)
        count += 1

    print(f"Simulation completed. Processed {count} signals. Executed {executed}.")

if __name__ == "__main__":
    simulate()
