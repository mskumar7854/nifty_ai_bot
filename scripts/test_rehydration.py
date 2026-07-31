import sqlite3
import pandas as pd
import datetime
import numpy as np
from collections import defaultdict
from models import AgentOutput, Direction, Strength, MarketSnapshot
from config.settings import Settings

# Dummy Timestamp to make eval work
Timestamp = pd.Timestamp

def load_rehydration_data(db_path, limit=5):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT timestamp, spot_price, vix, agent_outputs_json, gap_penalty_multiplier
        FROM decision_snapshots 
        WHERE agent_outputs_json != '{}'
        ORDER BY timestamp ASC
        LIMIT ?
    """, (limit,))
    
    rows = cursor.fetchall()
    conn.close()
    
    snapshots = []
    for row in rows:
        outputs_str = row['agent_outputs_json']
        # Use eval to reconstruct AgentOutputs
        env = {
            'AgentOutput': AgentOutput,
            'Direction': Direction,
            'Strength': Strength,
            'Timestamp': pd.Timestamp,
            'datetime': datetime,
            'np': np
        }
        try:
            outputs_dict_raw = eval(outputs_str, env)
        except Exception as e:
            print(f"Eval error: {e}")
            continue
            
        snapshots.append({
            'timestamp': row['timestamp'],
            'price': row['spot_price'],
            'outputs': outputs_dict_raw
        })
        
    return snapshots

if __name__ == "__main__":
    print("Testing rehydration...")
    data = load_rehydration_data("data/trading_v4_sim.db", 5)
    print(f"Loaded {len(data)} snapshots.")
    if data:
        print(f"Sample AgentOutput: {data[0]['outputs']['momentum']}")
