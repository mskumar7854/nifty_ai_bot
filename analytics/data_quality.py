import os
import json
import logging
from analytics.analytics_bus import analytics_bus

class DataQualityEngine:
    """
    Subscribes to signal_generated and quote_received events.
    Scores the quality of the data feeding into the strategy to distinguish
    between strategy failure and data failure.
    """
    def __init__(self):
        self.logger = logging.getLogger("data_quality_engine")
        self.data_dir = os.path.join("data", "analytics")
        os.makedirs(self.data_dir, exist_ok=True)
        self.log_file = os.path.join(self.data_dir, "data_quality.jsonl")
        
        # Subscribe to relevant events
        analytics_bus.subscribe("signal_generated", self.handle_signal_generated)
        analytics_bus.subscribe("quote_received", self.handle_quote_received)

    def handle_signal_generated(self, payload: dict):
        """Evaluate data quality at the moment a signal is generated."""
        snapshot = payload.get("snapshot", {})
        metadata = payload.get("metadata", {})
        
        # Calculate individual health metrics (0 to 1)
        # 1. Freshness (e.g., if latency > 1500ms, score drops)
        latency_ms = snapshot.get("latency_ms", 0)
        candle_freshness = max(0.0, 1.0 - (latency_ms / 1500.0))
        
        # 2. Quote health (inverted spread penalizes)
        quote = metadata.get("quote", {})
        bid, ask = quote.get("bid", 0), quote.get("ask", 0)
        quote_health = 1.0 if ask > bid and bid > 0 else 0.0
        
        # Aggregate data quality score
        data_quality_score = (candle_freshness + quote_health) / 2.0
        
        record = {
            "timestamp": payload.get("timestamp"),
            "event": "data_quality_evaluated",
            "signal_id": payload.get("signal_id"),
            "data_quality_score": round(data_quality_score, 4),
            "metrics": {
                "candle_freshness": round(candle_freshness, 4),
                "quote_health": round(quote_health, 4),
                "latency_ms": latency_ms
            }
        }
        self._write_to_log(record)
        
    def handle_quote_received(self, payload: dict):
        """Optional fine-grained quote tracking."""
        pass
        
    def _write_to_log(self, record: dict):
        try:
            with open(self.log_file, "a") as f:
                f.write(json.dumps(record) + "\n")
        except Exception as e:
            self.logger.error(f"Failed to write to {self.log_file}: {e}")

# Initialize and register
data_quality_engine = DataQualityEngine()
