import sqlite3
import json
import logging
import os
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
from config.settings import Settings, PipelineConfig
from core.replay_simulator import ReplaySimulator

logger = logging.getLogger("gate_attribution")
logging.basicConfig(level=logging.INFO, format="%(message)s")

def build_mock_signal(row: sqlite3.Row) -> Signal:
    """Reconstruct a Signal object from DB row."""
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

def run_simulation(config_name: str, pipeline_config: PipelineConfig, baseline_winners: set, rows: list, sim: ReplaySimulator, rejection_dist: dict, waterfall: dict) -> dict:
    settings = Settings()
    trade_filter = TradeFilter(settings)
    calibrator = ConfidenceCalibrator()
    ev_engine = ExpectedValueEngine(min_ev_r=0.50, min_ev_score=60.0)
    trend_tracker = TrendStructureTracker(max_reentry_per_trend=2)
    trade_filter.trend_tracker = trend_tracker
    
    stats = {"executed": 0, "wins": 0, "losses": 0, "r_win_sum": 0.0, "r_loss_sum": 0.0, "max_drawdown": 0.0, "winners_preserved": 0}
    
    current_r = 0.0
    peak_r = 0.0
    
    for row in rows:
        s = dict(row)
        snapshot_id = s.get("snapshot_id")
        
        signal = build_mock_signal(row)
        if signal.signal_type == SignalType.NO_TRADE:
            continue
            
        regime_name = signal.regime.value
        calibrated_pwin, calib_telemetry = calibrator.calibrate(signal.confidence, regime_name)
        if not hasattr(signal, "metadata") or signal.metadata is None:
            signal.metadata = {}
        signal.metadata["calibration_telemetry"] = calib_telemetry
        
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
        gate_results = json.loads(s.get("gate_results_json") or "{}")
        
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
                confluence_score=signal.confidence,
                pipeline_config=pipeline_config
            )
        except Exception as e:
            logger.error(f"Error evaluating filter: {e}")
            continue
            
        if result.passed:
            stats["executed"] += 1
            trend_tracker.record_trade_execution(signal.direction.value, snapshot.price)
            c_result = sim.simulate_rejection(s)
            if c_result:
                r_multiple = c_result.exp_r_15m
                
                current_r += r_multiple
                if current_r > peak_r:
                    peak_r = current_r
                drawdown = peak_r - current_r
                if drawdown > stats["max_drawdown"]:
                    stats["max_drawdown"] = drawdown
                    
                if c_result.is_win:
                    stats["wins"] += 1
                    stats["r_win_sum"] += r_multiple
                    if snapshot_id in baseline_winners:
                        stats["winners_preserved"] += 1
                else:
                    stats["losses"] += 1
                    stats["r_loss_sum"] += r_multiple
        else:
            # Rejection Distribution
            if config_name not in rejection_dist:
                rejection_dist[config_name] = {}
            conf = signal.confidence
            bin_start = int(conf // 5) * 5
            bin_end = bin_start + 5
            bin_key = f"{bin_start}-{bin_end}"
            rejection_dist[config_name][bin_key] = rejection_dist[config_name].get(bin_key, 0) + 1
            
            # Waterfall
            waterfall[config_name] = waterfall.get(config_name, 0) + 1

    return stats

def main():
    logger.info("Initializing Gate Attribution Study...")
    
    sim = ReplaySimulator()
    
    conn = sqlite3.connect("data/trading_v4_sim.db")
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM decision_snapshots ORDER BY timestamp").fetchall()
    
    # 0. Evaluate Baseline
    baseline_winners = set()
    total_baseline_executed = 0
    
    for row in rows:
        s = dict(row)
        v4_executed = s.get("final_decision", "") == "EXECUTE"
        if v4_executed:
            total_baseline_executed += 1
            c_result = sim.simulate_rejection(s)
            if c_result and c_result.is_win:
                baseline_winners.add(s.get("snapshot_id"))
                
    logger.info(f"Baseline Executed: {total_baseline_executed}, Baseline Winners: {len(baseline_winners)}")
    
    # Configs
    configs_a = {
        "Baseline (All OFF)": PipelineConfig(False, False, False, False, False),
        "+ Confidence": PipelineConfig(True, False, False, False, False),
        "+ Confluence": PipelineConfig(True, True, False, False, False),
        "+ EV": PipelineConfig(True, True, True, False, False),
        "+ Structure": PipelineConfig(True, True, True, True, False),
        "Full V2.1": PipelineConfig(True, True, True, True, True),
    }
    
    configs_b = {
        "Confidence ONLY": PipelineConfig(True, False, False, False, False),
        "Confluence ONLY": PipelineConfig(False, True, False, False, False),
        "EV ONLY": PipelineConfig(False, False, True, False, False),
        "Structure ONLY": PipelineConfig(False, False, False, True, False),
        "Regime ONLY": PipelineConfig(False, False, False, False, True),
    }
    
    rejection_dist = {}
    waterfall = {}
    
    def run_suite(configs, suite_name):
        results = []
        for name, cfg in configs.items():
            stats = run_simulation(name, cfg, baseline_winners, rows, sim, rejection_dist, waterfall)
            pf = stats["r_win_sum"] / abs(stats["r_loss_sum"]) if stats["r_loss_sum"] != 0 else 0
            win_rate = (stats["wins"] / stats["executed"] * 100) if stats["executed"] > 0 else 0
            opp_capture = (stats["winners_preserved"] / len(baseline_winners) * 100) if baseline_winners else 0
            
            results.append({
                "Configuration": name,
                "Trades": stats["executed"],
                "Win Rate": f"{win_rate:.1f}%",
                "Profit Factor": f"{pf:.2f}",
                "Drawdown": f"{stats['max_drawdown']:.2f}R",
                "Winners Preserved": f"{opp_capture:.1f}%"
            })
        return results

    results_a = run_suite(configs_a, "Experiment A")
    results_b = run_suite(configs_b, "Experiment B")
    
    # Generate Output Reports
    os.makedirs("reports", exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    md_path = f"reports/gate_attribution_{today}.md"
    csv_path = f"reports/gate_attribution_{today}.csv"
    
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Gate Attribution Study\n\n")
        
        f.write("## Experiment A: Cumulative Progression\n")
        f.write("| Configuration | Trades | Win Rate | Profit Factor | Drawdown | Winners Preserved |\n")
        f.write("| --- | --- | --- | --- | --- | --- |\n")
        for r in results_a:
            f.write(f"| {r['Configuration']} | {r['Trades']} | {r['Win Rate']} | {r['Profit Factor']} | {r['Drawdown']} | {r['Winners Preserved']} |\n")
            
        f.write("\n## Experiment B: Independent Isolated Contribution\n")
        f.write("| Configuration | Trades | Win Rate | Profit Factor | Drawdown | Winners Preserved |\n")
        f.write("| --- | --- | --- | --- | --- | --- |\n")
        for r in results_b:
            f.write(f"| {r['Configuration']} | {r['Trades']} | {r['Win Rate']} | {r['Profit Factor']} | {r['Drawdown']} | {r['Winners Preserved']} |\n")
            
        f.write("\n## Opportunity Waterfall\n")
        prev = len(rows)
        f.write(f"Total Opportunities: {prev}\n")
        for name in ["+ Confidence", "+ Confluence", "+ EV", "+ Structure", "Full V2.1"]:
            rejected = waterfall.get(name, 0)
            passed = len(rows) - rejected
            f.write(f"↓\n{name}: {passed} survived ({rejected} rejected)\n")
            
        f.write("\n## Rejection Distribution (By Confidence Range)\n")
        for name, dist in rejection_dist.items():
            if name in ["Baseline (All OFF)"]: continue
            f.write(f"### {name}\n")
            for bin_key in sorted(dist.keys()):
                bars = "■" * max(1, (dist[bin_key] // 2))
                f.write(f"{bin_key}% : {bars} ({dist[bin_key]})\n")
            f.write("\n")
            
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("Experiment,Configuration,Trades,Win Rate,Profit Factor,Drawdown,Winners Preserved\n")
        for r in results_a:
            f.write(f"A,{r['Configuration']},{r['Trades']},{r['Win Rate']},{r['Profit Factor']},{r['Drawdown']},{r['Winners Preserved']}\n")
        for r in results_b:
            f.write(f"B,{r['Configuration']},{r['Trades']},{r['Win Rate']},{r['Profit Factor']},{r['Drawdown']},{r['Winners Preserved']}\n")
            
    logger.info(f"Reports saved to {md_path} and {csv_path}")

if __name__ == '__main__':
    main()
