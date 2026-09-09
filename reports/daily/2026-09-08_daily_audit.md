> **🟡 DAILY DECISION: VALIDATION DATA INSUFFICIENT**
>
> Historical V2 replay unavailable because immutable raw decision inputs were not retained.

# Daily Trading Session Audit

**Date**: 2026-09-08  
**Campaign**: 2026-08-SHADOW-V2  
**Engine**: v5.0.2-REF  
**Mode**: SIMULATION  
**Git Commit**: a67b969  
**Market**: NIFTY 50  

---

## 1. Executive Summary

**Overall Status**: 🟡 VALIDATION DATA INSUFFICIENT

| Metric | Value |
| :--- | ---: |
| Market Evaluations (Engine Cycles) | 13,683 |
| Directional Candidates (V2 Snapshots) | 51 |
| Filtered Signals (Strategy Rejections) | 44 |
| Strategy-Approved Candidate Signals | 7 |
| Governance Blocked (Circuit Breaker) | 0 (ACTIVE) |
| Actual OMS Orders Routed | 5 |
| Actual Orders Filled | 5 |
| Execution Authorized Cycles | 7 |
| Counterfactual Replay Expectancy | -0.33R |
| System Posture | 🟢 ACTIVE |
| Runtime Errors (Fatal) | 0 |
| Runtime Errors (Recoverable) | 0 |
| Data Integrity | 100% |
| Campaign Progress | 0 / 20 valid (2 observed, 2 capture-valid, 0 excluded) |

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
| 1. Market Evaluations (Engine Cycles) | 13,683 | Telemetry source of truth: execution_metrics.jsonl |
| ├── BUY_CE Candidates | 21 | Call candidate evaluations |
| └── BUY_PE Candidates | 30 | Put candidate evaluations |
| 2. Predictive Candidates (Eligible for gates) | 51 | Shadow-eligible candidates |
| 3. Predictive Rejections | 44 | Intercepted by strategy/risk gates |
| 4. Strategy-Approved | 7 | Approved by predictive gates |
| 5. Governance-Blocked | 0 | Prevented by active ACTIVE circuit breaker |
| 6. OMS Orders Routed | 5 | Submitted to Order Management System |
| 7. Orders Filled | 5 | Confirmed entries (Open + Closed) |
| ├── Active Open Positions | 0 | Currently floating in position manager |
| └── Closed Outcomes | 0 | Finished trades contributing to realized P&L |

**Engine Evaluation / Safety Gate Breakdown**:

