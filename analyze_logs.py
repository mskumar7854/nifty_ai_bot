import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

"""
============================================
NIFTY AI LOG ANALYZER v2
4-Metric Post-Restart Monitor

Usage:
    python analyze_logs.py              # today only
    python analyze_logs.py --tail 5000  # last N lines
    python analyze_logs.py --all        # full log
    python analyze_logs.py --watch      # live tail (re-runs every 30s)
============================================
"""

import re
import sys
import time
import argparse
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime

LOG_FILE = Path("logs/nifty_ai.log")

# ── Regex Patterns ─────────────────────────────────────────────
PAT_TS          = re.compile(r"\[(\d{2}/\d{2}/\d{2} (\d{2}):\d{2}:\d{2})\]")
PAT_CYCLE       = re.compile(r"Engine v3 Cycle Started")
PAT_LATENCY     = re.compile(r"Cycle Latency: ([\d.]+)ms")
PAT_NOTRADE     = re.compile(r"NO TRADE \| (.+)")
PAT_NO_STREAK   = re.compile(r"NO-TRADE STREAK: (\d+) consecutive")
PAT_APPROVED    = re.compile(r"APPROVED \| Grade: (\S+) \| Score: ([\d.]+)")
PAT_ENTRY_QUAL  = re.compile(
    r"\[ENTRY_QUALITY\] Signal: (\S+) \| Buy: ([\d.]+) \| Sell: ([\d.]+) \| "
    r"Gap: ([\d.]+) \| Dom: ([\d.]+)% \| Regime: ([\d.]+) \| Quality: (\S+)"
)
PAT_PROBABILITY = re.compile(
    r"\[PROBABILITY\] Signal: (\S+) \| Score: ([\d.]+) \| Buy: ([\d.]+) \| Sell: ([\d.]+)"
)
PAT_REGIME_WARN = re.compile(r"Applying scaled penalty \(([\d.]+)x\)")
PAT_REGIME_CONF = re.compile(r"Regime confidence low \(([\d.]+)\)\.")
PAT_CONFLUENCE  = re.compile(r"High Confluence Detected")
PAT_ROUTE       = re.compile(r"V4 Dynamic Route Selected: \[(.+)\]")
PAT_LOW_CONF    = re.compile(r"Low Confidence Gate \(([\d.]+) < ([\d.]+)")
PAT_DOMINANCE   = re.compile(r"Minimum Dominance Rule \(Gap: ([\d.]+)")
PAT_TRADE_EXEC  = re.compile(r"LIVE TRADE EXECUTED|SIM: Entry confirmed")
PAT_WARNING     = re.compile(r" WARNING ")
PAT_ERROR       = re.compile(r" ERROR ")
PAT_CRITICAL    = re.compile(r" CRITICAL |🚨")
PAT_BULLISH     = re.compile(r"📈 BULLISH \| Conf: (\d+)%")
PAT_BEARISH     = re.compile(r"📉 BEARISH \| Conf: (\d+)%")


def parse_args():
    p = argparse.ArgumentParser(description="Nifty AI Log Analyzer v2")
    p.add_argument("--all",   action="store_true", help="Analyze full log")
    p.add_argument("--tail",  type=int, default=0, help="Analyze last N lines")
    p.add_argument("--watch", action="store_true", help="Live re-run every 30s")
    return p.parse_args()


def load_lines(args) -> list:
    if not LOG_FILE.exists():
        print(f"ERROR: Log file not found: {LOG_FILE}")
        sys.exit(1)

    content = LOG_FILE.read_text(encoding="utf-8", errors="replace")
    lines = content.splitlines()

    if args.tail:
        return lines[-args.tail:]
    if args.all:
        return lines

    today = datetime.now().strftime("%y/%m/%d")
    today_lines = [l for l in lines if today in l]
    print(f"[Filtering to today ({today}): {len(today_lines):,} of {len(lines):,} lines]\n")
    return today_lines


