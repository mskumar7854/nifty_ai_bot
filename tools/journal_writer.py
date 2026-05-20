"""
================================================================================
📓 PHASE 2 OPERATIONAL JOURNAL WRITER
Parses daily logs, execution truth, and trades data to generate a detailed,
structured markdown daily summary appended to logs/operational_journal.md.
Can be run automatically on stop() or executed manually.
================================================================================
"""

import os
import sys
import json
import re
from datetime import datetime, date

def get_today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")

def parse_journal_for_date(date_str: str, base_dir: str = ".") -> str:
    """
    Parses all logs for the specified date and returns a markdown daily entry.
    """
    trades_file = os.path.join(base_dir, "logs", f"trades_{date_str}.json")
    alerts_file = os.path.join(base_dir, "logs", "alerts.log")
    nifty_log_file = os.path.join(base_dir, "logs", "nifty_ai.log")
    
    # ── 1. PARSE TRADES & SIGNALS ──
    signals_count = 0
    signals_by_type = {}
    trades_executed = 0
    rejections_by_reason = {}
    pnl_total = 0.0
    has_trades = False
    
    if os.path.exists(trades_file):
        try:
            with open(trades_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        signals_count += 1
                        sig_type = record.get("signal", "unknown")
                        signals_by_type[sig_type] = signals_by_type.get(sig_type, 0) + 1
                        
                        if record.get("trade_executed") or record.get("filter_passed"):
                            trades_executed += 1
                            pnl_val = record.get("pnl")
                            if pnl_val is not None:
                                pnl_total += float(pnl_val)
                                has_trades = True
                        else:
                            reason = record.get("risk_reason", "unknown")
                            if reason:
                                rejections_by_reason[reason] = rejections_by_reason.get(reason, 0) + 1
                    except Exception as json_err:
                        pass
        except Exception as e:
            print(f"Error reading trades file {trades_file}: {e}")
            
    # ── 2. PARSE LOG FILES FOR HEALTH & METRICS ──
    oi_success = 0
    oi_fail = 0
    critical_gaps = []
    latencies = []
    broker_latencies = []
    decision_latencies = []
    db_latencies = []
    oi_latencies = []
    dashboard_latencies = []
    halts = 0
    anomalies = []
    regimes_detected = {}
    
    # Match logs matching the specific date (formatted as 'YYYY-MM-DD' or in timestamp)
    # The logs format in alerts.log starts with HH:MM:SS, but we can assume today's entries or match stamps
    # To be safe, we read nifty_ai.log and alerts.log and look for date patterns or just process current contents if called daily.
    # In live system, nifty_ai.log / alerts.log gets rolled daily.
    
    def process_log_file(filepath: str):
        nonlocal oi_success, oi_fail, halts
        if not os.path.exists(filepath):
            return
        
        # Regexes for parsing
        gap_re = re.compile(r"CRITICAL GAP DETECTED:\s*([\d\.]+)\s*pts")
        oi_fail_re = re.compile(r"OI Fetch FAILED")
        oi_success_re = re.compile(r"REAL OI Fetched")
        halt_re = re.compile(r"HALT|halted|HALTED|structural halt|auto-halt", re.IGNORECASE)
        orphan_re = re.compile(r"ORPHANED POSITIONS DETECTED|Found.*positions.*on.*broker.*not.*in.*OMS", re.IGNORECASE)
        
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
                
                # Check for critical gaps
                for gap_match in gap_re.finditer(content):
                    critical_gaps.append(float(gap_match.group(1)))
                
                # Check for OI fetches
                oi_success += len(oi_success_re.findall(content))
                oi_fail += len(oi_fail_re.findall(content))
                
                # Check for halts
                for line in content.splitlines():
                    # Limit to today's date if timestamp is present
                    if date_str in line or not re.match(r"^\d{4}-\d{2}-\d{2}", line):
                        if halt_re.search(line) and "log" not in line.lower() and "observer" not in line.lower():
                            halts += 1
                        if orphan_re.search(line):
                            anomaly_desc = "Orphaned positions detected on broker"
                            if anomaly_desc not in anomalies:
                                anomalies.append(anomaly_desc)
                
                # Parse Execution Truth JSON blocks
                # Find all 📊 EXECUTION TRUTH:
                truth_idx = 0
                while True:
                    truth_idx = content.find("📊 EXECUTION TRUTH:", truth_idx)
                    if truth_idx == -1:
                        break
                    
                    # Read the next JSON block by matching curly braces
                    start_json = content.find("{", truth_idx)
                    if start_json != -1:
                        # Find matching closing brace
                        depth = 0
                        end_json = start_json
                        while end_json < len(content):
                            char = content[end_json]
                            if char == "{":
                                depth += 1
                            elif char == "}":
                                depth -= 1
                                if depth == 0:
                                    break
                            end_json += 1
                        
                        if depth == 0 and end_json < len(content):
                            json_str = content[start_json:end_json+1]
                            try:
                                truth = json.loads(json_str)
                                
                                # Regime
                                reg = truth.get("regime")
                                if reg:
                                    regimes_detected[reg] = regimes_detected.get(reg, 0) + 1
                                    
                                # Latencies
                                lat = truth.get("latency", {})
                                if "cycle_ms" in lat:
                                    latencies.append(float(lat["cycle_ms"]))
                                elif "total_ms" in lat:
                                    latencies.append(float(lat["total_ms"]))
                                    
                                if "broker_ms" in lat:
                                    broker_latencies.append(float(lat["broker_ms"]))
                                if "decision_ms" in lat:
                                    decision_latencies.append(float(lat["decision_ms"]))
                                if "db_ms" in lat:
                                    db_latencies.append(float(lat["db_ms"]))
                                if "oi_ms" in lat:
                                    oi_latencies.append(float(lat["oi_ms"]))
                                if "dashboard_ms" in lat:
                                    dashboard_latencies.append(float(lat["dashboard_ms"]))
                                    
                            except Exception:
                                pass
                    truth_idx += 20
        except Exception as e:
            print(f"Error parsing log file {filepath}: {e}")

    # Process logs
    process_log_file(alerts_file)
    process_log_file(nifty_log_file)
    
    # ── 3. SYNTHESIZE VALUES ──
    # Regime
    if regimes_detected:
        dominant_regime = max(regimes_detected, key=regimes_detected.get)
    else:
        dominant_regime = "RANGING"
        
    if critical_gaps:
        max_gap = max(critical_gaps)
        regime_val = f"Gap + Defensive ({max_gap:.1f}pt gap)"
    else:
        regime_val = dominant_regime
        
    # OI Reliability
    total_oi_fetches = oi_success + oi_fail
    if total_oi_fetches == 0:
        oi_reliability = "NO ATTEMPTS"
    elif oi_fail == 0:
        oi_reliability = f"LIVE ({oi_success}/{total_oi_fetches} successful fetches)"
    elif oi_success == 0:
        oi_reliability = f"FAILED (0/{total_oi_fetches} successful fetches)"
    else:
        oi_reliability = f"DEGRADED ({oi_success}/{total_oi_fetches} successful fetches)"
        
    # Latency Profile
    if latencies:
        import numpy as np
        p95 = np.percentile(latencies, 95)
        median_lat = np.percentile(latencies, 50)
        max_lat = max(latencies)
        
        # Build breakdown string
        breakdown_parts = []
        if broker_latencies:
            breakdown_parts.append(f"Broker: {np.mean(broker_latencies):.0f}ms")
        if decision_latencies:
            breakdown_parts.append(f"Decision: {np.mean(decision_latencies):.0f}ms")
        if db_latencies:
            breakdown_parts.append(f"DB: {np.mean(db_latencies):.0f}ms")
        if oi_latencies:
            breakdown_parts.append(f"OI: {np.mean(oi_latencies):.0f}ms")
        if dashboard_latencies:
            breakdown_parts.append(f"Dash: {np.mean(dashboard_latencies):.0f}ms")
            
        breakdown_str = " | ".join(breakdown_parts)
        latency_val = f"p95={p95:.0f}ms | median={median_lat:.0f}ms | max={max_lat:.0f}ms ({breakdown_str})"
    else:
        latency_val = "NO DATA"
        
    # Signals Generated
    if signals_count > 0:
        sig_types_desc = ", ".join(f"{count} {stype}" for stype, count in signals_by_type.items())
        signals_val = f"{signals_count} ({sig_types_desc})"
    else:
        signals_val = "0"
        
    # Signals Rejected
    if rejections_by_reason:
        rej_desc = ", ".join(f"{count}× {reason}" for reason, count in rejections_by_reason.items())
        rejected_val = f"{sum(rejections_by_reason.values())} ({rej_desc})"
    else:
        rejected_val = "0"
        
    # Trades Executed
    trades_val = str(trades_executed)
    if has_trades:
        trades_val += f" (Total PnL: ₹{pnl_total:,.2f})"
        
    # Halts
    halts_val = str(halts)
    
    # Anomalies
    if anomalies:
        anomalies_val = "; ".join(anomalies)
    else:
        anomalies_val = "None"
        
    # Session Quality
    if oi_fail > 0 and oi_success == 0 and total_oi_fetches > 0:
        quality = "CONTAMINATED"
    elif halts > 0 or len(anomalies) > 0 or (latencies and max(latencies) > 2000):
        quality = "DEGRADED"
    else:
        quality = "NOMINAL"
        
    # Lessons
    lessons = []
    if oi_fail > 0:
        lessons.append("OI data fetching reliability is below 100% - check exchange segment segment mappings and retry loop backoff.")
    if latencies and max(latencies) > 1000:
        lessons.append("High cycle latency spikes observed - monitor SocketIO dashboard update throughput and database query locking.")
    if len(anomalies) > 0:
        lessons.append("Orphaned broker positions detected - ensure graceful shutdown and remote Telegram position reconciliation is active.")
    if signals_count > 0 and trades_executed == 0:
        lessons.append("Multiple signals generated but all blocked by trade filters (e.g. PEV threshold or 10-Gate) - strategy gates functioned correctly under defensive regime.")
        
    if not lessons:
        lessons.append("System executed successfully in nominal mode with no operational issues.")
        
    lessons_val = " ".join(lessons)
    
    # ── 4. CONSTRUCT MARKDOWN SUMMARY ──
    markdown = f"""
## {date_str}

| Field | Value |
|-------|-------|
| Regime | {regime_val} |
| OI Reliability | {oi_reliability} |
| Latency Profile | {latency_val} |
| Signals Generated | {signals_val} |
| Signals Rejected | {rejected_val} |
| Trades Executed | {trades_val} |
| Halts | {halts_val} |
| Anomalies | {anomalies_val} |
| Session Quality | {quality} |
| Lessons | {lessons_val} |
"""
    return markdown

def write_today(base_dir: str = ".") -> str:
    """
    Appends today's operational summary to logs/operational_journal.md.
    """
    today_str = get_today_str()
    journal_path = os.path.join(base_dir, "logs", "operational_journal.md")
    
    entry_md = parse_journal_for_date(today_str, base_dir)
    
    # Ensure logs folder exists
    os.makedirs(os.path.join(base_dir, "logs"), exist_ok=True)
    
    # Read existing content
    existing_content = ""
    if os.path.exists(journal_path):
        with open(journal_path, "r", encoding="utf-8") as f:
            existing_content = f.read()
            
    # Check if entry for today already exists to avoid duplicate appends
    header = f"## {today_str}"
    if header in existing_content:
        print(f"Operational journal entry for {today_str} already exists. Skipping append.")
        return journal_path
        
    # Append the new entry
    with open(journal_path, "a", encoding="utf-8") as f:
        if not existing_content:
            f.write("# Nifty AI Trading System - Operational Journal\n")
        f.write(entry_md)
        
    print(f"Successfully appended today's operational journal entry to: {journal_path}")
    return journal_path

if __name__ == "__main__":
    # If a date argument is provided, parse for that date, otherwise parse for today
    target_date = sys.argv[1] if len(sys.argv) > 1 else get_today_str()
    write_today()
