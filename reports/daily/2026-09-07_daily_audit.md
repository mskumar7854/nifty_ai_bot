> **🟡 DAILY DECISION: VALIDATION DATA INSUFFICIENT**
>
> Historical V2 replay unavailable because immutable raw decision inputs were not retained.

# Daily Trading Session Audit

**Date**: 2026-09-07  
**Campaign**: 2026-08-SHADOW-V2  
**Engine**: v5.0.2-REF  
**Mode**: SIMULATION  
**Git Commit**: 071ec1b  
**Market**: NIFTY 50  

---

## 1. Executive Summary

**Overall Status**: 🟡 VALIDATION DATA INSUFFICIENT

| Metric | Value |
| :--- | ---: |
| Market Evaluations (Engine Cycles) | 7,290 |
| Directional Candidates (V2 Snapshots) | 35 |
| Filtered Signals (Strategy Rejections) | 32 |
| Strategy-Approved Candidate Signals | 3 |
| Governance Blocked (Circuit Breaker) | 0 (ACTIVE) |
| Actual OMS Orders Routed | 0 |
| Actual Orders Filled | 0 |
| Execution Authorized Cycles | 6 |
| Counterfactual Replay Expectancy | +0.50R |
| System Posture | 🟢 ACTIVE |
| Runtime Errors (Fatal) | 0 |
| Runtime Errors (Recoverable) | 0 |
| Data Integrity | 100% |
| Campaign Progress | 0 / 20 valid (1 observed, 1 capture-valid, 0 excluded) |

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
| 1. Market Evaluations (Engine Cycles) | 7,290 | Telemetry source of truth: execution_metrics.jsonl |
| ├── BUY_CE Candidates | 15 | Call candidate evaluations |
| └── BUY_PE Candidates | 20 | Put candidate evaluations |
| 2. Predictive Candidates (Eligible for gates) | 35 | Shadow-eligible candidates |
| 3. Predictive Rejections | 32 | Intercepted by strategy/risk gates |
| 4. Strategy-Approved | 3 | Approved by predictive gates |
| 5. Governance-Blocked | 0 | Prevented by active ACTIVE circuit breaker |
| 6. OMS Orders Routed | 0 | Submitted to Order Management System |
| 7. Orders Filled | 0 | Confirmed entries (Open + Closed) |
| ├── Active Open Positions | 0 | Currently floating in position manager |
| └── Closed Outcomes | 0 | Finished trades contributing to realized P&L |

**Engine Evaluation / Safety Gate Breakdown**:

