> **🟡 DAILY DECISION: REVIEW REQUIRED**
>
> No trading data recorded. Check bot connectivity and data feed.

# Daily Trading Session Audit

**Date**: --help  
**Campaign**: 2026-08-SHADOW-V2  
**Engine**: v5.0.2-REF  
**Mode**: SIMULATION  
**Git Commit**: 7dfee6c  
**Market**: NIFTY 50  

---

## 1. Executive Summary

**Overall Status**: ⚠️ NO DATA (INVALID)

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
| Campaign Progress | 4 / 20 valid (6 observed, 1 excluded) |

## 2. Market Summary

**Status**: INCOMPLETE_SESSION_DATA

| Metric | Value |
| :--- | ---: |
| Open | --- |
| High | --- |
| Low | --- |
| Close | --- |

## 3. System Health

| Operational metric | Today |
| :--- | ---: |
| API rate-limit events | 0 |
| Circuit-breaker trips | 0 |
| Session degradation | NO |
| Fatal application errors | 0 |
| Recoverable application errors | 0 |
| Data integrity | 0% |

## 4. Signal Funnel & Trading Activity

| Lifecycle Stage | Count | Notes |
| :--- | ---: | :--- |
| 1. Evaluated Signals (Cycles) | 0 | Total market evaluations |
| ├── BUY_CE Candidates | 0 | Call candidate evaluations |
| └── BUY_PE Candidates | 0 | Put candidate evaluations |
| 2. Predictive Rejections | 0 | Intercepted by strategy/risk gates |
| 3. Capacity Rejections | 0 | Blocked by portfolio/open position heat |
| 4. Strategy-Approved (Governance Eligible) | 0 | Approved by predictive gates |
| 5. Governance-Blocked Signals | 0 | Prevented by active HALTED circuit breaker |
| 6. Actual OMS Orders Routed | 0 | Submitted to Order Management System |
| 7. Actual Orders Filled | 0 | Confirmed entries (Open + Closed) |
| ├── Active Open Positions | 0 | Currently floating in position manager |
| └── Closed Outcomes | 0 | Finished trades contributing to realized P&L |

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

## 6. Shadow Opportunity Summary (Strategy Quality Evaluation)

*Note: Shadow layer tracks counterfactual hold-to-exit performance using decision-time structural levels.*

No shadow opportunities evaluated.

## 6a. Executed Trades

No executed trades today.

## 7. V2 Validation Campaign Status

| Milestone | Status |
| :--- | :--- |
| Structural Leg Generation | 🟢 FROZEN |
| Simulation Execution Lifecycle | 🟢 VERIFIED |
| Raw Decision Capture | 🟢 IMPLEMENTED |
| Capture Integrity | 🟢 TESTED |
| Historical Replay Dataset | 🟡 ACCUMULATING (4/20 sessions) |
| Economic Scarcity Validation | ⏸️ PAUSED |
| Live Deployment | 🔴 BLOCKED |

**Campaign Status**: 🛑 NOT READY (16 sessions remaining)

## 8. Issues Detected

**Issues:** None operational
**Validation limitation:** Historical V2 replay data unavailable
**Risk:** Economic scarcity validation incomplete

## 9. Validation Manifest Snapshot

```yaml
campaign_id: 2026-08-SHADOW-V2
candidate_engine: v5.0.2-REF
git_commit: 7dfee6c
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

- [ ] Investigate data feed / API connectivity
- [ ] Verify Dhan API token is valid
- [ ] Re-run preflight checks
- [ ] Resume simulation after verification

**No engineering changes scheduled.**  
**Code Freeze**: ACTIVE  
**Campaign Progress**: 4 / 20

---
*Report generated automatically at 2026-08-25T17:17:36.209007 by `tools/generate_daily_audit.py`*