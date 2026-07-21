import os
import csv
import logging
import time
from typing import Dict, Any, Optional

class OIAnalyticsLogger:
    """
    Decoupled logger for capturing Market Structure (OI) analysis every cycle.
    Logs rich features and sets up pending outcomes for future resolution.
    Writes to data/oi_analytics.csv.
    """
    def __init__(self, base_dir: str = "data/oi_validation"):
        self.base_dir = base_dir
        self.logger = logging.getLogger("oi_analytics")
        self._ensure_file_exists(self._get_current_filepath())
        
    def _get_current_filepath(self) -> str:
        """Returns the filepath for the current week, e.g., data/oi_validation/2026-W30/oi_analytics.csv"""
        now = time.localtime()
        year_str = time.strftime("%Y", now)
        week_str = time.strftime("%V", now)
        folder = os.path.join(self.base_dir, f"{year_str}-W{week_str}")
        return os.path.join(folder, "oi_analytics.csv")
        
    def _ensure_file_exists(self, filepath: str):
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        if not os.path.exists(filepath):
            with open(filepath, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Timestamp", "Symbol", "Spot_Price", "Regime", 
                    "Pressure_Score", "Reliability", "Conviction",
                    "Support_Zone", "Resistance_Zone", "Migration", 
                    "Trap", "Wall_Break", "Wall_Absorption", 
                    "Engine_Decision", "Trade_ID", "Position_Size", 
                    "Entry_Price", "Exit_Price", "Exit_Reason",
                    "Delta_15m", "Delta_30m", "Delta_60m", "Final_PnL",
                    "Attr_Structure", "Attr_Tactical", "Attr_Freshness", "Attr_Expiry"
                ])

    def log_event(self, event: dict):
        """
        Logs an OI analytics event to the CSV file.
        Expects a flat dictionary matching the CSV columns.
        """
        row = [
            event.get("Timestamp", ""),
            event.get("Symbol", "NIFTY"),
            event.get("Spot_Price", ""),
            event.get("Regime", ""),
            event.get("Pressure_Score", ""),
            event.get("Reliability", ""),
            event.get("Conviction", ""),
            event.get("Support_Zone", ""),
            event.get("Resistance_Zone", ""),
            event.get("Migration", ""),
            event.get("Trap", ""),
            event.get("Wall_Break", ""),
            event.get("Wall_Absorption", ""),
            event.get("Engine_Decision", ""),
            event.get("Trade_ID", ""),
            event.get("Position_Size", ""),
            event.get("Entry_Price", ""),
            event.get("Exit_Price", ""),
            event.get("Exit_Reason", ""),
            event.get("Delta_15m", ""),
            event.get("Delta_30m", ""),
            event.get("Delta_60m", ""),
            event.get("Final_PnL", ""),
            event.get("Attr_Structure", ""),
            event.get("Attr_Tactical", ""),
            event.get("Attr_Freshness", ""),
            event.get("Attr_Expiry", "")
        ]
        
        filepath = self._get_current_filepath()
        self._ensure_file_exists(filepath)
        
        try:
            with open(filepath, "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(row)
        except Exception as e:
            self.logger.error(f"Failed to write to OI analytics CSV: {e}")
                
    def log_cycle(self, 
                  timestamp: str,
                  symbol: str,
                  spot_price: float,
                  regime: str,
                  oi_analysis: dict,
                  engine_decision: str,
                  trade_id: str = "",
                  position_size: int = 0,
                  entry_price: float = 0.0) -> str:
        """
        Log the cycle analysis. Outcomes can be joined later via Timestamp or Trade_ID.
        """
        # Extract features safely
        pressure = oi_analysis.get("pressure_score", 0)
        reliability = oi_analysis.get("reliability_score", 0)
        conviction = oi_analysis.get("conviction", 0)
        
        sup = oi_analysis.get("support_zone")
        sup_str = f"{sup['low']}-{sup['high']}" if sup else "NONE"
        
        res = oi_analysis.get("resistance_zone")
        res_str = f"{res['low']}-{res['high']}" if res else "NONE"
        
        migration = oi_analysis.get("migration_direction", "NONE")
        trap = oi_analysis.get("trap_type", "NONE")
        wall_break = oi_analysis.get("wall_break_direction", "NONE")
        absorption = str(oi_analysis.get("wall_absorption", False))
        
        attr = oi_analysis.get("feature_attribution", {})
        attr_struct = attr.get("Structure", 0)
        attr_tact = attr.get("Tactical", 0)
        attr_fresh = attr.get("Freshness_Penalty", 0)
        attr_exp = attr.get("Expiry_Penalty", 0)
        
        # Initial write with pending outcome fields empty
        row = [
            timestamp, symbol, spot_price, regime,
            pressure, reliability, conviction,
            sup_str, res_str, migration,
            trap, wall_break, absorption,
            engine_decision, trade_id, position_size,
            entry_price, "", "",
            "", "", "", "",
            attr_struct, attr_tact, attr_fresh, attr_exp
        ]
        
        filepath = self._get_current_filepath()
        self._ensure_file_exists(filepath)
        
        try:
            with open(filepath, "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(row)
        except Exception as e:
            self.logger.error(f"Failed to write to OI analytics CSV: {e}")
            
        return timestamp
