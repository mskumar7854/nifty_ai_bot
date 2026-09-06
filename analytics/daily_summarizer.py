import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

class DailySummarizer:
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)

    def generate_daily_summary(self, target_date: str = None):
        """
        Generates a single daily summary file derived from the ledger for the given date.
        Format of date: YYYY-MM-DD
        """
        if target_date is None:
            target_date = datetime.now().strftime("%Y-%m-%d")

        ledger_path = self.log_dir / f"ledger_{target_date}.json"
        if not ledger_path.exists():
            return None

        trades = []
        with open(ledger_path, 'r') as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    trades.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        if not trades:
            return None

        # Parse event logs to get signal and rejection counts
        signals_path = self.log_dir / f"signals_{target_date}.ndjson"
        rejections_path = self.log_dir / f"rejections_{target_date}.ndjson"
        
        signals_count = 0
        if signals_path.exists():
            with open(signals_path, 'r') as f:
                signals_count = sum(1 for line in f if line.strip())
                
        rejections_count = 0
        if rejections_path.exists():
            with open(rejections_path, 'r') as f:
                rejections_count = sum(1 for line in f if line.strip())

        entries = len(trades)
        wins = 0
        losses = 0
        net_pnl = 0.0
        total_r = 0.0
        best_trade_id = None
        best_pnl = float('-inf')
        worst_trade_id = None
        worst_pnl = float('inf')

        for trade_data in trades:
            analytics = trade_data.get("analytics", {})
            financial = analytics.get("financial", {})
            derived = analytics.get("derived", {})

            pnl = financial.get("net_pnl", 0.0)
            net_pnl += pnl
            
            if pnl > 0:
                wins += 1
            elif pnl < 0:
                losses += 1
                
            total_r += derived.get("r_multiple", 0.0)

            trade_id = trade_data.get("trade_id")
            if pnl > best_pnl:
                best_pnl = pnl
                best_trade_id = trade_id
            if pnl < worst_pnl:
                worst_pnl = pnl
                worst_trade_id = trade_id

        win_rate = (wins / entries) if entries > 0 else 0
        loss_rate = (losses / entries) if entries > 0 else 0
        
        # Expectancy formula: (Win% * AvgWinR) - (Loss% * AvgLossR) 
        # Simplified: average R per trade
        avg_r = (total_r / entries) if entries > 0 else 0.0
        expectancy = avg_r

        summary = {
            "date": target_date,
            "signals": signals_count,
            "entries": entries,
            "rejections": rejections_count,
            "wins": wins,
            "losses": losses,
            "net_pnl": round(net_pnl, 2),
            "expectancy": round(expectancy, 2),
            "avg_r": round(avg_r, 2),
            "best_trade": best_trade_id,
            "worst_trade": worst_trade_id
        }

        summary_path = self.log_dir / f"daily_summary_{target_date}.json"
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=4)

        return summary
