import json
import pandas as pd
from pathlib import Path
from datetime import datetime

def analyze_day(date_str: str = None):
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    # Load signals
    log_path = Path(f"logs/trades_{date_str}.csv")
    if not log_path.exists():
        print(f"No signal log found for {date_str} at {log_path}")
        return

    df = pd.read_csv(log_path)
    
    # Load exits if they exist and merge
    exit_path = Path(f"logs/exits_{date_str}.json")
    if exit_path.exists():
        with open(exit_path, 'r') as f:
            exits = [json.loads(line) for line in f if line.strip()]
        
        if exits:
            exits_df = pd.DataFrame(exits)
            # Merge exits into the main dataframe based on trade_id
            # This updates pnl, exit_price, exit_reason for rows that have matching trade_ids
            for _, exit_row in exits_df.iterrows():
                tid = exit_row.get("trade_id")
                if tid:
                    mask = df["trade_id"] == tid
                    if mask.any():
                        df.loc[mask, "exit_price"] = exit_row.get("exit_price")
                        df.loc[mask, "pnl"] = exit_row.get("pnl")
                        df.loc[mask, "exit_reason"] = exit_row.get("exit_reason")

    print(f"\n📊 Performance Analysis for {date_str}")
    print("=" * 40)
    
    total_signals = len(df)
    executed = df[df['trade_executed'] == True].copy()
    rejected = df[df['filter_passed'] == False].copy()
    
    print(f"Total Signals: {total_signals}")
    print(f"Trades Taken:  {len(executed)}")
    print(f"Rejected:      {len(rejected)}")
    print("-" * 40)

    # Convert PnL to numeric just in case
    executed['pnl'] = pd.to_numeric(executed['pnl'], errors='coerce')
    
    # Calculate executed trades performance
    if len(executed) > 0:
        completed = executed.dropna(subset=['pnl'])
        if len(completed) > 0:
            win_rate = (completed['pnl'] > 0).mean() * 100
            avg_pnl = completed['pnl'].mean()
            total_pnl = completed['pnl'].sum()
            print(f"Win rate: {win_rate:.1f}% (over {len(completed)} closed trades)")
            print(f"Avg PnL:  ₹{avg_pnl:.2f}")
            print(f"Net PnL:  ₹{total_pnl:.2f}")
        else:
            print("Trades are open. No closed PnL available yet.")
    else:
        print("No trades executed.")

    print("-" * 40)
    print(f"Rejected trades: {len(rejected)}")
    print("Filter impact (Avoided Loss / Missed Profit) simulation requires historical data exit logic.")
    # Placeholder for hypothetical PnL simulation on rejected trades.

if __name__ == "__main__":
    analyze_day()
