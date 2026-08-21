> **🟡 DAILY DECISION: OBSERVED — EXCLUDED FROM ECONOMIC VALIDATION**
>
> System experienced significant API rate limits or circuit breaker trips and ended in HALTED state. Session excluded from strategy-readiness campaign.

# Daily Trading Session Audit

**Date**: 2026-08-21  
**Campaign**: 2026-08-SHADOW-V2  
**Engine**: v5.0.2-REF  
**Mode**: SIMULATION  
**Git Commit**: e3bc73b  
**Market**: NIFTY 50  

---

## 1. Executive Summary

**Overall Status**: 🟡 DEGRADED + HALTED + EXCLUDED

| Metric | Value |
| :--- | ---: |
| Trading Cycles / Evaluated Signals | 49 |
| Filtered Signals (Strategy Rejections) | 49 |
| Strategy-Approved Candidate Signals | 0 |
| Governance Blocked (Circuit Breaker) | 0 (HALTED) |
| Actual OMS Orders Routed | 0 |
| Actual Orders Filled | 0 |
| Counterfactual Replay Expectancy | +0.52R |
| System Posture | 🔴 HALTED |
| Runtime Errors (Fatal) | 0 |
| Runtime Errors (Recoverable) | 0 |
| Data Integrity | 100% |
| Campaign Progress | 2 / 20 valid (3 observed, 1 excluded) |

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
| API rate-limit events | 1 |
| Circuit-breaker trips | 0 |
| Session degradation | YES |
| Fatal application errors | 0 |
| Recoverable application errors | 0 |
| Data integrity | 100% |

## 4. Signal Funnel & Trading Activity

| Lifecycle Stage | Count | Notes |
| :--- | ---: | :--- |
| 1. Evaluated Signals (Cycles) | 49 | Total market evaluations |
| ├── BUY_CE Candidates | 23 | Call candidate evaluations |
| └── BUY_PE Candidates | 26 | Put candidate evaluations |
| 2. Predictive Rejections | 49 | Intercepted by strategy/risk gates |
| 3. Capacity Rejections | 0 | Blocked by portfolio/open position heat |
| 4. Strategy-Approved (Governance Eligible) | 0 | Approved by predictive gates |
| 5. Governance-Blocked Signals | 0 | Prevented by active HALTED circuit breaker |
| 6. Actual OMS Orders Routed | 0 | Submitted to Order Management System |
| 7. Actual Orders Filled | 0 | Confirmed entries (Open + Closed) |
| ├── Active Open Positions | 0 | Currently floating in position manager |
| └── Closed Outcomes | 0 | Finished trades contributing to realized P&L |

**Predictive Rejection Breakdown**:

| Reason | Count | % of Rejections |
| :--- | ---: | ---: |
| PEV_TOO_LOW | 14 | 28.6% |
| REJECTED_REGIME_GRADE_B+_IN_SQUEEZE | 9 | 18.4% |
| LOW_CONFIDENCE | 5 | 10.2% |
| CHOP_ZONE_ACTIVE | 5 | 10.2% |
| BAD_STRUCTURE_EXPANDING | 5 | 10.2% |
| BAD_STRUCTURE_UNDEFINED | 4 | 8.2% |
| Execution Blocked: Strike Policy Blocked: Unknown market regime; fail closed | 2 | 4.1% |
| REJECTED_LOW_EV_+0.42R | 1 | 2.0% |
| REJECTED_LOW_EV_+0.20R | 1 | 2.0% |
| REJECTED_LOW_EV_+0.33R | 1 | 2.0% |
| REJECTED_SAME_STRUCTURAL_TREND | 1 | 2.0% |
| Weekend Buffer: no new trades after 15:10:00 on Friday | 1 | 2.0% |
| **Total Predictive Rejections** | **49** | **100.0%** |

## 5. Execution Quality

| Metric | Value |
| :--- | ---: |
| Effective Participation | 40.6% |
| Neutral Abstention | 59.4% |
| Average Confidence | 45.5% |
| Average EV | 0.22R |
| Precision | 0.0 |
| Recall | 0.0 |
| Balanced Accuracy | 0.5 |
| F1 Score | 0.0 |
| MCC | 0.0 |

## 6. Counterfactual Replay (Strategy Quality Evaluation)

*Note: Counterfactual replay evaluates hypothetical hold-to-exit performance across sequential 45-minute replay sampling windows.*

| Replay Metric | Value |
| :--- | ---: |
| Replay Sampling Windows | 7 |
| Strategy-Approved Candidates Evaluated | 0 |
| Window True Positives (TP - Profitable Window Approved) | 0 |
| Window True Negatives (TN - Unprofitable Window Avoided) | 4 |
| Window False Positives (FP - Unprofitable Window Approved) | 0 |
| Window False Negatives (FN - Profitable Window Missed) | 3 |
| Counterfactual Win Rate | 42.9% |
| Counterfactual Expectancy | +0.52R |

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
git_commit: e3bc73b
overall_status: NOT_READY
```

## 10. Campaign Trend

| Metric | Value |
| :--- | ---: |
| Replay Sessions | 2 / 20 |
| Replay Expectancy (Today) | +0.52R |
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
*Report generated automatically at 2026-08-21T17:11:04.951739 by `tools/generate_daily_audit.py`*