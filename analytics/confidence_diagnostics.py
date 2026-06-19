import os
import json
from collections import defaultdict

def bucket_confidence(conf):
    """Returns the bucket range string for a given confidence (0.0 to 1.0)"""
    if conf < 0.5:
        return "<50%"
    elif conf < 0.6:
        return "50-60%"
    elif conf < 0.7:
        return "60-70%"
    elif conf < 0.8:
        return "70-80%"
    elif conf < 0.9:
        return "80-90%"
    else:
        return "90-100%"

def analyze_confidence_calibration():
    data_dir = os.path.join("data", "analytics")
    conf_log = os.path.join(data_dir, "confidence_calibration.jsonl")
    agent_log = os.path.join(data_dir, "agent_attribution.jsonl")
    
    if not os.path.exists(conf_log) or not os.path.exists(agent_log):
        print(f"Diagnostics error: Missing data logs in {data_dir}")
        return

    # Data structures for Global and Regime Reliability
    # bucket -> {"conf_sum": 0, "wins": 0, "count": 0}
    global_buckets = defaultdict(lambda: {"conf_sum": 0.0, "wins": 0, "count": 0})
    regime_buckets = defaultdict(lambda: defaultdict(lambda: {"conf_sum": 0.0, "wins": 0, "count": 0}))
    
    total_trades = 0
    with open(conf_log, "r") as f:
        for line in f:
            try:
                r = json.loads(line)
                conf = r.get("raw_confidence", 0.0)
                win = r.get("is_win", 0)
                regime = r.get("regime", "UNKNOWN")
                
                bucket = bucket_confidence(conf)
                
                global_buckets[bucket]["conf_sum"] += conf
                global_buckets[bucket]["wins"] += win
                global_buckets[bucket]["count"] += 1
                
                regime_buckets[regime][bucket]["conf_sum"] += conf
                regime_buckets[regime][bucket]["wins"] += win
                regime_buckets[regime][bucket]["count"] += 1
                
                total_trades += 1
            except:
                pass

    # Data structure for Agent Reliability
    agent_stats = defaultdict(lambda: {"conf_sum": 0.0, "wins": 0, "count": 0})
    
    with open(agent_log, "r") as f:
        for line in f:
            try:
                r = json.loads(line)
                agent = r.get("agent")
                if agent == "_meta": continue
                conf = r.get("agent_conf", 0.0)
                win = r.get("is_correct", 0)
                
                agent_stats[agent]["conf_sum"] += conf
                agent_stats[agent]["wins"] += win
                agent_stats[agent]["count"] += 1
            except:
                pass

    print("\n" + "="*50)
    print("SPRINT 4: CONFIDENCE DIAGNOSTICS")
    print("="*50)
    
    print(f"\nTotal Trades Evaluated: {total_trades}")
    
    print("\n--- 1. CONFIDENCE HISTOGRAM & GLOBAL RELIABILITY CURVE ---")
    print(f"{'Bucket':<10} | {'% of Trades':<12} | {'Avg Predicted':<15} | {'Actual Win Rate':<15}")
    print("-" * 60)
    
    bucket_order = ["<50%", "50-60%", "60-70%", "70-80%", "80-90%", "90-100%"]
    
    for b in bucket_order:
        stats = global_buckets[b]
        if stats["count"] > 0:
            pct_trades = (stats["count"] / total_trades) * 100
            avg_pred = (stats["conf_sum"] / stats["count"]) * 100
            win_rate = (stats["wins"] / stats["count"]) * 100
            print(f"{b:<10} | {pct_trades:>5.1f}% ({stats['count']:>3}) | {avg_pred:>14.1f}% | {win_rate:>14.1f}%")
        else:
            print(f"{b:<10} | {'0.0% (  0)':<12} | {'-':<15} | {'-':<15}")

    print("\n--- 2. REGIME RELIABILITY (Avg Predicted vs Actual Win Rate) ---")
    print(f"{'Regime':<12} | {'Trades':<8} | {'Avg Predicted':<15} | {'Actual Win Rate':<15} | {'Delta (Bias)':<12}")
    print("-" * 70)
    for regime, r_buckets in regime_buckets.items():
        r_conf_sum = sum(b["conf_sum"] for b in r_buckets.values())
        r_wins = sum(b["wins"] for b in r_buckets.values())
        r_count = sum(b["count"] for b in r_buckets.values())
        
        if r_count > 0:
            avg_pred = (r_conf_sum / r_count) * 100
            win_rate = (r_wins / r_count) * 100
            delta = avg_pred - win_rate
            print(f"{regime:<12} | {r_count:<8} | {avg_pred:>14.1f}% | {win_rate:>14.1f}% | {delta:>+11.1f}%")

    print("\n--- 3. AGENT RELIABILITY (Avg Predicted vs Actual Win Rate) ---")
    print(f"{'Agent':<15} | {'Trades':<8} | {'Avg Predicted':<15} | {'Actual Win Rate':<15} | {'Delta (Bias)':<12}")
    print("-" * 75)
    for agent, stats in sorted(agent_stats.items(), key=lambda x: x[0]):
        # Ignore synthetic agents or metadata
        if agent in ["Agent_A", "Agent_B", "Agent_C", "_meta"]: continue
        
        if stats["count"] > 0:
            avg_pred = (stats["conf_sum"] / stats["count"]) * 100
            win_rate = (stats["wins"] / stats["count"]) * 100
            delta = avg_pred - win_rate
            print(f"{agent:<15} | {stats['count']:<8} | {avg_pred:>14.1f}% | {win_rate:>14.1f}% | {delta:>+11.1f}%")

    print("\n" + "="*50)
    print("Conclusion: Look for large 'Delta' values.")
    print("If Global or Regime Delta is highly positive (e.g., +30.0%),")
    print("the system is severely inflating confidence outputs.")
    print("If Agent Deltas are small but Global Delta is large,")
    print("the aggregation math is responsible for the inflation.")
    print("="*50 + "\n")

if __name__ == "__main__":
    analyze_confidence_calibration()