| Safety Gate / Reason | Count (Cycles) | % of Cycles |
| :--- | ---: | ---: |
| Not enough agreeing agents (2) | 4,725 | 34.5% |
| Signal Deduplication: Same direction signal within 300s | 2,667 | 19.5% |
| Not enough agreeing agents (1) | 1,666 | 12.2% |
| Probability Floor: dominant=0.090 < 0.18 (high gap but no edge) | 269 | 2.0% |
| Probability Floor: dominant=0.108 < 0.18 (high gap but no edge) | 157 | 1.1% |
| Probability Floor: dominant=0.118 < 0.18 (high gap but no edge) | 147 | 1.1% |
| Signal Integrity: SELL side collapsed (B=0.168 S=0.012, dominant=0.168 < 0.2, MPM=BALANCED) | 138 | 1.0% |
| Signal Integrity: BUY side collapsed (B=0.012 S=0.168, dominant=0.168 < 0.2, MPM=BALANCED) | 130 | 1.0% |
| Phase 2 Halt: Core Agents Neutral (No Setup) | 129 | 0.9% |
| Probability Floor: dominant=0.070 < 0.18 (high gap but no edge) | 120 | 0.9% |
| Probability Floor: dominant=0.111 < 0.18 (high gap but no edge) | 76 | 0.6% |
| Signal Integrity: SELL side collapsed (B=0.146 S=0.033, dominant=0.146 < 0.2, MPM=BALANCED) | 74 | 0.5% |
| Probability Floor: dominant=0.074 < 0.18 (high gap but no edge) | 71 | 0.5% |
| Signal Integrity: BUY side collapsed (B=0.049 S=0.090, dominant=0.090 < 0.2, MPM=BALANCED) | 68 | 0.5% |
| Probability Floor: dominant=0.129 < 0.18 (high gap but no edge) | 64 | 0.5% |
| Signal Integrity: BUY side collapsed (B=0.049 S=0.118, dominant=0.118 < 0.2, MPM=BALANCED) | 59 | 0.4% |
| Probability Floor: dominant=0.099 < 0.18 (high gap but no edge) | 52 | 0.4% |
| Probability Floor: dominant=0.095 < 0.18 (high gap but no edge) | 51 | 0.4% |
| Probability Floor: dominant=0.142 < 0.18 (high gap but no edge) | 50 | 0.4% |
| Signal Quality too low (C) | 45 | 0.3% |
| Probability Floor: dominant=0.092 < 0.18 (high gap but no edge) | 44 | 0.3% |
| Probability Floor: dominant=0.107 < 0.18 (high gap but no edge) | 44 | 0.3% |
| Probability Floor: dominant=0.078 < 0.18 (high gap but no edge) | 43 | 0.3% |
| Probability Floor: dominant=0.113 < 0.18 (high gap but no edge) | 40 | 0.3% |
| Signal Integrity: SELL side collapsed (B=0.125 S=0.033, dominant=0.125 < 0.2, MPM=BALANCED) | 38 | 0.3% |
| Probability Floor: dominant=0.125 < 0.18 (high gap but no edge) | 37 | 0.3% |
| Probability Floor: dominant=0.088 < 0.18 (high gap but no edge) | 37 | 0.3% |
| Probability Floor: dominant=0.114 < 0.18 (high gap but no edge) | 36 | 0.3% |
| Signal Integrity: SELL side collapsed (B=0.108 S=0.049, dominant=0.108 < 0.2, MPM=BALANCED) | 36 | 0.3% |
| Probability Floor: dominant=0.112 < 0.18 (high gap but no edge) | 35 | 0.3% |
| Probability Floor: dominant=0.152 < 0.18 (high gap but no edge) | 33 | 0.2% |
| Probability Floor: dominant=0.127 < 0.18 (high gap but no edge) | 32 | 0.2% |
| Probability Floor: dominant=0.094 < 0.18 (high gap but no edge) | 32 | 0.2% |
| Probability Floor: dominant=0.160 < 0.18 (high gap but no edge) | 31 | 0.2% |
| Probability Floor: dominant=0.139 < 0.18 (high gap but no edge) | 28 | 0.2% |
| Probability Floor: dominant=0.121 < 0.18 (high gap but no edge) | 27 | 0.2% |
| Signal Integrity: SELL side collapsed (B=0.090 S=0.049, dominant=0.090 < 0.2, MPM=BALANCED) | 27 | 0.2% |
| Probability Floor: dominant=0.119 < 0.18 (high gap but no edge) | 26 | 0.2% |
| Probability Floor: dominant=0.131 < 0.18 (high gap but no edge) | 25 | 0.2% |
| Probability Floor: dominant=0.136 < 0.18 (high gap but no edge) | 24 | 0.2% |
| Probability Floor: dominant=0.140 < 0.18 (high gap but no edge) | 24 | 0.2% |
| Probability Floor: dominant=0.144 < 0.18 (high gap but no edge) | 23 | 0.2% |
| Probability Floor: dominant=0.133 < 0.18 (high gap but no edge) | 23 | 0.2% |
| Probability Floor: dominant=0.124 < 0.18 (high gap but no edge) | 22 | 0.2% |
| Probability Floor: dominant=0.120 < 0.18 (high gap but no edge) | 22 | 0.2% |
| Signal Integrity: BUY side collapsed (B=0.049 S=0.099, dominant=0.099 < 0.2, MPM=BALANCED) | 20 | 0.1% |
| Probability Floor: dominant=0.102 < 0.18 (high gap but no edge) | 20 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.194 S=0.012, dominant=0.194 < 0.2, MPM=BALANCED) | 20 | 0.1% |
| Probability Floor: dominant=0.123 < 0.18 (high gap but no edge) | 19 | 0.1% |
| Probability Floor: dominant=0.153 < 0.18 (high gap but no edge) | 19 | 0.1% |
| Probability Floor: dominant=0.167 < 0.18 (high gap but no edge) | 19 | 0.1% |
| Probability Floor: dominant=0.138 < 0.18 (high gap but no edge) | 19 | 0.1% |
| Probability Floor: dominant=0.157 < 0.18 (high gap but no edge) | 18 | 0.1% |
| Probability Floor: dominant=0.110 < 0.18 (high gap but no edge) | 18 | 0.1% |
| Probability Floor: dominant=0.080 < 0.18 (high gap but no edge) | 18 | 0.1% |
| Probability Floor: dominant=0.163 < 0.18 (high gap but no edge) | 17 | 0.1% |
| Probability Floor: dominant=0.135 < 0.18 (high gap but no edge) | 17 | 0.1% |
| Probability Floor: dominant=0.116 < 0.18 (high gap but no edge) | 17 | 0.1% |
| Max daily trades reached (3/3) | 17 | 0.1% |
| Signal Integrity: BUY side collapsed (B=0.045 S=0.107, dominant=0.107 < 0.2, MPM=BALANCED) | 16 | 0.1% |
| Probability Floor: dominant=0.077 < 0.18 (high gap but no edge) | 16 | 0.1% |
| Probability Floor: dominant=0.083 < 0.18 (high gap but no edge) | 16 | 0.1% |
| Probability Floor: dominant=0.117 < 0.18 (high gap but no edge) | 15 | 0.1% |
| Probability Floor: dominant=0.130 < 0.18 (high gap but no edge) | 14 | 0.1% |
| Probability Floor: dominant=0.148 < 0.18 (high gap but no edge) | 14 | 0.1% |
| Probability Floor: dominant=0.151 < 0.18 (high gap but no edge) | 14 | 0.1% |
| Probability Floor: dominant=0.143 < 0.18 (high gap but no edge) | 14 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.081 S=0.046, dominant=0.081 < 0.2, MPM=BALANCED) | 14 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.074 S=0.049, dominant=0.074 < 0.2, MPM=BALANCED) | 14 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.079 S=0.046, dominant=0.079 < 0.2, MPM=BALANCED) | 12 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.172 S=0.045, dominant=0.172 < 0.2, MPM=BALANCED) | 12 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.175 S=0.045, dominant=0.175 < 0.2, MPM=BALANCED) | 12 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.121 S=0.045, dominant=0.121 < 0.2, MPM=BALANCED) | 12 | 0.1% |
| Probability Floor: dominant=0.105 < 0.18 (high gap but no edge) | 12 | 0.1% |
| Probability Floor: dominant=0.085 < 0.18 (high gap but no edge) | 12 | 0.1% |
| Signal Integrity: BUY side collapsed (B=0.049 S=0.108, dominant=0.108 < 0.2, MPM=BALANCED) | 12 | 0.1% |
| Signal Integrity: BUY side collapsed (B=0.049 S=0.074, dominant=0.074 < 0.2, MPM=BALANCED) | 11 | 0.1% |
| Signal Integrity: BUY side collapsed (B=0.043 S=0.147, dominant=0.147 < 0.2, MPM=BALANCED) | 11 | 0.1% |
| Probability Floor: dominant=0.179 < 0.18 (high gap but no edge) | 11 | 0.1% |
| Probability Floor: dominant=0.155 < 0.18 (high gap but no edge) | 11 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.077 S=0.046, dominant=0.077 < 0.2, MPM=BALANCED) | 11 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.171 S=0.040, dominant=0.171 < 0.2, MPM=BALANCED) | 10 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.190 S=0.040, dominant=0.190 < 0.2, MPM=BALANCED) | 10 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.084 S=0.046, dominant=0.084 < 0.2, MPM=BALANCED) | 10 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.170 S=0.045, dominant=0.170 < 0.2, MPM=BALANCED) | 10 | 0.1% |
| Signal Integrity: BUY side collapsed (B=0.044 S=0.107, dominant=0.107 < 0.2, MPM=BALANCED) | 10 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.078 S=0.046, dominant=0.078 < 0.2, MPM=BALANCED) | 10 | 0.1% |
| Probability Floor: dominant=0.103 < 0.18 (high gap but no edge) | 10 | 0.1% |
| Probability Floor: dominant=0.146 < 0.18 (high gap but no edge) | 10 | 0.1% |
| Probability Floor: dominant=0.173 < 0.18 (high gap but no edge) | 10 | 0.1% |
| Probability Floor: dominant=0.079 < 0.18 (high gap but no edge) | 10 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.099 S=0.049, dominant=0.099 < 0.2, MPM=BALANCED) | 10 | 0.1% |
| Probability Floor: dominant=0.147 < 0.18 (high gap but no edge) | 10 | 0.1% |
| Probability Floor: dominant=0.126 < 0.18 (high gap but no edge) | 10 | 0.1% |
| Signal Integrity: BUY side collapsed (B=0.042 S=0.128, dominant=0.128 < 0.2, MPM=BALANCED) | 10 | 0.1% |
| Probability Floor: dominant=0.081 < 0.18 (high gap but no edge) | 10 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.192 S=0.040, dominant=0.192 < 0.2, MPM=BALANCED) | 9 | 0.1% |
| Probability Floor: dominant=0.158 < 0.18 (high gap but no edge) | 9 | 0.1% |
| Probability Floor: dominant=0.106 < 0.18 (high gap but no edge) | 9 | 0.1% |
| Probability Floor: dominant=0.132 < 0.18 (high gap but no edge) | 9 | 0.1% |
| Probability Floor: dominant=0.156 < 0.18 (high gap but no edge) | 9 | 0.1% |
| Probability Floor: dominant=0.091 < 0.18 (high gap but no edge) | 9 | 0.1% |
| Probability Floor: dominant=0.137 < 0.18 (high gap but no edge) | 9 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.193 S=0.040, dominant=0.193 < 0.2, MPM=BALANCED) | 8 | 0.1% |
| Probability Floor: dominant=0.177 < 0.18 (high gap but no edge) | 8 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.086 S=0.046, dominant=0.086 < 0.2, MPM=BALANCED) | 8 | 0.1% |
| Probability Floor: dominant=0.084 < 0.18 (high gap but no edge) | 8 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.134 S=0.045, dominant=0.134 < 0.2, MPM=BALANCED) | 8 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.165 S=0.040, dominant=0.165 < 0.2, MPM=BALANCED) | 8 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.136 S=0.045, dominant=0.136 < 0.2, MPM=BALANCED) | 8 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.167 S=0.030, dominant=0.167 < 0.2, MPM=BALANCED) | 8 | 0.1% |
| Probability Floor: dominant=0.134 < 0.18 (high gap but no edge) | 8 | 0.1% |
| Signal Integrity: BUY side collapsed (B=0.040 S=0.198, dominant=0.198 < 0.2, MPM=BALANCED) | 8 | 0.1% |
| Signal Integrity: BUY side collapsed (B=0.044 S=0.095, dominant=0.095 < 0.2, MPM=BALANCED) | 8 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.105 S=0.045, dominant=0.105 < 0.2, MPM=BALANCED) | 8 | 0.1% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.107, dominant=0.107 < 0.2, MPM=BALANCED) | 8 | 0.1% |
| Probability Floor: dominant=0.104 < 0.18 (high gap but no edge) | 8 | 0.1% |
| Probability Floor: dominant=0.169 < 0.18 (high gap but no edge) | 8 | 0.1% |
| Probability Floor: dominant=0.087 < 0.18 (high gap but no edge) | 8 | 0.1% |
| Probability Floor: dominant=0.089 < 0.18 (high gap but no edge) | 8 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.080 S=0.046, dominant=0.080 < 0.2, MPM=BALANCED) | 8 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.118 S=0.049, dominant=0.118 < 0.2, MPM=BALANCED) | 8 | 0.1% |
| Signal Integrity: BUY side collapsed (B=0.043 S=0.128, dominant=0.128 < 0.2, MPM=BALANCED) | 8 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.076 S=0.046, dominant=0.076 < 0.2, MPM=BALANCED) | 8 | 0.1% |
| Probability Floor: dominant=0.075 < 0.18 (high gap but no edge) | 8 | 0.1% |
| Probability Floor: dominant=0.154 < 0.18 (high gap but no edge) | 8 | 0.1% |
| Probability Floor: dominant=0.115 < 0.18 (high gap but no edge) | 7 | 0.1% |
| Probability Floor: dominant=0.098 < 0.18 (high gap but no edge) | 7 | 0.1% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.121, dominant=0.121 < 0.2, MPM=BALANCED) | 7 | 0.1% |
| Probability Floor: dominant=0.086 < 0.18 (high gap but no edge) | 7 | 0.1% |
| Probability Floor: dominant=0.176 < 0.18 (high gap but no edge) | 7 | 0.1% |
| Probability Floor: dominant=0.171 < 0.18 (high gap but no edge) | 7 | 0.1% |
| Probability Floor: dominant=0.170 < 0.18 (high gap but no edge) | 7 | 0.1% |
| Probability Floor: dominant=0.141 < 0.18 (high gap but no edge) | 7 | 0.1% |
| Probability Floor: dominant=0.175 < 0.18 (high gap but no edge) | 7 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.169 S=0.040, dominant=0.169 < 0.2, MPM=BALANCED) | 6 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.119 S=0.046, dominant=0.119 < 0.2, MPM=BALANCED) | 6 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.130 S=0.033, dominant=0.130 < 0.2, MPM=BALANCED) | 6 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.135 S=0.045, dominant=0.135 < 0.2, MPM=BALANCED) | 6 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.140 S=0.045, dominant=0.140 < 0.2, MPM=BALANCED) | 6 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.174 S=0.045, dominant=0.174 < 0.2, MPM=BALANCED) | 6 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.168 S=0.040, dominant=0.168 < 0.2, MPM=BALANCED) | 6 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.183 S=0.040, dominant=0.183 < 0.2, MPM=BALANCED) | 6 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.165 S=0.045, dominant=0.165 < 0.2, MPM=BALANCED) | 6 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.164 S=0.045, dominant=0.164 < 0.2, MPM=BALANCED) | 6 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.082 S=0.046, dominant=0.082 < 0.2, MPM=BALANCED) | 6 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.075 S=0.046, dominant=0.075 < 0.2, MPM=BALANCED) | 6 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.103 S=0.040, dominant=0.103 < 0.2, MPM=BALANCED) | 6 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.042 S=0.107, dominant=0.107 < 0.2, MPM=BALANCED) | 6 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.030 S=0.175, dominant=0.175 < 0.2, MPM=BALANCED) | 6 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.045 S=0.128, dominant=0.128 < 0.2, MPM=BALANCED) | 6 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.087 S=0.046, dominant=0.087 < 0.2, MPM=BALANCED) | 6 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.185 S=0.030, dominant=0.185 < 0.2, MPM=BALANCED) | 6 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.048 S=0.185, dominant=0.185 < 0.2, MPM=BALANCED) | 6 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.106 S=0.045, dominant=0.106 < 0.2, MPM=BALANCED) | 6 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.162 S=0.045, dominant=0.162 < 0.2, MPM=BALANCED) | 6 | 0.0% |
| Probability Floor: dominant=0.082 < 0.18 (high gap but no edge) | 6 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.111, dominant=0.111 < 0.2, MPM=BALANCED) | 6 | 0.0% |
| Probability Floor: dominant=0.178 < 0.18 (high gap but no edge) | 6 | 0.0% |
| Probability Floor: dominant=0.168 < 0.18 (high gap but no edge) | 6 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.187, dominant=0.187 < 0.2, MPM=BALANCED) | 6 | 0.0% |
| Probability Floor: dominant=0.149 < 0.18 (high gap but no edge) | 5 | 0.0% |
| Probability Floor: dominant=0.128 < 0.18 (high gap but no edge) | 5 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.139 S=0.045, dominant=0.139 < 0.2, MPM=BALANCED) | 5 | 0.0% |
| Probability Floor: dominant=0.159 < 0.18 (high gap but no edge) | 5 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.104 S=0.040, dominant=0.104 < 0.2, MPM=BALANCED) | 5 | 0.0% |
| Probability Floor: dominant=0.166 < 0.18 (high gap but no edge) | 5 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.030 S=0.168, dominant=0.168 < 0.2, MPM=BALANCED) | 5 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.141 S=0.045, dominant=0.141 < 0.2, MPM=BALANCED) | 5 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.160 S=0.045, dominant=0.160 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.188 S=0.045, dominant=0.188 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Gate Filter: REJECTED_REGIME_GRADE_B+_IN_SQUEEZE | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.198 S=0.041, dominant=0.198 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.198 S=0.034, dominant=0.198 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.155 S=0.045, dominant=0.155 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.198 S=0.045, dominant=0.198 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Probability Floor: dominant=0.097 < 0.18 (high gap but no edge) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.113 S=0.046, dominant=0.113 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.139 S=0.040, dominant=0.139 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.197 S=0.040, dominant=0.197 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.198 S=0.040, dominant=0.198 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.173 S=0.040, dominant=0.173 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.140 S=0.040, dominant=0.140 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Probability Floor: dominant=0.165 < 0.18 (high gap but no edge) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.166 S=0.030, dominant=0.166 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.151 S=0.043, dominant=0.151 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.040 S=0.187, dominant=0.187 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.107 S=0.045, dominant=0.107 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.040 S=0.196, dominant=0.196 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.045 S=0.191, dominant=0.191 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.117, dominant=0.117 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.118, dominant=0.118 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.153 S=0.040, dominant=0.153 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.043 S=0.095, dominant=0.095 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.045 S=0.095, dominant=0.095 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.042 S=0.095, dominant=0.095 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.108 S=0.040, dominant=0.108 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.101 S=0.045, dominant=0.101 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.049 S=0.094, dominant=0.094 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.030 S=0.183, dominant=0.183 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.030 S=0.182, dominant=0.182 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.044 S=0.147, dominant=0.147 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.043 S=0.142, dominant=0.142 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.043 S=0.138, dominant=0.138 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.114 S=0.045, dominant=0.114 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.118 S=0.045, dominant=0.118 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.115 S=0.044, dominant=0.115 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Probability Floor: dominant=0.101 < 0.18 (high gap but no edge) | 4 | 0.0% |
| Probability Floor: dominant=0.093 < 0.18 (high gap but no edge) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.159 S=0.033, dominant=0.159 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.048 S=0.137, dominant=0.137 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.048 S=0.138, dominant=0.138 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.048 S=0.184, dominant=0.184 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.048 S=0.181, dominant=0.181 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.048 S=0.186, dominant=0.186 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.040 S=0.183, dominant=0.183 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.133 S=0.030, dominant=0.133 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.134 S=0.033, dominant=0.134 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.048 S=0.168, dominant=0.168 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.048 S=0.142, dominant=0.142 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.034 S=0.182, dominant=0.182 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.039 S=0.186, dominant=0.186 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.121 S=0.046, dominant=0.121 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Probability Floor: dominant=0.122 < 0.18 (high gap but no edge) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.047 S=0.116, dominant=0.116 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.095, dominant=0.095 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.033 S=0.149, dominant=0.149 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.030 S=0.158, dominant=0.158 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.030 S=0.185, dominant=0.185 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.042 S=0.124, dominant=0.124 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.171 S=0.045, dominant=0.171 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.167 S=0.045, dominant=0.167 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.166 S=0.045, dominant=0.166 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.113, dominant=0.113 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.123, dominant=0.123 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.030 S=0.173, dominant=0.173 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.030 S=0.171, dominant=0.171 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.154 S=0.033, dominant=0.154 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.155 S=0.033, dominant=0.155 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.152 S=0.033, dominant=0.152 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.040 S=0.168, dominant=0.168 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.040 S=0.172, dominant=0.172 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Probability Floor: dominant=0.174 < 0.18 (high gap but no edge) | 4 | 0.0% |
| Probability Floor: dominant=0.164 < 0.18 (high gap but no edge) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.190 S=0.036, dominant=0.190 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.049 S=0.078, dominant=0.078 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.101 S=0.047, dominant=0.101 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.178 S=0.045, dominant=0.178 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.176 S=0.045, dominant=0.176 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.050 S=0.139, dominant=0.139 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.180 S=0.045, dominant=0.180 < 0.2, MPM=BALANCED) | 3 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.177 S=0.045, dominant=0.177 < 0.2, MPM=BALANCED) | 3 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.144 S=0.045, dominant=0.144 < 0.2, MPM=BALANCED) | 3 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.126 S=0.045, dominant=0.126 < 0.2, MPM=BALANCED) | 3 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.040 S=0.199, dominant=0.199 < 0.2, MPM=BALANCED) | 3 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.108 S=0.045, dominant=0.108 < 0.2, MPM=BALANCED) | 3 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.044 S=0.142, dominant=0.142 < 0.2, MPM=BALANCED) | 3 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.088 S=0.046, dominant=0.088 < 0.2, MPM=BALANCED) | 3 | 0.0% |
| Probability Floor: dominant=0.145 < 0.18 (high gap but no edge) | 3 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.199 S=0.030, dominant=0.199 < 0.2, MPM=BALANCED) | 3 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.199 S=0.035, dominant=0.199 < 0.2, MPM=BALANCED) | 3 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.187 S=0.045, dominant=0.187 < 0.2, MPM=BALANCED) | 3 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.030 S=0.199, dominant=0.199 < 0.2, MPM=BALANCED) | 3 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.030 S=0.167, dominant=0.167 < 0.2, MPM=BALANCED) | 3 | 0.0% |
| Probability Floor: dominant=0.162 < 0.18 (high gap but no edge) | 3 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.199 S=0.040, dominant=0.199 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.194 S=0.040, dominant=0.194 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.195 S=0.040, dominant=0.195 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.189 S=0.040, dominant=0.189 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.151 S=0.039, dominant=0.151 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.166 S=0.046, dominant=0.166 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.158 S=0.039, dominant=0.158 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.160 S=0.039, dominant=0.160 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.164 S=0.039, dominant=0.164 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.157 S=0.039, dominant=0.157 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.161 S=0.039, dominant=0.161 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.162 S=0.039, dominant=0.162 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.197 S=0.041, dominant=0.197 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.196 S=0.041, dominant=0.196 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.196 S=0.040, dominant=0.196 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.198 S=0.046, dominant=0.198 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.190 S=0.034, dominant=0.190 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.196 S=0.039, dominant=0.196 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.198 S=0.048, dominant=0.198 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.168 S=0.039, dominant=0.168 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.181 S=0.033, dominant=0.181 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.126 S=0.046, dominant=0.126 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.184 S=0.045, dominant=0.184 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.143 S=0.045, dominant=0.143 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.145 S=0.040, dominant=0.145 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.134 S=0.040, dominant=0.134 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.138 S=0.040, dominant=0.138 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.172 S=0.040, dominant=0.172 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.170 S=0.040, dominant=0.170 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.174 S=0.040, dominant=0.174 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.141 S=0.040, dominant=0.141 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.170 S=0.043, dominant=0.170 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.166 S=0.043, dominant=0.166 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.140 S=0.043, dominant=0.140 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.133 S=0.045, dominant=0.133 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.141 S=0.043, dominant=0.141 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.142 S=0.040, dominant=0.142 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.200 S=0.040, dominant=0.200 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.137 S=0.045, dominant=0.137 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.174 S=0.038, dominant=0.174 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.198 S=0.043, dominant=0.198 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.128 S=0.045, dominant=0.128 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Gate Filter: PEV_TOO_LOW | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.151 S=0.045, dominant=0.151 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.151 S=0.042, dominant=0.151 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.163 S=0.030, dominant=0.163 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.167 S=0.033, dominant=0.167 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.121 S=0.043, dominant=0.121 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.040 S=0.178, dominant=0.178 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.040 S=0.189, dominant=0.189 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.045 S=0.163, dominant=0.163 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.040 S=0.165, dominant=0.165 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.045 S=0.160, dominant=0.160 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.040 S=0.169, dominant=0.169 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.040 S=0.114, dominant=0.114 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.040 S=0.111, dominant=0.111 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.040 S=0.118, dominant=0.118 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.040 S=0.195, dominant=0.195 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.040 S=0.185, dominant=0.185 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.159, dominant=0.159 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.112, dominant=0.112 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.110, dominant=0.110 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.105, dominant=0.105 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.160, dominant=0.160 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.156, dominant=0.156 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.155, dominant=0.155 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.157, dominant=0.157 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.153, dominant=0.153 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.079, dominant=0.079 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.075, dominant=0.075 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.082, dominant=0.082 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.047 S=0.114, dominant=0.114 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.117 S=0.040, dominant=0.117 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.107 S=0.040, dominant=0.107 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.043 S=0.106, dominant=0.106 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.188 S=0.040, dominant=0.188 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.186 S=0.040, dominant=0.186 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.102 S=0.040, dominant=0.102 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.041 S=0.193, dominant=0.193 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.036 S=0.168, dominant=0.168 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.030 S=0.148, dominant=0.148 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.030 S=0.184, dominant=0.184 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.043 S=0.163, dominant=0.163 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.042 S=0.142, dominant=0.142 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.045 S=0.138, dominant=0.138 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.043 S=0.159, dominant=0.159 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.150 S=0.044, dominant=0.150 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.147 S=0.044, dominant=0.147 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.099 S=0.044, dominant=0.099 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Probability Floor: dominant=0.109 < 0.18 (high gap but no edge) | 2 | 0.0% |
| Probability Floor: dominant=0.076 < 0.18 (high gap but no edge) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.085 S=0.046, dominant=0.085 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Probability Floor: dominant=0.096 < 0.18 (high gap but no edge) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.175 S=0.030, dominant=0.175 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.048 S=0.131, dominant=0.131 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.048 S=0.140, dominant=0.140 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.048 S=0.148, dominant=0.148 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.048 S=0.153, dominant=0.153 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.132 S=0.033, dominant=0.132 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.136 S=0.030, dominant=0.136 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.140 S=0.030, dominant=0.140 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.135 S=0.038, dominant=0.135 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.040 S=0.173, dominant=0.173 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.048 S=0.190, dominant=0.190 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.048 S=0.161, dominant=0.161 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.048 S=0.160, dominant=0.160 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.048 S=0.165, dominant=0.165 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.048 S=0.136, dominant=0.136 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.048 S=0.141, dominant=0.141 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.048 S=0.139, dominant=0.139 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.048 S=0.170, dominant=0.170 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.048 S=0.173, dominant=0.173 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.048 S=0.199, dominant=0.199 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.048 S=0.175, dominant=0.175 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.048 S=0.172, dominant=0.172 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.048 S=0.152, dominant=0.152 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Probability Floor: dominant=0.150 < 0.18 (high gap but no edge) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.048 S=0.187, dominant=0.187 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.048 S=0.196, dominant=0.196 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.048 S=0.200, dominant=0.200 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.030 S=0.193, dominant=0.193 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.040 S=0.149, dominant=0.149 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.034 S=0.193, dominant=0.193 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.034 S=0.185, dominant=0.185 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.039 S=0.187, dominant=0.187 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.039 S=0.194, dominant=0.194 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.111 S=0.044, dominant=0.111 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.134 S=0.046, dominant=0.134 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.123 S=0.044, dominant=0.123 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.123 S=0.043, dominant=0.123 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.123 S=0.045, dominant=0.123 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.148 S=0.030, dominant=0.148 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.198 S=0.030, dominant=0.198 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.197 S=0.030, dominant=0.197 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.196 S=0.034, dominant=0.196 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.193 S=0.034, dominant=0.193 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.187 S=0.034, dominant=0.187 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.200 S=0.034, dominant=0.200 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.191 S=0.034, dominant=0.191 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.121 S=0.044, dominant=0.121 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.106 S=0.040, dominant=0.106 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.111 S=0.045, dominant=0.111 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.030 S=0.151, dominant=0.151 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.030 S=0.154, dominant=0.154 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.030 S=0.153, dominant=0.153 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.030 S=0.181, dominant=0.181 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.044 S=0.124, dominant=0.124 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.043 S=0.124, dominant=0.124 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.041 S=0.191, dominant=0.191 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.110 S=0.045, dominant=0.110 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.109 S=0.045, dominant=0.109 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.104 S=0.045, dominant=0.104 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.036 S=0.175, dominant=0.175 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.035 S=0.156, dominant=0.156 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.034 S=0.152, dominant=0.152 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.179 S=0.045, dominant=0.179 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.183 S=0.045, dominant=0.183 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.199 S=0.045, dominant=0.199 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.196 S=0.045, dominant=0.196 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.195 S=0.045, dominant=0.195 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.074 S=0.046, dominant=0.074 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.089 S=0.046, dominant=0.089 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.115, dominant=0.115 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.116, dominant=0.116 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.030 S=0.196, dominant=0.196 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.030 S=0.195, dominant=0.195 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.030 S=0.198, dominant=0.198 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.030 S=0.197, dominant=0.197 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.030 S=0.192, dominant=0.192 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.030 S=0.170, dominant=0.170 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.034 S=0.192, dominant=0.192 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.034 S=0.168, dominant=0.168 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.034 S=0.169, dominant=0.169 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.034 S=0.198, dominant=0.198 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.034 S=0.195, dominant=0.195 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.030 S=0.172, dominant=0.172 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.034 S=0.170, dominant=0.170 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.088, dominant=0.088 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.084, dominant=0.084 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.138, dominant=0.138 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.044 S=0.128, dominant=0.128 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.042 S=0.197, dominant=0.197 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.030 S=0.180, dominant=0.180 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.045 S=0.176, dominant=0.176 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.045 S=0.182, dominant=0.182 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.128, dominant=0.128 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.177 S=0.030, dominant=0.177 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.171 S=0.030, dominant=0.171 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.168 S=0.030, dominant=0.168 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.147 S=0.030, dominant=0.147 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.154 S=0.030, dominant=0.154 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.045 S=0.177, dominant=0.177 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.045 S=0.181, dominant=0.181 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.045 S=0.151, dominant=0.151 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.157 S=0.033, dominant=0.157 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.148 S=0.033, dominant=0.148 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.142 S=0.033, dominant=0.142 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.135 S=0.033, dominant=0.135 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.134 S=0.030, dominant=0.134 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.139 S=0.030, dominant=0.139 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.139 S=0.035, dominant=0.139 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.138 S=0.035, dominant=0.138 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.132 S=0.030, dominant=0.132 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.040 S=0.171, dominant=0.171 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.040 S=0.141, dominant=0.141 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.040 S=0.107, dominant=0.107 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.173 S=0.030, dominant=0.173 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.178 S=0.039, dominant=0.178 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.168 S=0.045, dominant=0.168 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.195 S=0.036, dominant=0.195 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.196 S=0.036, dominant=0.196 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.199 S=0.041, dominant=0.199 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.187 S=0.036, dominant=0.187 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.181 S=0.030, dominant=0.181 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.193 S=0.036, dominant=0.193 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.187 S=0.047, dominant=0.187 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.083 S=0.046, dominant=0.083 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.043 S=0.107, dominant=0.107 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.042 S=0.116, dominant=0.116 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.102 S=0.045, dominant=0.102 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.076, dominant=0.076 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.044 S=0.118, dominant=0.118 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.043 S=0.134, dominant=0.134 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.042 S=0.134, dominant=0.134 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.035 S=0.171, dominant=0.171 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.041 S=0.198, dominant=0.198 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.036 S=0.197, dominant=0.197 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.034 S=0.181, dominant=0.181 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.034 S=0.173, dominant=0.173 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.194, dominant=0.194 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.039 S=0.180, dominant=0.180 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.039 S=0.184, dominant=0.184 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.192, dominant=0.192 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.190, dominant=0.190 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.039 S=0.183, dominant=0.183 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.045 S=0.184, dominant=0.184 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.035 S=0.170, dominant=0.170 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.163 S=0.046, dominant=0.163 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.158 S=0.046, dominant=0.158 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.162 S=0.046, dominant=0.162 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.156 S=0.046, dominant=0.156 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.131 S=0.047, dominant=0.131 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.125 S=0.047, dominant=0.125 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.126 S=0.047, dominant=0.126 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.132 S=0.047, dominant=0.132 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.103 S=0.047, dominant=0.103 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.105 S=0.047, dominant=0.105 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.044 S=0.111, dominant=0.111 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.044 S=0.123, dominant=0.123 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.047 S=0.123, dominant=0.123 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.047 S=0.142, dominant=0.142 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.181 S=0.045, dominant=0.181 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.049 S=0.144, dominant=0.144 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.048 S=0.119, dominant=0.119 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.034 S=0.184, dominant=0.184 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.043 S=0.121, dominant=0.121 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.039 S=0.164, dominant=0.164 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.039 S=0.169, dominant=0.169 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.039 S=0.167, dominant=0.167 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.039 S=0.166, dominant=0.166 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.030 S=0.165, dominant=0.165 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.191 S=0.040, dominant=0.191 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.157 S=0.045, dominant=0.157 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.158 S=0.045, dominant=0.158 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.159 S=0.045, dominant=0.159 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.159 S=0.039, dominant=0.159 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Probability Floor: dominant=0.180 < 0.18 (high gap but no edge) | 1 | 0.0% |
| Phase 1 Halt: Bad time to trade: CLOSING | 1 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.196 S=0.038, dominant=0.196 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.196 S=0.043, dominant=0.196 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Gate Filter: BAD_STRUCTURE_EXPANDING | 1 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.125 S=0.040, dominant=0.125 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.120 S=0.040, dominant=0.120 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.101 S=0.040, dominant=0.101 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.048 S=0.193, dominant=0.193 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.077, dominant=0.077 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.044 S=0.163, dominant=0.163 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Trade cooldown: 0s remaining | 1 | 0.0% |
| Gate Filter: REJECTED_SAME_STRUCTURAL_TREND | 1 | 0.0% |
| Gate Filter: CHOP_ZONE_ACTIVE | 1 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.107 S=0.044, dominant=0.107 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Loss Cooldown active: 24m remaining | 1 | 0.0% |
| Loss Cooldown active: 18m remaining | 1 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.131 S=0.033, dominant=0.131 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.131 S=0.038, dominant=0.131 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.048 S=0.189, dominant=0.189 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Loss Cooldown active: 13m remaining | 1 | 0.0% |
| Loss Cooldown active: 9m remaining | 1 | 0.0% |
| Loss Cooldown active: 2m remaining | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.048 S=0.180, dominant=0.180 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.035 S=0.199, dominant=0.199 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.122, dominant=0.122 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.035 S=0.197, dominant=0.197 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.035 S=0.167, dominant=0.167 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.085, dominant=0.085 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.045 S=0.197, dominant=0.197 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.131 S=0.045, dominant=0.131 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.150 S=0.045, dominant=0.150 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.192 S=0.045, dominant=0.192 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.044 S=0.116, dominant=0.116 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.035 S=0.168, dominant=0.168 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.030 S=0.169, dominant=0.169 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.035 S=0.169, dominant=0.169 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.136 S=0.047, dominant=0.136 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.156 S=0.047, dominant=0.156 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| **Total Engine Cycles** | **13,683** | **100.0%** |

