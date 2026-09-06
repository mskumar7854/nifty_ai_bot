> **🟡 DAILY DECISION: VALIDATION DATA INSUFFICIENT**
>
> Historical V2 replay unavailable because immutable raw decision inputs were not retained.

# Daily Trading Session Audit

**Date**: 2026-08-19  
**Campaign**: 2026-08-SHADOW-V2  
**Engine**: v5.0.2-REF  
**Mode**: SIMULATION  
**Git Commit**: 84cc0ae  
**Market**: NIFTY 50  

---

## 1. Executive Summary

**Overall Status**: 🟡 HALTED (HALTED)

| Metric | Value |
| :--- | ---: |
| Trading Cycles / Evaluated Signals | 43 |
| Filtered Signals (Strategy Rejections) | 40 |
| Strategy-Approved Candidate Signals | 3 |
| Governance Blocked (Circuit Breaker) | 3 (HALTED) |
| Actual OMS Orders Routed | 0 |
| Actual Orders Filled | 0 |
| Counterfactual Replay Expectancy | -0.05R |
| System Posture | 🔴 HALTED |
| Runtime Errors (Fatal) | 0 |
| Runtime Errors (Recoverable) | 0 |
| Data Integrity | 100% |
| Campaign Progress | 1 / 20 sessions |

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
| Data Completeness | 100% |

## 4. Signal Funnel & Trading Activity

| Lifecycle Stage | Count | Notes |
| :--- | ---: | :--- |
| Evaluated Signals / Cycles | 43 | Total market evaluations |
| BUY_CE Signals Evaluated | 22 | Call candidate evaluations |
| BUY_PE Signals Evaluated | 21 | Put candidate evaluations |
| Total Rejected Signals | 40 | Intercepted by strategy/risk gates |
| Predictive Rejections | 40 | Blocked by regime/structure/confidence gates |
| Capacity Rejections | 0 | Blocked by portfolio/open position heat |
| Strategy-Approved Candidates | 3 | Approved by Decision Pipeline |
| Governance-Blocked Signals | 3 | Prevented by active HALTED circuit breaker |
| Actual OMS Orders Routed | 0 | Submitted to Order Management System |
| Actual Orders Filled | 0 | Confirmed entries (Open + Closed) |
| Active Open Positions | 0 | Currently floating in position manager |
| Closed Outcomes | 0 | Finished trades contributing to realized P&L |

**Predictive Rejection Breakdown**:

| Reason | Count | % of Rejections |
| :--- | ---: | ---: |
| BAD_STRUCTURE_EXPANDING | 13 | 32.5% |
| LOW_CONFIDENCE | 6 | 15.0% |
| PEV_TOO_LOW | 6 | 15.0% |
| REJECTED_SAME_STRUCTURAL_TREND | 4 | 10.0% |
| Execution Blocked: Premium Fetch Failed | 3 | 7.5% |
| REJECTED_REGIME_GRADE_B+_IN_SQUEEZE | 3 | 7.5% |
| CHOP_ZONE_ACTIVE | 2 | 5.0% |
| REJECTED_LOW_EV_+0.49R | 1 | 2.5% |
| REJECTED_LOW_EV_+0.35R | 1 | 2.5% |
| REJECTED_LOW_EV_+0.41R | 1 | 2.5% |
| **Total Predictive Rejections** | **40** | **100.0%** |

## 5. Execution Quality

| Metric | Value |
| :--- | ---: |
| Effective Participation | 42.4% |
| Neutral Abstention | 57.6% |
| Average Confidence | 52.6% |
| Average EV | 0.4R |
| Precision | 1.0 |
| Recall | 0.333 |
| Balanced Accuracy | 0.666 |
| F1 Score | 0.5 |
| MCC | 0.5 |

## 6. Counterfactual Replay (Strategy Quality Evaluation)

*Note: Counterfactual replay evaluates hypothetical hold-to-exit performance across sequential 45-minute replay sampling windows.*

| Replay Metric | Value |
| :--- | ---: |
| Replay Sampling Windows | 9 |
| Strategy-Approved Candidates Evaluated | 3 |
| Window True Positives (TP - Profitable Window Approved) | 1 |
| Window True Negatives (TN - Unprofitable Window Avoided) | 6 |
| Window False Positives (FP - Unprofitable Window Approved) | 0 |
| Window False Negatives (FN - Profitable Window Missed) | 2 |
| Counterfactual Win Rate | 33.3% |
| Counterfactual Expectancy | -0.05R |

## 6a. Executed Trades

No executed trades today.

## 7. V2 Validation Campaign Status

| Milestone | Status |
| :--- | :--- |
| Structural Leg Generation | 🟢 FROZEN |
| Simulation Execution Lifecycle | 🟢 VERIFIED |
| Raw Decision Capture | 🟢 IMPLEMENTED |
| Capture Integrity | 🟢 TESTED |
| Historical Replay Dataset | 🟡 ACCUMULATING (1/20 sessions) |
| Economic Scarcity Validation | ⏸️ PAUSED |
| Live Deployment | 🔴 BLOCKED |

**Campaign Status**: 🛑 NOT READY (19 sessions remaining)

## 8. Issues Detected

No issues detected.

## 9. Validation Manifest Snapshot

```yaml
campaign_id: 2026-08-SHADOW-V2
candidate_engine: v5.0.2-REF
git_commit: 84cc0ae
overall_status: NOT_READY
```

## 10. Campaign Trend

| Metric | Value |
| :--- | ---: |
| Replay Sessions | 1 / 20 |
| Replay Expectancy (Today) | -0.05R |
| Runtime Errors (Today) | 0 fatal, 0 recoverable |
| Consecutive Healthy Sessions | 1 |

## 11. Daily Conclusion

**Economic validation of Structural Leg Scarcity is currently unproven because the historical V2 raw decision inputs required for deterministic replay were not retained.**

The primary objective of the current 20-session campaign is to **build a trustworthy prospective dataset that makes future V2 replay deterministic.**

We have successfully validated:
- ✅ Structural Leg State Machine
- ✅ Simulation Execution Lifecycle
- ✅ Governance / HALT protection
- ✅ Raw decision capture mechanism
- ✅ Capture Integrity
- ❌ Historical Economic Validation (DATA UNAVAILABLE)

Live deployment remains **blocked** under the Stage-Gate Governance Policy until all readiness criteria are satisfied.

## 12. Tomorrow's Checklist

- [ ] Start bot in SIMULATION mode
- [ ] Verify Dhan API connection
- [ ] Verify data feed is FRESH
- [ ] Run full market session
- [ ] Generate Daily Audit
- [ ] Review 🟢 / 🟡 / 🔴 banner

**No engineering changes scheduled.**  
**Code Freeze**: ACTIVE  
**Campaign Progress**: 1 / 20

---
*Report generated automatically at 2026-08-19T18:25:35.797718 by `tools/generate_daily_audit.py`*