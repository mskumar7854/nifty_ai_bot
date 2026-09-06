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

from pathlib import Path

WORKSPACE_DIR = str(Path(__file__).resolve().parent.parent)
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

    def run_replay(self, date_filter: str = None, enforce_oms_concurrency: bool = True) -> dict:
        if not os.path.exists(self.db_path):
            print(f"Database not found: {self.db_path}")
            return {}

        conn = sqlite3.connect(self.db_path)
        query = "SELECT snapshot_id, timestamp, market_json, decision_json, confidence_json, gate_results_json, agents_json, execution_json FROM decision_snapshots_v2"
        if date_filter:
            query += f" WHERE timestamp LIKE '{date_filter}%'"
        
        try:
            df_snaps = pd.read_sql_query(query, conn)
        except Exception:
            df_snaps = pd.DataFrame()
        conn.close()

        if df_snaps.empty:
            return {}

        df_snaps["dt"] = pd.to_datetime(df_snaps["timestamp"])
        df_snaps = df_snaps.sort_values("dt").reset_index(drop=True)

        records = []
        active_until = None

        for idx, row in df_snaps.iterrows():
            dt_snap = row["dt"]
            
            m_json = json.loads(row["market_json"]) if row["market_json"] else {}
            d_json = json.loads(row["decision_json"]) if row["decision_json"] else {}
            c_json = json.loads(row["confidence_json"]) if row["confidence_json"] else {}
            e_json = json.loads(row["execution_json"]) if row.get("execution_json") else {}
            
            spot = m_json.get("spot_price", 0.0)
            atr = m_json.get("atr", 12.0) or 12.0
            
            entry_p = float(e_json.get("entry_price", 0.0))
            sl_p = float(e_json.get("stop_loss", 0.0))
            tp_p = float(e_json.get("target_1", 0.0))
            sig_dir = str(e_json.get("direction", ""))
            
            has_levels = bool(entry_p > 0 and sl_p > 0 and tp_p > 0)
            
            if has_levels:
                sig_type = "BUY_CE" if sig_dir == "LONG" else "BUY_PE" if sig_dir == "SHORT" else "BUY_CE"
                spot_entry = entry_p
                sl_dist = abs(entry_p - sl_p)
                tp_dist = abs(tp_p - entry_p)
            else:
                sig_type = "BUY_PE" if dt_snap.hour >= 10 and dt_snap.hour <= 14 and dt_snap.minute > 20 else "BUY_CE"
                spot_entry = spot
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

                    fav = (spot_entry - p) if sig_type == "BUY_PE" else (p - spot_entry)
                    adv = (p - spot_entry) if sig_type == "BUY_PE" else (spot_entry - p)
                    
                    if fav > mfe_pts: mfe_pts = fav
                    if adv > mae_pts: mae_pts = adv
                    
                    if adv >= sl_dist and outcome == "TIME_EXIT":
                        outcome = "STOPPED_OUT (-1.0R)"
                        realized_r = -1.0
                        exit_dt = f_dt
                        break
                    elif fav >= tp_dist and outcome == "TIME_EXIT":
                        outcome = "TARGET_HIT (+2.0R)"
                        realized_r = round(tp_dist/sl_dist, 2) if sl_dist > 0 else 2.0
                        exit_dt = f_dt
                        break
                        
                if outcome == "TIME_EXIT":
                    last_snap = future_snaps.iloc[-1]
                    f_m = json.loads(last_snap["market_json"]) if last_snap["market_json"] else {}
                    end_p = f_m.get("spot_price", spot_entry)
                    pnl_pts = (spot_entry - end_p) if sig_type == "BUY_PE" else (end_p - spot_entry)
                    realized_r = round(pnl_pts / sl_dist, 2) if sl_dist > 0 else 0.0
                    exit_dt = last_snap["dt"]

            filter_action = d_json.get("action", "REJECTED")
            initial_rejection_class = d_json.get("initial_rejection_class", "MARGINAL") if filter_action == "REJECTED" else None
            
            is_accepted = (filter_action == "EXECUTE")
            is_good_trade = (realized_r > 0)
            
            # Concurrency logic applies ONLY to approved trades that we simulate executing
            if is_accepted and enforce_oms_concurrency:
                if active_until is not None and dt_snap < active_until:
                    # OMS blocked it
                    is_accepted = False
                    filter_action = "REJECTED"
                    initial_rejection_class = "OMS_BLOCKED"
                else:
                    active_until = exit_dt

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
                "has_levels": has_levels,
                "spot": spot_entry,
                "raw_conf": c_json.get("raw", 0.0),
                "sl_pts": round(sl_dist, 1),
                "mfe_pts": round(mfe_pts, 1),
                "mfe_r": round(mfe_pts / sl_dist, 2) if sl_dist > 0 else 0.0,
                "mae_pts": round(mae_pts, 1),
                "mae_r": round(mae_pts / sl_dist, 2) if sl_dist > 0 else 0.0,
                "outcome": outcome,
                "realized_r": realized_r,
                "is_accepted": is_accepted,
                "is_rejected": not is_accepted,
                "is_good_trade": is_good_trade,
                "initial_rejection_class": initial_rejection_class,
                "classification": classification,
                "reason": d_json.get("reason", "") if d_json.get("reason") else "UNKNOWN_REJECTION_REASON"
            })

        df_res = pd.DataFrame(records)
        if df_res.empty: return {}
        df_res = df_res.drop_duplicates(subset=["snapshot_id"])
        
        # Metrics Calculation
        evaluated_candidates = len(df_res)
        
        df_shadow = df_res[df_res["has_levels"] == True]
        shadow_eligible = len(df_shadow)
        
        rejected_opportunities = df_shadow[df_shadow["is_rejected"] == True]
        rejected_count = len(rejected_opportunities)
        
        genuinely_bad = len(rejected_opportunities[rejected_opportunities["initial_rejection_class"] == "GENUINELY_BAD"])
        marginal = len(rejected_opportunities[rejected_opportunities["initial_rejection_class"] == "MARGINAL"])
        
        rejected_profitable = len(rejected_opportunities[rejected_opportunities["is_good_trade"] == True])
        rejected_unprofitable = len(rejected_opportunities[rejected_opportunities["is_good_trade"] == False])
        
        pos_r_avail = df_shadow[df_shadow["is_good_trade"] == True]["realized_r"].sum()
        pos_r_captured = df_shadow[(df_shadow["is_good_trade"] == True) & (df_shadow["is_accepted"] == True)]["realized_r"].sum()
        
        neg_r_avail = df_shadow[df_shadow["is_good_trade"] == False]["realized_r"].sum()
        neg_r_eliminated = rejected_opportunities[rejected_opportunities["is_good_trade"] == False]["realized_r"].sum()
        
        pos_r_cap_pct = (pos_r_captured / pos_r_avail * 100.0) if pos_r_avail > 0 else None
        neg_r_elim_pct = (neg_r_eliminated / neg_r_avail * 100.0) if neg_r_avail < 0 else None
        
        opp_cost = rejected_opportunities[rejected_opportunities["is_good_trade"] == True]["realized_r"].sum()
        
        gate_attribution = {}
        if not rejected_opportunities.empty:
            for gate, group in rejected_opportunities.groupby("reason"):
                gate_name = str(gate).strip()
                if not gate_name or gate_name.lower() == "nan":
                    gate_name = "UNKNOWN_REJECTION_REASON"
                
                # Coerce to numeric, filling NaNs with 0
                r_vals = pd.to_numeric(group["realized_r"], errors="coerce").fillna(0.0)
                
                profitable = len(r_vals[r_vals > 0])
                unprofitable = len(r_vals[r_vals < 0])
                missed_profit = r_vals[r_vals > 0].sum()
                saved_loss = r_vals[r_vals < 0].sum()
                net_r = r_vals.sum()
                
                gate_attribution[gate_name] = {
                    "rejected": len(group),
                    "profitable": profitable,
                    "unprofitable": unprofitable,
                    "missed_profit": float(missed_profit),
                    "saved_loss": float(saved_loss),
                    "net_r": float(net_r)
                }

        return {
            "evaluated_candidates": evaluated_candidates,
            "shadow_eligible": shadow_eligible,
            "rejected_opportunities": rejected_count,
            "genuinely_bad": genuinely_bad,
            "marginal": marginal,
            "rejected_profitable": rejected_profitable,
            "rejected_unprofitable": rejected_unprofitable,
            "pos_r_avail": pos_r_avail,
            "pos_r_captured": pos_r_captured,
            "pos_r_cap_pct": pos_r_cap_pct,
            "neg_r_avail": neg_r_avail,
            "neg_r_eliminated": neg_r_eliminated,
            "neg_r_elim_pct": neg_r_elim_pct,
            "opp_cost": opp_cost,
            "gate_attribution": gate_attribution,
            "df_res": df_res
        }

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
    res = replay_engine.run_replay(enforce_oms_concurrency=True)
    if not res:
        print("No replay data found.")
        sys.exit(0)
        
    print("SHADOW OPPORTUNITY SUMMARY\n")
    print(f"Evaluated candidates: {res['evaluated_candidates']}")
    print(f"Shadow-eligible opportunities: {res['shadow_eligible']}")
    print(f"Rejected opportunities: {res['rejected_opportunities']}\n")
    
    print(f"Genuinely bad: {res['genuinely_bad']}")
    print(f"Marginal: {res['marginal']}\n")
    
    print(f"Rejected opportunities that became profitable: {res['rejected_profitable']}")
    print(f"Rejected opportunities that became unprofitable: {res['rejected_unprofitable']}\n")
    
    print(f"Positive R available: +{res['pos_r_avail']:.2f}R")
    print(f"Positive R captured: +{res['pos_r_captured']:.2f}R")
    if res['pos_r_cap_pct'] is not None:
        print(f"Positive expectancy captured: {res['pos_r_cap_pct']:.1f}%")
    else:
        print("Positive expectancy captured: N/A - no positive opportunity existed")
    print("")
    print(f"Negative R available: {res['neg_r_avail']:.2f}R")
    print(f"Negative R eliminated: {res['neg_r_eliminated']:.2f}R")
    if res['neg_r_elim_pct'] is not None:
        print(f"Negative expectancy eliminated: {res['neg_r_elim_pct']:.1f}%")
    else:
        print("Negative expectancy eliminated: N/A - no negative opportunity existed")
    print("")
    print(f"Opportunity cost: {res['opp_cost']:+.2f}R\n")
    
    print("GATE ATTRIBUTION ANALYSIS\n")
    print("| Gate | Rejected | Profitable | Unprofitable | Missed Profit | Saved Loss | Net Counterfactual R |")
    print("| :--- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for gate, stats in res.get("gate_attribution", {}).items():
        print(f"| {gate} | {stats['rejected']} | {stats['profitable']} | {stats['unprofitable']} | {stats['missed_profit']:+.2f}R | {stats['saved_loss']:+.2f}R | {stats['net_r']:+.2f}R |")