**Observed Market Regimes (Engine Telemetry)**:

| Regime | Cycles | % of Session |
| :--- | ---: | ---: |
| SQUEEZE | 10,317 | 75.4% |
| WEAK_TREND_DOWN | 2,237 | 16.3% |
| WEAK_TREND_UP | 892 | 6.5% |
| RANGING | 236 | 1.7% |
| LOW_VOL | 1 | 0.0% |
| **Total Cycles** | **13,683** | **100.0%** |

**Predictive Rejection Breakdown**:

| Reason | Count | % of Rejections |
| :--- | ---: | ---: |
| Max daily trades reached (3/3) | 17 | 38.6% |
| BAD_STRUCTURE_EXPANDING | 6 | 13.6% |
| REJECTED_REGIME_GRADE_B+_IN_SQUEEZE | 6 | 13.6% |
| Max open positions (1/1) | 3 | 6.8% |
| REJECTED_SAME_STRUCTURAL_TREND | 2 | 4.5% |
| PEV_TOO_LOW | 2 | 4.5% |
| LOW_CONFIDENCE | 1 | 2.3% |
| Trade cooldown: 0s remaining | 1 | 2.3% |
| CHOP_ZONE_ACTIVE | 1 | 2.3% |
| Loss Cooldown active: 24m remaining | 1 | 2.3% |
| Loss Cooldown active: 18m remaining | 1 | 2.3% |
| Loss Cooldown active: 13m remaining | 1 | 2.3% |
| Loss Cooldown active: 9m remaining | 1 | 2.3% |
| Loss Cooldown active: 2m remaining | 1 | 2.3% |
| **Total Predictive Rejections** | **44** | **100.0%** |

