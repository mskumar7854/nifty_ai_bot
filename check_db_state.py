import sqlite3
import pandas as pd
from datetime import datetime
import json

DB_PATH = 'data/trading_v4.db'

def check_db():
    print(f"\n{'='*60}")
    print(f"📦 NIFTY AI DATABASE STATE — {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*60}\n")
    
    conn = sqlite3.connect(DB_PATH)
    
    print("🚦 ACTIVE SIGNAL QUEUE:")
    try:
        query = "SELECT id, status, execution_status, created_at, queue_position FROM signals ORDER BY created_at DESC LIMIT 5"
        df = pd.read_sql_query(query, conn)
        if df.empty:
            print("  (Empty)")
        else:
            print(df.to_string(index=False))
    except Exception as e:
        print(f"  Error reading signals: {e}")
        
    print("\n📈 RECENT TRADES (PERSISTED):")
    try:
        query = "SELECT timestamp, result, pnl, regime, signal_type FROM trades ORDER BY id DESC LIMIT 5"
        df_trades = pd.read_sql_query(query, conn)
        if df_trades.empty:
            print("  (Empty)")
        else:
            print(df_trades.to_string(index=False))
    except Exception as e:
        print(f"  Error reading trades: {e}")
        
    # Check for anomalies
    print("\n🔍 ANOMALY DETECTION:")
    try:
        # Check for stranded 'executing' signals
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM signals WHERE execution_status = 'executing'")
        executing_count = cursor.fetchone()[0]
        if executing_count > 0:
            print(f"  ⚠️ ALERT: {executing_count} signals are in 'executing' state (Crash detection needed!)")
        else:
            print("  ✅ No stranded executing signals found.")
            
        # Check for un-pruned zombies
        import time
        now = time.time()
        cursor.execute("SELECT COUNT(*) FROM signals WHERE status = 'queued' AND (? - created_at) > 30", (now,))
        zombie_count = cursor.fetchone()[0]
        if zombie_count > 0:
            print(f"  ⚠️ ALERT: {zombie_count} zombie signals > 30s old detected in queue.")
        else:
            print("  ✅ Queue is lean (No zombies).")
            
    except Exception as e:
        print(f"  Anomaly check error: {e}")
        
    conn.close()
    print(f"\n{'='*60}")

if __name__ == "__main__":
    check_db()
