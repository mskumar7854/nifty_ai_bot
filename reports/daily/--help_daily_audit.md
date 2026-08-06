> **🟡 DAILY DECISION: REVIEW REQUIRED**
>
> No trading data recorded. Check bot connectivity and data feed.

# Daily Trading Session Audit

**Date**: --help  
**Campaign**: 2026-08-SHADOW-V1  
**Engine**: v5.0.0-REF  
**Mode**: SIMULATION  
**Git Commit**: 07c0206  
**Market**: NIFTY 50  

---

## 1. Executive Summary

**Overall Status**: ⚠️ NO DATA

| Metric | Value |
| :--- | ---: |
| Trading Cycles | 0 |
| Signals Generated | 0 |
| Trades Executed | 0 |
| Runtime Errors (Fatal) | 0 |
| Runtime Errors (Recoverable) | 0 |
| Data Integrity | 0% |
| Campaign Progress | 4 / 20 sessions |

## 2. Market Summary

| Metric | Value |
| :--- | ---: |
| Open | 0 |
| High | 0 |
| Low | 0 |
| Close | 0 |

## 3. System Health

| Metric | Value |
| :--- | ---: |
| Fatal Errors | 0 |
| Recoverable Errors | 0 |
| Data Completeness | 0% |

## 4. Trading Activity

| Metric | Value |
| :--- | ---: |
| Signals Generated | 0 |
| BUY_CE | 0 |
| BUY_PE | 0 |
| Trades Executed | 0 |
| Rejected | 0 |

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

## 6. Counterfactual Replay (OMS Constrained)

| Metric | Value |
| :--- | ---: |
| Candidate Signals | 0 |
| True Positives (TP) | 0 |
| True Negatives (TN) | 0 |
| False Positives (FP) | 0 |
| False Negatives (FN) | 0 |
| Replay Win Rate | 0.0% |
| Replay Expectancy | +0.00R |

## 7. Readiness Campaign Progress

| Gate | Status |
| :--- | :---: |
| Replay Sessions (4/20) | ❌ |
| Profit Factor > 1.50 | ✅ |
| Expectancy > +0.40R | ❌ |
| Drawdown < 5.0R | ✅ |
| False Positive Rate < 15% | ✅ |
| Calibration Error < 5% | ✅ |
| Unit Tests 100% | ✅ |
| Fatal Runtime Errors = 0 | ✅ |
| Telemetry Integrity 100% | ❌ |

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
| Replay Expectancy (Today) | +0.00R |
| Runtime Errors (Today) | 0 fatal, 0 recoverable |
| Consecutive Healthy Sessions | 1 |

## 11. Daily Conclusion

Today's simulation completed successfully.
No fatal runtime failure(s) occurred.
No trades were executed. 0 signal(s) were rejected by filters.
Replay validation showed negative expectancy.
The validation campaign now contains **4** of the required **20** sessions.
Live deployment remains **blocked** under the Stage-Gate Governance Policy until all readiness criteria are satisfied.

## 12. Tomorrow's Checklist

- [ ] Investigate data feed / API connectivity
- [ ] Verify Dhan API token is valid
- [ ] Re-run preflight checks
- [ ] Resume simulation after verification

**No engineering changes scheduled.**  
**Code Freeze**: ACTIVE  
**Campaign Progress**: 4 / 20

---
*Report generated automatically at 2026-08-06T18:35:14.801194 by `tools/generate_daily_audit.py`*