## 5. Execution Quality

| Metric | Value |
| :--- | ---: |
| Effective Participation | 40.5% |
| Neutral Abstention | 59.5% |
| Average Confidence | 57.1% |
| Average EV | 0.51R |
| Precision | 0.0 |
| Recall | 0.0 |
| Balanced Accuracy | 0.438 |
| F1 Score | 0.0 |
| MCC | -0.173 |

## 6. Shadow Opportunity Summary (Strategy Quality Evaluation)

*Note: Shadow layer tracks counterfactual hold-to-exit performance using decision-time structural levels.*

Evaluated candidates: 51
Shadow-eligible opportunities: 51
Rejected opportunities: 46

Genuinely bad: 0
Marginal: 44

Rejected opportunities that became profitable: 11
Rejected opportunities that became unprofitable: 35

Positive R available: +21.98R
Positive R captured: +0.00R
Positive expectancy captured: 0.0%

Negative R available: -39.00R
Negative R eliminated: -34.00R
Negative expectancy eliminated: 87.2%

Opportunity cost: +21.98R

### Gate Attribution Analysis

| Gate | Rejected | Profitable | Unprofitable | Missed Profit | Saved Loss | Net Counterfactual R |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| BAD_STRUCTURE_EXPANDING | 6 | 1 | 5 | +2.02R | -5.00R | -2.98R |
| CHOP_ZONE_ACTIVE | 1 | 0 | 1 | +0.00R | -1.00R | -1.00R |
| LOW_CONFIDENCE | 1 | 1 | 0 | +2.02R | +0.00R | +2.02R |
| Loss Cooldown active: 13m remaining | 1 | 0 | 1 | +0.00R | -1.00R | -1.00R |
| Loss Cooldown active: 18m remaining | 1 | 0 | 1 | +0.00R | -1.00R | -1.00R |
| Loss Cooldown active: 24m remaining | 1 | 0 | 1 | +0.00R | -1.00R | -1.00R |
| Loss Cooldown active: 2m remaining | 1 | 1 | 0 | +1.99R | +0.00R | +1.99R |
| Loss Cooldown active: 9m remaining | 1 | 0 | 1 | +0.00R | -1.00R | -1.00R |
| Max daily trades reached (3/3) | 17 | 4 | 13 | +7.99R | -13.00R | -5.01R |
| Max open positions (1/1) | 3 | 1 | 2 | +2.00R | -2.00R | +0.00R |
| PEV_TOO_LOW | 2 | 1 | 1 | +1.99R | -1.00R | +0.99R |
| Passed all gates | 2 | 0 | 2 | +0.00R | -2.00R | -2.00R |
| REJECTED_REGIME_GRADE_B+_IN_SQUEEZE | 6 | 2 | 3 | +3.97R | -3.00R | +0.97R |
| REJECTED_SAME_STRUCTURAL_TREND | 2 | 0 | 2 | +0.00R | -2.00R | -2.00R |
| Trade cooldown: 0s remaining | 1 | 0 | 1 | +0.00R | -1.00R | -1.00R |

