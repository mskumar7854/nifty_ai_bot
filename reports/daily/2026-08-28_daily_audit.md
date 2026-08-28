> **🟡 DAILY DECISION: VALIDATION DATA INSUFFICIENT**
>
> Historical V2 replay unavailable because immutable raw decision inputs were not retained.

# Daily Trading Session Audit

**Date**: 2026-08-28  
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
| Trading Cycles / Evaluated Signals | 44 |
| Filtered Signals (Strategy Rejections) | 44 |
| Strategy-Approved Candidate Signals | 0 |
| Governance Blocked (Circuit Breaker) | 0 (HALTED) |
| Actual OMS Orders Routed | 0 |
| Actual Orders Filled | 0 |
| Counterfactual Replay Expectancy | +0.09R |
| System Posture | 🔴 HALTED |
| Runtime Errors (Fatal) | 0 |
| Runtime Errors (Recoverable) | 0 |
| Data Integrity | 100% |
| Campaign Progress | 7 / 20 valid (8 observed, 1 excluded) |

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
| 1. Market Evaluations (Cycles) | 44 | Total market evaluations |
| ├── BUY_CE Candidates | 19 | Call candidate evaluations |
| └── BUY_PE Candidates | 25 | Put candidate evaluations |
| 2. Predictive Candidates (Eligible for gates) | 44 | Shadow-eligible candidates |
| 3. Predictive Rejections | 44 | Intercepted by strategy/risk gates |
| 4. Strategy-Approved | 0 | Approved by predictive gates |
| 5. Governance-Blocked | 0 | Prevented by active HALTED circuit breaker |
| 6. OMS Orders Routed | 0 | Submitted to Order Management System |
| 7. Orders Filled | 0 | Confirmed entries (Open + Closed) |
| ├── Active Open Positions | 0 | Currently floating in position manager |
| └── Closed Outcomes | 0 | Finished trades contributing to realized P&L |

**Predictive Rejection Breakdown**:

| Reason | Count | % of Rejections |
| :--- | ---: | ---: |
| PEV_TOO_LOW | 12 | 27.3% |
| BAD_STRUCTURE_EXPANDING | 10 | 22.7% |
| CHOP_ZONE_ACTIVE | 6 | 13.6% |
| Execution Blocked: Strike Policy Blocked: Unknown market regime; fail closed | 5 | 11.4% |
| REJECTED_REGIME_GRADE_B+_IN_SQUEEZE | 4 | 9.1% |
| REJECTED_SAME_STRUCTURAL_TREND | 2 | 4.5% |
| LOW_CONFIDENCE | 1 | 2.3% |
| REJECTED_LOW_EV_+0.36R | 1 | 2.3% |
| REJECTED_LOW_EV_+0.20R | 1 | 2.3% |
| REJECTED_LOW_EV_+0.27R | 1 | 2.3% |
| Weekend Buffer: no new trades after 15:10:00 on Friday | 1 | 2.3% |
| **Total Predictive Rejections** | **44** | **100.0%** |

## 5. Execution Quality

| Metric | Value |
| :--- | ---: |
| Effective Participation | 41.3% |
| Neutral Abstention | 58.7% |
| Average Confidence | 47.2% |
| Average EV | 0.26R |
| Precision | 0.0 |
| Recall | 0.0 |
| Balanced Accuracy | 0.5 |
| F1 Score | 0.0 |
| MCC | 0.0 |

## 6. Shadow Opportunity Summary (Strategy Quality Evaluation)

*Note: Shadow layer tracks counterfactual hold-to-exit performance using decision-time structural levels.*

Evaluated candidates: 44
Shadow-eligible opportunities: 44
Rejected opportunities: 44

Genuinely bad: 0
Marginal: 39

Rejected opportunities that became profitable: 16
Rejected opportunities that became unprofitable: 28

Positive R available: +31.04R
Positive R captured: +0.00R
Positive expectancy captured: 0.0%

Negative R available: -27.00R
Negative R eliminated: -27.00R
Negative expectancy eliminated: 100.0%

Opportunity cost: +31.04R

### Gate Attribution Analysis

| Gate | Rejected | Profitable | Unprofitable | Missed Profit | Saved Loss | Net Counterfactual R |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| BAD_STRUCTURE_EXPANDING | 10 | 3 | 7 | +5.06R | -7.00R | -1.94R |
| CHOP_ZONE_ACTIVE | 6 | 3 | 3 | +5.99R | -3.00R | +2.99R |
| Execution Blocked: Strike Policy Blocked: Unknown market regime; fail closed | 5 | 3 | 2 | +6.01R | -2.00R | +4.01R |
| LOW_CONFIDENCE | 1 | 0 | 1 | +0.00R | -1.00R | -1.00R |
| PEV_TOO_LOW | 12 | 5 | 7 | +9.99R | -7.00R | +2.99R |
| REJECTED_LOW_EV_+0.20R | 1 | 1 | 0 | +2.00R | +0.00R | +2.00R |
| REJECTED_LOW_EV_+0.27R | 1 | 0 | 1 | +0.00R | -1.00R | -1.00R |
| REJECTED_LOW_EV_+0.36R | 1 | 0 | 1 | +0.00R | -1.00R | -1.00R |
| REJECTED_REGIME_GRADE_B+_IN_SQUEEZE | 4 | 1 | 3 | +1.99R | -3.00R | -1.01R |
| REJECTED_SAME_STRUCTURAL_TREND | 2 | 0 | 2 | +0.00R | -2.00R | -2.00R |
| Weekend Buffer: no new trades after 15:10:00 on Friday | 1 | 0 | 0 | +0.00R | +0.00R | +0.00R |

## 6a. Executed Trades

No executed trades today.

## 7. V2 Validation Campaign Status

| Milestone | Status |
| :--- | :--- |
| Structural Leg Generation | 🟢 FROZEN |
| Simulation Execution Lifecycle | 🟢 VERIFIED |
| Raw Decision Capture | 🟢 IMPLEMENTED |
| Capture Integrity | 🟢 TESTED |
| Historical Replay Dataset | 🟡 ACCUMULATING (7/20 sessions) |
| Economic Scarcity Validation | ⏸️ PAUSED |
| Live Deployment | 🔴 BLOCKED |

**Campaign Status**: 🛑 NOT READY (13 sessions remaining)

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
| Replay Sessions | 7 / 20 |
| Replay Expectancy (Today) | +0.09R |
| Runtime Errors (Today) | 0 fatal, 0 recoverable |
| Consecutive Healthy Sessions | 5 |

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
**Campaign Progress**: 7 / 20

---
*Report generated automatically at 2026-08-28T15:40:08.548109 by `tools/generate_daily_audit.py`*