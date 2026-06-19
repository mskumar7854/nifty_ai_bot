import os
import json
import logging
import numpy as np
from typing import Dict, List
from collections import defaultdict
from analytics.analytics_bus import analytics_bus

class AgentAttribution:
    """
    Evaluates individual agent performance focusing on Edge Contribution (EV).
    Calculates Regime-Aware Agent EV, Agent Accuracy, Brier Score, ECE, Stability Score,
    and the Agent Correlation Matrix.
    """
    def __init__(self):
        self.logger = logging.getLogger("agent_attribution")
        self.data_dir = os.path.join("data", "analytics")
        os.makedirs(self.data_dir, exist_ok=True)
        self.log_file = os.path.join(self.data_dir, "agent_attribution.jsonl")
        self.leaderboard_file = os.path.join(self.data_dir, "agent_leaderboard.json")
        
        analytics_bus.subscribe("trade_closed", self.handle_trade_closed)

    def handle_trade_closed(self, payload: dict):
        try:
            pos = payload.get("position", {})
            if not pos:
                return
                
            pnl = payload.get("exit_price", 0.0) - pos.get("entry_price", 0.0)
            if pos.get("direction", "BUY").upper() == "SELL":
                pnl = -pnl
            if "pnl" in payload:
                pnl = payload["pnl"]
                
            winning_dir = "BUY" if pnl > 0 else ("SELL" if pnl < 0 else "NEUTRAL")
            regime = pos.get("regime_at_entry", "UNKNOWN")
            
            agent_breakdown = pos.get("agent_breakdown", {})
            if not agent_breakdown:
                agent_breakdown = pos.get("agent_votes", {})
            
            # Record each agent's vote for this trade
            trade_agents = {}
            for agent_name, vote in agent_breakdown.items():
                if agent_name == "_meta":
                    continue
                    
                agent_dir = vote.get("direction", "NEUTRAL").upper()
                agent_conf = vote.get("confidence", 0.0)
                
                is_correct = 1 if (agent_dir == winning_dir and winning_dir != "NEUTRAL") else 0
                
                if agent_dir == "NEUTRAL":
                    ev_contribution = 0.0
                elif agent_dir == winning_dir:
                    ev_contribution = abs(pnl)
                else:
                    ev_contribution = -abs(pnl)
                    
                record = {
                    "timestamp": payload.get("timestamp", pos.get("exit_time")),
                    "position_id": pos.get("position_id"),
                    "agent": agent_name,
                    "regime": regime,
                    "agent_dir": agent_dir,
                    "agent_conf": agent_conf,
                    "is_correct": is_correct,
                    "ev_contribution": round(ev_contribution, 2)
                }
                trade_agents[agent_name] = record
                self._write_to_log(record)
                
            self.generate_leaderboard()
            
        except Exception as e:
            self.logger.error(f"Error processing trade_closed in AgentAttribution: {e}")

    def generate_leaderboard(self):
        if not os.path.exists(self.log_file):
            return
            
        records = []
        with open(self.log_file, "r") as f:
            for line in f:
                try:
                    records.append(json.loads(line))
                except:
                    pass
                    
        agent_history = defaultdict(list)
        trade_votes = defaultdict(dict)
        
        for r in records:
            agent = r["agent"]
            pos_id = r["position_id"]
            agent_history[agent].append(r)
            
            # Map direction to numeric for correlation
            d = r["agent_dir"]
            val = 1 if d == "BUY" else (-1 if d == "SELL" else 0)
            trade_votes[pos_id][agent] = val
            
        leaderboard = []
        
        for agent, history in agent_history.items():
            overall_trades = len(history)
            if overall_trades == 0:
                continue
                
            overall_ev = sum(r["ev_contribution"] for r in history) / overall_trades
            overall_accuracy = sum(r["is_correct"] for r in history) / overall_trades
            
            # Brier Score & ECE
            brier_sum = 0.0
            buckets = {i: {"conf_sum": 0.0, "wins": 0, "count": 0} for i in range(10)}
            
            for r in history:
                c = r["agent_conf"]
                w = r["is_correct"]
                brier_sum += (c - w) ** 2
                
                idx = min(9, int(c * 10))
                buckets[idx]["conf_sum"] += c
                buckets[idx]["wins"] += w
                buckets[idx]["count"] += 1
                
            overall_brier = brier_sum / overall_trades
            
            ece = 0.0
            for b in buckets.values():
                if b["count"] > 0:
                    avg_conf = b["conf_sum"] / b["count"]
                    win_rate = b["wins"] / b["count"]
                    weight = b["count"] / overall_trades
                    ece += weight * abs(avg_conf - win_rate)
            
            # Stability Score
            correctness_array = [r["is_correct"] for r in history]
            stability = {"last_20": 0.0, "last_50": 0.0, "last_100": 0.0}
            
            def calc_stability(arr, window):
                if len(arr) < window: return 0.0
                recent = arr[-window:]
                chunk_size = max(1, window // 10)
                if len(recent) < chunk_size * 2: return 0.0
                chunks = [sum(recent[i:i+chunk_size])/chunk_size for i in range(0, len(recent), chunk_size)]
                return round(float(np.std(chunks)), 4)
                
            stability["last_20"] = calc_stability(correctness_array, 20)
            stability["last_50"] = calc_stability(correctness_array, 50)
            stability["last_100"] = calc_stability(correctness_array, 100)
            
            # Regime Aware
            regimes = {}
            for r in history:
                reg = r["regime"]
                if reg not in regimes:
                    regimes[reg] = {"trades": 0, "correct": 0, "ev_sum": 0.0}
                regimes[reg]["trades"] += 1
                regimes[reg]["correct"] += r["is_correct"]
                regimes[reg]["ev_sum"] += r["ev_contribution"]
                
            regime_stats = {}
            for reg, stats in regimes.items():
                r_trades = stats["trades"]
                regime_stats[reg] = {
                    "accuracy": round(stats["correct"] / r_trades, 4),
                    "ev": round(stats["ev_sum"] / r_trades, 2),
                    "trades": r_trades
                }
                
            leaderboard.append({
                "name": agent,
                "ev": round(overall_ev, 2),
                "accuracy": round(overall_accuracy, 4),
                "brier_score": round(overall_brier, 4),
                "ece": round(ece, 4),
                "participation_count": overall_trades,
                "stability_stddev": stability,
                "by_regime": regime_stats
            })
            
        leaderboard.sort(key=lambda x: x["ev"], reverse=True)
        
        # Calculate Correlation Matrix
        agent_names = list(agent_history.keys())
        correlation_matrix = {}
        
        for i, a1 in enumerate(agent_names):
            correlation_matrix[a1] = {}
            for j, a2 in enumerate(agent_names):
                if i == j:
                    correlation_matrix[a1][a2] = 1.0
                    continue
                if j < i:
                    correlation_matrix[a1][a2] = correlation_matrix[a2][a1]
                    continue
                    
                v1, v2 = [], []
                for votes in trade_votes.values():
                    if a1 in votes and a2 in votes:
                        v1.append(votes[a1])
                        v2.append(votes[a2])
                
                if len(v1) > 1:
                    # np.corrcoef can return NaN if variance is 0
                    with np.errstate(divide='ignore', invalid='ignore'):
                        corr = np.corrcoef(v1, v2)[0, 1]
                        if np.isnan(corr):
                            corr = 0.0
                else:
                    corr = 0.0
                    
                correlation_matrix[a1][a2] = round(float(corr), 4)
        
        output = {
            "top_agents": leaderboard,
            "correlation_matrix": correlation_matrix
        }
        
        try:
            with open(self.leaderboard_file, "w") as f:
                json.dump(output, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to write leaderboard: {e}")

    def _write_to_log(self, record: dict):
        try:
            with open(self.log_file, "a") as f:
                f.write(json.dumps(record) + "\n")
        except Exception as e:
            self.logger.error(f"Failed to write to {self.log_file}: {e}")

agent_attribution = AgentAttribution()
