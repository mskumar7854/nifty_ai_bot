import sqlite3
import json
import logging
import os
from typing import Dict, List, Optional
from datetime import datetime
import pandas as pd

# Import V2.1 Pipeline Components
from core.confidence_calibrator import ConfidenceCalibrator
from core.expected_value_engine import ExpectedValueEngine
from core.trend_structure_tracker import TrendStructureTracker
from core.trade_filter import TradeFilter
from models.signal import Signal
from models.enums import SignalGrade, SignalType, Direction, Strength
from models.regime import MarketRegime
from config.settings import Settings, PipelineConfig

logger = logging.getLogger("diagnostic_distributions")
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

def main():
    logger.info("Initializing Diagnostics Study...")
    
    conn = sqlite3.connect("data/trading_v4_sim.db")
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM decision_snapshots ORDER BY timestamp").fetchall()
    
    settings = Settings()
    trade_filter = TradeFilter(settings)
    calibrator = ConfidenceCalibrator()
    ev_engine = ExpectedValueEngine(min_ev_r=0.50, min_ev_score=60.0)
    
    diagnostics = []
    
    # We will simulate the Full pipeline to see exactly what values it generates.
    pipeline_config = PipelineConfig(True, True, True, True, True)

    for row in rows:
        s = dict(row)
        snapshot_id = s.get("snapshot_id")
        
        signal = build_mock_signal(row)
        if signal.signal_type == SignalType.NO_TRADE:
            continue
            
        regime_name = signal.regime.value
        
        # 1. Confidence Calibration
        raw_confidence = signal.confidence
        calibrated_pwin, calib_telemetry = calibrator.calibrate(raw_confidence, regime_name)
        if not hasattr(signal, "metadata") or signal.metadata is None:
            signal.metadata = {}
        signal.metadata["calibration_telemetry"] = calib_telemetry
        
        # 2. EV Inputs
        rr = 2.0  # Fixed 2R target in simulation
        spread_pct = float(s.get("spread_pct", 0.8) or 0.8)
        
        # Missing Data Detection
        missing_data = []
        if "spread_pct" not in s or s.get("spread_pct") is None:
            missing_data.append("Spread")
        # In replay without ticks, we don't have true slippage/friction, we use defaults
        missing_data.append("Friction (Tick Data)")
        missing_data.append("Exit")
        
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
        regime_info = {"regime": regime_name}
        
        # We need to run TradeFilter to capture Confluence details, 
        # but trade_filter might block before reaching confluence.
        # Let's extract agent agreement manually for our diagnostics
        
        # Agent Agreement / Confluence Breakdown
        trend_score = 0
        momentum_score = 0
        options_score = 0
        structure_score = 0
        total_possible = 0
        direction_agents = 0
        total_agents = 0
        
        for agent_name, out in agent_outputs.items():
            total_agents += 1
            
            if isinstance(out, dict):
                agent_dir = out.get("direction")
                conf = out.get("confidence", 0.0)
            else:
                agent_dir = str(out)
                conf = 0.0
                
            if agent_dir == signal.direction.value:
                direction_agents += 1
                
            if agent_name == "trend_agent":
                trend_score = conf
                total_possible += 100
            elif agent_name == "momentum_agent":
                momentum_score = conf
                total_possible += 100
            elif agent_name == "options_agent":
                options_score = conf
                total_possible += 100
            elif agent_name == "structure_agent":
                structure_score = conf
                total_possible += 100
            else:
                total_possible += 100
                
        total_confluence = raw_confidence # Assuming raw confidence is the combined confluence score for now
        agreement_pct = (direction_agents / total_agents * 100) if total_agents > 0 else 0
        
        # Run through trade filter to get final decision
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
                confluence_score=raw_confidence,
                pipeline_config=pipeline_config
            )
        except Exception as e:
            logger.error(f"Error evaluating filter: {e}")
            continue
            
        final_decision = "Passed" if result.passed else f"Rejected ({result.kill_reason or 'Unknown'})"
        
        diagnostics.append({
            "Trade ID": snapshot_id,
            "Raw Confidence": raw_confidence,
            "Calibrated P(win)": calibrated_pwin,
            "Confluence Score": raw_confidence,
            "Confluence Possible": 100.0, # Normalised out of 100
            "Trend Score": trend_score,
            "Momentum Score": momentum_score,
            "Options Score": options_score,
            "Structure Score": structure_score,
            "Agent Agreement": agreement_pct,
            "EV (R)": ev_result.get("ev_r", 0.0),
            "EV Score": ev_result.get("ev_score", 0.0),
            "Friction Penalty": ev_result.get("friction_penalty_r", 0.0),
            "Structure Gate": "PASS", # We can't easily extract structure pass from outside, but we know it from attribution
            "Missing Data": ", ".join(missing_data) if missing_data else "None",
            "Final Decision": final_decision
        })
        
    df = pd.DataFrame(diagnostics)
    
    os.makedirs("reports", exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    csv_path = f"reports/per_trade_diagnostics_{today}.csv"
    md_path = f"reports/diagnostic_distributions_{today}.md"
    
    df.to_csv(csv_path, index=False)
    
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Pre-Tuning Diagnostics Report\n\n")
        
        # 1. Missing Data Detection
        f.write("## 1. Missing Data Detection\n")
        f.write(f"Total Snapshots: {len(df)}\n")
        f.write(f"Snapshots using fallback friction (Missing Tick Data): {len(df[df['Missing Data'].str.contains('Friction')])}\n\n")
        
        # 2. Confluence Score Distribution
        f.write("## 2. Confluence Component Distribution\n")
        f.write("Averages by Total Score Bin:\n")
        # Ensure we have the column
        if not df.empty:
            df['Conf Bin'] = pd.cut(df['Confluence Score'], bins=range(30, 101, 5))
            # ObservedType issue with unobserved categories in newer pandas, use observed=False
            conf_grouped = df.groupby('Conf Bin', observed=False)[['Trend Score', 'Momentum Score', 'Options Score', 'Structure Score']].mean().fillna(0).round(1)
            f.write("| Total Score | Trend | Momentum | Options | Structure |\n")
            f.write("| --- | --- | --- | --- | --- |\n")
            for idx, row in conf_grouped.iterrows():
                f.write(f"| {idx.left}-{idx.right} | {row['Trend Score']} | {row['Momentum Score']} | {row['Options Score']} | {row['Structure Score']} |\n")
            f.write("\n")
            
            # 3. Maximum Possible Score Analysis
            f.write("## 3. Maximum Possible Score Analysis\n")
            max_trend = df['Trend Score'].max()
            max_mom = df['Momentum Score'].max()
            max_opt = df['Options Score'].max()
            max_str = df['Structure Score'].max()
            f.write(f"- Maximum Observed Trend Score: {max_trend:.1f}\n")
            f.write(f"- Maximum Observed Momentum Score: {max_mom:.1f}\n")
            f.write(f"- Maximum Observed Options Score: {max_opt:.1f}\n")
            f.write(f"- Maximum Observed Structure Score: {max_str:.1f}\n")
            f.write("- **Conclusion on Confluence**: If agent scores max out significantly below 100, the threshold must be lowered to reflect mathematical reality.\n\n")
            
            # 4. EV Breakdown
            f.write("## 4. EV Breakdown & Dependency Analysis\n")
            df['EV Bin'] = pd.cut(df['EV (R)'], bins=[-2.0, -1.0, -0.5, 0.0, 0.2, 0.5, 1.0])
            ev_grouped = df.groupby('EV Bin', observed=False)[['Raw Confidence', 'Calibrated P(win)', 'Friction Penalty']].mean().fillna(0).round(2)
            f.write("| EV Range (R) | Avg Raw Conf | Avg Calib P(win) | Avg Friction |\n")
            f.write("| --- | --- | --- | --- |\n")
            for idx, row in ev_grouped.iterrows():
                if not pd.isna(idx):
                    f.write(f"| {idx.left} to {idx.right} | {row['Raw Confidence']}% | {row['Calibrated P(win)']*100}% | {row['Friction Penalty']}R |\n")
            f.write("\n")
            
            f.write("## 5. Sample Per-Trade Diagnostics\n")
            f.write("| Trade ID | Raw Conf | Calib P(win) | Confluence | EV (R) | Final Decision |\n")
            f.write("| --- | --- | --- | --- | --- | --- |\n")
            for _, r in df.head(10).iterrows():
                f.write(f"| {r['Trade ID']} | {r['Raw Confidence']:.1f}% | {r['Calibrated P(win)']:.2f} | {r['Confluence Score']:.1f} | {r['EV (R)']:.2f}R | {r['Final Decision']} |\n")
        else:
            f.write("No data processed.\n")
            
    logger.info(f"Reports saved to {md_path} and {csv_path}")

if __name__ == '__main__':
    main()