| Safety Gate / Reason | Count (Cycles) | % of Cycles |
| :--- | ---: | ---: |
| Not enough agreeing agents (2) | 2,334 | 32.0% |
| Signal Deduplication: Same direction signal within 300s | 2,227 | 30.5% |
| Not enough agreeing agents (1) | 885 | 12.1% |
| Probability Floor: dominant=0.090 < 0.18 (high gap but no edge) | 164 | 2.2% |
| Signal Quality too low (C) | 125 | 1.7% |
| Probability Floor: dominant=0.107 < 0.18 (high gap but no edge) | 77 | 1.1% |
| Phase 2 Halt: Core Agents Neutral (No Setup) | 50 | 0.7% |
| Probability Floor: dominant=0.088 < 0.18 (high gap but no edge) | 45 | 0.6% |
| Signal Integrity: SELL side collapsed (B=0.168 S=0.012, dominant=0.168 < 0.2, MPM=BALANCED) | 41 | 0.6% |
| Signal Integrity: BUY side collapsed (B=0.012 S=0.168, dominant=0.168 < 0.2, MPM=BALANCED) | 37 | 0.5% |
| Probability Floor: dominant=0.142 < 0.18 (high gap but no edge) | 34 | 0.5% |
| Probability Floor: dominant=0.074 < 0.18 (high gap but no edge) | 33 | 0.5% |
| Probability Floor: dominant=0.116 < 0.18 (high gap but no edge) | 30 | 0.4% |
| Probability Floor: dominant=0.153 < 0.18 (high gap but no edge) | 30 | 0.4% |
| Probability Floor: dominant=0.108 < 0.18 (high gap but no edge) | 27 | 0.4% |
| Probability Floor: dominant=0.103 < 0.18 (high gap but no edge) | 27 | 0.4% |
| Probability Floor: dominant=0.118 < 0.18 (high gap but no edge) | 23 | 0.3% |
| Probability Floor: dominant=0.163 < 0.18 (high gap but no edge) | 21 | 0.3% |
| Probability Floor: dominant=0.129 < 0.18 (high gap but no edge) | 21 | 0.3% |
| Signal Integrity: BUY side collapsed (B=0.047 S=0.074, dominant=0.074 < 0.2, MPM=BALANCED) | 20 | 0.3% |
| Signal Integrity: BUY side collapsed (B=0.049 S=0.118, dominant=0.118 < 0.2, MPM=BALANCED) | 20 | 0.3% |
| Probability Floor: dominant=0.133 < 0.18 (high gap but no edge) | 20 | 0.3% |
| Probability Floor: dominant=0.135 < 0.18 (high gap but no edge) | 19 | 0.3% |
| Probability Floor: dominant=0.110 < 0.18 (high gap but no edge) | 19 | 0.3% |
| Probability Floor: dominant=0.092 < 0.18 (high gap but no edge) | 18 | 0.2% |
| Probability Floor: dominant=0.126 < 0.18 (high gap but no edge) | 18 | 0.2% |
| Probability Floor: dominant=0.144 < 0.18 (high gap but no edge) | 16 | 0.2% |
| Probability Floor: dominant=0.177 < 0.18 (high gap but no edge) | 16 | 0.2% |
| Probability Floor: dominant=0.125 < 0.18 (high gap but no edge) | 14 | 0.2% |
| Probability Floor: dominant=0.139 < 0.18 (high gap but no edge) | 14 | 0.2% |
| Probability Floor: dominant=0.157 < 0.18 (high gap but no edge) | 14 | 0.2% |
| Signal Integrity: SELL side collapsed (B=0.090 S=0.049, dominant=0.090 < 0.2, MPM=BALANCED) | 14 | 0.2% |
| Probability Floor: dominant=0.175 < 0.18 (high gap but no edge) | 13 | 0.2% |
| Probability Floor: dominant=0.112 < 0.18 (high gap but no edge) | 13 | 0.2% |
| Probability Floor: dominant=0.140 < 0.18 (high gap but no edge) | 13 | 0.2% |
| Probability Floor: dominant=0.113 < 0.18 (high gap but no edge) | 12 | 0.2% |
| Probability Floor: dominant=0.084 < 0.18 (high gap but no edge) | 12 | 0.2% |
| Probability Floor: dominant=0.098 < 0.18 (high gap but no edge) | 11 | 0.2% |
| Probability Floor: dominant=0.083 < 0.18 (high gap but no edge) | 10 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.096 S=0.040, dominant=0.096 < 0.2, MPM=BALANCED) | 10 | 0.1% |
| Probability Floor: dominant=0.124 < 0.18 (high gap but no edge) | 10 | 0.1% |
| Probability Floor: dominant=0.164 < 0.18 (high gap but no edge) | 10 | 0.1% |
| Probability Floor: dominant=0.119 < 0.18 (high gap but no edge) | 10 | 0.1% |
| Probability Floor: dominant=0.155 < 0.18 (high gap but no edge) | 9 | 0.1% |
| Probability Floor: dominant=0.138 < 0.18 (high gap but no edge) | 9 | 0.1% |
| Signal Integrity: BUY side collapsed (B=0.049 S=0.090, dominant=0.090 < 0.2, MPM=BALANCED) | 8 | 0.1% |
| Probability Floor: dominant=0.149 < 0.18 (high gap but no edge) | 8 | 0.1% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.079, dominant=0.079 < 0.2, MPM=BALANCED) | 8 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.152 S=0.046, dominant=0.152 < 0.2, MPM=BALANCED) | 8 | 0.1% |
| Probability Floor: dominant=0.095 < 0.18 (high gap but no edge) | 8 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.183 S=0.041, dominant=0.183 < 0.2, MPM=BALANCED) | 8 | 0.1% |
| Probability Floor: dominant=0.115 < 0.18 (high gap but no edge) | 8 | 0.1% |
| Probability Floor: dominant=0.127 < 0.18 (high gap but no edge) | 8 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.158 S=0.046, dominant=0.158 < 0.2, MPM=BALANCED) | 8 | 0.1% |
| Probability Floor: dominant=0.151 < 0.18 (high gap but no edge) | 7 | 0.1% |
| Probability Floor: dominant=0.166 < 0.18 (high gap but no edge) | 7 | 0.1% |
| Probability Floor: dominant=0.114 < 0.18 (high gap but no edge) | 7 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.098 S=0.040, dominant=0.098 < 0.2, MPM=BALANCED) | 6 | 0.1% |
| Signal Integrity: BUY side collapsed (B=0.044 S=0.100, dominant=0.100 < 0.2, MPM=BALANCED) | 6 | 0.1% |
| Gate Filter: PEV_TOO_LOW | 6 | 0.1% |
| Probability Floor: dominant=0.150 < 0.18 (high gap but no edge) | 6 | 0.1% |
| Signal Integrity: BUY side collapsed (B=0.049 S=0.108, dominant=0.108 < 0.2, MPM=BALANCED) | 6 | 0.1% |
| Probability Floor: dominant=0.159 < 0.18 (high gap but no edge) | 6 | 0.1% |
| Probability Floor: dominant=0.109 < 0.18 (high gap but no edge) | 6 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.171 S=0.036, dominant=0.171 < 0.2, MPM=BALANCED) | 6 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.182 S=0.041, dominant=0.182 < 0.2, MPM=BALANCED) | 6 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.186 S=0.041, dominant=0.186 < 0.2, MPM=BALANCED) | 6 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.179 S=0.046, dominant=0.179 < 0.2, MPM=BALANCED) | 6 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.183 S=0.033, dominant=0.183 < 0.2, MPM=BALANCED) | 6 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.154 S=0.046, dominant=0.154 < 0.2, MPM=BALANCED) | 6 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.155 S=0.046, dominant=0.155 < 0.2, MPM=BALANCED) | 6 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.157 S=0.046, dominant=0.157 < 0.2, MPM=BALANCED) | 6 | 0.1% |
| Signal Integrity: BUY side collapsed (B=0.040 S=0.183, dominant=0.183 < 0.2, MPM=BALANCED) | 6 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.131 S=0.046, dominant=0.131 < 0.2, MPM=BALANCED) | 6 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.160 S=0.046, dominant=0.160 < 0.2, MPM=BALANCED) | 6 | 0.1% |
| Signal Integrity: BUY side collapsed (B=0.047 S=0.093, dominant=0.093 < 0.2, MPM=BALANCED) | 6 | 0.1% |
| Probability Floor: dominant=0.160 < 0.18 (high gap but no edge) | 5 | 0.1% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.107, dominant=0.107 < 0.2, MPM=BALANCED) | 5 | 0.1% |
| Probability Floor: dominant=0.075 < 0.18 (high gap but no edge) | 5 | 0.1% |
| Probability Floor: dominant=0.111 < 0.18 (high gap but no edge) | 5 | 0.1% |
| Probability Floor: dominant=0.102 < 0.18 (high gap but no edge) | 5 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.102 S=0.040, dominant=0.102 < 0.2, MPM=BALANCED) | 4 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.110 S=0.040, dominant=0.110 < 0.2, MPM=BALANCED) | 4 | 0.1% |
| Signal Integrity: BUY side collapsed (B=0.041 S=0.093, dominant=0.093 < 0.2, MPM=BALANCED) | 4 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.099 S=0.040, dominant=0.099 < 0.2, MPM=BALANCED) | 4 | 0.1% |
| Signal Integrity: BUY side collapsed (B=0.043 S=0.107, dominant=0.107 < 0.2, MPM=BALANCED) | 4 | 0.1% |
| Probability Floor: dominant=0.156 < 0.18 (high gap but no edge) | 4 | 0.1% |
| Probability Floor: dominant=0.132 < 0.18 (high gap but no edge) | 4 | 0.1% |
| Probability Floor: dominant=0.085 < 0.18 (high gap but no edge) | 4 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.081 S=0.046, dominant=0.081 < 0.2, MPM=BALANCED) | 4 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.077 S=0.046, dominant=0.077 < 0.2, MPM=BALANCED) | 4 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.076 S=0.046, dominant=0.076 < 0.2, MPM=BALANCED) | 4 | 0.1% |
| Probability Floor: dominant=0.167 < 0.18 (high gap but no edge) | 4 | 0.1% |
| Probability Floor: dominant=0.148 < 0.18 (high gap but no edge) | 4 | 0.1% |
| Probability Floor: dominant=0.152 < 0.18 (high gap but no edge) | 4 | 0.1% |
| Probability Floor: dominant=0.147 < 0.18 (high gap but no edge) | 4 | 0.1% |
| Probability Floor: dominant=0.079 < 0.18 (high gap but no edge) | 4 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.075 S=0.046, dominant=0.075 < 0.2, MPM=BALANCED) | 4 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.078 S=0.046, dominant=0.078 < 0.2, MPM=BALANCED) | 4 | 0.1% |
| Probability Floor: dominant=0.165 < 0.18 (high gap but no edge) | 4 | 0.1% |
| Probability Floor: dominant=0.093 < 0.18 (high gap but no edge) | 4 | 0.1% |
| Probability Floor: dominant=0.121 < 0.18 (high gap but no edge) | 4 | 0.1% |
| Probability Floor: dominant=0.104 < 0.18 (high gap but no edge) | 4 | 0.1% |
| Probability Floor: dominant=0.097 < 0.18 (high gap but no edge) | 4 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.191 S=0.041, dominant=0.191 < 0.2, MPM=BALANCED) | 4 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.181 S=0.041, dominant=0.181 < 0.2, MPM=BALANCED) | 4 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.195 S=0.041, dominant=0.195 < 0.2, MPM=BALANCED) | 4 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.180 S=0.030, dominant=0.180 < 0.2, MPM=BALANCED) | 4 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.198 S=0.041, dominant=0.198 < 0.2, MPM=BALANCED) | 4 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.193 S=0.041, dominant=0.193 < 0.2, MPM=BALANCED) | 4 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.190 S=0.041, dominant=0.190 < 0.2, MPM=BALANCED) | 4 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.184 S=0.041, dominant=0.184 < 0.2, MPM=BALANCED) | 4 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.172 S=0.046, dominant=0.172 < 0.2, MPM=BALANCED) | 4 | 0.1% |
| Probability Floor: dominant=0.178 < 0.18 (high gap but no edge) | 4 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.196 S=0.030, dominant=0.196 < 0.2, MPM=BALANCED) | 4 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.186 S=0.033, dominant=0.186 < 0.2, MPM=BALANCED) | 4 | 0.1% |
| Signal Integrity: BUY side collapsed (B=0.049 S=0.170, dominant=0.170 < 0.2, MPM=BALANCED) | 4 | 0.1% |
| Probability Floor: dominant=0.105 < 0.18 (high gap but no edge) | 4 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.169 S=0.046, dominant=0.169 < 0.2, MPM=BALANCED) | 4 | 0.1% |
| Probability Floor: dominant=0.173 < 0.18 (high gap but no edge) | 4 | 0.1% |
| Probability Floor: dominant=0.180 < 0.18 (high gap but no edge) | 4 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.164 S=0.046, dominant=0.164 < 0.2, MPM=BALANCED) | 4 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.150 S=0.046, dominant=0.150 < 0.2, MPM=BALANCED) | 4 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.118 S=0.046, dominant=0.118 < 0.2, MPM=BALANCED) | 4 | 0.1% |
| Probability Floor: dominant=0.146 < 0.18 (high gap but no edge) | 4 | 0.1% |
| Probability Floor: dominant=0.143 < 0.18 (high gap but no edge) | 4 | 0.1% |
| Signal Integrity: BUY side collapsed (B=0.040 S=0.182, dominant=0.182 < 0.2, MPM=BALANCED) | 4 | 0.1% |
| Phase 2 Halt: Intraday Spike Freeze active | 4 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.185 S=0.046, dominant=0.185 < 0.2, MPM=BALANCED) | 4 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.188 S=0.046, dominant=0.188 < 0.2, MPM=BALANCED) | 4 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.128 S=0.046, dominant=0.128 < 0.2, MPM=BALANCED) | 4 | 0.1% |
| Probability Floor: dominant=0.089 < 0.18 (high gap but no edge) | 3 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.044 S=0.107, dominant=0.107 < 0.2, MPM=BALANCED) | 3 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.043 S=0.116, dominant=0.116 < 0.2, MPM=BALANCED) | 3 | 0.0% |
| Probability Floor: dominant=0.078 < 0.18 (high gap but no edge) | 3 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.042 S=0.155, dominant=0.155 < 0.2, MPM=BALANCED) | 3 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.043 S=0.144, dominant=0.144 < 0.2, MPM=BALANCED) | 3 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.118 S=0.040, dominant=0.118 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.109 S=0.040, dominant=0.109 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.104 S=0.040, dominant=0.104 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.107 S=0.040, dominant=0.107 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.041 S=0.100, dominant=0.100 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.042 S=0.100, dominant=0.100 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.101 S=0.040, dominant=0.101 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.106 S=0.045, dominant=0.106 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.107 S=0.045, dominant=0.107 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.044 S=0.121, dominant=0.121 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.043 S=0.121, dominant=0.121 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.042 S=0.107, dominant=0.107 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.042 S=0.131, dominant=0.131 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.101 S=0.045, dominant=0.101 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.104 S=0.045, dominant=0.104 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Probability Floor: dominant=0.076 < 0.18 (high gap but no edge) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.198 S=0.040, dominant=0.198 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.175 S=0.040, dominant=0.175 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.185 S=0.040, dominant=0.185 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.169 S=0.040, dominant=0.169 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.138 S=0.040, dominant=0.138 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.136 S=0.040, dominant=0.136 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.143 S=0.040, dominant=0.143 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.140 S=0.040, dominant=0.140 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.165 S=0.045, dominant=0.165 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.163 S=0.045, dominant=0.163 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.171 S=0.045, dominant=0.171 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.141 S=0.045, dominant=0.141 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.169 S=0.045, dominant=0.169 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.155 S=0.045, dominant=0.155 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.152 S=0.045, dominant=0.152 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.045 S=0.107, dominant=0.107 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.043 S=0.135, dominant=0.135 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Gate Filter: BAD_STRUCTURE_UNDEFINED | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.168 S=0.033, dominant=0.168 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.166 S=0.038, dominant=0.166 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.080 S=0.046, dominant=0.080 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Probability Floor: dominant=0.082 < 0.18 (high gap but no edge) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.084 S=0.046, dominant=0.084 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.083 S=0.046, dominant=0.083 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.079 S=0.046, dominant=0.079 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.082 S=0.046, dominant=0.082 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Probability Floor: dominant=0.120 < 0.18 (high gap but no edge) | 2 | 0.0% |
| Probability Floor: dominant=0.099 < 0.18 (high gap but no edge) | 2 | 0.0% |
| Probability Floor: dominant=0.096 < 0.18 (high gap but no edge) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.170 S=0.036, dominant=0.170 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.176 S=0.041, dominant=0.176 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.172 S=0.036, dominant=0.172 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.143 S=0.030, dominant=0.143 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.183 S=0.046, dominant=0.183 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.190 S=0.046, dominant=0.190 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.182 S=0.046, dominant=0.182 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.187 S=0.046, dominant=0.187 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.189 S=0.046, dominant=0.189 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.144 S=0.034, dominant=0.144 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.171 S=0.040, dominant=0.171 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.173 S=0.040, dominant=0.173 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.191 S=0.046, dominant=0.191 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.174 S=0.036, dominant=0.174 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.187 S=0.041, dominant=0.187 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.185 S=0.041, dominant=0.185 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.178 S=0.041, dominant=0.178 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.180 S=0.041, dominant=0.180 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.146 S=0.030, dominant=0.146 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.148 S=0.030, dominant=0.148 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.198 S=0.033, dominant=0.198 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.181 S=0.033, dominant=0.181 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.187 S=0.033, dominant=0.187 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.184 S=0.033, dominant=0.184 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.188 S=0.033, dominant=0.188 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.195 S=0.030, dominant=0.195 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.197 S=0.040, dominant=0.197 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.199 S=0.030, dominant=0.199 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Probability Floor: dominant=0.162 < 0.18 (high gap but no edge) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.049 S=0.159, dominant=0.159 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.049 S=0.163, dominant=0.163 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.049 S=0.167, dominant=0.167 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Probability Floor: dominant=0.123 < 0.18 (high gap but no edge) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.045 S=0.131, dominant=0.131 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.043 S=0.128, dominant=0.128 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Probability Floor: dominant=0.158 < 0.18 (high gap but no edge) | 2 | 0.0% |
| Probability Floor: dominant=0.136 < 0.18 (high gap but no edge) | 2 | 0.0% |
| Probability Floor: dominant=0.168 < 0.18 (high gap but no edge) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.171 S=0.046, dominant=0.171 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Probability Floor: dominant=0.179 < 0.18 (high gap but no edge) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.175 S=0.046, dominant=0.175 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.151 S=0.046, dominant=0.151 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.161 S=0.046, dominant=0.161 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Probability Floor: dominant=0.169 < 0.18 (high gap but no edge) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.109 S=0.046, dominant=0.109 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Probability Floor: dominant=0.130 < 0.18 (high gap but no edge) | 2 | 0.0% |
| Probability Floor: dominant=0.141 < 0.18 (high gap but no edge) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.149 S=0.033, dominant=0.149 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.147 S=0.033, dominant=0.147 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.150 S=0.033, dominant=0.150 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.153 S=0.033, dominant=0.153 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.131 S=0.033, dominant=0.131 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.139 S=0.037, dominant=0.139 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.137 S=0.037, dominant=0.137 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.074 S=0.049, dominant=0.074 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.040 S=0.151, dominant=0.151 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.040 S=0.179, dominant=0.179 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.040 S=0.187, dominant=0.187 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.040 S=0.184, dominant=0.184 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.040 S=0.178, dominant=0.178 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Probability Floor: dominant=0.170 < 0.18 (high gap but no edge) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.163 S=0.046, dominant=0.163 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.124 S=0.046, dominant=0.124 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.156 S=0.046, dominant=0.156 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.044 S=0.093, dominant=0.093 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.043 S=0.100, dominant=0.100 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.045 S=0.121, dominant=0.121 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.045 S=0.139, dominant=0.139 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.118 S=0.045, dominant=0.118 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Probability Floor: dominant=0.154 < 0.18 (high gap but no edge) | 1 | 0.0% |
| Probability Floor: dominant=0.117 < 0.18 (high gap but no edge) | 1 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.116 S=0.046, dominant=0.116 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.196 S=0.046, dominant=0.196 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.186 S=0.030, dominant=0.186 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.186 S=0.035, dominant=0.186 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.180 S=0.035, dominant=0.180 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Gate Filter: LOW_CONFIDENCE | 1 | 0.0% |
| Gate Filter: REJECTED_LOW_EV_+0.17R | 1 | 0.0% |
| Gate Filter: BAD_STRUCTURE_EXPANDING | 1 | 0.0% |
| Probability Floor: dominant=0.134 < 0.18 (high gap but no edge) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.045 S=0.150, dominant=0.150 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.043 S=0.166, dominant=0.166 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Gate Filter: REJECTED_REGIME_GRADE_B+_IN_SQUEEZE | 1 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.123 S=0.046, dominant=0.123 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.152 S=0.038, dominant=0.152 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Gate Filter: REJECTED_LOW_EV_+0.48R | 1 | 0.0% |
| Gate Filter: REJECTED_LOW_EV_+0.43R | 1 | 0.0% |
| Probability Floor: dominant=0.171 < 0.18 (high gap but no edge) | 1 | 0.0% |
| Gate Filter: REJECTED_SAME_STRUCTURAL_TREND | 1 | 0.0% |
| Gate Filter: REJECTED_LOW_EV_+0.29R | 1 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.132 S=0.046, dominant=0.132 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| **Total Engine Cycles** | **7,290** | **100.0%** |

