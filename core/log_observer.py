import json
import logging
from collections import defaultdict
from pathlib import Path
from datetime import datetime

logger = logging.getLogger("log_observer")

class LogObserver:
    """
    Analytics brain running alongside the trading brain.
    Transforms raw logs into structured, decision-ready data and provides real-time intraday intelligence.
    """
    MIN_TRADES_FOR_CONTEXT = 5

    def __init__(self):
        self.trades = []
        self.gate_rejections = defaultdict(int)
        self.oi_real = 0
        self.oi_total = 0
        self.signals_generated = 0
        self.consecutive_losses = 0
        
        self.regime_stats = defaultdict(list)
        self.time_buckets = defaultdict(list)
        
        self.analytics_file = Path("data/analytics.json")
        self.analytics_file.parent.mkdir(exist_ok=True, parents=True)

    def on_signal(self):
        """Called every time a new signal is generated (before gates)."""
        self.signals_generated += 1

    def on_cycle_end(self, latency_sec: float):
        """Called at the end of every cycle to monitor execution speed."""
        if latency_sec > 0.5:
            logger.warning(f"⚠️ HIGH LATENCY: {round(latency_sec, 3)}s (Execution Risk)")

    def on_trade_close(self, trade_data: dict):
        hour = str(datetime.now().hour)
        trade_data["hour"] = hour
        
        regime = trade_data.get("regime", "UNKNOWN")
        r_val = trade_data.get("r", 0)
        hold_min = trade_data.get("hold_min", 1.0)
        
        # 5. Time-in-Trade Efficiency (R per minute)
        efficiency = r_val / max(hold_min, 1.0)
        trade_data["efficiency"] = efficiency
        
        self.regime_stats[regime].append(r_val)
        self.time_buckets[hour].append(r_val)
        
        self.trades.append(trade_data)
        
        # 1. Detect Strategy Breakdown Early (Loss clustering)
        if r_val < 0:
            self.consecutive_losses += 1
            if self.consecutive_losses >= 3:
                time_range = f"{datetime.now().hour}:00-{datetime.now().hour+1}:00"
                logger.critical(
                    f"🚨 LOSS CLUSTER — {self.consecutive_losses} losses in {regime} regime ({time_range})"
                )
        else:
            self.consecutive_losses = 0
            
        self._evaluate_edge()
        self._persist()

    def sync_gate_rejections(self, master_rejections: dict):
        self.gate_rejections.update(master_rejections)
        
        # 2. Detect Over-Filtering
        total_rejections = sum(self.gate_rejections.values())
        if total_rejections > 100 and len(self.trades) == 0:
            # We don't want to spam this every cycle, so let's log it periodically
            if total_rejections % 50 == 0:
                logger.warning(f"⚠️ OVER-FILTERING: 0 trades despite {total_rejections} rejections.")
        
        self._persist()

    def on_oi_update(self, source: str):
        self.oi_total += 1
        if source == "REAL":
            self.oi_real += 1

        # 4. Enforce OI Reliability — only in LIVE modes.
        # In SIMULATION, simulated OI is expected behavior, not a failure.
        import os
        system_mode = os.getenv("SYSTEM_MODE", "SIMULATION").upper()
        if system_mode == "SIMULATION":
            return  # Simulated OI is acceptable — don't degrade

        if self.oi_total > 10:
            reliability = (self.oi_real / self.oi_total) * 100
            if reliability < 80:
                # Log periodically — every 100 cycles instead of 20 to reduce noise
                if self.oi_total % 100 == 0:
                    # v3.6: OI fallback architecture in decision_engine_v3 owns the response.
                    # This observer is for passive reporting only — do NOT set strategy_degraded here.
                    logger.warning(
                        f"⚠️ [OI OBSERVER] OI real-data rate {reliability:.1f}% < 80% "
                        f"({self.oi_real}/{self.oi_total} real) "
                        f"— engine fallback active (weight redistributed, strategy continues)"
                    )

    def _evaluate_edge(self):
        """3. Detect Bad R Structure (Negative Edge) with Context"""
        if len(self.trades) < 2:
            return
            
        # Evaluate overall edge periodically (not on every single trade to avoid spam)
        if len(self.trades) % 5 == 0:
            self._check_edge(self.trades, "OVERALL")
            
        # Evaluate specific regime edge based on the last trade
        last_trade = self.trades[-1]
        last_regime = last_trade.get("regime", "UNKNOWN")
        regime_trades = [t for t in self.trades if t.get("regime") == last_regime]
        
        if len(regime_trades) >= self.MIN_TRADES_FOR_CONTEXT:
            self._check_edge(regime_trades, last_regime)

    def _check_edge(self, trade_list: list, context: str):
        if len(trade_list) < self.MIN_TRADES_FOR_CONTEXT:
            return
            
        wins = [t for t in trade_list if t.get("r", 0) > 0]
        losses = [t for t in trade_list if t.get("r", 0) < 0]

        avg_win_r = sum(t["r"] for t in wins) / len(wins) if wins else 0
        avg_loss_r = sum(t["r"] for t in losses) / len(losses) if losses else 0
        
        if avg_win_r > 0 and avg_loss_r < 0:
            if avg_win_r < abs(avg_loss_r):
                net_r = avg_win_r + avg_loss_r
                logger.warning(
                    f"⚠️ NEGATIVE EDGE — {context} regime | Avg R: {net_r:.2f} "
                    f"(Win: +{avg_win_r:.2f}R < Loss: {avg_loss_r:.2f}R)"
                )

    def summary(self) -> dict:
        wins = [t for t in self.trades if t.get("r", 0) > 0]
        losses = [t for t in self.trades if t.get("r", 0) < 0]

        avg_win = sum(t["r"] for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t["r"] for t in losses) / len(losses) if losses else 0
        
        net_r = sum(t.get("r", 0) for t in self.trades)
        net_pnl = sum(t.get("pnl", 0) for t in self.trades)
        
        avg_efficiency = sum(t.get("efficiency", 0) for t in self.trades) / len(self.trades) if self.trades else 0
        
        trades_count = len(self.trades)
        conversion_rate = (trades_count / self.signals_generated) * 100 if self.signals_generated > 0 else 0
        
        # Expectancy Calculation (The Real Edge)
        win_rate = len(wins) / trades_count if trades_count > 0 else 0
        loss_rate = len(losses) / trades_count if trades_count > 0 else 0
        expectancy_r = (win_rate * avg_win) - (loss_rate * abs(avg_loss))

        regime_perf = {}
        for reg, r_list in self.regime_stats.items():
            trades = len(r_list)
            regime_perf[reg] = {
                "avg_r": round(sum(r_list) / trades, 2) if trades else 0,
                "trades": trades,
                "confidence": "HIGH" if trades >= self.MIN_TRADES_FOR_CONTEXT else "LOW"
            }
            
        time_perf = {}
        for hr, r_list in self.time_buckets.items():
            trades = len(r_list)
            time_perf[hr] = {
                "avg_r": round(sum(r_list) / trades, 2) if trades else 0,
                "trades": trades,
                "confidence": "HIGH" if trades >= self.MIN_TRADES_FOR_CONTEXT else "LOW"
            }

        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "signals_generated": self.signals_generated,
            "trades_count": trades_count,
            "conversion_rate_pct": round(conversion_rate, 2),
            "expectancy_r": round(expectancy_r, 3),
            "avg_efficiency": round(avg_efficiency, 3),
            "wins": len(wins),
            "losses": len(losses),
            "avg_win_r": round(avg_win, 2),
            "avg_loss_r": round(avg_loss, 2),
            "net_r": round(net_r, 2),
            "net_pnl": round(net_pnl, 2),
            "oi_reliability_pct": round((self.oi_real / max(1, self.oi_total)) * 100, 1),
            "gate_rejections": dict(self.gate_rejections),
            "regime_performance": regime_perf,
            "time_performance": time_perf,
            "consecutive_losses_current": self.consecutive_losses
        }

    def _persist(self):
        try:
            with open(self.analytics_file, "w") as f:
                json.dump(self.summary(), f, indent=2)
        except Exception as e:
            logger.error(f"Failed to write analytics: {e}")
