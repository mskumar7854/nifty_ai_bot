import os
import json
import logging
from typing import List, Dict
from analytics.analytics_bus import analytics_bus

class ConfidenceCalibration:
    """
    Answers: "When the system is 80% confident, does it win 80% of the time?"
    Tracks raw_confidence, ECE, Brier Score, and Regime-based calibration.
    """
    def __init__(self):
        self.logger = logging.getLogger("confidence_calibration")
        self.data_dir = os.path.join("data", "analytics")
        os.makedirs(self.data_dir, exist_ok=True)
        self.log_file = os.path.join(self.data_dir, "confidence_calibration.jsonl")
        
        # We need trade_closed to know if it won or lost.
        # But we also need the original confidence. trade_closed passes the position dict,
        # which usually has `weighted_score` or `buy_score`/`sell_score`.
        analytics_bus.subscribe("trade_closed", self.handle_trade_closed)

    def handle_trade_closed(self, payload: dict):
        try:
            pos = payload.get("position", {})
            if not pos:
                return
            
            # The raw confidence is usually the weighted_score or max(buy_score, sell_score)
            raw_confidence = pos.get("weighted_score", 0.0)
            if raw_confidence == 0.0:
                raw_confidence = max(pos.get("buy_score", 0.0), pos.get("sell_score", 0.0))
            
            pnl = payload.get("exit_price", 0.0) - pos.get("entry_price", 0.0)
            if pos.get("direction", "BUY").upper() == "SELL":
                pnl = -pnl
                
            is_win = 1 if pnl > 0 else 0
            
            regime = pos.get("regime_at_entry", "UNKNOWN")
            
            # Extract calibrated confidence if available
            calibrated_confidence = pos.get("calibrated_confidence", raw_confidence)
            
            record = {
                "timestamp": payload.get("timestamp", pos.get("exit_time")),
                "position_id": pos.get("position_id"),
                "raw_confidence": round(raw_confidence, 4),
                "calibrated_confidence": round(calibrated_confidence, 4),
                "is_win": is_win,
                "regime": regime,
                "pnl": round(pnl, 2)
            }
            
            self._write_to_log(record)
            
        except Exception as e:
            self.logger.error(f"Error processing trade_closed in ConfidenceCalibration: {e}")

    def calculate_metrics(self) -> dict:
        """
        Reads historical calibration logs and computes ECE and Brier Score.
        """
        if not os.path.exists(self.log_file):
            return {"trades": 0, "ece": 0.0, "brier": 0.0, "by_regime": {}}
            
        records = []
        with open(self.log_file, "r") as f:
            for line in f:
                try:
                    records.append(json.loads(line))
                except:
                    pass
                    
        if not records:
            return {"trades": 0, "ece": 0.0, "brier": 0.0, "by_regime": {}}
            
        return self._compute_from_records(records)

    def _compute_from_records(self, records: List[Dict]) -> dict:
        total_brier = 0.0
        
        # Bucket by decile for ECE
        buckets = {i: {"conf_sum": 0.0, "wins": 0, "count": 0} for i in range(10)}
        regime_stats = {}
        
        for r in records:
            conf = r.get("raw_confidence", 0.0)
            win = r.get("is_win", 0)
            regime = r.get("regime", "UNKNOWN")
            
            # Brier Score = (predicted_prob - actual_outcome)^2
            total_brier += (conf - win) ** 2
            
            # Bucket logic
            bucket_idx = min(9, int(conf * 10))
            buckets[bucket_idx]["conf_sum"] += conf
            buckets[bucket_idx]["wins"] += win
            buckets[bucket_idx]["count"] += 1
            
            if regime not in regime_stats:
                regime_stats[regime] = {"conf_sum": 0.0, "wins": 0, "count": 0, "brier_sum": 0.0}
            regime_stats[regime]["conf_sum"] += conf
            regime_stats[regime]["wins"] += win
            regime_stats[regime]["count"] += 1
            regime_stats[regime]["brier_sum"] += (conf - win) ** 2
            
        n = len(records)
        brier = total_brier / n
        
        ece = 0.0
        for b in buckets.values():
            if b["count"] > 0:
                avg_conf = b["conf_sum"] / b["count"]
                win_rate = b["wins"] / b["count"]
                weight = b["count"] / n
                ece += weight * abs(avg_conf - win_rate)
                
        by_regime = {}
        for reg, stats in regime_stats.items():
            r_n = stats["count"]
            r_avg_conf = stats["conf_sum"] / r_n
            r_win_rate = stats["wins"] / r_n
            r_brier = stats["brier_sum"] / r_n
            by_regime[reg] = {
                "trades": r_n,
                "avg_confidence": round(r_avg_conf, 4),
                "win_rate": round(r_win_rate, 4),
                "brier": round(r_brier, 4),
                "calibration_error": round(abs(r_avg_conf - r_win_rate), 4)
            }
            
        return {
            "trades": n,
            "brier_score": round(brier, 4),
            "ece": round(ece, 4),
            "by_regime": by_regime
        }
        
    def _write_to_log(self, record: dict):
        try:
            with open(self.log_file, "a") as f:
                f.write(json.dumps(record) + "\n")
        except Exception as e:
            self.logger.error(f"Failed to write to {self.log_file}: {e}")

    def generate_shadow_report(self):
        """Computes ECE for both raw and calibrated confidence and writes to JSON."""
        if not os.path.exists(self.log_file):
            return
            
        records = []
        with open(self.log_file, "r") as f:
            for line in f:
                try:
                    records.append(json.loads(line))
                except:
                    pass
                    
        if not records:
            return
            
        raw_ece = self._compute_ece(records, "raw_confidence")
        shadow_ece = self._compute_ece(records, "calibrated_confidence")
        
        report = {
            "trades": len(records),
            "raw_ece": raw_ece,
            "shadow_ece": shadow_ece,
            "samples": []
        }
        
        # Add 5 random samples
        import random
        sample_records = random.sample(records, min(5, len(records)))
        for r in sample_records:
            report["samples"].append({
                "raw_confidence": r.get("raw_confidence"),
                "calibrated_confidence": r.get("calibrated_confidence"),
                "actual_outcome": r.get("is_win"),
                "regime": r.get("regime")
            })
            
        report_path = os.path.join(self.data_dir, "shadow_calibration_report.json")
        try:
            with open(report_path, "w") as f:
                json.dump(report, f, indent=4)
        except Exception as e:
            self.logger.error(f"Failed to write shadow report: {e}")

    def _compute_ece(self, records, conf_key="raw_confidence"):
        buckets = {i: {"conf_sum": 0.0, "wins": 0, "count": 0} for i in range(10)}
        n = len(records)
        
        for r in records:
            conf = r.get(conf_key, 0.0)
            win = r.get("is_win", 0)
            
            bucket_idx = min(9, int(conf * 10))
            buckets[bucket_idx]["conf_sum"] += conf
            buckets[bucket_idx]["wins"] += win
            buckets[bucket_idx]["count"] += 1
            
        ece = 0.0
        for b in buckets.values():
            if b["count"] > 0:
                avg_conf = b["conf_sum"] / b["count"]
                win_rate = b["wins"] / b["count"]
                weight = b["count"] / n
                ece += weight * abs(avg_conf - win_rate)
                
        return round(ece, 4)

confidence_calibration = ConfidenceCalibration()
