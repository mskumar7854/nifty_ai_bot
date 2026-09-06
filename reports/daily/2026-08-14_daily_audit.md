> **🟢 DAILY DECISION: NO ACTION REQUIRED**
>
> System healthy. Campaign continues. No engineering changes recommended.

# Daily Trading Session Audit

**Date**: 2026-08-14  
**Campaign**: 2026-08-SHADOW-V2  
**Engine**: v5.0.2-REF  
**Mode**: SIMULATION  
**Git Commit**: 65712c2  
**Market**: NIFTY 50  

---

## 1. Executive Summary

**Overall Status**: ✅ HEALTHY

| Metric | Value |
| :--- | ---: |
| Trading Cycles | 42 |
| Signals Generated | 42 |
| Trades Executed | 1 |
| Runtime Errors (Fatal) | 0 |
| Runtime Errors (Recoverable) | 0 |
| Data Integrity | 100% |
| Campaign Progress | 10 / 20 sessions |

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

## 4. Trading Activity

| Metric | Value |
| :--- | ---: |
| Signals Generated | 42 |
| BUY_CE | 14 |
| BUY_PE | 28 |
| Trades Executed | 1 |
| Total Rejected | 41 |
| Predictive Rejections | 37 |
| Capacity Rejections | 4 |

**Top Predictive Rejection Reasons**:

| Reason | Count |
| :--- | ---: |
| BAD_STRUCTURE_EXPANDING | 9 |
| LOW_CONFIDENCE | 8 |
| REJECTED_LOW_EV_+0.43R | 7 |
| PEV_TOO_LOW | 6 |
| REJECTED_REGIME_GRADE_B+_IN_SQUEEZE | 4 |

**Top Capacity Rejection Reasons**:

| Reason | Count |
| :--- | ---: |
| Max Open Positions | 4 |

## 5. Execution Quality

| Metric | Value |
| :--- | ---: |
| Effective Participation | 41.3% |
| Neutral Abstention | 58.7% |
| Average Confidence | 48.7% |
| Average EV | 0.49R |
| Precision | 1.0 |
| Recall | 0.5 |
| Balanced Accuracy | 0.75 |
| F1 Score | 0.667 |
| MCC | 0.655 |

## 6. Counterfactual Replay (OMS Constrained)

| Metric | Value |
| :--- | ---: |
| Candidate Signals | 8 |
| True Positives (TP) | 1 |
| True Negatives (TN) | 6 |
| False Positives (FP) | 0 |
| False Negatives (FN) | 1 |
| Replay Win Rate | 25.0% |
| Replay Expectancy | -0.16R |

## 7. Readiness Campaign Progress

| Gate | Status |
| :--- | :---: |
| Replay Sessions (10/20) | ❌ |
| Profit Factor > 1.50 | ✅ |
| Expectancy > +0.40R | ❌ |
| Drawdown < 5.0R | ✅ |
| False Positive Rate < 15% | ✅ |
| Calibration Error < 5% | ✅ |
| Unit Tests 100% | ✅ |
| Fatal Runtime Errors = 0 | ✅ |
| Telemetry Integrity 100% | ✅ |

**Campaign Status**: 🛑 NOT READY (10 sessions remaining)

## 8. Issues Detected

No issues detected.

## 9. Validation Manifest Snapshot

```yaml
campaign_id: 2026-08-SHADOW-V2
candidate_engine: v5.0.2-REF
git_commit: 65712c2
overall_status: NOT_READY
```

## 10. Campaign Trend

| Metric | Value |
| :--- | ---: |
| Replay Sessions | 10 / 20 |
| Replay Expectancy (Today) | -0.16R |
| Runtime Errors (Today) | 0 fatal, 0 recoverable |
| Consecutive Healthy Sessions | 9 |

## 11. Daily Conclusion

Today's simulation completed successfully.
No fatal runtime failure(s) occurred.
1 trade(s) were executed.
Replay validation showed negative expectancy.
The validation campaign now contains **10** of the required **20** sessions.
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
**Campaign Progress**: 10 / 20

---
*Report generated automatically at 2026-08-14T15:40:02.516294 by `tools/generate_daily_audit.py`*