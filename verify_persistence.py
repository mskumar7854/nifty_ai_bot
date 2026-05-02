import subprocess
import time
import sqlite3
import os

def run_cmd(cmd):
    print(f"Executing: {cmd}")
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)

def verify():
    print("\n" + "="*50)
    print("🧪 FINAL PERSISTENCE VALIDATOR (v4.6.2)")
    print("="*50)

    # 1. Fresh Start
    run_cmd("docker-compose down")
    run_cmd("docker-compose up -d --build")
    time.sleep(15)

    # 2. Inject State into Container
    print("📡 Injecting mock signal VFY-999...")
    ts = int(time.time())
    sql = f"INSERT OR REPLACE INTO signals (id, status, created_at) VALUES ('VFY-999', 'pending', {ts});"
    run_cmd(f"docker exec nifty-trader-prod sqlite3 data/trading_v4.db \"{sql}\"")

    # 3. Destroy Container
    print("💣 Wiping container...")
    run_cmd("docker-compose down")

    # 4. Verify Host File
    db_path = "data/trading_v4.db"
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        res = conn.execute("SELECT status FROM signals WHERE id='VFY-999'").fetchone()
        conn.close()
        
        if res and res[0] == 'pending':
            print("✅ PERSISTENCE VERIFIED: VFY-999 survived the wipe!")
        else:
            print("❌ ERROR: Signal not found in local DB file.")
    else:
        print("❌ ERROR: Local DB file not found.")

    print("="*50 + "\n")

if __name__ == "__main__":
    verify()
