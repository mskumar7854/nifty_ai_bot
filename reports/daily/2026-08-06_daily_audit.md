> **🟢 DAILY DECISION: NO ACTION REQUIRED**
>
> System healthy. Campaign continues. No engineering changes recommended.

# Daily Trading Session Audit

**Date**: 2026-08-06  
**Campaign**: 2026-08-SHADOW-V1  
**Engine**: v5.0.0-REF  
**Mode**: SIMULATION  
**Git Commit**: 07c0206  
**Market**: NIFTY 50  

---

## 1. Executive Summary

**Overall Status**: ✅ PASS

| Metric | Value |
| :--- | ---: |
| Trading Cycles | 14 |
| Signals Generated | 14 |
| Trades Executed | 0 |
| Runtime Errors (Fatal) | 0 |
| Runtime Errors (Recoverable) | 0 |
| Data Integrity | 100% |
| Campaign Progress | 4 / 20 sessions |

## 2. Market Summary

| Metric | Value |
| :--- | ---: |
| Open | 24616.7 |
| High | 24674.65 |
| Low | 24616.7 |
| Close | 24660.6 |

## 3. System Health

| Metric | Value |
| :--- | ---: |
| Fatal Errors | 0 |
| Recoverable Errors | 0 |
| Data Completeness | 100% |

## 4. Trading Activity

| Metric | Value |
| :--- | ---: |
| Signals Generated | 14 |
| BUY_CE | 5 |
| BUY_PE | 9 |
| Trades Executed | 0 |
| Rejected | 14 |

**Top Rejection Reasons**:

| Reason | Count |
| :--- | ---: |
| LOW_AGENT_AGREEMENT | 12 |
| LOW_CONFIDENCE | 2 |

## 5. Execution Quality

| Metric | Value |
| :--- | ---: |
| Effective Participation | 42.9% |
| Neutral Abstention | 57.1% |
| Average Confidence | 56.8% |
| Average EV | 0.46R |
| Precision | 0.0 |
| Recall | 0.0 |
| Balanced Accuracy | 0.5 |
| F1 Score | 0.0 |
| MCC | 0.0 |

## 6. Counterfactual Replay (OMS Constrained)

| Metric | Value |
| :--- | ---: |
| Candidate Signals | 6 |
| True Positives (TP) | 0 |
| True Negatives (TN) | 3 |
| False Positives (FP) | 0 |
| False Negatives (FN) | 3 |
| Replay Win Rate | 50.0% |
| Replay Expectancy | +0.82R |

## 7. Readiness Campaign Progress

| Gate | Status |
| :--- | :---: |
| Replay Sessions (4/20) | ❌ |
| Profit Factor > 1.50 | ✅ |
| Expectancy > +0.40R | ✅ |
| Drawdown < 5.0R | ✅ |
| False Positive Rate < 15% | ✅ |
| Calibration Error < 5% | ✅ |
| Unit Tests 100% | ✅ |
| Fatal Runtime Errors = 0 | ✅ |
| Telemetry Integrity 100% | ✅ |

**Campaign Status**: 🛑 NOT READY (16 sessions remaining)

## 8. Issues Detected

No issues detected.

## 9. Validation Manifest Snapshot

```yaml
campaign_id: 2026-08-SHADOW-V1
candidate_engine: v5.0.0-REF
git_commit: 07c0206
overall_status: NOT_READY
```

## 10. Campaign Trend

| Metric | Value |
| :--- | ---: |
| Replay Sessions | 4 / 20 |
| Replay Expectancy (Today) | +0.82R |
| Runtime Errors (Today) | 0 fatal, 0 recoverable |
| Consecutive Healthy Sessions | 4 |

## 11. Daily Conclusion

Today's simulation completed successfully.
No fatal runtime failure(s) occurred.
No trades were executed. 14 signal(s) were rejected by filters.
Replay validation confirmed positive expectancy.
The validation campaign now contains **4** of the required **20** sessions.
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
**Campaign Progress**: 4 / 20

---
*Report generated automatically at 2026-08-06T18:35:45.744032 by `tools/generate_daily_audit.py`*