**Observed Market Regimes (Engine Telemetry)**:

| Regime | Cycles | % of Session |
| :--- | ---: | ---: |
| SQUEEZE | 3,772 | 51.7% |
| WEAK_TREND_DOWN | 2,037 | 27.9% |
| WEAK_TREND_UP | 788 | 10.8% |
| RANGING | 548 | 7.5% |
| STRONG_TREND_DOWN | 119 | 1.6% |
| STRONG_TREND_UP | 24 | 0.3% |
| TREND_UP | 1 | 0.0% |
| RANGE | 1 | 0.0% |
| **Total Cycles** | **7,290** | **100.0%** |

**Predictive Rejection Breakdown**:

| Reason | Count | % of Rejections |
| :--- | ---: | ---: |
| PEV_TOO_LOW | 8 | 25.0% |
| REJECTED_REGIME_GRADE_B+_IN_SQUEEZE | 6 | 18.8% |
| BAD_STRUCTURE_EXPANDING | 3 | 9.4% |
| Execution Blocked: Strike Policy Blocked: Unknown market regime; fail closed | 3 | 9.4% |
| CHOP_ZONE_ACTIVE | 3 | 9.4% |
| BAD_STRUCTURE_UNDEFINED | 3 | 9.4% |
| LOW_CONFIDENCE | 1 | 3.1% |
| REJECTED_LOW_EV_+0.17R | 1 | 3.1% |
| REJECTED_LOW_EV_+0.48R | 1 | 3.1% |
| REJECTED_LOW_EV_+0.43R | 1 | 3.1% |
| REJECTED_SAME_STRUCTURAL_TREND | 1 | 3.1% |
| REJECTED_LOW_EV_+0.29R | 1 | 3.1% |
| **Total Predictive Rejections** | **32** | **100.0%** |

