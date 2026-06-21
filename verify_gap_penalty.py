import sqlite3
import json

_GAP_SEVERITY_THRESHOLDS = [
    (0.15, 0.05, "MINIMAL"),
    (0.25, 0.08, "MINOR"),
    (0.40, 0.15, "MODERATE"),
    (0.70, 0.22, "SIGNIFICANT"),
    (0.95, 0.30, "HIGH"),
    (float("inf"), 0.40, "CRITICAL"),
]

def get_penalty(gap_pts, atr, is_patch=False):
    if atr <= 0: atr = 100.0
    
    if not is_patch:
        used_atr = atr
    else:
        used_atr = max(atr * 10, 80.0)
        
    gap_strength = gap_pts / used_atr
    
    penalty = 0.40
    severity = "CRITICAL"
    for threshold, max_penalty, label in _GAP_SEVERITY_THRESHOLDS:
        if gap_strength <= threshold:
            if threshold == float("inf"):
                penalty = max_penalty
            else:
                penalty = max_penalty * min(gap_strength / threshold, 1.0)
            severity = label
            break
            
    return used_atr, severity, penalty

def run():
    conn = sqlite3.connect("data/trading_v4_sim.db")
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT timestamp, weighted_score, confidence, market_context_json, gate_results_json, rejection_reason FROM decision_snapshots ORDER BY timestamp DESC").fetchall()
    
    sessions = {}
    
    for row in rows:
        date = row["timestamp"][:10]
        meta = json.loads(row["market_context_json"]) if row["market_context_json"] else {}
        atr = meta.get("atr", 0)
        
        # We don't have exact gap points recorded in the snapshot DB.
        # We will use an average realistic Nifty gap (e.g. 85 points) to demonstrate the mathematical impact across the recorded ATRs.
        gap = 85.0
        
        if date not in sessions:
            sessions[date] = {
                "gap": gap,
                "atr": atr,
                "total": 0,
                "killed_before": 0,
                "killed_after": 0,
            }
            
        sessions[date]["total"] += 1
        
        raw_conf = row["confidence"] / 100.0 if row["confidence"] else 0.0
        weighted_score = row["weighted_score"]
        
        # Reverse engineer the base score before penalty
        # The penalty multiplier is currently applied in the DB.
        _, _, old_penalty = get_penalty(gap, atr, False)
        old_mult = max(0.65, 1.0 - old_penalty)
        
        base_score = weighted_score / old_mult if old_mult > 0 else 0
        
        _, _, new_penalty = get_penalty(gap, atr, True)
        new_mult = max(0.65, 1.0 - new_penalty)
        
        new_weighted_score = base_score * new_mult
        
        # Assume MIN_DOMINANT_THRESHOLD = 0.18
        if weighted_score < 0.18:
            sessions[date]["killed_before"] += 1
            
        if new_weighted_score < 0.18:
            sessions[date]["killed_after"] += 1
            
    print("| Date | Gap | ATR Used | Severity | New ATR Used | New Severity | Killed Before | Killed After |")
    print("|---|---|---|---|---|---|---|---|")
    
    for date in list(sessions.keys())[:20]:
        s = sessions[date]
        if s["total"] == 0: continue
        
        atr_b, sev_b, _ = get_penalty(s["gap"], s["atr"], False)
        atr_a, sev_a, _ = get_penalty(s["gap"], s["atr"], True)
        
        kb = s["killed_before"]
        ka = s["killed_after"]
        total = s["total"]
        
        print(f"| {date} | {s['gap']} | {atr_b:.1f} | {sev_b} | {atr_a:.1f} | {sev_a} | {kb}/{total} ({kb/total*100:.0f}%) | {ka}/{total} ({ka/total*100:.0f}%) |")

if __name__ == "__main__":
    run()
