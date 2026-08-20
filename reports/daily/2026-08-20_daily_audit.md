> **🟡 DAILY DECISION: VALIDATION DATA INSUFFICIENT**
>
> Historical V2 replay unavailable because immutable raw decision inputs were not retained.

# Daily Trading Session Audit

**Date**: 2026-08-20  
**Campaign**: 2026-08-SHADOW-V2  
**Engine**: v5.0.2-REF  
**Mode**: SIMULATION  
**Git Commit**: e792eeb  
**Market**: NIFTY 50  

---

## 1. Executive Summary

**Overall Status**: 🟡 HALTED (HALTED)

| Metric | Value |
| :--- | ---: |
| Trading Cycles / Evaluated Signals | 52 |
| Filtered Signals (Strategy Rejections) | 52 |
| Strategy-Approved Candidate Signals | 0 |
| Governance Blocked (Circuit Breaker) | 0 (HALTED) |
| Actual OMS Orders Routed | 0 |
| Actual Orders Filled | 0 |
| Counterfactual Replay Expectancy | +0.25R |
| System Posture | 🔴 HALTED |
| Runtime Errors (Fatal) | 0 |
| Runtime Errors (Recoverable) | 0 |
| Data Integrity | 100% |
| Campaign Progress | 2 / 20 sessions |

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
| Evaluated Signals / Cycles | 52 | Total market evaluations |
| BUY_CE Signals Evaluated | 24 | Call candidate evaluations |
| BUY_PE Signals Evaluated | 28 | Put candidate evaluations |
| Total Rejected Signals | 52 | Intercepted by strategy/risk gates |
| Predictive Rejections | 52 | Blocked by regime/structure/confidence gates |
| Capacity Rejections | 0 | Blocked by portfolio/open position heat |
| Strategy-Approved Candidates | 0 | Approved by Decision Pipeline |
| Governance-Blocked Signals | 0 | Prevented by active HALTED circuit breaker |
| Actual OMS Orders Routed | 0 | Submitted to Order Management System |
| Actual Orders Filled | 0 | Confirmed entries (Open + Closed) |
| Active Open Positions | 0 | Currently floating in position manager |
| Closed Outcomes | 0 | Finished trades contributing to realized P&L |

**Predictive Rejection Breakdown**:

| Reason | Count | % of Rejections |
| :--- | ---: | ---: |
| BAD_STRUCTURE_EXPANDING | 10 | 19.2% |
| PEV_TOO_LOW | 9 | 17.3% |
| LOW_CONFIDENCE | 9 | 17.3% |
| REJECTED_REGIME_GRADE_B+_IN_SQUEEZE | 7 | 13.5% |
| REJECTED_SAME_STRUCTURAL_TREND | 6 | 11.5% |
| Execution Blocked: Strike Policy Blocked: Unknown market regime; fail closed | 4 | 7.7% |
| BAD_STRUCTURE_UNDEFINED | 1 | 1.9% |
| REJECTED_LOW_EV_+0.25R | 1 | 1.9% |
| REJECTED_LOW_EV_+0.40R | 1 | 1.9% |
| REJECTED_LOW_EV_+0.36R | 1 | 1.9% |
| CHOP_ZONE_ACTIVE | 1 | 1.9% |
| REJECTED_LOW_EV_+0.32R | 1 | 1.9% |
| REJECTED_LOW_EV_+0.37R | 1 | 1.9% |
| **Total Predictive Rejections** | **52** | **100.0%** |

## 5. Execution Quality

| Metric | Value |
| :--- | ---: |
| Effective Participation | 39.9% |
| Neutral Abstention | 60.1% |
| Average Confidence | 49.2% |
| Average EV | 0.29R |
| Precision | 0.0 |
| Recall | 0.0 |
| Balanced Accuracy | 0.5 |
| F1 Score | 0.0 |
| MCC | 0.0 |

## 6. Counterfactual Replay (Strategy Quality Evaluation)

*Note: Counterfactual replay evaluates hypothetical hold-to-exit performance across sequential 45-minute replay sampling windows.*

| Replay Metric | Value |
| :--- | ---: |
| Replay Sampling Windows | 9 |
| Strategy-Approved Candidates Evaluated | 0 |
| Window True Positives (TP - Profitable Window Approved) | 0 |
| Window True Negatives (TN - Unprofitable Window Avoided) | 5 |
| Window False Positives (FP - Unprofitable Window Approved) | 0 |
| Window False Negatives (FN - Profitable Window Missed) | 4 |
| Counterfactual Win Rate | 44.4% |
| Counterfactual Expectancy | +0.25R |

## 6a. Executed Trades

No executed trades today.

## 7. V2 Validation Campaign Status

| Milestone | Status |
| :--- | :--- |
| Structural Leg Generation | 🟢 FROZEN |
| Simulation Execution Lifecycle | 🟢 VERIFIED |
| Raw Decision Capture | 🟢 IMPLEMENTED |
| Capture Integrity | 🟢 TESTED |
| Historical Replay Dataset | 🟡 ACCUMULATING (2/20 sessions) |
| Economic Scarcity Validation | ⏸️ PAUSED |
| Live Deployment | 🔴 BLOCKED |

**Campaign Status**: 🛑 NOT READY (18 sessions remaining)

## 8. Issues Detected

**Issues:** None operational
**Validation limitation:** Historical V2 replay data unavailable
**Risk:** Economic scarcity validation incomplete

## 9. Validation Manifest Snapshot

```yaml
campaign_id: 2026-08-SHADOW-V2
candidate_engine: v5.0.2-REF
git_commit: e792eeb
overall_status: NOT_READY
```

## 10. Campaign Trend

| Metric | Value |
| :--- | ---: |
| Replay Sessions | 2 / 20 |
| Replay Expectancy (Today) | +0.25R |
| Runtime Errors (Today) | 0 fatal, 0 recoverable |
| Consecutive Healthy Sessions | 2 |

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
**Campaign Progress**: 2 / 20

---
*Report generated automatically at 2026-08-20T15:40:05.678742 by `tools/generate_daily_audit.py`*