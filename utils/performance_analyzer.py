import json
import os
import argparse
from collections import defaultdict
from typing import List, Dict

DEFAULT_LOG = "logs/trades.ndjson"
FALLBACK_LOG = "logs/test_trades.ndjson"

def load_trades(log_path: str) -> List[Dict]:
    """
    🧠 THE LOG LOADER (NDJSON Optimized)
    Loads trades with automatic fallback to test logs if production is empty.
    """
    active_path = log_path
    
    if not os.path.exists(active_path):
        # Check for legacy .json if .ndjson doesn't exist
        legacy_path = active_path.replace(".ndjson", ".json")
        if os.path.exists(legacy_path):
            print(f"⚠️  Found legacy JSON logs at {legacy_path}")
            active_path = legacy_path
        else:
            if os.path.exists(FALLBACK_LOG) and active_path != FALLBACK_LOG:
                print(f"⚠️  No trade logs found at {active_path}. Falling back to sample data.")
                active_path = FALLBACK_LOG
            else:
                print(f"❌ No logs available at {active_path}")
                return []

    trades = []
    try:
        with open(active_path, "r", encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    try:
                        trades.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except Exception as e:
        print(f"❌ Error reading {active_path}: {e}")
        return []

    if not trades:
        print(f"⚪ No trades recorded in {active_path}")
    else:
        print(f"📖 Loaded {len(trades)} trades from {active_path}")
        
    return trades

def analyze_performance(trades: List[Dict]):
    """
    🧠 THE STRATEGY AUDITOR
    Answers: What works? Who is winning? Where is the risk?
    """
    if not trades:
        return

    total = len(trades)
    wins = sum(1 for t in trades if t.get("outcome") == "WIN")
    losses = sum(1 for t in trades if t.get("outcome") == "LOSS")
    breakevens = sum(1 for t in trades if t.get("outcome") == "BREAKEVEN")
    
    win_rate = (wins / total) * 100 if total > 0 else 0
    total_pnl = sum(t.get("pnl", 0) for t in trades)
    avg_pnl = total_pnl / total if total > 0 else 0

    print("=" * 60)
    print("📊 MASTER PERFORMANCE SUMMARY")
    print("=" * 60)
    print(f"Total Trades:    {total}")
    print(f"Win Rate:        {win_rate:.1f}% ({wins}W / {losses}L / {breakevens}B)")
    print(f"Total PnL:       ₹{total_pnl:,.0f}")
    print(f"Avg PnL/Trade:   ₹{avg_pnl:,.0f}")
    print("-" * 60)

    # 1. SCORE EFFECTIVENESS
    def print_segment(label, segment):
        if not segment: return
        s_wins = sum(1 for t in segment if t.get("outcome") == "WIN")
        s_wr = (s_wins / len(segment)) * 100
        s_pnl = sum(t.get("pnl", 0) for t in segment) / len(segment)
        print(f"{label:<25} | Count: {len(segment):>2} | WR: {s_wr:>5.1f}% | AvgPnL: ₹{s_pnl:>6.0f}")

    high_score = [t for t in trades if t.get("weighted_score", 0) >= 0.75]
    mid_score = [t for t in trades if 0.65 <= t.get("weighted_score", 0) < 0.75]
    
    print("🎯 SCORE SURVIVAL RATES")
    print_segment("High Conf (>=0.75)", high_score)
    print_segment("Mid Conf (0.65-0.75)", mid_score)
    print("-" * 60)

    # 2. ENTRY TYPE BREAKDOWN
    entry_types = defaultdict(list)
    for t in trades:
        entry_types[t.get("entry_type", "UNKNOWN")].append(t)
    
    print("🔌 ENTRY TYPE ANALYSIS")
    for etype, segment in entry_types.items():
        print_segment(f"Type: {etype}", segment)
    print("-" * 60)

    # 3. SYSTEM VERSIONING
    versions = defaultdict(list)
    for t in trades:
        versions[t.get("system_version", "v1.0")].append(t)
    
    print("🏗️  VERSION PERFORMANCE")
    for v, segment in versions.items():
        print_segment(f"Version: {v}", segment)
    print("-" * 60)

    # 4. REGIME PERFORMANCE
    regimes = defaultdict(list)
    for t in trades:
        regimes[t.get("market_regime", "UNKNOWN")].append(t)
    
    print("🌐 REGIME PROFITABILITY")
    for regime, segment in regimes.items():
        print_segment(f"Regime: {regime}", segment)
    print("=" * 60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="🧠 Nifty AI Performance Analyzer")
    parser.add_argument("--log", type=str, default=DEFAULT_LOG, help="Path to trade logs (.ndjson or .json)")
    
    args = parser.parse_args()
    
    trades_list = load_trades(args.log)
    analyze_performance(trades_list)