## 5. Execution Quality

| Metric | Value |
| :--- | ---: |
| Effective Participation | 41.8% |
| Neutral Abstention | 58.2% |
| Average Confidence | 50.3% |
| Average EV | 0.34R |
| Precision | 0.5 |
| Recall | 0.056 |
| Balanced Accuracy | 0.498 |
| F1 Score | 0.1 |
| MCC | -0.007 |

## 6. Shadow Opportunity Summary (Strategy Quality Evaluation)

*Note: Shadow layer tracks counterfactual hold-to-exit performance using decision-time structural levels.*

- **Evaluated candidates**: 35
- **Shadow-eligible opportunities**: 35
- **Rejected opportunities**: 32 gate-rejected (+ 1 concurrency-blocked = 33 non-executed)
- **Rejected-opportunity adverse-outcome rate**: 53.1% (17 of 32 gate-rejected opportunities became unprofitable; 15 became profitable)
- **Positive R available**: +33.59R (Σ positive counterfactual R across all 18 profitable shadow-eligible opportunities; revised from uncorrected +29.96R after fixing Put direction mapping)
- **Positive R captured**: +1.98R (captured by 14:50 strategy-authorized setup)
- **Positive expectancy captured**: 5.9%
- **Negative R available**: -16.00R
- **Negative-R elimination**: 93.8% (-15.00R loss eliminated out of -16.00R potential downside)
- **Opportunity cost**: +31.61R (Σ positive R of all rejected/concurrency-blocked setups: +33.59R available - +1.98R captured = +31.61R)

