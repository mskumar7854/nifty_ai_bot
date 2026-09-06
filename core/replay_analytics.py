"""
core/replay_analytics.py
Phase 4A: Snapshot Replay Engine - Statistical Intelligence
"""
from typing import List, Dict
import collections
from core.replay_simulator import CounterfactualResult

class ReplayAnalytics:
    @staticmethod
    def calculate_gate_impact(results: List[CounterfactualResult]) -> List[Dict]:
        """
        Groups counterfactual results by rejection reason.
        Calculates Net Protection Value (Avoided Loss - Missed Upside).
        """
        gates = collections.defaultdict(lambda: {
            "count": 0,
            "suppressed_r": 0.0,
            "prevented_loss_r": 0.0,
            "win_count": 0
        })
        
        for res in results:
            if not res: continue
            # Credit the first listed reason (or all of them proportionally, but first is fine for now)
            reason = res.rejection_reasons[0] if res.rejection_reasons else "UNKNOWN"
            
            gates[reason]["count"] += 1
            gates[reason]["suppressed_r"] += res.suppressed_r
            gates[reason]["prevented_loss_r"] += res.prevented_loss_r
            if res.is_win:
                gates[reason]["win_count"] += 1
                
        output = []
        for gate, metrics in gates.items():
            net_r = metrics["prevented_loss_r"] - metrics["suppressed_r"]
            win_rate = (metrics["win_count"] / metrics["count"]) * 100
            
            output.append({
                "gate": gate,
                "count": metrics["count"],
                "suppressed_r": metrics["suppressed_r"],
                "prevented_loss_r": metrics["prevented_loss_r"],
                "net_r": net_r,
                "empirical_win_rate": win_rate
            })
            
        # Sort by Net R (most protective first)
        output.sort(key=lambda x: x["net_r"], reverse=True)
        return output

    @staticmethod
    def calibrate_confidence_bands(results: List[CounterfactualResult]) -> List[Dict]:
        """
        Groups all trades (EXECUTE and REJECTED) into confidence bands.
        """
        bands = collections.defaultdict(lambda: {"count": 0, "wins": 0, "exp_r": 0.0})
        
        for res in results:
            if not res: continue
            
            # Confidence is 0-100 usually, but sometimes 0-1
            conf = res.confidence
            if conf > 1.0: conf = conf / 100.0  # Normalize to 0-1
            
            # Banding: 0.40, 0.50, 0.60
            band_lower = round(int(conf * 10) / 10.0, 1)
            band_upper = round(band_lower + 0.1, 1)
            band_name = f"{band_lower:.2f}-{band_upper:.2f}"
            
            bands[band_name]["count"] += 1
            if res.is_win:
                bands[band_name]["wins"] += 1
            bands[band_name]["exp_r"] += res.exp_r_15m
            
        output = []
        for band, metrics in bands.items():
            if metrics["count"] == 0: continue
            wr = (metrics["wins"] / metrics["count"]) * 100
            avg_r = metrics["exp_r"] / metrics["count"]
            output.append({
                "band": band,
                "count": metrics["count"],
                "win_rate": wr,
                "avg_r": avg_r
            })
            
        output.sort(key=lambda x: x["band"])
        return output

    @staticmethod
    def analyze_longitudinal(results: List[CounterfactualResult], slice_by: str = "hour") -> List[Dict]:
        """
        Groups counterfactual results by a temporal or structural dimension.
        slice_by options: "hour", "regime", "vix"
        """
        groups = collections.defaultdict(lambda: {
            "count": 0,
            "wins": 0,
            "exp_r_5m": 0.0,
            "exp_r_15m": 0.0,
            "exp_r_30m": 0.0,
            "suppressed_r": 0.0,
            "prevented_loss_r": 0.0
        })
        
        for res in results:
            if not res: continue
            
            key = "UNKNOWN"
            if slice_by == "hour":
                # Timestamp format: 2026-05-22T09:16:35.123456
                try:
                    # Extract the hour part
                    time_part = res.timestamp.split("T")[1]
                    key = time_part[:2]
                except Exception:
                    key = "???"
            elif slice_by == "regime":
                key = res.regime
            elif slice_by == "vix":
                v = res.vix
                if v < 13:
                    key = "< 13 (LOW_VOL)"
                elif 13 <= v < 16:
                    key = "13-16 (NORMAL)"
                elif 16 <= v < 20:
                    key = "16-20 (HIGH)"
                else:
                    key = "> 20 (EXTREME)"
                    
            groups[key]["count"] += 1
            if res.is_win:
                groups[key]["wins"] += 1
            groups[key]["exp_r_5m"] += res.exp_r_5m
            groups[key]["exp_r_15m"] += res.exp_r_15m
            groups[key]["exp_r_30m"] += res.exp_r_30m
            groups[key]["suppressed_r"] += res.suppressed_r
            groups[key]["prevented_loss_r"] += res.prevented_loss_r
            
        output = []
        for key, m in groups.items():
            if m["count"] == 0: continue
            
            wr = (m["wins"] / m["count"]) * 100
            avg_5m = m["exp_r_5m"] / m["count"]
            avg_15m = m["exp_r_15m"] / m["count"]
            avg_30m = m["exp_r_30m"] / m["count"]
            net_r = m["prevented_loss_r"] - m["suppressed_r"]
            
            output.append({
                "slice_value": key,
                "count": m["count"],
                "win_rate": wr,
                "avg_r_5m": avg_5m,
                "avg_r_15m": avg_15m,
                "avg_r_30m": avg_30m,
                "net_r": net_r
            })
            
        # Sort reasonably
        if slice_by == "hour":
            output.sort(key=lambda x: x["slice_value"])
        else:
            output.sort(key=lambda x: x["count"], reverse=True)
            
        return output