## 6a. Executed Trades

| Time | Contract | Leg | Entry # | Reset | Plan Entry | Act Entry | SL | T1 | T2 | Exit | Result | Net P&L | R | Status | Reason |
|------|----------|-----|---------|-------|-----------:|----------:|---:|---:|---:|------:|--------|---------:|--:|--------|--------|
| 09:44 | NIFTY26SEP23650PE | - | - | - | 32.65 | 32.65 | 24.49 | - | - | 0.00 | LOSS | -₹1681 | -4.12R | CLOSED | UNKNOWN |
| 09:59 | NIFTY26SEP23650PE | - | - | - | 32.85 | 32.85 | 24.64 | - | - | 0.00 | LOSS | -₹1691 | -4.12R | CLOSED | UNKNOWN |
| 11:07 | NIFTY26SEP23650PE | - | - | - | 27.25 | 27.25 | 20.40 | - | - | 0.00 | LOSS | -₹1411 | -4.12R | CLOSED | UNKNOWN |
| 12:03 | NIFTY26SEP23650PE | - | - | - | 30.30 | 30.30 | 22.70 | - | - | 0.00 | LOSS | -₹1563 | -4.11R | CLOSED | UNKNOWN |
| 12:36 | NIFTY26SEP23650CE | - | - | - | 59.15 | 59.15 | 44.40 | - | - | 0.00 | LOSS | -₹3007 | -4.08R | CLOSED | UNKNOWN |

