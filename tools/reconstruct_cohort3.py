import os
import re
import json
from datetime import datetime

def reconstruct_cohort3():
    log_file_path = os.path.join("logs", "nifty_ai.log")
    output_json_path = os.path.join("data", "cohort3_reconstructed.json")
    output_md_path = os.path.join("logs", "cohort3_reconstructed_report.md")

    if not os.path.exists(log_file_path):
        print(f"[-] Log file not found at {log_file_path}")
        return

    print(f"[+] Reconstructing Cohort 3 signals from {log_file_path}...")

    # Pattern for CONF GATE logs:
    # 09:42:01 | agent.decision_v3    | INFO     | 🔹 [CONF GATE] Gap-decay relax applied: live_conf=0.470 - 0.014 = 0.456 (elapsed=6min, severity=MAJOR)
    conf_gate_pattern = re.compile(
        r"(\d{2}:\d{2}:\d{2}) \| agent\.decision_v3\s+\| INFO\s+\| 🔹 \[CONF GATE\] Gap-decay relax applied: live_conf=([\d\.]+) - ([\d\.]+) = ([\d\.]+) \(elapsed=(\d+)min, severity=(\w+)\)"
    )

    # Pattern for NO TRADE logs following low confidence:
    # 09:42:01 | agent.decision_v3    | INFO     | 🔹 ⚪ NO TRADE | Low Confidence Gate (0.29 < 0.46, regime: 0.55, gap_elapsed: 6min)
    no_trade_pattern = re.compile(
        r"(\d{2}:\d{2}:\d{2}) \| agent\.decision_v3\s+\| INFO\s+\| 🔹 ⚪ NO TRADE \| Low Confidence Gate \(([\d\.]+) < ([\d\.]+)"
    )

    # Pattern for GRADE/Post-penalty logs (means it passed the confidence gate!):
    # 09:45:01 | agent.decision_v3    | INFO     | [GRADE] Post-penalty score: 0.380 | Grade: B | Unified penalty: 0.824
    grade_pattern = re.compile(
        r"(\d{2}:\d{2}:\d{2}) \| agent\.decision_v3\s+\| INFO\s+\| \[GRADE\] Post-penalty score: ([\d\.]+) \| Grade: (\w+)"
    )

    reconstructed_signals = []
    
    with open(log_file_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    # Track relaxation events
    active_relaxations = {} # time_str -> relax_info
    
    # We will do a multi-pass or stateful scan over log lines
    for i, line in enumerate(lines):
        # 1. Look for relaxation application
        match_relax = conf_gate_pattern.search(line)
        if match_relax:
            time_str, live_conf, decay, adaptive, elapsed, severity = match_relax.groups()
            active_relaxations[time_str] = {
                "time": time_str,
                "live_conf": float(live_conf),
                "decay": float(decay),
                "adaptive_conf": float(adaptive),
                "elapsed_min": int(elapsed),
                "gap_severity": severity,
                "passed_gate": True,  # Default to True, check if overridden by NO TRADE
                "score": None,
                "grade": None,
                "status": "Fired"
            }
            continue

        # 2. Look for NO TRADE due to Low Confidence at same time stamp
        match_no_trade = no_trade_pattern.search(line)
        if match_no_trade:
            time_str, score, threshold = match_no_trade.groups()
            if time_str in active_relaxations:
                active_relaxations[time_str]["passed_gate"] = False
                active_relaxations[time_str]["score"] = float(score)
                active_relaxations[time_str]["status"] = "Suppressed (Low Confidence)"
            continue

        # 3. Look for successful GRADE logs indicating it passed the confidence gate
        match_grade = grade_pattern.search(line)
        if match_grade:
            time_str, score, grade = match_grade.groups()
            if time_str in active_relaxations:
                active_relaxations[time_str]["passed_gate"] = True
                active_relaxations[time_str]["score"] = float(score)
                active_relaxations[time_str]["grade"] = grade
                # Check if it was a true Cohort 3 (score < live_conf but >= adaptive_conf)
                live_c = active_relaxations[time_str]["live_conf"]
                adapt_c = active_relaxations[time_str]["adaptive_conf"]
                sc = float(score)
                if sc >= adapt_c and sc < live_c:
                    active_relaxations[time_str]["status"] = "Fired (Cohort 3 Alpha)"
                else:
                    active_relaxations[time_str]["status"] = "Fired (Static Valid)"

    # Filter out relaxations to list
    reconstructed_signals = list(active_relaxations.values())
    
    # Write to JSON
    os.makedirs(os.path.dirname(output_json_path), exist_ok=True)
    with open(output_json_path, "w", encoding="utf-8") as jf:
        json.dump(reconstructed_signals, jf, indent=2)
    print(f"[+] Saved {len(reconstructed_signals)} reconstructed entries to {output_json_path}")

    # Generate Markdown report
    md_content = []
    md_content.append("# Retroactive Cohort 3 Reconstruction Report")
    md_content.append(f"Generated on: {datetime.now().isoformat()}\n")
    md_content.append("This report lists all signals evaluated under dynamic confidence threshold relaxations parsed from `logs/nifty_ai.log`.\n")
    md_content.append("| Time | Original Threshold | Adjusted Threshold | Decay | Score | Grade | Status |")
    md_content.append("|---|---|---|---|---|---|---|")
    
    cohort3_count = 0
    for sig in reconstructed_signals:
        score_val = f"{sig['score']:.3f}" if sig['score'] is not None else "N/A"
        grade_val = sig['grade'] if sig['grade'] is not None else "N/A"
        status = sig['status']
        if "Cohort 3" in status:
            cohort3_count += 1
            status = f"**{status}**"
        
        md_content.append(
            f"| {sig['time']} | {sig['live_conf']:.3f} | {sig['adaptive_conf']:.3f} | "
            f"{sig['decay']:.3f} | {score_val} | {grade_val} | {status} |"
        )
    
    md_content.append(f"\n**Summary:** Identified {len(reconstructed_signals)} dynamic thresholding events. "
                      f"Of these, **{cohort3_count}** were true Cohort 3 alpha executions (passed due to dynamic relaxation).")

    with open(output_md_path, "w", encoding="utf-8") as mf:
        mf.write("\n".join(md_content))
    print(f"[+] Saved markdown report to {output_md_path}")

if __name__ == "__main__":
    reconstruct_cohort3()
