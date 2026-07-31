import sqlite3
import json
import os

def check_completeness():
    db_path = "data/trading_v4_sim.db"
    if not os.path.exists(db_path):
        print("Database not found.")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM decision_snapshots_v2")
    rows = cursor.fetchall()
    
    if not rows:
        print("No snapshots found.")
        return

    total = len(rows)
    executed = sum(1 for r in rows if json.loads(r['decision_json']).get("action") == "EXECUTE")
    
    scores = {
        "Market": 0,
        "Agents": 0,
        "Confidence": 0,
        "EV": 0,
        "Structure": 0,
        "Cost": 0,
        "Risk": 0,
        "Gate Results": 0,
        "Decision": 0,
        "Timeline": 0,
        "Outcome": 0,
        "Lineage": 0,
        "Hash Valid": 0,
        "Replay Integrity": 0,
    }

    for row in rows:
        market = json.loads(row['market_json'])
        if market and market.get("spot_price"):
            scores["Market"] += 1
            
        agents = json.loads(row['agents_json'])
        if agents:
            scores["Agents"] += 1
            
        conf = json.loads(row['confidence_json'])
        if conf and conf.get("raw", 0) > 0:
            scores["Confidence"] += 1
            
        ev = json.loads(row['expected_value_json'])
        if ev and "ev_r" in ev:
            scores["EV"] += 1
            
        struct = json.loads(row['structure_json'])
        if struct:
            scores["Structure"] += 1
            
        if ev and "ev_r" in ev: # If we don't have cost, fallback to EV fields
            scores["Cost"] += 1
            
        risk = json.loads(row['risk_json'])
        if risk:
            scores["Risk"] += 1
            
        gates = json.loads(row['gate_results_json'])
        if gates:
            scores["Gate Results"] += 1
            
        decision = json.loads(row['decision_json'])
        if decision and decision.get("action"):
            scores["Decision"] += 1
            
        timeline = json.loads(row['event_timeline_json'])
        if timeline and len(timeline) >= 2:
            scores["Timeline"] += 1
            
        outcome = json.loads(row['outcome_json']) if row['outcome_json'] != 'null' else None
        if outcome:
            scores["Outcome"] += 1
            
        lineage = row['trade_id'] or row['shadow_trade_id'] or row['parent_snapshot_id']
        if lineage:
            scores["Lineage"] += 1
            
        if row['snapshot_hash']:
            scores["Hash Valid"] += 1
            
        replay = json.loads(row['replay_status_json'])
        if replay and replay.get("deterministic", False):
            scores["Replay Integrity"] += 1

    print(f"Total Snapshots: {total}")
    print(f"Executed Trades: {executed}")
    print("-" * 30)
    print("Completeness Score:")
    for cat, score in scores.items():
        pct = (score / total) * 100
        print(f"{cat:<15}: {pct:>6.1f}%")
        
    readiness = sum(scores.values()) / (len(scores) * total) * 100
    print("-" * 30)
    print(f"Research Readiness: {readiness:.1f}%")

if __name__ == "__main__":
    check_completeness()
