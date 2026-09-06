import sqlite3
import json
from collections import defaultdict
from core.replay_simulator import ReplaySimulator, CounterfactualResult
from core.trend_structure_tracker import TrendStructureTracker
from models.enums import Direction

def load_snapshots(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM decision_snapshots ORDER BY timestamp ASC").fetchall()
    conn.close()
    return rows

def run_replay(snapshots, scarcity_on=True):
    sim = ReplaySimulator(db_path="data/trading_v4_live.db")
    tracker = TrendStructureTracker(max_reentry_per_trend=2 if scarcity_on else 999)
    
    opportunities = 0
    executions = 0
    total_r = 0.0
    wins = 0
    peak_r = 0.0
    drawdown = 0.0
    third_entries = 0
    rejected_by_scarcity = 0
    rejected_pnl = 0.0
    
    gross_profit = 0.0
    gross_loss = 0.0
    
    for row in snapshots:
        s = dict(row)
        
        buy_score = float(s.get("buy_score", 0.0))
        sell_score = float(s.get("sell_score", 0.0))
        direction = "BULLISH" if buy_score > sell_score else "BEARISH"
        
        opportunities += 1
        
        auth, reason, _ = tracker.check_reentry_allowed(direction)
        
        if not auth:
            if "Already entered 2 times" in reason or scarcity_on:
                rejected_by_scarcity += 1
                c_result = sim.simulate_rejection(s)
                if c_result:
                    rejected_pnl += c_result.exp_r_15m
            continue
            
        if tracker.entries_in_leg >= 2:
            third_entries += 1
            
        c_result = sim.simulate_rejection(s)
        if c_result:
            executions += 1
            r = c_result.exp_r_15m
            total_r += r
            if r > 0: 
                wins += 1
                gross_profit += r
            else:
                gross_loss += abs(r)
                
            if total_r > peak_r:
                peak_r = total_r
            else:
                dd = peak_r - total_r
                if dd > drawdown: drawdown = dd
                
            tracker.record_trade_execution(direction, entry_price=100.0, timestamp=s["timestamp"])
            
    avg_r = total_r / executions if executions else 0
    win_rate = wins / executions if executions else 0
    pf = (gross_profit / gross_loss) if gross_loss > 0 else 999.0
    
    return {
        "Opportunities": opportunities,
        "Executions": executions,
        "Avg R": avg_r,
        "Expectancy": avg_r,
        "Win rate": win_rate * 100,
        "Profit factor": pf,
        "Max drawdown": drawdown,
        "3rd-entry attempts": third_entries,
        "Rejected by scarcity": rejected_by_scarcity,
        "Counterfactual P&L of rejected trades": rejected_pnl
    }

if __name__ == "__main__":
    db_path = "data/trading_v4_live.db"
    snaps = load_snapshots(db_path)
    
    print("Running Scarcity ON pass...")
    res_on = run_replay(snaps, scarcity_on=True)
    
    print("Running Scarcity OFF pass...")
    res_off = run_replay(snaps, scarcity_on=False)
    
    print("\n### Counterfactual Replay Results\n")
    print("| Metric | Scarcity ON | Scarcity OFF | Delta |")
    print("|---|---|---|---|")
    for k in res_on.keys():
        v_on = res_on[k]
        v_off = res_off[k]
        delta = v_on - v_off
        
        fmt = lambda v: f"{v:.2f}" if isinstance(v, float) else str(v)
        
        print(f"| {k} | {fmt(v_on)} | {fmt(v_off)} | {fmt(delta)} |")
