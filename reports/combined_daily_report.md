# Consolidated Daily Trading Session & Audit Report

> **🟢 COMBINED STATUS: ALL 6 SESSIONS HEALTHY (NO ACTION REQUIRED)**
>
> System operational across all recorded daily sessions. 0 fatal runtime errors detected. Risk filters performing nominal trade rejection. Readiness campaign continues.

---

## 1. Multi-Session Executive Summary

**Overall Campaign Status**: ✅ HEALTHY_NO_TRADE  
**Sessions Analyzed**: 6 Days (`2026-08-04` to `2026-08-11`)  
**Campaign Progress**: 7 / 20 sessions completed (13 remaining)  
**Target Engine**: v5.0.0-REF  
**Operating Mode**: SIMULATION / SHADOW  

| Metric | Multi-Session Total / Mean |
| :--- | ---: |
| **Total Trading Cycles / Signals** | 300 |
| **BUY_CE Signals Generated** | 72 (24.0%) |
| **BUY_PE Signals Generated** | 228 (76.0%) |
| **Live Trades Executed** | 0 |
| **Signals Rejected by Filters** | 300 (100.0%) |
| **Counterfactual Replay Signals** | 113 |
| **Fatal Runtime Errors** | 0 |
| **Recoverable System Errors** | 0 |
| **Data Completeness & Integrity** | 100% |

---

## 2. Session-by-Session Breakdown Table

| Date | Overall Status | Signals | CE / PE | Exec | Rejected | Top Rejection Reason | Avg Conf | Avg EV | Replay Candidates |
| :--- | :--- | ---: | ---: | ---: | ---: | :--- | ---: | ---: | ---: |
| 2026-08-04 | ✅ PASS | 44 | 15 / 29 | 0 | 44 | LOW_AGENT_AGREEMENT | 38.8% | 0.48R | 14 |
| 2026-08-05 | ✅ PASS | 18 | 11 / 7 | 0 | 18 | LOW_AGENT_AGREEMENT | 55.3% | 0.43R | 11 |
| 2026-08-06 | ✅ PASS | 14 | 5 / 9 | 0 | 14 | LOW_AGENT_AGREEMENT | 56.8% | 0.46R | 6 |
| 2026-08-07 | ✅ HEALTHY_NO_TRADE | 16 | 7 / 9 | 0 | 16 | LOW_AGENT_AGREEMENT | 60.2% | 0.49R | 7 |
| 2026-08-10 | ✅ HEALTHY_NO_TRADE | 162 | 10 / 152 | 0 | 162 | Failed trade filter | 54.2% | 1.1R | 73 |
| 2026-08-11 | ✅ HEALTHY_NO_TRADE | 46 | 24 / 22 | 0 | 46 | LOW_AGENT_AGREEMENT | 52.3% | 0.59R | 2 |

---

## 3. Signal & Risk Rejection Analysis

Total Signals Evaluated: **300**  
Total Signals Filtered/Rejected: **300**  

| Rejection Reason | Count | Percentage |
| :--- | ---: | ---: |
| **LOW_AGENT_AGREEMENT** | 137 | 45.7% |
| **LOW_CONFIDENCE** | 16 | 5.3% |
| **CHOP_ZONE_ACTIVE** | 5 | 1.7% |
| **LOW_CONFLUENCE** | 1 | 0.3% |
| **Failed trade filter** | 141 | 47.0% |

### Key Findings:
1. **Low Agent Agreement (137 signals)**: Multi-agent voting system successfully prevented low-confluence setups across all trading days.
2. **Failed Trade Filter (141 signals)**: Risk engine and chop zone detectors blocked high-risk signals on choppy sessions (e.g. 2026-08-10).
3. **Zero False Positives Allowed into Execution**: Zero unwanted trades executed under tight Stage-Gate governance rules.

---

## 4. Counterfactual Replay & Shadow Validation

- Total Counterfactual Replay Candidates Evaluated: **113**
- Shadow execution engine validated setup profit factor (> 1.50) and positive expectancy (+0.12R to +0.49R across test windows).
- Concurrency rules (`max_active_positions = 1`) strictly enforced across all replays.

---

## 5. System Health & Operational Audit

| Audit Area | Status | Observed Result |
| :--- | :---: | :--- |
| **Fatal Errors** | ✅ PASS | 0 fatal errors logged across all 6 sessions |
| **Recoverable Errors** | ✅ PASS | 0 unhandled exceptions or recoverable crashes |
| **Telemetry & Log Integrity** | ✅ PASS | 100% schema validation pass rate |
| **Database Cryptographic Hash** | ✅ PASS | Replay DB SHA-256 verified |

---

## 6. Stage-Gate Readiness Campaign Progress

| Gate # | Metric | Observed Status | Required Target | Gate Status |
| :---: | :--- | :---: | :---: | :---: |
| 1 | Replay Sessions Count | 7 sessions | ≥ 20 sessions | ❌ In Progress |
| 2 | Profit Factor (PF) | > 1.50 | > 1.50 | ✅ PASS |
| 3 | Realized Expectancy | Positive (+0.12R) | > +0.40R | ❌ In Progress |
| 4 | Max Peak Drawdown | < 5.0R | < 5.0R | ✅ PASS |
| 5 | False Positive Rate | < 15.0% | < 15.0% | ✅ PASS |
| 6 | Calibration Error | < 5.0% | < 5.0% | ✅ PASS |
| 7 | Unit Test Pass Rate | 100.0% | 100.0% | ✅ PASS |
| 8 | Fatal Runtime Errors | 0 | 0 | ✅ PASS |
| 9 | Telemetry Integrity | 100.0% | 100.0% | ✅ PASS |

**Campaign Verdict**: 🛑 **NOT READY FOR LIVE CAPITAL** (13 shadow sessions remaining)

---

## 7. Conclusions & Next Operational Steps

1. **System Stability**: The trading engine operates in a stable, zero-fatal-error state across all daily sessions.
2. **Filter Governance**: 100% of invalid or low-agreement signals were correctly rejected before reaching order routing.
3. **Next Steps**:
   - Continue shadow trading execution for remaining **13** sessions.
   - Maintain active code freeze on production trading rules.
   - Run `python tools/generate_combined_daily_report.py` after each daily session to keep this master report updated.

---
*Report generated automatically at 2026-08-11T15:47:01.324178 by `tools/generate_combined_daily_report.py`*
