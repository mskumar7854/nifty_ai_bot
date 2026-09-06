import os
import sys
import json
import sqlite3
import pandas as pd
import datetime
import numpy as np
from typing import Dict, List, Any
from pathlib import Path

# Adjust python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import AgentOutput, Direction, Strength, MarketSnapshot, MarketRegime
from core.decision_engine import DecisionEngine
from core.experiment_config import ExperimentConfig
from config.settings import Settings

# Dummy Timestamp to make eval work
Timestamp = pd.Timestamp

class RehydratedAgent:
    def __init__(self, name: str):
        self.name = name
        self.current_outputs = {}
        
    def run(self, df, snapshot):
        return self.current_outputs.get(self.name)
        
    def get_trade_params(self, direction, current_price, atr):
        out = self.current_outputs.get("risk")
        if not out or not out.details:
            return None
        d = out.details
        if direction == Direction.BULLISH:
            return {
                "entry": current_price,
                "sl": d.get("sl_long", current_price - 10),
                "target1": d.get("target1_long", current_price + 20),
                "target2": d.get("target2_long", current_price + 40),
                "position_size": d.get("position_size", 100),
                "risk_amount": 5000
            }
        else:
            return {
                "entry": current_price,
                "sl": d.get("sl_short", current_price + 10),
                "target1": d.get("target1_short", current_price - 20),
                "target2": d.get("target2_short", current_price - 40),
                "position_size": d.get("position_size", 100),
                "risk_amount": 5000
            }

