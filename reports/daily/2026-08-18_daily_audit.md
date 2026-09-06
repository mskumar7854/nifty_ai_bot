> **🟡 DAILY DECISION: REVIEW REQUIRED**
>
> No trading data recorded. Check bot connectivity and data feed.

# Daily Trading Session Audit

**Date**: 2026-08-18  
**Campaign**: 2026-08-SHADOW-V2  
**Engine**: v5.0.2-REF  
**Mode**: SIMULATION  
**Git Commit**: ebfea5e  
**Market**: NIFTY 50  

---

## 1. Executive Summary

**Overall Status**: ⚠️ NO DATA

| Metric | Value |
| :--- | ---: |
| Trading Cycles / Evaluated Signals | 0 |
| Filtered Signals (Strategy Rejections) | 0 |
| Strategy-Approved Candidate Signals | 0 |
| Governance Blocked (Circuit Breaker) | 0 (HALTED) |
| Actual OMS Orders Routed | 0 |
| Actual Orders Filled | 0 |
| Counterfactual Replay Expectancy | +0.00R |
| System Posture | 🔴 HALTED |
| Runtime Errors (Fatal) | 0 |
| Runtime Errors (Recoverable) | 0 |
| Data Integrity | 0% |
| Campaign Progress | 0 / 20 sessions |

## 2. Market Summary

**Status**: INCOMPLETE_SESSION_DATA

| Metric | Value |
| :--- | ---: |
| Open | --- |
| High | --- |
| Low | --- |
| Close | --- |

## 3. System Health

| Metric | Value |
| :--- | ---: |
| Fatal Errors | 0 |
| Recoverable Errors | 0 |
| Data Completeness | 0% |

## 4. Signal Funnel & Trading Activity

| Lifecycle Stage | Count | Notes |
| :--- | ---: | :--- |
| Evaluated Signals / Cycles | 0 | Total market evaluations |
| BUY_CE Signals Evaluated | 0 | Call candidate evaluations |
| BUY_PE Signals Evaluated | 0 | Put candidate evaluations |
| Total Rejected Signals | 0 | Intercepted by strategy/risk gates |
| Predictive Rejections | 0 | Blocked by regime/structure/confidence gates |
| Capacity Rejections | 0 | Blocked by portfolio/open position heat |
| Strategy-Approved Candidates | 0 | Approved by Decision Pipeline |
| Governance-Blocked Signals | 0 | Prevented by active HALTED circuit breaker |
| Actual OMS Orders Routed | 0 | Submitted to Order Management System |
| Actual Orders Filled | 0 | Confirmed entries (Open + Closed) |
| Active Open Positions | 0 | Currently floating in position manager |
| Closed Outcomes | 0 | Finished trades contributing to realized P&L |

## 5. Execution Quality

| Metric | Value |
| :--- | ---: |
| Effective Participation | 0% |
| Neutral Abstention | 0% |
| Average Confidence | 0% |
| Average EV | 0R |
| Precision | N/A |
| Recall | N/A |
| Balanced Accuracy | N/A |
| F1 Score | N/A |
| MCC | N/A |

## 6. Counterfactual Replay (Strategy Quality Evaluation)

*Note: Counterfactual replay evaluates hypothetical hold-to-exit performance across sequential 45-minute replay sampling windows.*

| Replay Metric | Value |
| :--- | ---: |
| Replay Sampling Windows | 0 |
| Strategy-Approved Candidates Evaluated | 0 |
| True Positives (TP - Profitable Approved) | 0 |
| True Negatives (TN - Avoided Unprofitable) | 0 |
| False Positives (FP - Unprofitable Approved) | 0 |
| False Negatives (FN - Missed Profitable) | 0 |
| Counterfactual Win Rate | 0.0% |
| Counterfactual Expectancy | +0.00R |

## 6a. Executed Trades

No executed trades today.

## 7. V2 Validation Campaign Status

| Milestone | Status |
| :--- | :--- |
| Structural Leg Generation | 🟢 FROZEN |
| Simulation Execution Lifecycle | 🟢 VERIFIED |
| Raw Decision Capture | 🟢 IMPLEMENTED |
| Capture Integrity | 🟢 TESTED |
| Historical Replay Dataset | 🟡 ACCUMULATING (0/20 sessions) |
| Economic Scarcity Validation | ⏸️ PAUSED |
| Live Deployment | 🔴 BLOCKED |

**Campaign Status**: 🛑 NOT READY (20 sessions remaining)

## 8. Issues Detected

No issues detected.

## 9. Validation Manifest Snapshot

```yaml
campaign_id: 2026-08-SHADOW-V2
candidate_engine: v5.0.2-REF
git_commit: ebfea5e
overall_status: NOT_READY
```

## 10. Campaign Trend

| Metric | Value |
| :--- | ---: |
| Replay Sessions | 0 / 20 |
| Replay Expectancy (Today) | +0.00R |
| Runtime Errors (Today) | 0 fatal, 0 recoverable |
| Consecutive Healthy Sessions | 10 |

## 11. Daily Conclusion

**Economic validation of Structural Leg Scarcity is currently unproven because the historical V2 raw decision inputs required for deterministic replay were not retained.**

We have successfully validated:
- ✅ Structural Leg State Machine
- ✅ Simulation Execution Lifecycle
- ❌ Historical Economic Validation (DATA UNAVAILABLE)

Live deployment remains **blocked** under the Stage-Gate Governance Policy until all readiness criteria are satisfied.

## 12. Tomorrow's Checklist

- [ ] Investigate data feed / API connectivity
- [ ] Verify Dhan API token is valid
- [ ] Re-run preflight checks
- [ ] Resume simulation after verification

**No engineering changes scheduled.**  
**Code Freeze**: ACTIVE  
**Campaign Progress**: 0 / 20

---
*Report generated automatically at 2026-08-18T22:23:02.947509 by `tools/generate_daily_audit.py`*