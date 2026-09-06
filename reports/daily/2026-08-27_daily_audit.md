> **🟡 DAILY DECISION: VALIDATION DATA INSUFFICIENT**
>
> Historical V2 replay unavailable because immutable raw decision inputs were not retained.

# Daily Trading Session Audit

**Date**: 2026-08-27  
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
| Trading Cycles / Evaluated Signals | 51 |
| Filtered Signals (Strategy Rejections) | 51 |
| Strategy-Approved Candidate Signals | 0 |
| Governance Blocked (Circuit Breaker) | 0 (HALTED) |
| Actual OMS Orders Routed | 0 |
| Actual Orders Filled | 0 |
| Counterfactual Replay Expectancy | -0.03R |
| System Posture | 🔴 HALTED |
| Runtime Errors (Fatal) | 0 |
| Runtime Errors (Recoverable) | 0 |
| Data Integrity | 100% |
| Campaign Progress | 6 / 20 valid (7 observed, 1 excluded) |

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
| 1. Market Evaluations (Cycles) | 51 | Total market evaluations |
| ├── BUY_CE Candidates | 22 | Call candidate evaluations |
| └── BUY_PE Candidates | 29 | Put candidate evaluations |
| 2. Predictive Candidates (Eligible for gates) | 51 | Shadow-eligible candidates |
| 3. Predictive Rejections | 51 | Intercepted by strategy/risk gates |
| 4. Strategy-Approved | 0 | Approved by predictive gates |
| 5. Governance-Blocked | 0 | Prevented by active HALTED circuit breaker |
| 6. OMS Orders Routed | 0 | Submitted to Order Management System |
| 7. Orders Filled | 0 | Confirmed entries (Open + Closed) |
| ├── Active Open Positions | 0 | Currently floating in position manager |
| └── Closed Outcomes | 0 | Finished trades contributing to realized P&L |

**Predictive Rejection Breakdown**:

| Reason | Count | % of Rejections |
| :--- | ---: | ---: |
| PEV_TOO_LOW | 15 | 29.4% |
| BAD_STRUCTURE_EXPANDING | 9 | 17.6% |
| REJECTED_SAME_STRUCTURAL_TREND | 9 | 17.6% |
| REJECTED_REGIME_GRADE_B+_IN_SQUEEZE | 6 | 11.8% |
| Execution Blocked: Strike Policy Blocked: Unknown market regime; fail closed | 6 | 11.8% |
| REJECTED_LOW_EV_+0.41R | 2 | 3.9% |
| CHOP_ZONE_ACTIVE | 2 | 3.9% |
| REJECTED_LOW_EV_+0.21R | 1 | 2.0% |
| REJECTED_LOW_EV_+0.50R | 1 | 2.0% |
| **Total Predictive Rejections** | **51** | **100.0%** |

## 5. Execution Quality

| Metric | Value |
| :--- | ---: |
| Effective Participation | 41.2% |
| Neutral Abstention | 58.8% |
| Average Confidence | 52.4% |
| Average EV | 0.39R |
| Precision | 0.0 |
| Recall | 0.0 |
| Balanced Accuracy | 0.5 |
| F1 Score | 0.0 |
| MCC | 0.0 |

## 6. Shadow Opportunity Summary (Strategy Quality Evaluation)

*Note: Shadow layer tracks counterfactual hold-to-exit performance using decision-time structural levels.*

Evaluated candidates: 51
Shadow-eligible opportunities: 51
Rejected opportunities: 51

Genuinely bad: 0
Marginal: 45

Rejected opportunities that became profitable: 16
Rejected opportunities that became unprofitable: 35

Positive R available: +31.95R
Positive R captured: +0.00R
Positive expectancy captured: 0.0%

Negative R available: -33.49R
Negative R eliminated: -33.49R
Negative expectancy eliminated: 100.0%

Opportunity cost: +31.95R

### Gate Attribution Analysis

| Gate | Rejected | Profitable | Unprofitable | Missed Profit | Saved Loss | Net Counterfactual R |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| BAD_STRUCTURE_EXPANDING | 9 | 3 | 5 | +5.97R | -4.49R | +1.48R |
| CHOP_ZONE_ACTIVE | 2 | 0 | 2 | +0.00R | -2.00R | -2.00R |
| Execution Blocked: Strike Policy Blocked: Unknown market regime; fail closed | 6 | 1 | 5 | +2.00R | -5.00R | -3.00R |
| PEV_TOO_LOW | 15 | 4 | 11 | +8.01R | -11.00R | -2.99R |
| REJECTED_LOW_EV_+0.21R | 1 | 0 | 1 | +0.00R | -1.00R | -1.00R |
| REJECTED_LOW_EV_+0.41R | 2 | 1 | 1 | +1.98R | -1.00R | +0.98R |
| REJECTED_LOW_EV_+0.50R | 1 | 0 | 1 | +0.00R | -1.00R | -1.00R |
| REJECTED_REGIME_GRADE_B+_IN_SQUEEZE | 6 | 2 | 4 | +3.98R | -4.00R | -0.02R |
| REJECTED_SAME_STRUCTURAL_TREND | 9 | 5 | 4 | +10.01R | -4.00R | +6.01R |

## 6a. Executed Trades

No executed trades today.

## 7. V2 Validation Campaign Status

| Milestone | Status |
| :--- | :--- |
| Structural Leg Generation | 🟢 FROZEN |
| Simulation Execution Lifecycle | 🟢 VERIFIED |
| Raw Decision Capture | 🟢 IMPLEMENTED |
| Capture Integrity | 🟢 TESTED |
| Historical Replay Dataset | 🟡 ACCUMULATING (6/20 sessions) |
| Economic Scarcity Validation | ⏸️ PAUSED |
| Live Deployment | 🔴 BLOCKED |

**Campaign Status**: 🛑 NOT READY (14 sessions remaining)

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
| Replay Sessions | 6 / 20 |
| Replay Expectancy (Today) | -0.03R |
| Runtime Errors (Today) | 0 fatal, 0 recoverable |
| Consecutive Healthy Sessions | 4 |

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
**Campaign Progress**: 6 / 20

---
*Report generated automatically at 2026-08-27T15:40:05.501097 by `tools/generate_daily_audit.py`*