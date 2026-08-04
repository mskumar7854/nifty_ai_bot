import sqlite3
import json
import os
import sys
import pandas as pd
import numpy as np
import hashlib
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

WORKSPACE_DIR = r"c:\Users\Selva\Downloads\nifty-ai-system"
DB_PATH = os.path.join(WORKSPACE_DIR, "data", "trading_v4_sim.db")

class MultiSessionCounterfactualReplay:
    """
    Quantitative Multi-Session Replay Engine with Production OMS Concurrency Constraints:
    - Production OMS Sequential Mode: Enforces max_active_positions = 1 (no overlapping trades).
    - Unconstrained Signal Mode: Evaluates raw counterfactual potential of all candidate signals.
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    def get_db_hash(self) -> str:
        if not os.path.exists(self.db_path):
            return "N/A"
        hasher = hashlib.sha256()
        with open(self.db_path, "rb") as f:
            buf = f.read(65536)
            while len(buf) > 0:
                hasher.update(buf)
                buf = f.read(65536)
        return hasher.hexdigest()[:12]

    def run_replay(self, date_filter: str = None, enforce_oms_concurrency: bool = True) -> pd.DataFrame:
        if not os.path.exists(self.db_path):
            print(f"Database not found: {self.db_path}")
            return pd.DataFrame()

        conn = sqlite3.connect(self.db_path)
        query = "SELECT snapshot_id, timestamp, market_json, decision_json, confidence_json, gate_results_json, agents_json FROM decision_snapshots_v2"
        if date_filter:
            query += f" WHERE timestamp LIKE '{date_filter}%'"
        
        df_snaps = pd.read_sql_query(query, conn)
        conn.close()

        if df_snaps.empty:
            print("No decision snapshots found for replay.")
            return pd.DataFrame()

        df_snaps["dt"] = pd.to_datetime(df_snaps["timestamp"])
        df_snaps = df_snaps.sort_values("dt").reset_index(drop=True)

        records = []
        active_until = None  # Track position exit time for Production OMS mode

        for idx, row in df_snaps.iterrows():
            dt_snap = row["dt"]
            
            # OMS Concurrency Gate: Skip signal if a position is currently active
            if enforce_oms_concurrency and active_until is not None and dt_snap < active_until:
                continue

            m_json = json.loads(row["market_json"]) if row["market_json"] else {}
            d_json = json.loads(row["decision_json"]) if row["decision_json"] else {}
            c_json = json.loads(row["confidence_json"]) if row["confidence_json"] else {}
            
            spot = m_json.get("spot_price", 0.0)
            atr = m_json.get("atr", 12.0) or 12.0
            
            sig_type = "BUY_PE" if dt_snap.hour >= 10 and dt_snap.hour <= 14 and dt_snap.minute > 20 else "BUY_CE"
            
            sl_dist = max(atr * 1.5, 10.0)
            tp_dist = sl_dist * 2.0
            
            future_snaps = df_snaps[df_snaps["dt"] >= dt_snap]
            
            mfe_pts = 0.0
            mae_pts = 0.0
            outcome = "TIME_EXIT"
            realized_r = 0.0
            exit_dt = dt_snap + pd.Timedelta(minutes=45)
            
            if len(future_snaps) > 1:
                for _, f_row in future_snaps.iterrows():
                    f_dt = f_row["dt"]
                    f_m = json.loads(f_row["market_json"]) if f_row["market_json"] else {}
                    p = f_m.get("spot_price")
                    if not p: continue

                    fav = (spot - p) if sig_type == "BUY_PE" else (p - spot)
                    adv = (p - spot) if sig_type == "BUY_PE" else (spot - p)
                    
                    if fav > mfe_pts: mfe_pts = fav
                    if adv > mae_pts: mae_pts = adv
                    
                    if adv >= sl_dist and outcome == "TIME_EXIT":
                        outcome = "STOPPED_OUT (-1.0R)"
                        realized_r = -1.0
                        exit_dt = f_dt
                        break
                    elif fav >= tp_dist and outcome == "TIME_EXIT":
                        outcome = "TARGET_HIT (+2.0R)"
                        realized_r = 2.0
                        exit_dt = f_dt
                        break
                        
                if outcome == "TIME_EXIT":
                    last_snap = future_snaps.iloc[-1]
                    f_m = json.loads(last_snap["market_json"]) if last_snap["market_json"] else {}
                    end_p = f_m.get("spot_price", spot)
                    pnl_pts = (spot - end_p) if sig_type == "BUY_PE" else (end_p - spot)
                    realized_r = round(pnl_pts / sl_dist, 2)
                    exit_dt = last_snap["dt"]

            if enforce_oms_concurrency:
                active_until = exit_dt

            filter_action = d_json.get("action", "REJECTED")
            is_accepted = filter_action == "EXECUTE"
            is_good_trade = realized_r > 0

            # Confusion Matrix Classification
            if is_good_trade and is_accepted:
                classification = "TP"
            elif not is_good_trade and not is_accepted:
                classification = "TN"
            elif is_good_trade and not is_accepted:
                classification = "FN"
            else:
                classification = "FP"

            records.append({
                "date": dt_snap.strftime("%Y-%m-%d"),
                "time": dt_snap.strftime("%H:%M"),
                "snapshot_id": row["snapshot_id"],
                "signal": sig_type,
                "spot": spot,
                "raw_conf": c_json.get("raw", 0.0),
                "sl_pts": round(sl_dist, 1),
                "mfe_pts": round(mfe_pts, 1),
                "mfe_r": round(mfe_pts / sl_dist, 2),
                "mae_pts": round(mae_pts, 1),
                "mae_r": round(mae_pts / sl_dist, 2),
                "outcome": outcome,
                "realized_r": realized_r,
                "classification": classification,
                "reason": d_json.get("reason", "UNKNOWN")
            })

        return pd.DataFrame(records)

    def evaluate_filter_quality(self, df_res: pd.DataFrame) -> dict:
        if df_res.empty:
            return {}

        tp = (df_res["classification"] == "TP").sum()
        tn = (df_res["classification"] == "TN").sum()
        fp = (df_res["classification"] == "FP").sum()
        fn = (df_res["classification"] == "FN").sum()

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

        num = (tp * tn) - (fp * fn)
        den = np.sqrt(float((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn)))
        mcc = (num / den) if den > 0 else 0.0

        return {
            "TP": tp, "TN": tn, "FP": fp, "FN": fn,
            "Precision": round(precision, 3),
            "Recall": round(recall, 3),
            "Specificity": round(specificity, 3),
            "F1_Score": round(f1_score, 3),
            "MCC": round(mcc, 3)
        }

if __name__ == "__main__":
    replay_engine = MultiSessionCounterfactualReplay()
    print("==================================================")
    print("MULTI-SESSION REPLAY ENGINE (OMS CONCURRENCY MODE)")
    print("==================================================")
    df_oms = replay_engine.run_replay(enforce_oms_concurrency=True)
    print(f"Total Sequential OMS Trades: {len(df_oms)}")
    if not df_oms.empty:
        cum_r = df_oms["realized_r"].cumsum()
        peak = cum_r.cummax()
        dd = peak - cum_r
        max_dd = dd.max()
        print(f"OMS Cumulative Expectancy: {df_oms['realized_r'].sum():+.2f}R")
        print(f"OMS Max Drawdown: {max_dd:.2f}R")
