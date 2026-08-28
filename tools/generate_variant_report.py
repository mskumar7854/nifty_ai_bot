"""
============================================================
🔬 SHADOW VARIANT EXPERIMENT REPORT
============================================================
Generates a daily multi-variant comparison report.
Matches the counterfactual outcomes of candidates with their
post-commit variant decisions.

Distinguishes between:
- Qualified Candidates: passed the variant's policy
- Counterfactual Executions: OMS-constrained trades

Answers: "What happens if we change the policy?"
============================================================
"""

import sqlite3
import sys
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass, field
from typing import List, Dict
import json

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

WORKSPACE = Path(r"c:\Users\Selva\Downloads\nifty-ai-system")
sys.path.insert(0, str(WORKSPACE))

import pandas as pd

# We reuse the exact counterfactual outcome calculation from the ablation tool
# to ensure zero drift between the diagnostic and the experiment.
from tools.gate_ablation_analysis import load_all_candidates, CandidateRecord, simulate_oms_sequential

DB_PATH = WORKSPACE / "data" / "trading_v4_sim.db"
REPORT_DIR = WORKSPACE / "reports"

@dataclass
class VariantMetrics:
    variant_id: str
    description: str
    qualified_count: int = 0
    qualified_profitable: int = 0
    qualified_unprofitable: int = 0
    qualified_net_r: float = 0.0
    
    executed_cands: List[CandidateRecord] = field(default_factory=list)
    
    main_blockers: Dict[str, int] = None

    def __post_init__(self):
        self.main_blockers = defaultdict(int)

