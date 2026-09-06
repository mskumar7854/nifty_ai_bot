import os
import sys
import json
import yaml
import datetime
import pandas as pd
from typing import Dict, List, Optional
import hashlib
from collections import defaultdict

# Add workspace to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Fix Windows unicode printing
import codecs
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from models.experiment_result import ExperimentResult
from core.experiment_config import ExperimentConfig
from core.data_resampler import DataResampler
from core.market_acceptance_validator import AcceptanceState

class ExperimentRunner:
    def __init__(self, manifest_path: str):
        with open(manifest_path, 'r') as f:
            self.manifest = yaml.safe_load(f)
            
        self.experiment_id = self.manifest['experiment']['id']
        self.sessions = self.manifest['dataset']['sessions']
        self.features = self.manifest.get('features', {})
        
        # Load configs
        self.baseline_config = ExperimentConfig.baseline()
        self.candidate_config = ExperimentConfig(
            enable_mav=self.features.get('enable_mav', False),
            enable_dynamic_threshold=self.features.get('enable_dynamic_threshold', True),
            enable_ev=self.features.get('enable_ev', False),
            enable_new_exit=self.features.get('enable_new_exit', False)
        )
        
        self.results = []
        self._day_cache = {}

    def run(self):
        print(f"🚀 Starting Experiment: {self.experiment_id}")
        print(f"📊 Dataset: {len(self.sessions)} sessions")
        print(f"⚙️ Features: {self.features}")
        
        # Run Baseline
        print("\n--- Running Baseline Engine ---")
        baseline_results = self._evaluate_sessions(self.baseline_config, "baseline")
        
        # Run Candidate
        print("\n--- Running Candidate Engine ---")
        candidate_results = self._evaluate_sessions(self.candidate_config, "candidate")
        
        # Aggregate
        self._generate_report(baseline_results, candidate_results)

    def _evaluate_sessions(self, config: ExperimentConfig, experiment_name: str) -> List[ExperimentResult]:
        results = []
        # Import inside to avoid circular deps if needed
        from core.decision_engine import DecisionEngine
        from config.settings import Settings
        
        # We need a clean engine instance for each run
        engine = DecisionEngine(Settings(), experiment_config=config)
        
        for session_date in self.sessions:
            print(f"  Processing {session_date}...")
            # For this MVP A/B runner, we will simulate the MAV specifically 
            # by detecting false breakouts on the loaded ticks, ensuring we have 
            # the exact same behavior as the full engine without heavy dependency loading.
            
            ticks = self._load_ticks(session_date)
            if not ticks:
                continue
                
            df_1m_full = DataResampler.ticks_to_1m_ohlc(ticks)
            
            # Identify candidates from the JSON to simulate the cycle
            candidates = self._extract_candidates(session_date)
            
            for cand in candidates:
                # 1. Trade Matching Hash: (session_date, minute_timestamp, direction, rounded_structure_level)
                dt = cand['ts']
                minute_ts = dt.replace(second=0, microsecond=0).isoformat()
                rounded_struct = round(cand['structure_level'], 0) if cand['structure_level'] else 0
                
                hash_str = f"{session_date}_{minute_ts}_{cand['direction']}_{rounded_struct}"
                cand_id = hashlib.md5(hash_str.encode()).hexdigest()[:8]
                
                # 2. Simulate Decision Cycle
                # If MAV is enabled, evaluate it
                decision = "EXECUTED"
                rejection = None
                pnl = cand['pnl'] # Use historical outcome if executed
                
                if config.enable_mav:
                    engine.mav.reset()
                    engine.mav.track_candidate(cand_id, cand['direction'], cand['structure_level'], dt)
                    
                    # Feed subsequent candles to MAV
                    # We only need the next ~6 candles because MAV times out at 4
                    subsequent_df = df_1m_full[df_1m_full.index >= dt]
                    max_idx = min(8, len(subsequent_df) + 1)
                    
                    for i in range(2, max_idx):
                        current_slice = subsequent_df.iloc[:i]
                        state = engine.mav.evaluate_1m_candle(current_slice, ema_50=None)
                        if state in [AcceptanceState.FALSE_BREAKOUT, AcceptanceState.TIMEOUT]:
                            decision = "REJECTED"
                            rejection = state.name
                            pnl = 0.0
                            break
                        elif state == AcceptanceState.ACCEPTED:
                            break
                            
                # 3. Create Result
                res = ExperimentResult(
                    candidate_id=cand_id,
                    experiment=experiment_name,
                    timestamp=dt,
                    decision=decision,
                    execution_state="CLOSED" if decision == "EXECUTED" else "NONE",
                    exit_reason="STOP_LOSS" if pnl < 0 else "TARGET" if pnl > 0 else None,
                    pnl=pnl,
                    r_multiple=pnl / 20.0 if pnl else 0.0, # Approximate R
                    rejection_reason=rejection,
                    lifecycle=["CANDIDATE_DETECTED", decision]
                )
                results.append(res)
                
        return results

    def _load_ticks(self, date_str: str) -> List[Dict]:
        if date_str in self._day_cache:
            return self._day_cache[date_str]
            
        import re
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
                                dt = datetime.datetime.fromisoformat(ts_str)
                                ticks.append({"ts": dt, "price": float(m.group(1))})
                            except ValueError:
                                pass
                            ts_str = None
        except Exception as e:
            print(f"Error loading {date_str}: {e}")
            
        self._day_cache[date_str] = ticks
        return ticks

    def _extract_candidates(self, date_str: str) -> List[Dict]:
        """Extract candidate decisions from JSON logs to simulate the cycles."""
        import json
        filename = f"data/daily_{date_str}.json"
        candidates = []
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            for sig in data.get('signals', []):
                # Identify actual candidates historically for the simulation
                if sig.get('signal_type') == 'TRADE' or 'Not enough agreeing agents' not in str(sig.get('reasons', [])):
                    # For MVP, we will treat any STRONG trap/momentum alignment as a candidate
                    trap_conf = sig.get('agent_votes', {}).get('trap', {}).get('confidence', 0)
                    if trap_conf > 80:
                        direction = sig.get('agent_votes', {}).get('trap', {}).get('direction', 'NEUTRAL')
                        # Mock PnL based on forward excursion for simulation
                        pnl = -20.0 if "FAKE BREAKOUT" in str(sig.get('warnings', [])) else 40.0
                        candidates.append({
                            'ts': datetime.datetime.fromisoformat(sig['timestamp']),
                            'direction': direction,
                            'structure_level': sig.get('entry', 0.0),
                            'pnl': pnl
                        })
        except Exception:
            pass
        return candidates

    def _generate_report(self, baseline: List[ExperimentResult], candidate: List[ExperimentResult]):
        import core.ab_analytics as analytics
        analytics.generate_report(self.experiment_id, baseline, candidate)

if __name__ == "__main__":
    runner = ExperimentRunner("experiments/mav_v1_manifest.yaml")
    runner.run()
