> **🟡 DAILY DECISION: VALIDATION DATA INSUFFICIENT**
>
> Historical V2 replay unavailable because immutable raw decision inputs were not retained.

# Daily Trading Session Audit

**Date**: 2026-08-24  
**Campaign**: 2026-08-SHADOW-V2  
**Engine**: v5.0.2-REF  
**Mode**: SIMULATION  
**Git Commit**: 7dfee6c  
**Market**: NIFTY 50  

---

## 1. Executive Summary

**Overall Status**: 🟡 HALTED (HALTED)

| Metric | Value |
| :--- | ---: |
| Trading Cycles / Evaluated Signals | 40 |
| Filtered Signals (Strategy Rejections) | 40 |
| Strategy-Approved Candidate Signals | 0 |
| Governance Blocked (Circuit Breaker) | 0 (HALTED) |
| Actual OMS Orders Routed | 0 |
| Actual Orders Filled | 0 |
| Counterfactual Replay Expectancy | +0.41R |
| System Posture | 🔴 HALTED |
| Runtime Errors (Fatal) | 0 |
| Runtime Errors (Recoverable) | 0 |
| Data Integrity | 100% |
| Campaign Progress | 3 / 20 valid (4 observed, 1 excluded) |

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
| Data integrity | 100% |

## 4. Signal Funnel & Trading Activity

| Lifecycle Stage | Count | Notes |
| :--- | ---: | :--- |
| 1. Evaluated Signals (Cycles) | 40 | Total market evaluations |
| ├── BUY_CE Candidates | 16 | Call candidate evaluations |
| └── BUY_PE Candidates | 24 | Put candidate evaluations |
| 2. Predictive Rejections | 40 | Intercepted by strategy/risk gates |
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
| REJECTED_REGIME_GRADE_B+_IN_SQUEEZE | 12 | 30.0% |
| PEV_TOO_LOW | 11 | 27.5% |
| REJECTED_SAME_STRUCTURAL_TREND | 5 | 12.5% |
| BAD_STRUCTURE_EXPANDING | 4 | 10.0% |
| CHOP_ZONE_ACTIVE | 4 | 10.0% |
| Execution Blocked: Strike Policy Blocked: Unknown market regime; fail closed | 2 | 5.0% |
| REJECTED_LOW_EV_+0.18R | 1 | 2.5% |
| REJECTED_LOW_EV_+0.33R | 1 | 2.5% |
| **Total Predictive Rejections** | **40** | **100.0%** |

## 5. Execution Quality

| Metric | Value |
| :--- | ---: |
| Effective Participation | 40.6% |
| Neutral Abstention | 59.4% |
| Average Confidence | 50.3% |
| Average EV | 0.34R |
| Precision | 0.0 |
| Recall | 0.0 |
| Balanced Accuracy | 0.5 |
| F1 Score | 0.0 |
| MCC | 0.0 |

## 6. Shadow Opportunity Summary (Strategy Quality Evaluation)

*Note: Shadow layer tracks counterfactual hold-to-exit performance using decision-time structural levels.*

Evaluated candidates: 40
Shadow-eligible opportunities: 0
Rejected opportunities: 0

Genuinely bad: 0
Marginal: 0

Rejected opportunities that became profitable: 0
Rejected opportunities that became unprofitable: 0

Positive R available: +0.00R
Positive R captured: +0.00R
Positive expectancy captured: N/A - no positive opportunity existed

Negative R available: 0.00R
Negative R eliminated: 0.00R
Negative expectancy eliminated: N/A - no negative opportunity existed

Opportunity cost: +0.00R

## 6a. Executed Trades

No executed trades today.

## 7. V2 Validation Campaign Status

| Milestone | Status |
| :--- | :--- |
| Structural Leg Generation | 🟢 FROZEN |
| Simulation Execution Lifecycle | 🟢 VERIFIED |
| Raw Decision Capture | 🟢 IMPLEMENTED |
| Capture Integrity | 🟢 TESTED |
| Historical Replay Dataset | 🟡 ACCUMULATING (3/20 sessions) |
| Economic Scarcity Validation | ⏸️ PAUSED |
| Live Deployment | 🔴 BLOCKED |

**Campaign Status**: 🛑 NOT READY (17 sessions remaining)

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
| Replay Sessions | 3 / 20 |
| Replay Expectancy (Today) | +0.41R |
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

- [ ] Start bot in SIMULATION mode
- [ ] Verify Dhan API connection
- [ ] Verify data feed is FRESH
- [ ] Run full market session
- [ ] Generate Daily Audit
- [ ] Review 🟢 / 🟡 / 🔴 banner

**No engineering changes scheduled.**  
**Code Freeze**: ACTIVE  
**Campaign Progress**: 3 / 20

---
*Report generated automatically at 2026-08-24T16:43:01.727666 by `tools/generate_daily_audit.py`*