### Gate Attribution Analysis

| Gate | Rejected | Profitable | Unprofitable | Missed Profit | Saved Loss | Net Counterfactual R |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| BAD_STRUCTURE_EXPANDING | 3 | 2 | 1 | +3.99R | -1.00R | +2.99R |
| BAD_STRUCTURE_UNDEFINED | 3 | 1 | 2 | +2.00R | -2.00R | +0.00R |
| CHOP_ZONE_ACTIVE | 3 | 2 | 1 | +4.01R | -1.00R | +3.01R |
| Execution Blocked: Strike Policy Blocked: Unknown market regime; fail closed | 3 | 1 | 2 | +2.00R | -2.00R | +0.00R |
| LOW_CONFIDENCE | 1 | 0 | 1 | +0.00R | -1.00R | -1.00R |
| PEV_TOO_LOW | 8 | 4 | 4 | +7.87R | -4.00R | +3.87R |
| Passed all gates (OMS Concurrency Blocked) | 1 | 1 | 0 | +0.35R | +0.00R | +0.35R |
| REJECTED_LOW_EV_+0.17R | 1 | 0 | 1 | +0.00R | -1.00R | -1.00R |
| REJECTED_LOW_EV_+0.29R | 1 | 0 | 0 | +0.00R | +0.00R | +0.00R |
| REJECTED_LOW_EV_+0.43R | 1 | 1 | 0 | +1.99R | +0.00R | +1.99R |
| REJECTED_LOW_EV_+0.48R | 1 | 1 | 0 | +2.01R | +0.00R | +2.01R |
| REJECTED_REGIME_GRADE_B+_IN_SQUEEZE | 6 | 3 | 3 | +6.00R | -3.00R | +3.00R |
| REJECTED_SAME_STRUCTURAL_TREND | 1 | 1 | 0 | +1.39R | +0.00R | +1.39R |