class BenchmarkV2Runner:
    def __init__(self, db_path="data/trading_v4_sim.db", csv_dir="data/csv"):
        self.db_path = db_path
        self.csv_dir = csv_dir
        self.settings = Settings()
        
        # Load Baseline Engine
        self.baseline_config = ExperimentConfig(
            enable_mav=False
        )
        self.baseline_config.experiment_id = "baseline_v1"
        self.baseline_config.benchmark_version = "v2.0"
        
        self.baseline_engine = DecisionEngine(settings=self.settings, experiment_config=self.baseline_config)
        self._inject_mock_agents(self.baseline_engine)
        
        # Load Experimental Engine
        self.mav_config = ExperimentConfig(
            enable_mav=True
        )
        self.mav_config.experiment_id = "mav_v2"
        self.mav_config.benchmark_version = "v2.0"
        
        self.mav_engine = DecisionEngine(settings=self.settings, experiment_config=self.mav_config)
        self._inject_mock_agents(self.mav_engine)
        
        self.baseline_traces = []
        self.mav_traces = []

    def _inject_mock_agents(self, engine: DecisionEngine):
        # We will dynamically populate this per snapshot
        engine.agents.clear()
            
    def _update_mock_agents(self, engine: DecisionEngine, outputs: Dict[str, AgentOutput]):
        engine.agents.clear()
        for name, out in outputs.items():
            agent = RehydratedAgent(name)
            agent.current_outputs = outputs
            engine.agents[name] = agent

    def _load_snapshots(self, date_str: str = "2026-06-17"):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT timestamp, spot_price, vix, agent_outputs_json, gap_penalty_multiplier, effective_confidence_threshold
            FROM decision_snapshots 
            WHERE timestamp LIKE ? AND length(agent_outputs_json) > 5
            ORDER BY timestamp ASC
        """, (f"{date_str}%",))
        
        rows = cursor.fetchall()
        conn.close()
        
        snapshots = []
        env = {
            'AgentOutput': AgentOutput,
            'Direction': Direction,
            'Strength': Strength,
            'Timestamp': pd.Timestamp,
            'datetime': datetime,
            'np': np
        }
        import re
        for row in rows:
            try:
                outputs_dict_raw = json.loads(row['agent_outputs_json'])
                outputs_dict = {}
                for k, v in outputs_dict_raw.items():
                    if isinstance(v, str) and v.startswith("AgentOutput"):
                        v = re.sub(r"<Direction\.([A-Z_]+): '[A-Z_]+'>", r"Direction.\1", v)
                        v = re.sub(r"<Strength\.([A-Z_]+): '[A-Z_]+'>", r"Strength.\1", v)
                        outputs_dict[k] = eval(v, env)
                    else:
                        outputs_dict[k] = v
                snapshots.append({
                    'timestamp': pd.to_datetime(row['timestamp']),
                    'price': row['spot_price'],
                    'vix': row['vix'],
                    'outputs': outputs_dict,
                    'confidence_threshold': row['effective_confidence_threshold'],
                    'gap_multiplier': row['gap_penalty_multiplier']
                })
            except Exception as e:
                print(f"Failed to parse snapshot {row['timestamp']}: {e}")
                continue
        return snapshots

    def _load_csv_data(self, date_str: str) -> pd.DataFrame:
        import re
        from core.data_resampler import DataResampler
        
        filename = f"data/daily_{date_str}.json"
        ticks = []
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                ts_str = None
                for line in f:
                    if '"timestamp"' in line:
                        m = re.search(r'"timestamp"\s*:\s*"([^"]+)"', line)
                        if m: ts_str = m.group(1)
                    elif '"entry"' in line and ts_str:
                        m = re.search(r'"entry"\s*:\s*([\d\.]+)', line)
                        if m:
                            try:
                                dt = pd.to_datetime(ts_str)
                                ticks.append({"ts": dt, "price": float(m.group(1))})
                            except ValueError:
                                pass
                            ts_str = None
        except Exception as e:
            return pd.DataFrame()
            
        if not ticks:
            return pd.DataFrame()
            
        df = DataResampler.ticks_to_1m_ohlc(ticks)
        return df

    def run(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT substr(timestamp, 1, 10) FROM decision_snapshots WHERE length(agent_outputs_json) > 5")
        date_strs = sorted([row[0] for row in cursor.fetchall()])
        conn.close()
        
        for date_str in date_strs:
            print(f"Loading data for {date_str}...")
            snapshots = self._load_snapshots(date_str)
            df_full = self._load_csv_data(date_str)
            
            print(f"Replaying {len(snapshots)} snapshots...")
            for snap_data in snapshots:
                ts = snap_data['timestamp']
                
                # Slice DF up to current timestamp
                df_current = df_full[df_full.index <= ts] if not df_full.empty else None
                
                snapshot = MarketSnapshot(
                    timestamp=ts,
                    price=snap_data['price'],
                    open=snap_data['price'],
                    high=snap_data['price'],
                    low=snap_data['price'],
                    close=snap_data['price'],
                    volume=0,
                    vwap=snap_data['price'],
                    rsi=50.0,
                    ema_fast=snap_data['price'],
                    ema_slow=snap_data['price'],
                    atr=10.0,
                    india_vix=snap_data['vix'] or 0.0
                )
                
                from models.decision_trace import HistoricalContextOverride, ReplayMode, ReplayFidelity
                
                hist_conf = snap_data.get('confidence_threshold', 0.0)
                if hist_conf == 0.0:
                    fidelity = ReplayFidelity.PARTIAL
                    confidence_val = 0.63
                    hist_conf = 0.20 # Fallback
                else:
                    fidelity = ReplayFidelity.EXACT
                    confidence_val = 0.98

                hist_override = HistoricalContextOverride(
                    mode=ReplayMode.HISTORICAL,
                    fidelity=fidelity,
                    confidence=confidence_val,
                    confidence_threshold=hist_conf,
                    gap_multiplier=snap_data.get('gap_multiplier')
                )
                
                counterfactual_override = HistoricalContextOverride(
                    mode=ReplayMode.COUNTERFACTUAL,
                    fidelity=ReplayFidelity.COUNTERFACTUAL,
                    confidence=1.0
                )
                
                # Run Baseline (Counterfactual)
                self._update_mock_agents(self.baseline_engine, snap_data['outputs'])
                b_signal = self.baseline_engine.process(df_current, snapshot, counterfactual_override)
                if hasattr(b_signal, 'trace') and b_signal.trace:
                    self.baseline_traces.append(b_signal.trace)
                    
                # Run Experimental (MAV Counterfactual)
                self._update_mock_agents(self.mav_engine, snap_data['outputs'])
                m_signal = self.mav_engine.process(df_current, snapshot, counterfactual_override)
                if hasattr(m_signal, 'trace') and m_signal.trace:
                    self.mav_traces.append(m_signal.trace)
                    
        print("Done replaying.")
        
        self._analyze_results()
        
    def _analyze_results(self):
        print("\n=== PIPELINE ATTRIBUTION & STAGE LEAKAGE ===")
        
        def print_leakage(name, traces):
            stage_counts = {"Agents": 0, "Candidate Detection": 0, "MAV": 0, "Signal Integrity": 0, "Risk Budget": 0, "Execution": 0}
            for t in traces:
                for s in t.stages:
                    if s.action.name == "PASSED":
                        stage_counts[s.stage_name] += 1
            
            print(f"\n[{name}] Waterfall:")
            print(f"Total Cycles: {len(traces)}")
            print(f" -> Agents Passed: {stage_counts['Agents']}")
            print(f" -> Candidate Detected: {stage_counts['Candidate Detection']}")
            print(f" -> MAV Passed: {stage_counts['MAV']}")
            print(f" -> Signal Integrity Passed: {stage_counts['Signal Integrity']}")
            print(f" -> Risk Budget Passed: {stage_counts['Risk Budget']}")
            print(f" -> EXECUTED: {stage_counts['Execution']}")
            
        print_leakage("Baseline", self.baseline_traces)
        print_leakage("MAV (Experimental)", self.mav_traces)
        
        # Trace Diff
        from core.trace_diff import TraceComparer
        print("\n=== TRACE DIFF (DIVERGENCE) ===")
        divergences = 0
        
        diff_log_path = "trace_diffs.log"
        with open(diff_log_path, "w", encoding="utf-8") as f:
            for b_trace, m_trace in zip(self.baseline_traces, self.mav_traces):
                if b_trace.timestamp != m_trace.timestamp:
                    continue
                    
                b_stages = [s.action.name for s in b_trace.stages]
                m_stages = [s.action.name for s in m_trace.stages]
                
                if b_stages != m_stages:
                    divergences += 1
                    diff_text = TraceComparer.compare(b_trace, m_trace)
                    f.write(diff_text + "\n\n" + "="*50 + "\n\n")
                    
                    if divergences <= 3:
                        print(f"\nDivergence at Cycle: {b_trace.cycle_id} ({b_trace.timestamp})")
                        print(f" Check {diff_log_path} for detailed report.")
                        
        print(f"\nTotal Divergences found: {divergences}")
        print(f"Detailed trace diffs written to {diff_log_path}")

if __name__ == "__main__":
    import sys
    # Fix for windows console output
    sys.stdout.reconfigure(encoding='utf-8')
    runner = BenchmarkV2Runner()
    runner.run()