def analyze(lines: list) -> None:
    # ── Accumulators ──────────────────────────────────────────
    cycles           = 0
    latencies        = []
    no_trade_reasons = Counter()
    no_trade_streaks = []
    entry_qualities  = []          # list of dicts from ENTRY_QUALITY lines
    approved         = []
    regime_penalties = []
    regime_low_vals  = []
    confluence_hits  = 0
    routes           = Counter()
    low_conf_vals    = []
    dominance_fails  = []
    trades_executed  = 0
    warnings         = 0
    errors           = 0
    criticals        = 0
    hour_cycles      = Counter()
    hour_trades      = Counter()
    current_hour     = None

    for line in lines:
        m = PAT_TS.search(line)
        if m:
            current_hour = m.group(2)

        if PAT_CYCLE.search(line):
            cycles += 1
            if current_hour:
                hour_cycles[current_hour] += 1

        # ── Metric 4: Latency ──
        m = PAT_LATENCY.search(line)
        if m:
            latencies.append(float(m.group(1)))

        # ── No-trade analysis ──
        m = PAT_NOTRADE.search(line)
        if m:
            reason = m.group(1).strip()
            if "Low Confidence" in reason:
                reason = "Low Confidence Gate"
            elif "Minimum Dominance" in reason:
                reason = "Minimum Dominance Rule"
            elif "Phase 1" in reason:
                reason = reason.replace("Phase 1 Halt: ", "P1: ")
            elif "Phase 2" in reason:
                reason = reason.replace("Phase 2 Halt: ", "P2: ")
            elif "Phase 4" in reason:
                reason = reason.replace("Phase 4 Halt: ", "P4: ")
            no_trade_reasons[reason[:65]] += 1

        m = PAT_NO_STREAK.search(line)
        if m:
            no_trade_streaks.append(int(m.group(1)))

        # ── Metric 2: Entry quality ──
        m = PAT_ENTRY_QUAL.search(line)
        if m:
            entry_qualities.append({
                "signal":  m.group(1),
                "buy":     float(m.group(2)),
                "sell":    float(m.group(3)),
                "gap":     float(m.group(4)),
                "dom_pct": float(m.group(5)),
                "regime":  float(m.group(6)),
                "quality": m.group(7),
            })

        m = PAT_APPROVED.search(line)
        if m:
            approved.append({"grade": m.group(1), "score": float(m.group(2))})

        # ── Regime ──
        m = PAT_REGIME_WARN.search(line)
        if m:
            regime_penalties.append(float(m.group(1)))
        m = PAT_REGIME_CONF.search(line)
        if m:
            regime_low_vals.append(float(m.group(1)))

        # ── Confluence & routing ──
        if PAT_CONFLUENCE.search(line):
            confluence_hits += 1
        m = PAT_ROUTE.search(line)
        if m:
            for agent in m.group(1).replace("'", "").replace('"', "").split(", "):
                routes[agent.strip()] += 1

        # ── Threshold tracking ──
        m = PAT_LOW_CONF.search(line)
        if m:
            low_conf_vals.append(float(m.group(1)))
        m = PAT_DOMINANCE.search(line)
        if m:
            dominance_fails.append(float(m.group(1)))

        # ── Trades ──
        if PAT_TRADE_EXEC.search(line):
            trades_executed += 1
            if current_hour:
                hour_trades[current_hour] += 1

        if PAT_WARNING.search(line):
            warnings += 1
        if PAT_ERROR.search(line):
            errors += 1
        if PAT_CRITICAL.search(line):
            criticals += 1

    # ════════════════════════════════════════════════════════════
    # PRINT REPORT
    # ════════════════════════════════════════════════════════════
    W  = 64
    sep = "=" * W
    def hdr(title):
        print(f"\n{'─'*4} {title} {'─'*(W - len(title) - 6)}")

    print(sep)
    print(f"  NIFTY AI SYSTEM  |  LOG MONITOR v2")
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(sep)

    # ── SYSTEM SNAPSHOT ──────────────────────────────────────
    hdr("SYSTEM SNAPSHOT")
    total_notrade = sum(no_trade_reasons.values())
    filter_rate   = (total_notrade / max(cycles, 1)) * 100
    print(f"  Cycles run      : {cycles:,}")
    print(f"  Lines analyzed  : {len(lines):,}")
    print(f"  Filter rate     : {filter_rate:.1f}%  ({total_notrade:,} blocked / {cycles:,} cycles)")
    print(f"  Warnings        : {warnings:,}   Errors: {errors}   Criticals: {criticals}")

    # ── METRIC 1: TRADE COUNT ─────────────────────────────────
    hdr("METRIC 1 | TRADE COUNT")
    trades_per_100 = (trades_executed / max(cycles, 1)) * 100
    if trades_executed == 0:
        verdict_trades = "ZERO TRADES  — system still suppressed or market is genuinely flat"
    elif trades_executed <= 8:
        verdict_trades = "HEALTHY  (2-8 trades = right cadence for intraday)"
    elif trades_executed <= 15:
        verdict_trades = "ELEVATED  — watch for chop entries (check Metric 2)"
    else:
        verdict_trades = "OVERTRADING  — tighten adaptive_gap or confidence floor"

    print(f"  Trades executed : {trades_executed}")
    print(f"  Rate            : {trades_per_100:.2f} per 100 cycles")
    print(f"  Verdict         : {verdict_trades}")

    if no_trade_streaks:
        print(f"\n  Longest no-trade streak seen : {max(no_trade_streaks):,} cycles")

    if hour_cycles:
        print(f"\n  Hourly trade distribution:")
        for h in sorted(set(list(hour_cycles.keys()) + list(hour_trades.keys()))):
            cyc = hour_cycles.get(h, 0)
            trd = hour_trades.get(h, 0)
            bar = "T" * trd
            print(f"    {h}:xx  [{cyc:4d} cycles | {trd} trades]  {bar}")

    # ── METRIC 2: ENTRY QUALITY ───────────────────────────────
    hdr("METRIC 2 | ENTRY QUALITY")
    if not entry_qualities:
        print("  No ENTRY_QUALITY records found.")
        if trades_executed > 0:
            print("  (Trades occurred but quality logging may be from old process)")
    else:
        strong  = [e for e in entry_qualities if e["quality"] == "STRONG"]
        mod     = [e for e in entry_qualities if e["quality"] == "MODERATE"]
        weak    = [e for e in entry_qualities if e["quality"] == "WEAK"]
        avg_dom = sum(e["dom_pct"] for e in entry_qualities) / len(entry_qualities)
        avg_gap = sum(e["gap"] for e in entry_qualities) / len(entry_qualities)
        ce      = [e for e in entry_qualities if e["signal"] == "BUY_CE"]
        pe      = [e for e in entry_qualities if e["signal"] == "BUY_PE"]

        print(f"  Entries analyzed : {len(entry_qualities)}")
        print(f"  STRONG entries   : {len(strong)}  ({len(strong)/len(entry_qualities)*100:.0f}%)")
        print(f"  MODERATE entries : {len(mod)}  ({len(mod)/len(entry_qualities)*100:.0f}%)")
        print(f"  WEAK entries     : {len(weak)}  ({len(weak)/len(entry_qualities)*100:.0f}%)  <-- watch these")
        print(f"  Avg dominance    : {avg_dom:.1f}%  (target: >8%)")
        print(f"  Avg gap          : {avg_gap:.4f}  (gate: 0.04)")
        print(f"  BUY_CE / BUY_PE  : {len(ce)} / {len(pe)}")

        # Warn if too many weak entries
        if len(weak) > len(entry_qualities) * 0.3:
            print(f"\n  WARNING: {len(weak)/len(entry_qualities)*100:.0f}% of entries are WEAK quality.")
            print(f"  Consider raising adaptive_gap from 0.04 -> 0.05 or confidence floor to 0.34.")

        if avg_dom < 8.0:
            print(f"\n  WARNING: Avg dominance {avg_dom:.1f}% < 8% target.")
            print(f"  Signals are barely one-directional — potential chop entries.")

        # Show each entry
        print(f"\n  Entry log:")
        for e in entry_qualities[-20:]:   # show last 20
            flag = " <WEAK>" if e["quality"] == "WEAK" else ""
            print(f"    {e['signal']}  gap={e['gap']:.3f}  dom={e['dom_pct']:.1f}%  "
                  f"regime={e['regime']:.2f}  [{e['quality']}]{flag}")

    # ── METRIC 3: CONFIDENCE DISTRIBUTION ────────────────────
    hdr("METRIC 3 | CONFIDENCE DISTRIBUTION (at gate)")
    if low_conf_vals:
        buckets = {
            "< 0.30 (noise)":     sum(1 for v in low_conf_vals if v < 0.30),
            "0.30-0.32 (floor)":  sum(1 for v in low_conf_vals if 0.30 <= v < 0.32),
            "0.32-0.35 (gate)":   sum(1 for v in low_conf_vals if 0.32 <= v < 0.35),
            "0.35-0.40":          sum(1 for v in low_conf_vals if 0.35 <= v < 0.40),
            "0.40-0.45":          sum(1 for v in low_conf_vals if 0.40 <= v < 0.45),
            "0.45+ (passed)":     sum(1 for v in low_conf_vals if v >= 0.45),
        }
        total_conf = len(low_conf_vals)
        for bucket, count in buckets.items():
            if count:
                bar = "|" * min(int(count / max(total_conf / 30, 1)), 30)
                print(f"  {bucket:<25} {count:5,}  {bar}")

        avg_conf = sum(low_conf_vals) / total_conf
        print(f"\n  Avg blocked conf : {avg_conf:.3f}  (gate: 0.32 in low-regime, 0.45 normal)")
        if avg_conf > 0.30:
            print(f"  Signals are building above noise floor — adaptive gate is working.")
        else:
            print(f"  WARNING: Most signals still below 0.30. Regime penalty may still be too strong.")
    else:
        print("  No confidence gate hits found (all signals either passed or blocked earlier).")

    if dominance_fails:
        avg_fail_gap = sum(dominance_fails) / len(dominance_fails)
        print(f"\n  Minimum Dominance Rule blocked: {len(dominance_fails):,}x  (avg gap: {avg_fail_gap:.4f})")
        if avg_fail_gap > 0.035:
            print(f"  Gaps averaging {avg_fail_gap:.4f} are very close to the 0.04 threshold.")
            print(f"  If trade count is low, consider relaxing to 0.035 cautiously.")

    # ── METRIC 4: LATENCY ────────────────────────────────────
    hdr("METRIC 4 | CYCLE LATENCY")
    if not latencies:
        print("  No slow-cycle latency warnings logged.")
        print("  All cycles are running under 500ms threshold.")
        if trades_executed >= 0 and cycles > 0:
            print("  asyncio.to_thread fix appears to be active.")
    else:
        avg_lat  = sum(latencies) / len(latencies)
        max_lat  = max(latencies)
        p95_lat  = sorted(latencies)[int(len(latencies) * 0.95)]
        over500  = sum(1 for l in latencies if l > 500)
        over1000 = sum(1 for l in latencies if l > 1000)

        print(f"  Slow cycles (>500ms) : {len(latencies):,}")
        print(f"  Average              : {avg_lat:.0f}ms  (target: <250ms)")
        print(f"  95th percentile      : {p95_lat:.0f}ms")
        print(f"  Max                  : {max_lat:.0f}ms")
        print(f"  >500ms count         : {over500:,}")
        print(f"  >1000ms count        : {over1000:,}")

        if avg_lat < 250:
            print(f"\n  LATENCY FIXED. asyncio.to_thread is active and working.")
        elif avg_lat < 450:
            print(f"\n  IMPROVING — but still above target. Check if old process is still running.")
        else:
            print(f"\n  STILL HIGH — bot may be running old process without the fix.")
            print(f"  Action: kill all python processes and restart bot.")

    # ── NO-TRADE BREAKDOWN ────────────────────────────────────
    hdr("NO-TRADE REASON BREAKDOWN")
    if no_trade_reasons:
        total = sum(no_trade_reasons.values())
        for reason, count in no_trade_reasons.most_common(10):
            pct = count / total * 100
            bar = "|" * min(int(pct / 2), 35)
            print(f"  {count:5,}x  {pct:5.1f}%  {bar}  {reason}")
    else:
        print("  No NO TRADE signals found.")

    # ── REGIME SUMMARY ────────────────────────────────────────
    hdr("REGIME SUMMARY")
    if regime_low_vals:
        avg_r = sum(regime_low_vals) / len(regime_low_vals)
        min_r = min(regime_low_vals)
        max_r = max(regime_low_vals)
        print(f"  Low-regime events   : {len(regime_low_vals):,}")
        print(f"  Avg regime conf     : {avg_r:.3f}  (smooth threshold: 0.60)")
        print(f"  Min / Max           : {min_r:.3f} / {max_r:.3f}")
        if regime_penalties:
            avg_pen = sum(regime_penalties) / len(regime_penalties)
            print(f"  Avg penalty applied : {avg_pen:.3f}x  (old system was 0.50x fixed)")
        if avg_r >= 0.58:
            print(f"  REGIME IMPROVING — approaching normal threshold.")
        elif avg_r >= 0.52:
            print(f"  Regime borderline — adaptive thresholds are correctly active.")
        else:
            print(f"  Regime weak (<0.52) — market is genuinely choppy. Fewer trades expected.")
    else:
        print("  No regime warnings logged — regime confidence >= 0.60 all day.")
        print("  All agents running at full weight.")

    # ── V4 ROUTER ─────────────────────────────────────────────
    if routes:
        hdr("V4 DYNAMIC AGENT ROUTING")
        total_r = sum(routes.values())
        for agent, count in routes.most_common():
            pct = count / total_r * 100
            bar = "|" * int(pct / 2)
            print(f"  {agent:<22} {count:4d}x  {pct:5.1f}%  {bar}")

    # ── FINAL VERDICT ─────────────────────────────────────────
    print(f"\n{sep}")
    print("  FINAL VERDICT")
    print(sep)

    issues  = []
    positives = []

    if trades_executed == 0 and cycles > 50:
        issues.append("ZERO TRADES after 50+ cycles — check if bot was restarted with new code")
    elif 1 <= trades_executed <= 8:
        positives.append(f"Trade count healthy: {trades_executed} trades (target: 2-8)")
    elif trades_executed > 15:
        issues.append(f"OVERTRADING: {trades_executed} trades — tighten adaptive_gap or confidence floor")

    if entry_qualities:
        weak_pct = len([e for e in entry_qualities if e["quality"] == "WEAK"]) / len(entry_qualities)
        if weak_pct > 0.30:
            issues.append(f"HIGH WEAK ENTRY RATE: {weak_pct*100:.0f}% — noise trades getting through")
        else:
            positives.append(f"Entry quality: {weak_pct*100:.0f}% weak (target: <30%)")

    if latencies:
        avg_lat = sum(latencies) / len(latencies)
        if avg_lat > 450:
            issues.append(f"LATENCY STILL HIGH: {avg_lat:.0f}ms avg — restart bot with new code")
        elif avg_lat < 250:
            positives.append(f"Latency fixed: {avg_lat:.0f}ms avg (was 600ms)")

    if criticals > 0:
        issues.append(f"{criticals} CRITICAL log entries — investigate immediately")
    if errors > 10:
        issues.append(f"{errors} ERROR entries — system unstable")

    if not issues and not positives:
        print("  Not enough data to verdict — run longer or use --tail 10000")
    else:
        for p in positives:
            print(f"  OK    {p}")
        for i in issues:
            print(f"  WARN  {i}")

    print(sep)
    print(f"  Lines: {len(lines):,}  |  Cycles: {cycles:,}  |  Trades: {trades_executed}")
    print(sep)


def main():
    args = parse_args()

    if args.watch:
        print("WATCH MODE — refreshing every 30s. Ctrl+C to stop.")
        while True:
            lines = load_lines(args)
            analyze(lines)
            print("\n[Next refresh in 30s...]\n")
            time.sleep(30)
    else:
        lines = load_lines(args)
        analyze(lines)


if __name__ == "__main__":
    main()