## 6a. Executed Trades

No executed trades today (Actual Orders Routed: 0, Orders Filled: 0, Realized P&L: ₹0.00 / 0.00R). System operated in SIMULATION mode.

## 6b. Counterfactual Replay Results of Strategy-Authorized Setups

*Note: These candidate setups passed all strategy and risk gates, but were NOT executed live on broker. Results reflect counterfactual hold-to-exit replay against actual market data.*

| Time (IST) | Snapshot ID | Direction | Planned Entry | Stop Loss | Target 1 | Risk (SL) | MFE (Peak) | MAE (Max DD) | Production Replay Outcome | Counterfactual R |
| :---: | :--- | :---: | ---: | ---: | ---: | ---: | ---: | ---: | :---: | ---: |
| 13:58:07 | `20260907-135807-3163-74D8` | BULLISH (`BUY_CE`) | 23,777.95 | 23,772.30 | 23,789.30 | 5.65 pts | +5.05 pts (+0.89R) | -7.75 pts (-1.37R) | STOPPED_OUT | **-1.00R** |
| 14:50:04 | `20260907-145004-5526-F323` | BEARISH (`BUY_PE`) | 23,755.00 | 23,760.60 | 23,743.90 | 5.60 pts | +12.95 pts (+2.31R) | 0.00 pts (0.00R) | TARGET_HIT | **+1.98R (~+2.00R)** |
| 15:00:05 | `20260907-150005-6115-BF84` | BEARISH (`BUY_PE`) | 23,744.55 | 23,751.70 | 23,730.30 | 7.15 pts | +2.50 pts (+0.35R) | -5.10 pts (-0.71R) | OMS_BLOCKED (Active Trade #2) | *[Excl. in Prod]* |

### Counterfactual Performance Summary
- **Strategy-Authorized Setups Generated**: 3
- **Production-Eligible Setups (Sequential `max_active_positions = 1`)**: 2 (Trade #3 excluded due to active Trade #2)
- **Production-Constrained Counterfactual Result**: **-1.00R + 1.98R = +1.00R** (Primary Metric)
- **Unconstrained Signal Replay Result (Concurrent)**: **-1.00R + 1.98R + 0.35R = +1.33R** (Diagnostic Metric; Trade #3 mark-to-market at close = +0.35R)
- **Actual Realized P&L**: **0.00R (₹0.00)**
- **Replay Methodology Note**: In early manual scratch calculation, Trade #3 was approximated as 0.00R flat time exit. The canonical replay engine evaluates time exits by marking-to-market at the final session candle (+2.50 pts / 7.15 pts risk = +0.35R). Under production sequential constraints, this setup is blocked by Trade #2 regardless, leaving the production result unchanged at +1.00R.

## 7. V2 Validation Campaign Status

| Milestone | Status |
| :--- | :--- |
| Structural Leg Generation | 🟢 FROZEN |
| Simulation Execution Lifecycle | 🟢 VERIFIED |
| Raw Decision Capture | 🟢 IMPLEMENTED |
| Capture Integrity | 🟢 TESTED |
| Historical Replay Dataset | 🟡 ACCUMULATING (0/20 economic sessions, 1 capture-valid) |
| Economic Scarcity Validation | ⏸️ PAUSED |
| Live Deployment | 🔴 BLOCKED |

**Campaign Status**: 🛑 NOT READY (20 sessions remaining)

## 8. Issues Detected

**Issues:** None operational
**Validation limitation:** Historical V2 replay data unavailable
**Risk:** Economic scarcity validation incomplete

## 9. Validation Manifest Snapshot

```yaml
campaign_id: 2026-08-SHADOW-V2
candidate_engine: v5.0.2-REF
git_commit: 071ec1b
overall_status: NOT_READY
```

## 10. Campaign Trend

| Metric | Value |
| :--- | ---: |
| Replay Sessions (Economic Valid) | 0 / 20 |
| Capture-Valid Observed Sessions | 1 |
| Replay Expectancy (Today) | +0.50R |
| Runtime Errors (Today) | 0 fatal, 0 recoverable |
| Consecutive Healthy Sessions | 7 |

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
**Campaign Progress**: 0 / 20 economic-valid (1 capture-valid)

---
*Report generated automatically at 2026-09-07T16:00:47.558122 by `tools/generate_daily_audit.py`*