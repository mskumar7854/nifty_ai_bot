> **🟢 DAILY DECISION: NO ACTION REQUIRED**
>
> System healthy. Campaign continues. No engineering changes recommended.

# Daily Trading Session Audit

**Date**: 2026-08-13  
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
| Trading Cycles | 49 |
| Signals Generated | 49 |
| Trades Executed | 4 |
| Runtime Errors (Fatal) | 0 |
| Runtime Errors (Recoverable) | 0 |
| Data Integrity | 100% |
| Campaign Progress | 9 / 20 sessions |

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
| Signals Generated | 49 |
| BUY_CE | 22 |
| BUY_PE | 27 |
| Trades Executed | 4 |
| Total Rejected | 45 |
| Predictive Rejections | 37 |
| Capacity Rejections | 8 |

**Top Predictive Rejection Reasons**:

| Reason | Count |
| :--- | ---: |
| REJECTED_LOW_EV_+0.43R | 12 |
| REJECTED_REGIME_GRADE_B+_IN_SQUEEZE | 10 |
| PEV_TOO_LOW | 7 |
| LOW_CONFIDENCE | 3 |
| CHOP_ZONE_ACTIVE | 3 |

**Top Capacity Rejection Reasons**:

| Reason | Count |
| :--- | ---: |
| Max Open Positions | 8 |

## 5. Execution Quality

| Metric | Value |
| :--- | ---: |
| Effective Participation | 40.5% |
| Neutral Abstention | 59.5% |
| Average Confidence | 52.8% |
| Average EV | 0.51R |
| Precision | 0.5 |
| Recall | 0.333 |
| Balanced Accuracy | 0.621 |
| F1 Score | 0.4 |
| MCC | 0.284 |

## 6. Counterfactual Replay (OMS Constrained)

| Metric | Value |
| :--- | ---: |
| Candidate Signals | 14 |
| True Positives (TP) | 1 |
| True Negatives (TN) | 10 |
| False Positives (FP) | 1 |
| False Negatives (FN) | 2 |
| Replay Win Rate | 21.4% |
| Replay Expectancy | -0.23R |

## 7. Readiness Campaign Progress

| Gate | Status |
| :--- | :---: |
| Replay Sessions (9/20) | ❌ |
| Profit Factor > 1.50 | ✅ |
| Expectancy > +0.40R | ❌ |
| Drawdown < 5.0R | ✅ |
| False Positive Rate < 15% | ✅ |
| Calibration Error < 5% | ✅ |
| Unit Tests 100% | ✅ |
| Fatal Runtime Errors = 0 | ✅ |
| Telemetry Integrity 100% | ✅ |

**Campaign Status**: 🛑 NOT READY (11 sessions remaining)

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
| Replay Sessions | 9 / 20 |
| Replay Expectancy (Today) | -0.23R |
| Runtime Errors (Today) | 0 fatal, 0 recoverable |
| Consecutive Healthy Sessions | 8 |

## 11. Daily Conclusion

Today's simulation completed successfully.
No fatal runtime failure(s) occurred.
4 trade(s) were executed.
Replay validation showed negative expectancy.
The validation campaign now contains **9** of the required **20** sessions.
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
**Campaign Progress**: 9 / 20

---
*Report generated automatically at 2026-08-13T17:59:01.373087 by `tools/generate_daily_audit.py`*