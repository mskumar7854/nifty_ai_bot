"""
core/replay_simulator.py
Phase 4A: Snapshot Replay Engine - Counterfactual Execution Modeling
"""
import sqlite3
import json
import re
import datetime
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger("replay_simulator")
logging.basicConfig(level=logging.INFO, format="%(message)s")

@dataclass
class CounterfactualResult:
    snapshot_id: str
    timestamp: str
    regime: str
    vix: float
    rejection_reasons: List[str]
    confidence: float
    direction: str  # "BUY" or "SELL"
    
    # Excursion (Spot)
    mfe_spot: float
    mae_spot: float
    time_to_mfe_sec: float
    
    # Horizons Expected R (based on fixed exit if stop/target not hit)
    exp_r_5m: float
    exp_r_15m: float
    exp_r_30m: float
    
    # Primary Outcome (15m evaluation)
    suppressed_r: float  # >0 if profitable edge missed
    prevented_loss_r: float  # >0 if loss avoided
    
    # Final Result
    is_win: bool


class ReplaySimulator:
    def __init__(self, db_path="data/trading_v4_sim.db"):
        self.db_path = db_path
        self._day_cache = {}  # date_str -> list of dicts {"ts": datetime, "price": float}

    def _load_day_ticks(self, date_str: str) -> List[Dict]:
        if date_str in self._day_cache:
            return self._day_cache[date_str]
        
        filename = f"data/daily_{date_str}.json"
        ticks = []
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                ts_str = None
                for line in f:
                    if '"timestamp"' in line:
                        m = re.search(r'"timestamp"\s*:\s*"([^"]+)"', line)
                        if m:
                            ts_str = m.group(1)
                    elif '"entry"' in line and ts_str:
                        m = re.search(r'"entry"\s*:\s*([\d\.]+)', line)
                        if m:
                            price = float(m.group(1))
                            try:
                                dt = datetime.datetime.fromisoformat(ts_str)
                                ticks.append({"ts": dt, "price": price})
                            except ValueError:
                                pass
                            ts_str = None
            logger.debug(f"Loaded {len(ticks)} ticks for {date_str}")
        except FileNotFoundError:
            logger.debug(f"No market data file for {date_str}")
        except Exception as e:
            logger.error(f"Error loading {date_str}: {e}")
            
        self._day_cache[date_str] = ticks
        return ticks

    def simulate_rejection(self, row: sqlite3.Row) -> Optional[CounterfactualResult]:
        s = dict(row)
        
        # Evaluate all trades for compare_versions
        pass
            
        # Parse fields
        try:
            ts = datetime.datetime.fromisoformat(s["timestamp"])
            spot_entry = float(s["spot_price"])
            buy_score = float(s.get("buy_score", 0.0))
            sell_score = float(s.get("sell_score", 0.0))
            confidence = float(s.get("confidence", 0.0))
            
            # Determine rejected direction
            if buy_score > sell_score:
                direction = "BUY"
            elif sell_score > buy_score:
                direction = "SELL"
            else:
                return None  # Neutral, not a missed trade
                
            # Get Context
            market_context = json.loads(s.get("market_context_json") or "{}")
            atr = float(market_context.get("atr") or 20.0)
            if atr < 5.0: atr = 20.0
            
            gate_results = json.loads(s.get("gate_results_json") or "{}")
            rejection_reasons = list(gate_results.keys())
            if not rejection_reasons and s.get("rejection_reason"):
                rejection_reasons = [s["rejection_reason"]]
                
        except Exception as e:
            logger.error(f"Failed parsing snapshot {s.get('snapshot_id')}: {e}")
            return None

        # Fixed parameters
        stop_pts = atr * 1.5
        target_pts = atr * 3.0  # 2R target
        
        date_str = ts.strftime("%Y-%m-%d")
        ticks = self._load_day_ticks(date_str)
        if not ticks:
            return None
            
        # Fast forward to snapshot time
        # Binary search could be used, but linear is fine for ~5000 items
        start_idx = 0
        for i, t in enumerate(ticks):
            if t["ts"] >= ts:
                start_idx = i
                break
        else:
            return None # Snapshot is at the end of the file
            
        # Tracking metrics
        mfe = 0.0
        mae = 0.0
        time_to_mfe = 0.0
        
        hit_stop_15m = False
        hit_target_15m = False
        
        r_5m = 0.0
        r_15m = 0.0
        r_30m = 0.0
        
        final_15m_r = 0.0

        for t in ticks[start_idx:]:
            dt = (t["ts"] - ts).total_seconds()
            if dt > 30 * 60:
                break
                
            curr_price = t["price"]
            
            if direction == "BUY":
                favorable = curr_price - spot_entry
                adverse = spot_entry - curr_price
            else:
                favorable = spot_entry - curr_price
                adverse = curr_price - spot_entry
                
            if favorable > mfe:
                mfe = favorable
                time_to_mfe = dt
            if adverse > mae:
                mae = adverse
                
            current_r = favorable / stop_pts
            
            # Record horizons
            if dt <= 5 * 60:
                r_5m = current_r
            if dt <= 15 * 60:
                r_15m = current_r
                if adverse >= stop_pts and not hit_target_15m and not hit_stop_15m:
                    hit_stop_15m = True
                    final_15m_r = -1.0
                if favorable >= target_pts and not hit_stop_15m and not hit_target_15m:
                    hit_target_15m = True
                    final_15m_r = 2.0
            if dt <= 30 * 60:
                r_30m = current_r

        # If it didn't hit stop or target in 15m, exit at market
        if not hit_stop_15m and not hit_target_15m:
            final_15m_r = r_15m
            
        # Cap R between -1 and 2 for realistic expectancy tracking
        final_15m_r = max(-1.0, min(final_15m_r, 2.0))
            
        # Protection vs Suppression
        suppressed_r = max(0.0, final_15m_r)
        prevented_loss_r = abs(min(0.0, final_15m_r))
        is_win = final_15m_r > 0

        return CounterfactualResult(
            snapshot_id=s["snapshot_id"],
            timestamp=s["timestamp"],
            regime=s.get("regime", "UNKNOWN"),
            vix=float(s.get("vix", 0.0) or 0.0),
            rejection_reasons=rejection_reasons,
            confidence=confidence,
            direction=direction,
            mfe_spot=mfe,
            mae_spot=mae,
            time_to_mfe_sec=time_to_mfe,
            exp_r_5m=max(-1.0, r_5m),
            exp_r_15m=final_15m_r,
            exp_r_30m=max(-1.0, r_30m),
            suppressed_r=suppressed_r,
            prevented_loss_r=prevented_loss_r,
            is_win=is_win
        )

if __name__ == "__main__":
    import sys
    sim = ReplaySimulator()
    conn = sqlite3.connect("data/trading_v4_sim.db")
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM decision_snapshots WHERE final_decision = 'REJECTED' ORDER BY timestamp DESC LIMIT 50").fetchall()
    
    count = 0
    for r in rows:
        res = sim.simulate_rejection(r)
        if res:
            print(f"{res.snapshot_id} | {res.direction} | 15m R: {res.exp_r_15m:+.2f} | MFE: {res.mfe_spot:.1f} | Rejection: {res.rejection_reasons}")
            count += 1
            if count >= 5: break
