> **🟢 DAILY DECISION: NO ACTION REQUIRED**
>
> System healthy. Campaign continues. No engineering changes recommended.

# Daily Trading Session Audit

**Date**: 2026-08-17  
**Campaign**: 2026-08-SHADOW-V2  
**Engine**: v5.0.2-REF  
**Mode**: SIMULATION  
**Git Commit**: ebfea5e  
**Market**: NIFTY 50  

---

## 1. Executive Summary

**Overall Status**: ✅ HEALTHY

| Metric | Value |
| :--- | ---: |
| Trading Cycles / Evaluated Signals | 339 |
| Filtered Signals (Strategy Rejections) | 331 |
| Strategy-Approved Candidate Signals | 8 |
| Governance Blocked (Circuit Breaker) | 0 (ACTIVE) |
| Actual OMS Orders Routed | 3 |
| Actual Orders Filled | 0 |
| Counterfactual Replay Expectancy | +0.30R |
| System Posture | 🟢 ACTIVE |
| Runtime Errors (Fatal) | 0 |
| Runtime Errors (Recoverable) | 0 |
| Data Integrity | 100% |
| Campaign Progress | 11 / 20 sessions |

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
| Evaluated Signals / Cycles | 339 | Total market evaluations |
| BUY_CE Signals Evaluated | 304 | Call candidate evaluations |
| BUY_PE Signals Evaluated | 35 | Put candidate evaluations |
| Total Rejected Signals | 331 | Intercepted by strategy/risk gates |
| Predictive Rejections | 331 | Blocked by regime/structure/confidence gates |
| Capacity Rejections | 0 | Blocked by portfolio/open position heat |
| Strategy-Approved Candidates | 8 | Approved by Decision Pipeline |
| Governance-Blocked Signals | 0 | Prevented by active ACTIVE circuit breaker |
| Actual OMS Orders Routed | 3 | Submitted to Order Management System |
| Actual Orders Filled | 0 | Confirmed entries (Open + Closed) |
| Active Open Positions | 0 | Currently floating in position manager |
| Closed Outcomes | 0 | Finished trades contributing to realized P&L |

**Predictive Rejection Breakdown**:

| Reason | Count | % of Rejections |
| :--- | ---: | ---: |
| Failed trade filter | 282 | 85.2% |
| REJECTED_REGIME_GRADE_B+_IN_SQUEEZE | 10 | 3.0% |
| REJECTED_SAME_STRUCTURAL_TREND | 9 | 2.7% |
| PEV_TOO_LOW | 7 | 2.1% |
| BAD_STRUCTURE_EXPANDING | 6 | 1.8% |
| LOW_CONFIDENCE | 5 | 1.5% |
| BAD_STRUCTURE_UNDEFINED | 2 | 0.6% |
| REJECTED_LOW_EV_+0.39R | 1 | 0.3% |
| REJECTED_LOW_EV_+0.30R | 1 | 0.3% |
| REJECTED_LOW_EV_+0.22R | 1 | 0.3% |
| CHOP_ZONE_ACTIVE | 1 | 0.3% |
| REJECTED_LOW_EV_+0.38R | 1 | 0.3% |
| REJECTED_LOW_EV_+0.32R | 1 | 0.3% |
| REJECTED_LOW_EV_+0.40R | 1 | 0.3% |
| REJECTED_LOW_EV_+0.31R | 1 | 0.3% |
| REJECTED_LOW_EV_+0.16R | 1 | 0.3% |
| REJECTED_LOW_EV_+0.21R | 1 | 0.3% |
| **Total Predictive Rejections** | **331** | **100.0%** |

## 5. Execution Quality

| Metric | Value |
| :--- | ---: |
| Effective Participation | 90.2% |
| Neutral Abstention | 9.8% |
| Average Confidence | 53.5% |
| Average EV | 1.06R |
| Precision | 0.0 |
| Recall | 0.0 |
| Balanced Accuracy | 0.5 |
| F1 Score | 0.0 |
| MCC | 0.0 |

## 6. Counterfactual Replay (Strategy Quality Evaluation)

*Note: Counterfactual replay evaluates hypothetical hold-to-exit performance across sequential 45-minute replay sampling windows.*

| Replay Metric | Value |
| :--- | ---: |
| Replay Sampling Windows | 132 |
| Strategy-Approved Candidates Evaluated | 8 |
| True Positives (TP - Profitable Approved) | 0 |
| True Negatives (TN - Avoided Unprofitable) | 75 |
| False Positives (FP - Unprofitable Approved) | 0 |
| False Negatives (FN - Missed Profitable) | 57 |
| Counterfactual Win Rate | 43.2% |
| Counterfactual Expectancy | +0.30R |

## 7. Readiness Campaign Progress

| Gate | Status |
| :--- | :---: |
| Replay Sessions (11/20) | ❌ |
| Profit Factor > 1.50 | ✅ |
| Expectancy > +0.40R | ❌ |
| Drawdown < 5.0R | ✅ |
| False Positive Rate < 15% | ✅ |
| Calibration Error < 5% | ✅ |
| Unit Tests 100% | ✅ |
| Fatal Runtime Errors = 0 | ✅ |
| Telemetry Integrity 100% | ✅ |

**Campaign Status**: 🛑 NOT READY (9 sessions remaining)

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
| Replay Sessions | 11 / 20 |
| Replay Expectancy (Today) | +0.30R |
| Runtime Errors (Today) | 0 fatal, 0 recoverable |
| Consecutive Healthy Sessions | 10 |

## 11. Daily Conclusion

Today's simulation completed successfully.
No fatal runtime failure(s) occurred.
No trades were executed. 331 signal(s) were rejected by strategy and risk filters.
Counterfactual replay validation confirmed positive expectancy.
The validation campaign now contains **11** of the required **20** sessions.
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
**Campaign Progress**: 11 / 20

---
*Report generated automatically at 2026-08-17T23:09:24.818448 by `tools/generate_daily_audit.py`*