def generate_report():
    print("Loading candidate records with counterfactual outcomes...")
    candidates = {c.snapshot_id: c for c in load_all_candidates()}
    
    if not candidates:
        print("No candidates found in database.")
        return
        
    print(f"Loaded {len(candidates)} V2 snapshots.")
    
    conn = sqlite3.connect(str(DB_PATH))
    
    # Get variant descriptions
    try:
        from core.shadow_variant_runner import VARIANTS
        descriptions = {k: v.get("description", "") for k, v in VARIANTS.items()}
    except ImportError:
        descriptions = defaultdict(str)
    
    # Load variant decisions
    cursor = conn.execute("""
        SELECT snapshot_id, variant_id, variant_decision, variant_primary_blocker
        FROM variant_decisions
    """)
    
    metrics: Dict[str, VariantMetrics] = {}
    
    for row in cursor.fetchall():
        snap_id, var_id, decision, blocker = row
        
        if var_id not in metrics:
            metrics[var_id] = VariantMetrics(variant_id=var_id, description=descriptions.get(var_id, ""))
            
        if snap_id not in candidates:
            continue
            
        cand = candidates[snap_id]
        m = metrics[var_id]
        
        if decision == "WOULD_FAIL":
            if blocker:
                m.main_blockers[blocker] += 1
        elif decision == "WOULD_PASS":
            # 1. Policy Qualification
            m.qualified_count += 1
            m.qualified_net_r += cand.realized_r
            if cand.realized_r > 0:
                m.qualified_profitable += 1
            elif cand.realized_r < 0:
                m.qualified_unprofitable += 1
                
    # Now simulate OMS constraint (one trade at a time) for Executed counts
    for var_id, m in metrics.items():
        cursor = conn.execute("""
            SELECT v.snapshot_id, v.timestamp
            FROM variant_decisions v
            WHERE v.variant_id = ? AND v.variant_decision = 'WOULD_PASS'
            ORDER BY v.timestamp
        """, (var_id,))
        
        passed_snaps = cursor.fetchall()
        passed_set = {s[0] for s in passed_snaps}
        
        def qualifies_fn(cand: CandidateRecord) -> bool:
            return cand.snapshot_id in passed_set
            
        executed_cands = simulate_oms_sequential(list(candidates.values()), qualifies_fn)
        m.executed_cands = executed_cands
            
    conn.close()
    
    from tools.gate_ablation_analysis import compute_r_metrics
    
    # Pre-calculate metrics
    computed_metrics = {}
    for var_id, m in metrics.items():
        e_r_vals = [c.realized_r for c in m.executed_cands]
        e_metrics = compute_r_metrics(e_r_vals)
        computed_metrics[var_id] = e_metrics
        
    # Build Session x Variant Cumulative R matrix
    # Get all unique dates
    all_dates = sorted(list(set(c.date for c in candidates.values())))
    session_matrix = {date: {var_id: 0.0 for var_id in metrics.keys()} for date in all_dates}
    
    # Accumulate daily R
    for var_id, m in metrics.items():
        for cand in m.executed_cands:
            session_matrix[cand.date][var_id] += cand.realized_r
            
    # Convert to cumulative R
    cumulative_matrix = {date: {var_id: 0.0 for var_id in metrics.keys()} for date in all_dates}
    running_totals = {var_id: 0.0 for var_id in metrics.keys()}
    
    for date in all_dates:
        for var_id in metrics.keys():
            running_totals[var_id] += session_matrix[date][var_id]
            cumulative_matrix[date][var_id] = running_totals[var_id]
            
    conn.close()
    
    # ── FORMAT REPORT ──
    report_lines = [
        "# 🔬 Shadow Variant Experiment Report",
        "",
        "> **PRELIMINARY DATA** — Simulated counterfactual outcomes.",
        "> *Do not confuse 'Qualified Candidates' with actual live executions.*",
        "",
        "## Policy Qualification vs. Execution",
        "",
        "| Variant | Description | Qualified | Executed (OMS) | Net R (Exec) | Win% (Exec) | Main Blocker |",
        "|---------|-------------|----------:|---------------:|-------------:|------------:|--------------|"
    ]
    
    # Sort by variant ID
    sorted_vars = sorted(metrics.keys())
    for var_id in sorted_vars:
        m = metrics[var_id]
        e_m = computed_metrics[var_id]
        
        win_pct = e_m["win_rate"]
        top_blocker = max(m.main_blockers.items(), key=lambda x: x[1])[0] if m.main_blockers else "None"
        
        desc = m.description.split("—")[0].strip() if "—" in m.description else m.description
        if len(desc) > 20: desc = desc[:17] + "..."
        
        report_lines.append(
            f"| {var_id:<15} | {desc:<15} | {m.qualified_count:9} | {e_m['count']:14} | {e_m['net_r']:>11.2f}R | {win_pct:>10.1f}% | {top_blocker} |"
        )
        
    report_lines.append("")
    report_lines.append("## Cumulative R by Session")
    report_lines.append("")
    
    # Table Header
    header = "| Session | " + " | ".join(sorted_vars) + " |"
    separator = "|--------|" + "|".join(["-" * max(len(v) + 2, 8) for v in sorted_vars]) + "|"
    report_lines.append(header)
    report_lines.append(separator)
    
    for date in all_dates:
        row = f"| {date} | "
        cols = []
        for var_id in sorted_vars:
            val = cumulative_matrix[date][var_id]
            # Format width to match header
            width = max(len(var_id), 6)
            cols.append(f"{val:>{width}.2f}R")
        row += " | ".join(cols) + " |"
        report_lines.append(row)
        
    report_lines.append("")
    report_lines.append("## Variant Details")
    report_lines.append("")
    
    for var_id in sorted_vars:
        m = metrics[var_id]
        e_m = computed_metrics[var_id]
        report_lines.append(f"### {var_id}")
        report_lines.append(f"*{m.description}*")
        report_lines.append("")
        report_lines.append(f"- **Qualified Candidates:** {m.qualified_count} (W: {m.qualified_profitable}, L: {m.qualified_unprofitable})")
        report_lines.append(f"- **Counterfactual Executions:** {e_m['count']} (W: {e_m['winners']}, L: {e_m['losers']})")
        report_lines.append(f"- **Net R:** {e_m['net_r']:.2f}R")
        report_lines.append(f"- **Win Rate:** {e_m['win_rate']:.1f}%")
        report_lines.append(f"- **Profit Factor:** {e_m['profit_factor']:.2f}")
        report_lines.append(f"- **Avg R / Trade:** {e_m['avg_r']:.2f}R")
        report_lines.append(f"- **Median R:** {e_m['median_r']:.2f}R")
        report_lines.append(f"- **Max Drawdown (R):** {e_m['max_ae']:.2f}R")
        report_lines.append(f"- **Max Consec Losses:** {e_m['max_consec_losses']}")
        report_lines.append("")
        report_lines.append("Top Rejection Reasons:")
        sorted_blockers = sorted(m.main_blockers.items(), key=lambda x: x[1], reverse=True)[:3]
        for b_name, b_count in sorted_blockers:
            report_lines.append(f"- {b_name}: {b_count}")
        report_lines.append("")
        
    out_path = REPORT_DIR / f"variant_report_{pd.Timestamp.now().strftime('%Y%m%d')}.md"
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text("\n".join(report_lines), encoding="utf-8")
    
    print(f"\nReport generated: {out_path}")
    print("\n" + "\n".join(report_lines[:20]))

if __name__ == "__main__":
    generate_report()