### Daily Trade Summary

Executed Trades:        5
Winning Trades:         0
Losing Trades:          5
Win Rate:               0.0%
Gross P&L:              -₹9352
Total Costs:            ₹2873
Net P&L:                -₹9352
Total R:                -20.55R
Average R:              -4.11R
Largest Win:            +₹0
Largest Loss:           -₹3007

## 7. V2 Validation Campaign Status

| Milestone | Status |
| :--- | :--- |
| Structural Leg Generation | 🟢 FROZEN |
| Simulation Execution Lifecycle | 🟢 VERIFIED |
| Raw Decision Capture | 🟢 IMPLEMENTED |
| Capture Integrity | 🟢 TESTED |
| Historical Replay Dataset | 🟡 ACCUMULATING (0/20 economic sessions, 2 capture-valid) |
| Economic Scarcity Validation | ⏸️ PAUSED |
| Live Deployment | 🔴 BLOCKED |

**Campaign Status**: 🛑 NOT READY (20 sessions remaining)

## 8. Issues Detected

**Issues:** 🟠 DATA / LINEAGE INTEGRITY ISSUE — NON-FATAL
> [!WARNING]
> Execution Ledger & PositionManager reconciliation contradiction identified. 5 OMS orders were routed and filled, but PositionManager in-memory state was decoupled upon process restart, causing execution reconciliation mismatches.

**Operational Health:** 🟢 Nominal (13,683 cycles evaluated, 0 fatal runtime errors, 0 recoverable errors)
**Validation limitation:** Historical V2 replay data unavailable; deterministic replay dataset incomplete
**Risk:** Economic scarcity validation incomplete

## 9. Validation Manifest Snapshot

```yaml
campaign_id: 2026-08-SHADOW-V2
candidate_engine: v5.0.2-REF
git_commit: a67b969
overall_status: NOT_READY
```

## 10. Campaign Trend

| Metric | Value |
| :--- | ---: |
| Replay Sessions (Economic Valid) | 0 / 20 |
| Capture-Valid Observed Sessions | 2 |
| Replay Expectancy (Today) | -0.33R |
| Runtime Errors (Today) | 0 fatal, 0 recoverable |
| Consecutive Healthy Sessions | 8 |

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
**Campaign Progress**: 0 / 20 economic-valid (2 capture-valid)

---
*Report generated automatically at 2026-09-08T16:58:16.686749 by `tools/generate_daily_audit.py`*