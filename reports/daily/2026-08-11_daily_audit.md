> **🟢 DAILY DECISION: NO ACTION REQUIRED**
>
> System healthy. Campaign continues. No engineering changes recommended.

# Daily Trading Session Audit

**Date**: 2026-08-11  
**Campaign**: 2026-08-SHADOW-V1  
**Engine**: v5.0.0-REF  
**Mode**: SIMULATION  
**Git Commit**: 21cbda1  
**Market**: NIFTY 50  

---

## 1. Executive Summary

**Overall Status**: ✅ HEALTHY_NO_TRADE

| Metric | Value |
| :--- | ---: |
| Trading Cycles | 46 |
| Signals Generated | 46 |
| Trades Executed | 0 |
| Runtime Errors (Fatal) | 0 |
| Runtime Errors (Recoverable) | 0 |
| Data Integrity | 100% |
| Campaign Progress | 7 / 20 sessions |

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
| Signals Generated | 46 |
| BUY_CE | 24 |
| BUY_PE | 22 |
| Trades Executed | 0 |
| Rejected | 46 |

**Top Rejection Reasons**:

| Reason | Count |
| :--- | ---: |
| LOW_AGENT_AGREEMENT | 41 |
| LOW_CONFIDENCE | 5 |

## 5. Execution Quality

| Metric | Value |
| :--- | ---: |
| Effective Participation | 40.2% |
| Neutral Abstention | 59.8% |
| Average Confidence | 52.3% |
| Average EV | 0.59R |
| Precision | 0.0 |
| Recall | 0.0 |
| Balanced Accuracy | 0.5 |
| F1 Score | 0.0 |
| MCC | 0.0 |

## 6. Counterfactual Replay (OMS Constrained)

| Metric | Value |
| :--- | ---: |
| Candidate Signals | 2 |
| True Positives (TP) | 0 |
| True Negatives (TN) | 2 |
| False Positives (FP) | 0 |
| False Negatives (FN) | 0 |
| Replay Win Rate | 0.0% |
| Replay Expectancy | -0.27R |

## 7. Readiness Campaign Progress

| Gate | Status |
| :--- | :---: |
| Replay Sessions (7/20) | ❌ |
| Profit Factor > 1.50 | ✅ |
| Expectancy > +0.40R | ❌ |
| Drawdown < 5.0R | ✅ |
| False Positive Rate < 15% | ✅ |
| Calibration Error < 5% | ✅ |
| Unit Tests 100% | ✅ |
| Fatal Runtime Errors = 0 | ✅ |
| Telemetry Integrity 100% | ✅ |

**Campaign Status**: 🛑 NOT READY (13 sessions remaining)

## 8. Issues Detected

No issues detected.

## 9. Validation Manifest Snapshot

```yaml
campaign_id: 2026-08-SHADOW-V1
candidate_engine: v5.0.0-REF
git_commit: 21cbda1
overall_status: NOT_READY
```

## 10. Campaign Trend

| Metric | Value |
| :--- | ---: |
| Replay Sessions | 7 / 20 |
| Replay Expectancy (Today) | -0.27R |
| Runtime Errors (Today) | 0 fatal, 0 recoverable |
| Consecutive Healthy Sessions | 7 |

## 11. Daily Conclusion

Today's simulation completed successfully.
No fatal runtime failure(s) occurred.
No trades were executed. 46 signal(s) were rejected by filters.
Replay validation showed negative expectancy.
The validation campaign now contains **7** of the required **20** sessions.
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
**Campaign Progress**: 7 / 20

---
*Report generated automatically at 2026-08-11T15:40:03.209087 by `tools/generate_daily_audit.py`*