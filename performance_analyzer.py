import json
import pandas as pd
from pathlib import Path
from datetime import datetime

def analyze_day(date_str: str = None):
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    # Load Daily Summary
    summary_path = Path(f"logs/daily_summary_{date_str}.json")
    if summary_path.exists():
        with open(summary_path, 'r') as f:
            summary = json.load(f)
        
        print(f"\n📊 Performance Analysis for {date_str} (From Daily Summary)")
        print("=" * 60)
        print(f"Total Signals: {summary.get('signals', 0)}")
        print(f"Trades Taken:  {summary.get('entries', 0)}")
        print(f"Rejected:      {summary.get('rejections', 0)}")
        print("-" * 60)
        print(f"Wins:          {summary.get('wins', 0)}")
        print(f"Losses:        {summary.get('losses', 0)}")
        print(f"Net PnL:       ₹{summary.get('net_pnl', 0.0):.2f}")
        print(f"Expectancy:    {summary.get('expectancy', 0.0):.2f}R")
        print(f"Avg R:         {summary.get('avg_r', 0.0):.2f}R")
        
        if summary.get("best_trade"):
            print(f"Best Trade:    {summary.get('best_trade')} ")
        if summary.get("worst_trade"):
            print(f"Worst Trade:   {summary.get('worst_trade')}")
        print("=" * 60)

    # Load Ledger for detailed breakdown if needed
    ledger_path = Path(f"logs/ledger_{date_str}.json")
    if ledger_path.exists():
        with open(ledger_path, 'r') as f:
            trades = [json.loads(line) for line in f if line.strip()]
            
        if trades:
            print(f"\nDetailed Ledger Insights ({len(trades)} Trades):")
            print("-" * 60)
            for t in trades:
                tid = t.get("trade_id", "UNKNOWN")
                outcome = t.get("outcome", "UNKNOWN")
                financial = t.get("analytics", {}).get("financial", {})
                net_pnl = financial.get("net_pnl", 0.0)
                decision = t.get("trade", {}).get("decision", {})
                grade = decision.get("grade", "U")
                
                print(f" - {tid} | Grade: {grade} | Outcome: {outcome:10} | PnL: ₹{net_pnl:>7.2f}")
    else:
        print(f"No ledger records found for {date_str} at {ledger_path}")

if __name__ == "__main__":
    analyze_day()
