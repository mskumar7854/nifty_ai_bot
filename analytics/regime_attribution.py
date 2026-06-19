import os
import json
import logging
from analytics.analytics_bus import analytics_bus
from analytics.confidence_calibration import confidence_calibration

class RegimeAttribution:
    """
    Isolates the profitability and characteristics of each market regime.
    Helps identify Toxic Regimes vs Alpha Regimes.
    """
    def __init__(self):
        self.logger = logging.getLogger("regime_attribution")
        self.data_dir = os.path.join("data", "analytics")
        os.makedirs(self.data_dir, exist_ok=True)
        self.log_file = os.path.join(self.data_dir, "regime_attribution.jsonl")
        
        analytics_bus.subscribe("trade_closed", self.handle_trade_closed)

    def handle_trade_closed(self, payload: dict):
        try:
            pos = payload.get("position", {})
            if not pos:
                return
                
            regime = pos.get("regime_at_entry", "UNKNOWN")
            
            pnl = payload.get("exit_price", 0.0) - pos.get("entry_price", 0.0)
            if pos.get("direction", "BUY").upper() == "SELL":
                pnl = -pnl
                
            # If explicit pnl is provided in payload (in case of options or futures), use it
            if "pnl" in payload:
                pnl = payload["pnl"]
                
            record = {
                "timestamp": payload.get("timestamp", pos.get("exit_time")),
                "position_id": pos.get("position_id"),
                "regime": regime,
                "pnl": round(pnl, 2),
                "is_win": 1 if pnl > 0 else 0
            }
            
            self._write_to_log(record)
            
        except Exception as e:
            self.logger.error(f"Error processing trade_closed in RegimeAttribution: {e}")

    def calculate_metrics(self) -> dict:
        """
        Reads historical regime logs and computes profitability metrics.
        """
        if not os.path.exists(self.log_file):
            return {}
            
        records = []
        with open(self.log_file, "r") as f:
            for line in f:
                try:
                    records.append(json.loads(line))
                except:
                    pass
                    
        regime_stats = {}
        for r in records:
            reg = r.get("regime", "UNKNOWN")
            pnl = r.get("pnl", 0.0)
            win = r.get("is_win", 0)
            
            if reg not in regime_stats:
                regime_stats[reg] = {
                    "trades": 0, "wins": 0, "gross_profit": 0.0, "gross_loss": 0.0, "net_pnl": 0.0
                }
                
            regime_stats[reg]["trades"] += 1
            regime_stats[reg]["wins"] += win
            regime_stats[reg]["net_pnl"] += pnl
            if pnl > 0:
                regime_stats[reg]["gross_profit"] += pnl
            else:
                regime_stats[reg]["gross_loss"] += abs(pnl)
                
        # Merge with ECE from confidence_calibration
        calibration_metrics = confidence_calibration.calculate_metrics().get("by_regime", {})
                
        results = {}
        for reg, stats in regime_stats.items():
            t = stats["trades"]
            w = stats["wins"]
            gp = stats["gross_profit"]
            gl = stats["gross_loss"]
            
            win_rate = w / t if t > 0 else 0.0
            profit_factor = gp / gl if gl > 0 else (gp if gp > 0 else 0.0)
            avg_win = gp / w if w > 0 else 0.0
            avg_loss = gl / (t - w) if (t - w) > 0 else 0.0
            ev = stats["net_pnl"] / t if t > 0 else 0.0
            
            calib = calibration_metrics.get(reg, {})
            ece = calib.get("calibration_error", 1.0)
            
            results[reg] = {
                "trades": t,
                "win_rate": round(win_rate, 4),
                "profit_factor": round(profit_factor, 2),
                "avg_win": round(avg_win, 2),
                "avg_loss": round(avg_loss, 2),
                "ev": round(ev, 2),
                "ece": round(ece, 4)
            }
            
        return results

    def _write_to_log(self, record: dict):
        try:
            with open(self.log_file, "a") as f:
                f.write(json.dumps(record) + "\n")
        except Exception as e:
            self.logger.error(f"Failed to write to {self.log_file}: {e}")

regime_attribution = RegimeAttribution()
