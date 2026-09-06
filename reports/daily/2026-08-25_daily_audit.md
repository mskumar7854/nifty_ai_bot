> **🟡 DAILY DECISION: VALIDATION DATA INSUFFICIENT**
>
> Historical V2 replay unavailable because immutable raw decision inputs were not retained.

# Daily Trading Session Audit

**Date**: 2026-08-25  
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
| Trading Cycles / Evaluated Signals | 33 |
| Filtered Signals (Strategy Rejections) | 33 |
| Strategy-Approved Candidate Signals | 0 |
| Governance Blocked (Circuit Breaker) | 0 (HALTED) |
| Actual OMS Orders Routed | 0 |
| Actual Orders Filled | 0 |
| Counterfactual Replay Expectancy | +0.66R |
| System Posture | 🔴 HALTED |
| Runtime Errors (Fatal) | 0 |
| Runtime Errors (Recoverable) | 0 |
| Data Integrity | 100% |
| Campaign Progress | 4 / 20 valid (5 observed, 1 excluded) |

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
| 1. Market Evaluations (Cycles) | 33 | Total market evaluations |
| ├── BUY_CE Candidates | 11 | Call candidate evaluations |
| └── BUY_PE Candidates | 22 | Put candidate evaluations |
| 2. Predictive Candidates (Eligible for gates) | 33 | Shadow-eligible candidates |
| 3. Predictive Rejections | 33 | Intercepted by strategy/risk gates |
| 4. Strategy-Approved | 0 | Approved by predictive gates |
| 5. Governance-Blocked | 0 | Prevented by active HALTED circuit breaker |
| 6. OMS Orders Routed | 0 | Submitted to Order Management System |
| 7. Orders Filled | 0 | Confirmed entries (Open + Closed) |
| ├── Active Open Positions | 0 | Currently floating in position manager |
| └── Closed Outcomes | 0 | Finished trades contributing to realized P&L |

**Predictive Rejection Breakdown**:

| Reason | Count | % of Rejections |
| :--- | ---: | ---: |
| REJECTED_SAME_STRUCTURAL_TREND | 15 | 45.5% |
| REJECTED_REGIME_GRADE_B+_IN_SQUEEZE | 5 | 15.2% |
| Execution Blocked: Strike Policy Blocked: Unknown market regime; fail closed | 4 | 12.1% |
| PEV_TOO_LOW | 3 | 9.1% |
| CHOP_ZONE_ACTIVE | 1 | 3.0% |
| BAD_STRUCTURE_UNDEFINED | 1 | 3.0% |
| REJECTED_REGIME_GRADE_B+_IN_RANGING | 1 | 3.0% |
| REJECTED_LOW_EV_+0.30R | 1 | 3.0% |
| REJECTED_LOW_EV_+0.47R | 1 | 3.0% |
| REJECTED_LOW_EV_+0.32R | 1 | 3.0% |
| **Total Predictive Rejections** | **33** | **100.0%** |

## 5. Execution Quality

| Metric | Value |
| :--- | ---: |
| Effective Participation | 42.4% |
| Neutral Abstention | 57.6% |
| Average Confidence | 65.9% |
| Average EV | 0.72R |
| Precision | 0.0 |
| Recall | 0.0 |
| Balanced Accuracy | 0.5 |
| F1 Score | 0.0 |
| MCC | 0.0 |

## 6. Shadow Opportunity Summary (Strategy Quality Evaluation)

*Note: Shadow layer tracks counterfactual hold-to-exit performance using decision-time structural levels.*

Evaluated candidates: 33
Shadow-eligible opportunities: 33
Rejected opportunities: 33

Genuinely bad: 0
Marginal: 29

Rejected opportunities that became profitable: 19
Rejected opportunities that became unprofitable: 14

Positive R available: +34.80R
Positive R captured: +0.00R
Positive expectancy captured: 0.0%

Negative R available: -13.00R
Negative R eliminated: -13.00R
Negative expectancy eliminated: 100.0%

Opportunity cost: +34.80R

### Gate Attribution Analysis

| Gate | Rejected | Profitable | Unprofitable | Missed Profit | Saved Loss | Net Counterfactual R |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| BAD_STRUCTURE_UNDEFINED | 1 | 0 | 1 | +0.00R | -1.00R | -1.00R |
| CHOP_ZONE_ACTIVE | 1 | 0 | 1 | +0.00R | -1.00R | -1.00R |
| Execution Blocked: Strike Policy Blocked: Unknown market regime; fail closed | 4 | 1 | 3 | +2.01R | -3.00R | -0.99R |
| PEV_TOO_LOW | 3 | 3 | 0 | +5.98R | +0.00R | +5.98R |
| REJECTED_LOW_EV_+0.30R | 1 | 0 | 1 | +0.00R | -1.00R | -1.00R |
| REJECTED_LOW_EV_+0.32R | 1 | 1 | 0 | +1.99R | +0.00R | +1.99R |
| REJECTED_LOW_EV_+0.47R | 1 | 0 | 1 | +0.00R | -1.00R | -1.00R |
| REJECTED_REGIME_GRADE_B+_IN_RANGING | 1 | 0 | 1 | +0.00R | -1.00R | -1.00R |
| REJECTED_REGIME_GRADE_B+_IN_SQUEEZE | 5 | 4 | 1 | +8.01R | -1.00R | +7.01R |
| REJECTED_SAME_STRUCTURAL_TREND | 15 | 10 | 4 | +16.81R | -4.00R | +12.81R |

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
| Replay Expectancy (Today) | +0.66R |
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
**Campaign Progress**: 4 / 20

---
*Report generated automatically at 2026-08-25T18:11:08.710947 by `tools/generate_daily_audit.py`*