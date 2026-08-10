> **🟢 DAILY DECISION: NO ACTION REQUIRED**
>
> System healthy. Campaign continues. No engineering changes recommended.

# Daily Trading Session Audit

**Date**: 2026-08-07  
**Campaign**: 2026-08-SHADOW-V1  
**Engine**: v5.0.0-REF  
**Mode**: SIMULATION  
**Git Commit**: a05330b  
**Market**: NIFTY 50  

---

## 1. Executive Summary

**Overall Status**: ✅ HEALTHY_NO_TRADE

| Metric | Value |
| :--- | ---: |
| Trading Cycles | 16 |
| Signals Generated | 16 |
| Trades Executed | 0 |
| Runtime Errors (Fatal) | 0 |
| Runtime Errors (Recoverable) | 0 |
| Data Integrity | 100% |
| Campaign Progress | 5 / 20 sessions |

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
| Signals Generated | 16 |
| BUY_CE | 7 |
| BUY_PE | 9 |
| Trades Executed | 0 |
| Rejected | 16 |

**Top Rejection Reasons**:

| Reason | Count |
| :--- | ---: |
| LOW_AGENT_AGREEMENT | 16 |

## 5. Execution Quality

| Metric | Value |
| :--- | ---: |
| Effective Participation | 42.9% |
| Neutral Abstention | 57.1% |
| Average Confidence | 60.2% |
| Average EV | 0.49R |
| Precision | 0.0 |
| Recall | 0.0 |
| Balanced Accuracy | 0.5 |
| F1 Score | 0.0 |
| MCC | 0.0 |

## 6. Counterfactual Replay (OMS Constrained)

| Metric | Value |
| :--- | ---: |
| Candidate Signals | 7 |
| True Positives (TP) | 0 |
| True Negatives (TN) | 3 |
| False Positives (FP) | 0 |
| False Negatives (FN) | 4 |
| Replay Win Rate | 57.1% |
| Replay Expectancy | +0.86R |

## 7. Readiness Campaign Progress

| Gate | Status |
| :--- | :---: |
| Replay Sessions (5/20) | ❌ |
| Profit Factor > 1.50 | ✅ |
| Expectancy > +0.40R | ✅ |
| Drawdown < 5.0R | ✅ |
| False Positive Rate < 15% | ✅ |
| Calibration Error < 5% | ✅ |
| Unit Tests 100% | ✅ |
| Fatal Runtime Errors = 0 | ✅ |
| Telemetry Integrity 100% | ✅ |

**Campaign Status**: 🛑 NOT READY (15 sessions remaining)

## 8. Issues Detected

No issues detected.

## 9. Validation Manifest Snapshot

```yaml
campaign_id: 2026-08-SHADOW-V1
candidate_engine: v5.0.0-REF
git_commit: a05330b
overall_status: NOT_READY
```

## 10. Campaign Trend

| Metric | Value |
| :--- | ---: |
| Replay Sessions | 5 / 20 |
| Replay Expectancy (Today) | +0.86R |
| Runtime Errors (Today) | 0 fatal, 0 recoverable |
| Consecutive Healthy Sessions | 5 |

## 11. Daily Conclusion

Today's simulation completed successfully.
No fatal runtime failure(s) occurred.
No trades were executed. 16 signal(s) were rejected by filters.
Replay validation confirmed positive expectancy.
The validation campaign now contains **5** of the required **20** sessions.
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
**Campaign Progress**: 5 / 20

---
*Report generated automatically at 2026-08-07T17:50:50.018299 by `tools/generate_daily_audit.py`*