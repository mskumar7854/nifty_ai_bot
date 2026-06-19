import os
import json
import logging
from analytics.analytics_bus import analytics_bus

class TradeQualityEngine:
    """
    Separates Process Quality (execution, timing, risk) from Strategy Quality (signal strength, regime).
    Helps answer whether a winning trade was just luck, or a losing trade was executed perfectly.
    """
    def __init__(self):
        self.logger = logging.getLogger("trade_quality_engine")
        self.data_dir = os.path.join("data", "analytics")
        os.makedirs(self.data_dir, exist_ok=True)
        self.log_file = os.path.join(self.data_dir, "trade_quality.jsonl")
        
        analytics_bus.subscribe("trade_closed", self.handle_trade_closed)

    def handle_trade_closed(self, payload: dict):
        try:
            pos = payload.get("position", {})
            if not pos:
                return
                
            # 1. Evaluate Process Quality
            process_score = self._evaluate_process_quality(pos, payload)
            
            # 2. Evaluate Strategy Quality
            strategy_score = self._evaluate_strategy_quality(pos)
            
            record = {
                "timestamp": payload.get("timestamp", pos.get("exit_time")),
                "position_id": pos.get("position_id"),
                "process_quality": round(process_score, 4),
                "strategy_quality": round(strategy_score, 4)
            }
            
            self._write_to_log(record)
            
        except Exception as e:
            self.logger.error(f"Error processing trade_closed in TradeQualityEngine: {e}")

    def _evaluate_process_quality(self, pos: dict, payload: dict) -> float:
        """
        Evaluate execution metrics.
        - Was entry slippage low?
        - Did we respect risk sizing?
        - Was the quote fresh?
        """
        score = 1.0
        
        # Slippage penalty
        entry_slip = pos.get("slippage_entry", 0.0)
        if entry_slip > 1.0:
            score -= 0.1
        elif entry_slip > 3.0:
            score -= 0.3
            
        # Spread cost penalty
        spread_pct = pos.get("spread_pct_entry", 0.0)
        if spread_pct > 1.0:
            score -= 0.2
            
        # Holding time (e.g. if held < 1 minute, might be a panic exit)
        hold_minutes = payload.get("hold_minutes", 0)
        if hold_minutes < 1.0 and payload.get("pnl", 0) < 0:
            score -= 0.2
            
        return max(0.0, score)

    def _evaluate_strategy_quality(self, pos: dict) -> float:
        """
        Evaluate signal and system metrics.
        - Was the weighted score high?
        - Was regime aligned?
        - What was the gap between buy and sell agents?
        """
        # Base score from raw confidence (e.g., 0.5 to 1.0)
        weighted_score = pos.get("weighted_score", 0.0)
        
        # Agent gap
        buy_score = pos.get("buy_score", 0.0)
        sell_score = pos.get("sell_score", 0.0)
        gap = abs(buy_score - sell_score)
        
        # Strategy quality is a mix of absolute confidence and directional clarity
        strategy_score = (weighted_score * 0.7) + (gap * 0.3)
        
        return max(0.0, min(1.0, strategy_score))

    def _write_to_log(self, record: dict):
        try:
            with open(self.log_file, "a") as f:
                f.write(json.dumps(record) + "\n")
        except Exception as e:
            self.logger.error(f"Failed to write to {self.log_file}: {e}")

trade_quality_engine = TradeQualityEngine()
