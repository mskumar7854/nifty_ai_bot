"""
P1: Analytics Intelligence Layer — Nifty AI System
====================================================

Provides self-explanatory statistical analysis over decision_snapshots
and trade_economics tables. All queries are read-only. No live state needed.

CLI Usage:
    python analytics.py expectancy
    python analytics.py expectancy --by regime
    python analytics.py expectancy --by spread_bucket
    python analytics.py expectancy --by grade
    python analytics.py expectancy --by hour
    python analytics.py mfe-mae
    python analytics.py execution
    python analytics.py agents
    python analytics.py summary
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

DB_PATH = "data/trading_v4.db"

CYAN    = "\033[96m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
RED     = "\033[91m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
RESET   = "\033[0m"

MIN_SAMPLE = 5  # Minimum trades/signals before reporting expectancy


def _get_conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _load_json(raw: Optional[str]) -> dict:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _fmt_r(r: float) -> str:
    """Format R-multiple with colour."""
    if r is None:
        return f"{DIM}N/A{RESET}"
    s = f"{r:+.2f}R"
    return f"{GREEN}{s}{RESET}" if r > 0 else f"{RED}{s}{RESET}"


def _bar(value: float, max_val: float, width: int = 30) -> str:
    if max_val == 0:
        return ""
    filled = int(abs(value) / max_val * width)
    char = "█" if value >= 0 else "░"
    color = GREEN if value >= 0 else RED
    return f"{color}{char * filled}{RESET}"


# ─────────────────────────────────────────────────────────────────────────────
# 1. Expectancy Analysis
# ─────────────────────────────────────────────────────────────────────────────

def _spread_bucket(pct: float) -> str:
    if pct < 0.5:   return "TIGHT  (<0.5%)"
    if pct < 1.0:   return "NORMAL (0.5-1%)"
    if pct < 1.5:   return "WIDE   (1-1.5%)"
    return             "VERY_WIDE (>1.5%)"


def _hour_bucket(ts: str) -> str:
    try:
        h = int(ts[11:13])
        m = int(ts[14:16])
        if h == 9 and m < 30:   return "09:00-09:30 (OPEN)"
        if h == 9:               return "09:30-10:00"
        if h == 10:              return "10:00-11:00"
        if h == 11:              return "11:00-12:00"
        if h == 12:              return "12:00-13:00 (LUNCH)"
        if h == 13:              return "13:00-14:00"
        if h == 14:              return "14:00-15:00"
        return                         "15:00+ (CLOSE)"
    except Exception:
        return "UNKNOWN"


def analyze_expectancy(conn: sqlite3.Connection, by: str = "regime") -> None:
    """
    Rejected Signal Expectancy Analysis — the most important P1 insight.

    Compares accepted vs rejected signals bucketed by the specified dimension.
    Uses decision_snapshots as the source of truth.

    This reveals: "Which filters are suppressing winners?"
    """

    rows = conn.execute("""
        SELECT
            ds.snapshot_id, ds.final_decision, ds.regime, ds.grade,
            ds.spread_pct, ds.timestamp, ds.weighted_score, ds.confidence,
            te.net_pnl, te.realized_r_multiple,
            te.spread_pct_entry, te.holding_seconds
        FROM decision_snapshots ds
        LEFT JOIN orders o ON ds.intent_id = o.intent_id
        LEFT JOIN trade_economics te ON ds.intent_id = te.intent_id
    """).fetchall()

    buckets: Dict[str, Dict] = {}

    for r in rows:
        s = dict(r)
        decision = s.get("final_decision", "UNKNOWN")

        if by == "regime":
            key = s.get("regime", "UNKNOWN") or "UNKNOWN"
        elif by == "spread_bucket":
            key = _spread_bucket(float(s.get("spread_pct") or 0))
        elif by == "grade":
            key = s.get("grade", "UNKNOWN") or "UNKNOWN"
        elif by == "hour":
            key = _hour_bucket(s.get("timestamp", ""))
        else:
            key = "ALL"

        if key not in buckets:
            buckets[key] = {
                "execute_count": 0, "rejected_count": 0,
                "execute_r": [], "rejected_r": [],
                "execute_pnl": [], "rejected_pnl": [],
            }

        r_mult = s.get("realized_r_multiple")
        net_pnl = s.get("net_pnl")

        if decision == "EXECUTE":
            buckets[key]["execute_count"] += 1
            if r_mult is not None: buckets[key]["execute_r"].append(float(r_mult))
            if net_pnl is not None: buckets[key]["execute_pnl"].append(float(net_pnl))
        elif decision == "REJECTED":
            buckets[key]["rejected_count"] += 1
            # Rejected signals have no trade_economics (that's the point — we want to infer)

    total_snaps = len(rows)
    print(f"\n{'═'*75}")
    print(f"{BOLD}{CYAN}📊 EXPECTANCY ANALYSIS  (by {by.upper()})  —  {total_snaps} total snapshots{RESET}")
    print(f"{'═'*75}")
    print(f"\n{'Key':28s}  {'Exec':>6}  {'Rej':>6}  {'Avg Net R':>10}  {'Avg PnL':>10}  {'Accept%':>8}")
    print(f"{'─'*75}")

    max_r = max((abs(sum(b["execute_r"]) / max(len(b["execute_r"]), 1)) for b in buckets.values()), default=1)

    for key in sorted(buckets.keys()):
        b = buckets[key]
        ex = b["execute_count"]
        rj = b["rejected_count"]
        total_key = ex + rj
        accept_pct = (ex / total_key * 100) if total_key else 0

        r_vals = b["execute_r"]
        avg_r = sum(r_vals) / len(r_vals) if r_vals else None

        pnl_vals = b["execute_pnl"]
        avg_pnl = sum(pnl_vals) / len(pnl_vals) if pnl_vals else None

        r_str  = _fmt_r(avg_r)
        pnl_str = f"₹{avg_pnl:+,.0f}" if avg_pnl is not None else f"{DIM}no fills{RESET}"
        conf = f"{DIM}(low sample){RESET}" if ex < MIN_SAMPLE else ""

        print(f"  {key:26s}  {ex:>6}  {rj:>6}  {r_str:>10}  {pnl_str:>10}  {accept_pct:>7.1f}%  {conf}")

    print(f"\n{DIM}  Only EXECUTE signals with closed trades have net R data.")
    print(f"  REJECTED signal P&L is structurally unavailable — that's the survivorship gap.{RESET}")
    print(f"{'═'*75}\n")


# ─────────────────────────────────────────────────────────────────────────────
# 2. MFE / MAE Analytics
# ─────────────────────────────────────────────────────────────────────────────

def analyze_mfe_mae(conn: sqlite3.Connection) -> None:
    """
    Trade path intelligence: Maximum Favorable/Adverse Excursion.

    Answers:
    - How much profit did we leave on the table (exit too early)?
    - How close did trades get to our stop before recovering?
    - Is the TSL engine exiting at the right moment?
    """
    rows = conn.execute("""
        SELECT
            te.intent_id, te.gross_pnl, te.net_pnl, te.realized_r_multiple,
            te.mfe, te.mae, te.holding_seconds,
            te.spread_cost, te.slippage_cost,
            ds.regime, ds.grade, ds.spread_pct
        FROM trade_economics te
        LEFT JOIN decision_snapshots ds ON te.intent_id = ds.intent_id
        WHERE te.net_pnl IS NOT NULL
    """).fetchall()

    if not rows:
        print(f"\n{YELLOW}No closed trade economics found yet.{RESET}\n")
        return

    n = len(rows)
    all_r     = [float(r["realized_r_multiple"] or 0) for r in rows]
    all_mfe   = [float(r["mfe"] or 0) for r in rows if r["mfe"] is not None]
    all_mae   = [float(r["mae"] or 0) for r in rows if r["mae"] is not None]
    all_hold  = [float(r["holding_seconds"] or 0) for r in rows if r["holding_seconds"]]
    all_net   = [float(r["net_pnl"] or 0) for r in rows]
    all_costs = [(float(r["spread_cost"] or 0) + float(r["slippage_cost"] or 0)) for r in rows]

    avg_r   = sum(all_r) / n
    avg_mfe = sum(all_mfe) / len(all_mfe) if all_mfe else 0
    avg_mae = sum(all_mae) / len(all_mae) if all_mae else 0
    avg_hold_min = (sum(all_hold) / len(all_hold) / 60) if all_hold else 0
    avg_net = sum(all_net) / n
    avg_cost = sum(all_costs) / n
    wins   = sum(1 for x in all_net if x > 0)
    losses = sum(1 for x in all_net if x < 0)

    # Exit Efficiency: actual_exit_pnl / mfe (how much of the available move did we capture?)
    efficiencies = []
    for row in rows:
        mfe = float(row["mfe"] or 0)
        net = float(row["net_pnl"] or 0)
        if mfe > 0 and net > 0:
            efficiencies.append(net / mfe)
    avg_efficiency = sum(efficiencies) / len(efficiencies) if efficiencies else None

    print(f"\n{'═'*65}")
    print(f"{BOLD}{CYAN}📈 MFE / MAE TRADE PATH ANALYTICS  —  {n} closed trades{RESET}")
    print(f"{'═'*65}")
    print(f"\n  {BOLD}Portfolio Summary:{RESET}")
    print(f"  Win / Loss          : {GREEN}{wins}{RESET} W / {RED}{losses}{RESET} L   (WR: {wins/n*100:.1f}%)")
    print(f"  Avg Net R           : {_fmt_r(avg_r)}")
    print(f"  Avg Net P&L         : {GREEN if avg_net > 0 else RED}₹{avg_net:+,.0f}{RESET}")
    print(f"  Avg Total Cost      : ₹{avg_cost:,.0f}  (spread + slippage per trade)")
    print(f"  Avg Hold Time       : {avg_hold_min:.1f} min")

    print(f"\n  {BOLD}Trade Path Quality:{RESET}")
    print(f"  Avg MFE (potential) : ₹{avg_mfe:+,.0f}")
    print(f"  Avg MAE (risk seen) : ₹{avg_mae:+,.0f}")
    if avg_efficiency is not None:
        eff_pct = avg_efficiency * 100
        eff_color = GREEN if eff_pct >= 60 else YELLOW if eff_pct >= 40 else RED
        print(f"  Exit Efficiency     : {eff_color}{eff_pct:.1f}%{RESET}  (% of MFE captured on winners)")
    if avg_mfe != 0:
        mfe_ratio = abs(avg_mae / avg_mfe) if avg_mfe else 0
        print(f"  MAE/MFE Ratio       : {mfe_ratio:.2f}  (lower = trades moved in your direction)")

    # Regime breakdown
    regime_data: Dict[str, list] = {}
    for row in rows:
        k = row["regime"] or "UNKNOWN"
        if k not in regime_data:
            regime_data[k] = []
        regime_data[k].append(float(row["net_pnl"] or 0))

    if len(regime_data) > 1:
        print(f"\n  {BOLD}Net P&L by Regime:{RESET}")
        for regime, pnls in sorted(regime_data.items()):
            avg = sum(pnls) / len(pnls)
            color = GREEN if avg > 0 else RED
            print(f"  {regime:25s}: {color}₹{avg:+,.0f}{RESET}  (n={len(pnls)})")

    print(f"\n{'═'*65}\n")


# ─────────────────────────────────────────────────────────────────────────────
# 3. Execution Quality Scoring
# ─────────────────────────────────────────────────────────────────────────────

def _execution_quality_score(spread_pct: float, quote_age_ms: float, slippage: float) -> float:
    """
    Composite execution quality score 0-100.
    Weights: spread 35%, quote freshness 20%, slippage 25%, fill efficiency 20%.
    """
    # Spread score (100 = tight, 0 = very wide)
    spread_score = max(0, 100 - (spread_pct / 2.0) * 100)

    # Quote freshness score (100 = fresh, 0 = stale >2000ms)
    freshness_score = max(0, 100 - (quote_age_ms / 2000) * 100)

    # Slippage score (100 = no slippage, 0 = >2 pts slippage)
    slippage_score = max(0, 100 - (abs(slippage) / 2.0) * 100)

    # Fill efficiency (placeholder — 80 until we have level2 data)
    fill_score = 80.0

    return (spread_score * 0.35 + freshness_score * 0.20 + slippage_score * 0.25 + fill_score * 0.20)


def analyze_execution_quality(conn: sqlite3.Connection) -> None:
    """
    Execution Quality Analytics.

    Answers: "Is the engine's edge being eroded by execution friction?"
    Scores each trade 0-100 and compares quality buckets vs net P&L.
    """
    rows = conn.execute("""
        SELECT
            te.intent_id, te.net_pnl, te.spread_cost, te.slippage_cost,
            te.slippage_entry, te.spread_pct_entry, te.quote_age_ms,
            te.realized_r_multiple, ds.regime, ds.grade
        FROM trade_economics te
        LEFT JOIN decision_snapshots ds ON te.intent_id = ds.intent_id
        WHERE te.net_pnl IS NOT NULL
    """).fetchall()

    if not rows:
        print(f"\n{YELLOW}No closed trade economics found yet.{RESET}\n")
        return

    quality_buckets: Dict[str, List[float]] = {
        "EXCELLENT (80-100)": [],
        "GOOD      (60-80)":  [],
        "FAIR      (40-60)":  [],
        "POOR      (<40)":    [],
    }

    all_scores = []
    for r in rows:
        q = _execution_quality_score(
            float(r["spread_pct_entry"] or 0),
            float(r["quote_age_ms"] or 0),
            float(r["slippage_entry"] or 0),
        )
        all_scores.append(q)
        net = float(r["net_pnl"] or 0)
        if q >= 80:   quality_buckets["EXCELLENT (80-100)"].append(net)
        elif q >= 60: quality_buckets["GOOD      (60-80)"].append(net)
        elif q >= 40: quality_buckets["FAIR      (40-60)"].append(net)
        else:         quality_buckets["POOR      (<40)"].append(net)

    avg_q = sum(all_scores) / len(all_scores) if all_scores else 0
    avg_spread = sum(float(r["spread_pct_entry"] or 0) for r in rows) / len(rows)
    avg_slip   = sum(float(r["slippage_entry"] or 0) for r in rows) / len(rows)
    avg_age    = sum(float(r["quote_age_ms"] or 0) for r in rows) / len(rows)

    print(f"\n{'═'*65}")
    print(f"{BOLD}{CYAN}⚡ EXECUTION QUALITY ANALYTICS  —  {len(rows)} trades{RESET}")
    print(f"{'═'*65}")
    print(f"\n  {BOLD}Portfolio Execution Averages:{RESET}")
    print(f"  Avg Quality Score   : {avg_q:.1f}/100")
    print(f"  Avg Spread Entry    : {avg_spread:.2f}%")
    print(f"  Avg Slippage Entry  : ₹{avg_slip:+.2f}")
    print(f"  Avg Quote Age       : {avg_age:.0f}ms")

    print(f"\n  {BOLD}Net P&L by Execution Quality Bucket:{RESET}")
    print(f"  {'Bucket':26s}  {'Trades':>6}  {'Avg Net PnL':>12}  {'Total PnL':>12}")
    print(f"  {'─'*60}")

    for bucket, pnls in quality_buckets.items():
        if not pnls:
            continue
        avg = sum(pnls) / len(pnls)
        total = sum(pnls)
        color = GREEN if avg > 0 else RED
        print(f"  {bucket:26s}  {len(pnls):>6}  {color}₹{avg:>+10,.0f}{RESET}  {color}₹{total:>+10,.0f}{RESET}")

    print(f"\n  {DIM}Insight: If POOR quality trades have negative expectancy, add a pre-trade")
    print(f"  execution quality gate to block low-quality fills.{RESET}")
    print(f"{'═'*65}\n")


# ─────────────────────────────────────────────────────────────────────────────
# 4. Agent Contribution Scoring
# ─────────────────────────────────────────────────────────────────────────────

def analyze_agent_contribution(conn: sqlite3.Connection) -> None:
    """
    Agent Contribution Analysis.

    For each agent, computes:
    - How often it was present in winning vs losing trades
    - Average contribution score in winning vs losing trades
    - Marginal contribution to expectancy

    WARNING: This is correlation analysis, not causation. Use with caution.
    Requires MIN_SAMPLE trades before drawing conclusions.
    """
    snap_rows = conn.execute("""
        SELECT ds.snapshot_id, ds.agent_outputs_json, ds.intent_id, te.net_pnl
        FROM decision_snapshots ds
        LEFT JOIN trade_economics te ON ds.intent_id = te.intent_id
        WHERE ds.final_decision = 'EXECUTE' AND te.net_pnl IS NOT NULL
    """).fetchall()

    if len(snap_rows) < MIN_SAMPLE:
        print(f"\n{YELLOW}Insufficient data ({len(snap_rows)} trades, need {MIN_SAMPLE}+) for agent analysis.{RESET}\n")
        return

    agents: Dict[str, Dict] = {}

    for row in snap_rows:
        net_pnl = float(row["net_pnl"] or 0)
        win = net_pnl > 0
        outputs = _load_json(row["agent_outputs_json"])

        for agent_name, output in outputs.items():
            if agent_name not in agents:
                agents[agent_name] = {"win_scores": [], "loss_scores": [], "wins": 0, "losses": 0}
            score = output.get("score", output.get("value")) if isinstance(output, dict) else output
            try:
                score = float(score)
            except (TypeError, ValueError):
                score = 0.0

            if win:
                agents[agent_name]["win_scores"].append(score)
                agents[agent_name]["wins"] += 1
            else:
                agents[agent_name]["loss_scores"].append(score)
                agents[agent_name]["losses"] += 1

    print(f"\n{'═'*75}")
    print(f"{BOLD}{CYAN}🤖 AGENT CONTRIBUTION ANALYSIS  —  {len(snap_rows)} executed trades{RESET}")
    print(f"{'═'*75}")
    print(f"\n  {DIM}Avg score on WIN vs LOSS trades. Positive delta = agent adds value on winners.{RESET}")
    print(f"\n  {'Agent':30s}  {'Wins':>5}  {'Losses':>6}  {'Avg WIN score':>14}  {'Avg LOSS score':>15}  {'Delta':>8}")
    print(f"  {'─'*73}")

    for name, data in sorted(agents.items()):
        wins   = data["wins"]
        losses = data["losses"]
        ws = data["win_scores"]
        ls = data["loss_scores"]
        avg_w = sum(ws) / len(ws) if ws else None
        avg_l = sum(ls) / len(ls) if ls else None
        delta = (avg_w or 0) - (avg_l or 0) if (avg_w is not None and avg_l is not None) else None

        w_str = f"{avg_w:.3f}" if avg_w is not None else f"{DIM}N/A{RESET}"
        l_str = f"{avg_l:.3f}" if avg_l is not None else f"{DIM}N/A{RESET}"
        d_str = f"{GREEN}{delta:+.3f}{RESET}" if delta and delta > 0 else (f"{RED}{delta:+.3f}{RESET}" if delta else f"{DIM}N/A{RESET}")

        print(f"  {name:30s}  {wins:>5}  {losses:>6}  {w_str:>14}  {l_str:>15}  {d_str:>8}")

    print(f"\n  {DIM}⚠️  This is correlation analysis only. Positive delta does not prove causation.{RESET}")
    print(f"{'═'*75}\n")


# ─────────────────────────────────────────────────────────────────────────────
# 5. Full Summary
# ─────────────────────────────────────────────────────────────────────────────

def cmd_summary(conn: sqlite3.Connection) -> None:
    """Quick daily intelligence summary — all key metrics at a glance."""
    total_snaps = conn.execute("SELECT COUNT(*) FROM decision_snapshots").fetchone()[0]
    executed    = conn.execute("SELECT COUNT(*) FROM decision_snapshots WHERE final_decision='EXECUTE'").fetchone()[0]
    rejected    = conn.execute("SELECT COUNT(*) FROM decision_snapshots WHERE final_decision='REJECTED'").fetchone()[0]
    trades      = conn.execute("SELECT COUNT(*) FROM trade_economics WHERE net_pnl IS NOT NULL").fetchone()[0]
    total_net   = conn.execute("SELECT SUM(net_pnl) FROM trade_economics").fetchone()[0] or 0
    total_gross = conn.execute("SELECT SUM(gross_pnl) FROM trade_economics").fetchone()[0] or 0
    total_cost  = (total_gross - total_net)

    print(f"\n{'═'*60}")
    print(f"{BOLD}{CYAN}🧠 ANALYTICS INTELLIGENCE SUMMARY{RESET}")
    print(f"{'═'*60}")
    print(f"\n  Total decision snapshots : {total_snaps}")
    print(f"  EXECUTE decisions        : {GREEN}{executed}{RESET}")
    print(f"  REJECTED decisions       : {RED}{rejected}{RESET}  ({rejected/(total_snaps or 1)*100:.0f}% of all signals)")
    print(f"  Closed trades with econ  : {trades}")
    print(f"\n  {BOLD}P&L Summary (all closed trades):{RESET}")
    print(f"  Gross P&L   : ₹{total_gross:+,.0f}")
    print(f"  Total Costs : ₹{total_cost:+,.0f}")
    col = GREEN if total_net > 0 else RED
    print(f"  {BOLD}Net P&L     : {col}₹{total_net:+,.0f}{RESET}")

    print(f"\n  {DIM}Run `python analytics.py expectancy --by regime` for regime breakdown.")
    print(f"  Run `python analytics.py mfe-mae` for trade path quality.")
    print(f"  Run `python analytics.py execution` for execution quality scoring.{RESET}")
    print(f"{'═'*60}\n")


# ─────────────────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Nifty AI System — P1 Analytics Intelligence Layer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--db", default=DB_PATH)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_exp = sub.add_parser("expectancy", help="Rejected vs accepted signal expectancy analysis")
    p_exp.add_argument("--by", choices=["regime", "spread_bucket", "grade", "hour", "all"], default="regime")

    sub.add_parser("mfe-mae", help="MFE/MAE trade path intelligence")
    sub.add_parser("execution", help="Execution quality scoring and bucket analysis")
    sub.add_parser("agents", help="Agent contribution analysis (win vs loss correlation)")
    sub.add_parser("summary", help="Full daily intelligence summary")

    args = parser.parse_args()

    if not Path(args.db).exists():
        print(f"{RED}Database not found: {args.db}{RESET}")
        sys.exit(1)

    conn = _get_conn(args.db)

    if args.cmd == "expectancy":
        analyze_expectancy(conn, by=args.by)
    elif args.cmd == "mfe-mae":
        analyze_mfe_mae(conn)
    elif args.cmd == "execution":
        analyze_execution_quality(conn)
    elif args.cmd == "agents":
        analyze_agent_contribution(conn)
    elif args.cmd == "summary":
        cmd_summary(conn)

    conn.close()


if __name__ == "__main__":
    main()
