import json
import os
from typing import List, Dict
from models.experiment_result import ExperimentResult
from datetime import datetime

def generate_report(experiment_id: str, baseline: List[ExperimentResult], candidate: List[ExperimentResult]):
    """Generates the A/B comparison metrics and JSON output."""
    
    # 1. Economic & Standard Metrics
    def calc_metrics(results: List[ExperimentResult]) -> Dict:
        trades = [r for r in results if r.decision == "EXECUTED"]
        wins = [t for t in trades if t.pnl > 0]
        losses = [t for t in trades if t.pnl < 0]
        
        gross_profit = sum(t.pnl for t in wins)
        gross_loss = abs(sum(t.pnl for t in losses))
        
        return {
            "candidates": len(results),
            "executed": len(trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": len(wins) / len(trades) if trades else 0.0,
            "net_r": sum(t.r_multiple for t in trades),
            "gross_profit": gross_profit,
            "gross_loss": gross_loss,
            "profit_factor": gross_profit / gross_loss if gross_loss > 0 else float('inf'),
            "expectancy": (sum(t.pnl for t in trades) / len(trades)) if trades else 0.0
        }

    base_stats = calc_metrics(baseline)
    cand_stats = calc_metrics(candidate)
    
    # 2. Confusion Matrix (Trade Matching)
    # Match by candidate_id
    base_map = {r.candidate_id: r for r in baseline}
    cand_map = {r.candidate_id: r for r in candidate}
    
    tp = fp = tn = fn = 0
    reasons = {}
    
    for cid, b_res in base_map.items():
        c_res = cand_map.get(cid)
        if not c_res: continue
        
        b_executed = b_res.decision == "EXECUTED"
        c_executed = c_res.decision == "EXECUTED"
        is_winner = b_res.pnl > 0 if b_executed else c_res.pnl > 0 # assuming outcome doesn't change
        
        # We define ground truth as "Was this actually a profitable setup?" 
        # For simplicity, if baseline took it and won, it's a winner. If took it and lost, loser.
        if b_executed:
            if is_winner:
                if c_executed: tp += 1 # Winner Allowed
                else: fn += 1          # Winner Blocked
            else:
                if c_executed: fp += 1 # Loser Allowed
                else: 
                    tn += 1            # Loser Blocked
                    reason = c_res.rejection_reason or "UNKNOWN"
                    reasons[reason] = reasons.get(reason, 0) + 1
                    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    
    # 2.b Bad Trade Removal Efficiency (Losers Blocked / (Losers Blocked + Winners Blocked))
    bad_trade_removal_efficiency = tn / (tn + fn) if (tn + fn) > 0 else 0.0
    
    # 3. Output to Console
    print("\n=============================================")
    print(f"📊 EXPERIMENT RESULTS: {experiment_id}")
    print("=============================================\n")
    
    print(f"{'Metric':<25} | {'Baseline':<12} | {'MAV (Cand)':<12}")
    print("-" * 55)
    for k in base_stats.keys():
        b_val = base_stats[k]
        c_val = cand_stats[k]
        if isinstance(b_val, float):
            print(f"{k:<25} | {b_val:<12.2f} | {c_val:<12.2f}")
        else:
            print(f"{k:<25} | {b_val:<12} | {c_val:<12}")
            
    print("\n--- Confusion Matrix ---")
    print(f"True Positives (Winners Allowed)  : {tp}")
    print(f"False Positives (Losers Allowed)  : {fp}")
    print(f"True Negatives (Losers Blocked)   : {tn}")
    print(f"False Negatives (Winners Blocked) : {fn}")
    print(f"\nPrecision   : {precision:.1%}")
    print(f"Recall      : {recall:.1%}")
    print(f"Specificity : {specificity:.1%}")
    
    print("\n--- Efficiency Metrics ---")
    print(f"Bad Trade Removal Efficiency: {bad_trade_removal_efficiency:.1%} (Higher is better)")
    
    print("\n--- Failure Reasons ---")
    for r, count in reasons.items():
        print(f"{r:<20}: {count}")
        
    # 4. Save JSON Report
    report = {
        "experiment": experiment_id,
        "timestamp": datetime.now().isoformat(),
        "baseline": base_stats,
        "candidate": cand_stats,
        "classification": {
            "precision": precision,
            "recall": recall,
            "true_positives": tp,
            "false_positives": fp,
            "true_negatives": tn,
            "false_negatives": fn
        },
        "rejection_reasons": reasons
    }
    
    os.makedirs("experiments/results", exist_ok=True)
    with open(f"experiments/results/{experiment_id}_results.json", "w") as f:
        json.dump(report, f, indent=2)
        
    # Append to history.json
    history_path = "experiments/history.json"
    history = []
    if os.path.exists(history_path):
        with open(history_path, "r") as f:
            history = json.load(f)
            
    history.append({
        "experiment_id": experiment_id,
        "timestamp": report["timestamp"],
        "baseline_win_rate": base_stats["win_rate"],
        "candidate_win_rate": cand_stats["win_rate"],
        "precision": precision,
        "recall": recall
    })
    
    with open(history_path, "w") as f:
        json.dump(history, f, indent=2)
        
    print(f"\n✅ Results saved to experiments/results/{experiment_id}_results.json")
