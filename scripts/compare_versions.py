import sqlite3
import json
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime

# Import V2.1 Pipeline Components
from core.confidence_calibrator import ConfidenceCalibrator
from core.expected_value_engine import ExpectedValueEngine
from core.trend_structure_tracker import TrendStructureTracker
from core.trade_filter import TradeFilter, FilterResult
from models.signal import Signal
from models.enums import SignalGrade, SignalType, Direction, Strength
from models.regime import MarketRegime
from config.settings import Settings
from core.replay_simulator import ReplaySimulator

logger = logging.getLogger("compare_versions")
logging.basicConfig(level=logging.INFO, format="%(message)s")

def build_mock_signal(row: sqlite3.Row) -> Signal:
    """Reconstruct a Signal object from DB row."""
    # Convert DB row to expected format
    s = dict(row)
    
    buy_score = float(s.get("buy_score", 0.0))
    sell_score = float(s.get("sell_score", 0.0))
    
    if buy_score > sell_score:
        direction = Direction.BULLISH
    elif sell_score > buy_score:
        direction = Direction.BEARISH
    else:
        direction = Direction.NEUTRAL
        
    signal = Signal(
        id=s.get("snapshot_id"),
        signal_type=SignalType.NO_TRADE if direction == Direction.NEUTRAL else (SignalType.BUY_CE if direction == Direction.BULLISH else SignalType.BUY_PE),
        direction=direction,
        strength=Strength.MODERATE,
        regime=MarketRegime[s.get("regime", "UNKNOWN").upper()] if s.get("regime") else MarketRegime.UNKNOWN,
        confidence=float(s.get("confidence", 0.0)),
        grade=SignalGrade(s.get("grade", "C")) if s.get("grade") else SignalGrade.C,
        timestamp=datetime.fromisoformat(s["timestamp"]) if s.get("timestamp") else datetime.now(),
        metadata=json.loads(s.get("market_context_json") or "{}")
    )
    return signal

def main():
    logger.info("Initializing V2.1 Compare Versions Script...")
    
    # Initialize V2.1 Components
    settings = Settings()
    trade_filter = TradeFilter(settings)
    calibrator = ConfidenceCalibrator()
    ev_engine = ExpectedValueEngine(min_ev_r=0.50, min_ev_score=60.0)
    trend_tracker = TrendStructureTracker(max_reentry_per_trend=2)
    trade_filter.trend_tracker = trend_tracker
    
    sim = ReplaySimulator()
    
    conn = sqlite3.connect("data/trading_v4_sim.db")
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM decision_snapshots ORDER BY timestamp").fetchall()
    
    v4_stats = {"total": 0, "executed": 0, "wins": 0, "losses": 0, "r_sum": 0.0}
    v2_stats = {"total": 0, "executed": 0, "wins": 0, "losses": 0, "r_sum": 0.0}
    
    gate_attribution = {}
    
    logger.info(f"Processing {len(rows)} historical snapshots...")
    
    for row in rows:
        v4_stats["total"] += 1
        s = dict(row)
        
        # 1. Baseline V4.6.1 Execution
        v4_executed = s.get("final_decision", "") == "EXECUTE"
        
        # We only evaluate counterfactual results if confidence > 0 or executed
        c_result = sim.simulate_rejection(s)
        
        if v4_executed:
            v4_stats["executed"] += 1
            if c_result:
                v4_stats["r_sum"] += c_result.exp_r_15m
                if c_result.is_win:
                    v4_stats["wins"] += 1
                else:
                    v4_stats["losses"] += 1
                    
        # 2. V2.1 Pipeline Execution
        signal = build_mock_signal(row)
            
        if signal.signal_type == SignalType.NO_TRADE:
            continue
            
        v2_stats["total"] += 1
        
        regime_name = signal.regime.value
        calibrated_pwin, calib_telemetry = calibrator.calibrate(signal.confidence, regime_name)
        if not hasattr(signal, "metadata") or signal.metadata is None:
            signal.metadata = {}
        signal.metadata["calibration_telemetry"] = calib_telemetry
        
        # Provide sensible defaults for RR and spread to evaluate EV Engine
        rr = 2.0
        spread_pct = float(s.get("spread_pct", 0.8) or 0.8)
        
        ev_result = ev_engine.evaluate(
            calibrated_pwin=calibrated_pwin,
            risk_reward_ratio=rr,
            spread_pct=spread_pct
        )
        signal.ev_info = ev_result
        
        class MockSnapshot:
            pass
        snapshot = MockSnapshot()
        snapshot.price = float(s.get("spot_price", 0.0) or 0.0)
        
        agent_outputs = json.loads(s.get("agent_outputs_json") or "{}")
        market_context = json.loads(s.get("market_context_json") or "{}")
        gate_results = json.loads(s.get("gate_results_json") or "{}")
        
        # Ensure 'grade' is passed through regime info properly
        regime_info = {"regime": regime_name}
        
        try:
            result = trade_filter.evaluate(
                signal=signal,
                snapshot=snapshot,
                agent_outputs=agent_outputs,
                regime_info=regime_info,
                structure_info={},
                learning_info={},
                decay_info={},
                cost_info={},
                position_manager_status={},
                confluence_score=signal.confidence
            )
        except Exception as e:
            logger.error(f"Error evaluating filter: {e}")
            continue
            
        if result.passed:
            v2_stats["executed"] += 1
            trend_tracker.record_trade_execution(signal.direction.value, snapshot.price)
            if c_result:
                v2_stats["r_sum"] += c_result.exp_r_15m
                if c_result.is_win:
                    v2_stats["wins"] += 1
                else:
                    v2_stats["losses"] += 1
        else:
            reason = result.kill_reason
            gate_attribution[reason] = gate_attribution.get(reason, 0) + 1

    # Generate Report Table
    print("\n" + "="*50)
    print("V4.6.1 BASELINE vs V2.1 PERFORMANCE")
    print("="*50)
    
    def format_stats(stats):
        executed = stats['executed']
        wins = stats['wins']
        win_rate = (wins / executed * 100) if executed > 0 else 0
        avg_r = stats['r_sum'] / executed if executed > 0 else 0
        return f"{executed:4d} | {win_rate:5.1f}% | {avg_r:+5.2f}R | Total R: {stats['r_sum']:+6.2f}R"
        
    print(f"V4.6.1 Baseline: {format_stats(v4_stats)}")
    print(f"V2.1 Candidate : {format_stats(v2_stats)}")
    
    print("\n--- Gate Attribution (V2.1 Rejections) ---")
    for reason, count in sorted(gate_attribution.items(), key=lambda x: x[1], reverse=True):
        print(f"{count:4d} : {reason}")

if __name__ == '__main__':
    main()
