#!/usr/bin/env python3
"""
tools/structure_reset_experiment.py — Structure Reset Tiering & Monotonicity Experiment

Evaluates the 4 precise variants proposed by the user:
- Variant A: Current binary reject (Baseline)
- Variant B: Allow at 50% size
- Variant C: Allow at 25% size
- Variant D: Allow at 50% size only if confidence >= 65%

Methodological Safeguards:
1. In-Sample vs Out-of-Sample Split:
   - In-Sample (IS): 2026-08-04 to 2026-08-18 (11 sessions)
   - Out-of-Sample (OOS): 2026-08-19 to 2026-08-28 (8 sessions)
2. Monotonicity Analysis across Confidence Buckets:
   <55%, 55-60%, 60-65%, 65-70%, 70-75%, 75%+
3. Multi-Dimensional Risk Metrics:
   - Net R, Expectancy (Avg R), Profit Factor, Max Drawdown (R),
     Worst Losing Sequence, Trade Count, Exposure (Total R risked).
"""

import sys
import os
import json
import glob
from pathlib import Path
from collections import defaultdict
from typing import List, Dict

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent

def load_all_replay_records() -> List[Dict]:
    files = sorted(glob.glob(str(REPO_ROOT / "reports" / "daily" / "*_replay.json")))
    records = []
    for fpath in files:
        with open(fpath, "r", encoding="utf-8") as f:
            items = json.load(f)
            for it in items:
                it["source_file"] = os.path.basename(fpath)
                records.append(it)
    return records

def is_structure_reset_candidate(rec: Dict) -> bool:
    r = rec.get("reason", "")
    return "SAME_STRUCTURAL_TREND" in r

def calculate_metrics(trades: List[Dict], size_multiplier: float = 1.0) -> Dict:
    if not trades:
        return {
            "trades": 0, "wins": 0, "losses": 0, "neither": 0,
            "win_rate": 0.0, "net_r": 0.0, "expectancy": 0.0,
            "pf": 0.0, "max_dd_r": 0.0, "worst_streak": 0, "exposure_r": 0.0
        }

    realized = []
    for t in trades:
        raw_r = float(t.get("realized_r", 0.0))
        realized.append(raw_r * size_multiplier)

    wins = sum(1 for r in realized if r > 0)
    losses = sum(1 for r in realized if r < 0)
    neither = sum(1 for r in realized if r == 0)
    gross_pos = sum(r for r in realized if r > 0)
    gross_neg = abs(sum(r for r in realized if r < 0))
    net_r = gross_pos - gross_neg
    win_rate = (wins / len(realized) * 100) if realized else 0.0
    expectancy = (net_r / len(realized)) if realized else 0.0
    pf = (gross_pos / gross_neg) if gross_neg > 0 else (99.0 if gross_pos > 0 else 1.0)

    # Max Drawdown in R and worst losing streak
    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    streak = 0
    worst_streak = 0
    for r in realized:
        cumulative += r
        if cumulative > peak:
            peak = cumulative
        dd = peak - cumulative
        if dd > max_dd:
            max_dd = dd

        if r < 0:
            streak += 1
            if streak > worst_streak:
                worst_streak = streak
        else:
            streak = 0

    exposure = len(realized) * size_multiplier

    return {
        "trades": len(realized),
        "wins": wins,
        "losses": losses,
        "neither": neither,
        "win_rate": round(win_rate, 1),
        "net_r": round(net_r, 2),
        "expectancy": round(expectancy, 2),
        "pf": round(pf, 2),
        "max_dd_r": round(max_dd, 2),
        "worst_streak": worst_streak,
        "exposure_r": round(exposure, 2)
    }

def run_simulation():
    records = load_all_replay_records()
    sr_records = [r for r in records if is_structure_reset_candidate(r)]
    
    # Sort chronologically by date, time
    sr_records.sort(key=lambda x: (x.get("date", ""), x.get("time", "")))

    in_sample = [r for r in sr_records if r.get("date", "") <= "2026-08-18"]
    out_of_sample = [r for r in sr_records if r.get("date", "") > "2026-08-18"]

    print("="*85)
    print("STRUCTURE RESET TIERING & RISK-ADJUSTED EXPERIMENT")
    print(f"Total Filtered SR Records: {len(sr_records)}")
    print(f"  In-Sample (Aug 04 - Aug 18)   : {len(in_sample)} candidates")
    print(f"  Out-of-Sample (Aug 19 - Aug 28): {len(out_of_sample)} candidates")
    print("="*85)

    # 1. Monotonicity Analysis across Confidence Buckets (All Records)
    buckets = [
        ("<55%", lambda c: c < 55.0),
        ("55-60%", lambda c: 55.0 <= c < 60.0),
        ("60-65%", lambda c: 60.0 <= c < 65.0),
        ("65-70%", lambda c: 65.0 <= c < 70.0),
        ("70-75%", lambda c: 70.0 <= c < 75.0),
        ("75%+", lambda c: c >= 75.0),
    ]

    print("\n--- 1. CONFIDENCE BUCKET MONOTONICITY AUDIT ---")
    print(f"{'BUCKET':<10} | {'TRADES':<6} | {'WIN RATE':<9} | {'NET R':<8} | {'EXPECTANCY':<10} | {'MFE AVG':<8} | {'MAE AVG':<8}")
    print("-"*75)
    for b_label, pred in buckets:
        sub = [r for r in sr_records if pred(float(r.get("raw_conf", 0.0)))]
        if not sub:
            print(f"{b_label:<10} | {0:<6} | {'N/A':<9} | {'N/A':<8} | {'N/A':<10} | {'N/A':<8} | {'N/A':<8}")
            continue
        m = calculate_metrics(sub, 1.0)
        mfe_avg = sum(float(r.get("mfe_r", 0.0)) for r in sub) / len(sub)
        mae_avg = sum(float(r.get("mae_r", 0.0)) for r in sub) / len(sub)
        print(f"{b_label:<10} | {m['trades']:<6} | {m['win_rate']:>5.1f}%   | {m['net_r']:>+6.2f}R | {m['expectancy']:>+7.2f}R   | {mfe_avg:>6.2f}R | {mae_avg:>6.2f}R")

    # 2. Four Variant Evaluation (Overall, In-Sample, Out-of-Sample)
    def evaluate_variants(data_slice, label):
        print(f"\n--- {label.upper()} VARIANT EVALUATION ({len(data_slice)} candidates) ---")
        print(f"{'VARIANT':<38} | {'TRADES':<6} | {'NET R':<8} | {'EXP (R)':<8} | {'PF':<5} | {'MAX DD':<7} | {'STREAK':<6} | {'EXPOSURE':<8}")
        print("-"*95)

        # Variant A: Current binary reject (0 size)
        var_a = {"trades": 0, "net_r": 0.0, "expectancy": 0.0, "pf": 0.0, "max_dd_r": 0.0, "worst_streak": 0, "exposure_r": 0.0}
        print(f"{'A: Current Binary Reject (0%)':<38} | {var_a['trades']:<6} | {var_a['net_r']:>+6.2f}R | {var_a['expectancy']:>+6.2f}R | {var_a['pf']:>4.2f} | {var_a['max_dd_r']:>5.2f}R | {var_a['worst_streak']:<6} | {var_a['exposure_r']:>6.2f}R")

        # Variant B: Allow at 50% size
        var_b = calculate_metrics(data_slice, size_multiplier=0.50)
        print(f"{'B: Allow at 50% Size':<38} | {var_b['trades']:<6} | {var_b['net_r']:>+6.2f}R | {var_b['expectancy']:>+6.2f}R | {var_b['pf']:>4.2f} | {var_b['max_dd_r']:>5.2f}R | {var_b['worst_streak']:<6} | {var_b['exposure_r']:>6.2f}R")

        # Variant C: Allow at 25% size
        var_c = calculate_metrics(data_slice, size_multiplier=0.25)
        print(f"{'C: Allow at 25% Size':<38} | {var_c['trades']:<6} | {var_c['net_r']:>+6.2f}R | {var_c['expectancy']:>+6.2f}R | {var_c['pf']:>4.2f} | {var_c['max_dd_r']:>5.2f}R | {var_c['worst_streak']:<6} | {var_c['exposure_r']:>6.2f}R")

        # Variant D: Allow at 50% only if confidence >= 65%
        sub_d = [r for r in data_slice if float(r.get("raw_conf", 0.0)) >= 65.0]
        var_d = calculate_metrics(sub_d, size_multiplier=0.50)
        print(f"{'D: Allow 50% Size (Conf >= 65%)':<38} | {var_d['trades']:<6} | {var_d['net_r']:>+6.2f}R | {var_d['expectancy']:>+6.2f}R | {var_d['pf']:>4.2f} | {var_d['max_dd_r']:>5.2f}R | {var_d['worst_streak']:<6} | {var_d['exposure_r']:>6.2f}R")

    evaluate_variants(sr_records, "Entire Dataset (19 Sessions)")
    evaluate_variants(in_sample, "In-Sample (Aug 04 - Aug 18)")
    evaluate_variants(out_of_sample, "Out-of-Sample (Aug 19 - Aug 28)")

if __name__ == "__main__":
    run_simulation()
