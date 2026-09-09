> **🟡 DAILY DECISION: VALIDATION DATA INSUFFICIENT**
>
> Historical V2 replay unavailable because immutable raw decision inputs were not retained.

# Daily Trading Session Audit

**Date**: 2026-09-09  
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
| Market Evaluations (Engine Cycles) | 8,245 |
| Directional Candidates (V2 Snapshots) | 40 |
| Filtered Signals (Strategy Rejections) | 37 |
| Strategy-Approved Candidate Signals | 3 |
| Governance Blocked (Circuit Breaker) | 0 (ACTIVE) |
| Actual OMS Orders Routed | 0 |
| Actual Orders Filled | 0 |
| Execution Authorized Cycles | 3 |
| Counterfactual Replay Expectancy | -0.01R |
| System Posture | 🟢 ACTIVE |
| Runtime Errors (Fatal) | 0 |
| Runtime Errors (Recoverable) | 0 |
| Data Integrity | 100% |
| Campaign Progress | 0 / 20 valid (3 observed, 3 capture-valid, 0 excluded) |

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
| 1. Market Evaluations (Engine Cycles) | 8,245 | Telemetry source of truth: execution_metrics.jsonl |
| ├── BUY_CE Candidates | 19 | Call candidate evaluations |
| └── BUY_PE Candidates | 21 | Put candidate evaluations |
| 2. Predictive Candidates (Eligible for gates) | 40 | Shadow-eligible candidates |
| 3. Predictive Rejections | 37 | Intercepted by strategy/risk gates |
| 4. Strategy-Approved | 3 | Approved by predictive gates |
| 5. Governance-Blocked | 0 | Prevented by active ACTIVE circuit breaker |
| 6. OMS Orders Routed | 0 | Submitted to Order Management System |
| 7. Orders Filled | 0 | Confirmed entries (Open + Closed) |
| ├── Active Open Positions | 0 | Currently floating in position manager |
| └── Closed Outcomes | 0 | Finished trades contributing to realized P&L |

**Engine Evaluation / Safety Gate Breakdown**:

| Safety Gate / Reason | Count (Cycles) | % of Cycles |
| :--- | ---: | ---: |
| Signal Deduplication: Same direction signal within 300s | 2,764 | 33.5% |
| Not enough agreeing agents (2) | 1,600 | 19.4% |
| Not enough agreeing agents (1) | 656 | 8.0% |
| Signal Quality too low (C) | 606 | 7.3% |
| Probability Floor: dominant=0.108 < 0.18 (high gap but no edge) | 166 | 2.0% |
| Probability Floor: dominant=0.090 < 0.18 (high gap but no edge) | 116 | 1.4% |
| Signal Integrity: SELL side collapsed (B=0.168 S=0.012, dominant=0.168 < 0.2, MPM=BALANCED) | 87 | 1.1% |
| Probability Floor: dominant=0.153 < 0.18 (high gap but no edge) | 74 | 0.9% |
| Phase 2 Halt: Core Agents Neutral (No Setup) | 61 | 0.7% |
| Signal Integrity: BUY side collapsed (B=0.049 S=0.108, dominant=0.108 < 0.2, MPM=BALANCED) | 57 | 0.7% |
| Probability Floor: dominant=0.127 < 0.18 (high gap but no edge) | 56 | 0.7% |
| Probability Floor: dominant=0.095 < 0.18 (high gap but no edge) | 49 | 0.6% |
| Signal Integrity: BUY side collapsed (B=0.049 S=0.090, dominant=0.090 < 0.2, MPM=BALANCED) | 42 | 0.5% |
| Probability Floor: dominant=0.081 < 0.18 (high gap but no edge) | 41 | 0.5% |
| Probability Floor: dominant=0.099 < 0.18 (high gap but no edge) | 37 | 0.4% |
| Probability Floor: dominant=0.140 < 0.18 (high gap but no edge) | 36 | 0.4% |
| Probability Floor: dominant=0.085 < 0.18 (high gap but no edge) | 35 | 0.4% |
| Signal Integrity: BUY side collapsed (B=0.012 S=0.168, dominant=0.168 < 0.2, MPM=BALANCED) | 34 | 0.4% |
| Probability Floor: dominant=0.080 < 0.18 (high gap but no edge) | 31 | 0.4% |
| Probability Floor: dominant=0.157 < 0.18 (high gap but no edge) | 29 | 0.4% |
| Probability Floor: dominant=0.107 < 0.18 (high gap but no edge) | 27 | 0.3% |
| Probability Floor: dominant=0.120 < 0.18 (high gap but no edge) | 26 | 0.3% |
| Probability Floor: dominant=0.169 < 0.18 (high gap but no edge) | 26 | 0.3% |
| Probability Floor: dominant=0.103 < 0.18 (high gap but no edge) | 25 | 0.3% |
| Probability Floor: dominant=0.139 < 0.18 (high gap but no edge) | 25 | 0.3% |
| Probability Floor: dominant=0.135 < 0.18 (high gap but no edge) | 24 | 0.3% |
| Probability Floor: dominant=0.106 < 0.18 (high gap but no edge) | 24 | 0.3% |
| Probability Floor: dominant=0.142 < 0.18 (high gap but no edge) | 21 | 0.3% |
| Probability Floor: dominant=0.123 < 0.18 (high gap but no edge) | 18 | 0.2% |
| Probability Floor: dominant=0.074 < 0.18 (high gap but no edge) | 18 | 0.2% |
| Probability Floor: dominant=0.146 < 0.18 (high gap but no edge) | 17 | 0.2% |
| Probability Floor: dominant=0.125 < 0.18 (high gap but no edge) | 17 | 0.2% |
| Probability Floor: dominant=0.093 < 0.18 (high gap but no edge) | 16 | 0.2% |
| Probability Floor: dominant=0.113 < 0.18 (high gap but no edge) | 14 | 0.2% |
| Probability Floor: dominant=0.126 < 0.18 (high gap but no edge) | 14 | 0.2% |
| Probability Floor: dominant=0.087 < 0.18 (high gap but no edge) | 12 | 0.1% |
| Probability Floor: dominant=0.097 < 0.18 (high gap but no edge) | 12 | 0.1% |
| Probability Floor: dominant=0.086 < 0.18 (high gap but no edge) | 12 | 0.1% |
| Probability Floor: dominant=0.102 < 0.18 (high gap but no edge) | 12 | 0.1% |
| Probability Floor: dominant=0.111 < 0.18 (high gap but no edge) | 12 | 0.1% |
| Signal Integrity: BUY side collapsed (B=0.045 S=0.116, dominant=0.116 < 0.2, MPM=BALANCED) | 12 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.168 S=0.040, dominant=0.168 < 0.2, MPM=BALANCED) | 12 | 0.1% |
| Probability Floor: dominant=0.092 < 0.18 (high gap but no edge) | 11 | 0.1% |
| Probability Floor: dominant=0.121 < 0.18 (high gap but no edge) | 11 | 0.1% |
| Probability Floor: dominant=0.137 < 0.18 (high gap but no edge) | 11 | 0.1% |
| Probability Floor: dominant=0.147 < 0.18 (high gap but no edge) | 11 | 0.1% |
| Probability Floor: dominant=0.078 < 0.18 (high gap but no edge) | 10 | 0.1% |
| Probability Floor: dominant=0.098 < 0.18 (high gap but no edge) | 10 | 0.1% |
| Probability Floor: dominant=0.160 < 0.18 (high gap but no edge) | 10 | 0.1% |
| Probability Floor: dominant=0.105 < 0.18 (high gap but no edge) | 10 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.128 S=0.049, dominant=0.128 < 0.2, MPM=BALANCED) | 10 | 0.1% |
| Probability Floor: dominant=0.136 < 0.18 (high gap but no edge) | 10 | 0.1% |
| Probability Floor: dominant=0.143 < 0.18 (high gap but no edge) | 10 | 0.1% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.107, dominant=0.107 < 0.2, MPM=BALANCED) | 10 | 0.1% |
| Probability Floor: dominant=0.119 < 0.18 (high gap but no edge) | 10 | 0.1% |
| Signal Integrity: BUY side collapsed (B=0.048 S=0.116, dominant=0.116 < 0.2, MPM=BALANCED) | 10 | 0.1% |
| Signal Integrity: BUY side collapsed (B=0.030 S=0.152, dominant=0.152 < 0.2, MPM=BALANCED) | 10 | 0.1% |
| Probability Floor: dominant=0.109 < 0.18 (high gap but no edge) | 9 | 0.1% |
| Probability Floor: dominant=0.134 < 0.18 (high gap but no edge) | 9 | 0.1% |
| Probability Floor: dominant=0.091 < 0.18 (high gap but no edge) | 9 | 0.1% |
| Probability Floor: dominant=0.110 < 0.18 (high gap but no edge) | 9 | 0.1% |
| Probability Floor: dominant=0.084 < 0.18 (high gap but no edge) | 8 | 0.1% |
| Signal Integrity: BUY side collapsed (B=0.032 S=0.150, dominant=0.150 < 0.2, MPM=BALANCED) | 8 | 0.1% |
| Probability Floor: dominant=0.141 < 0.18 (high gap but no edge) | 8 | 0.1% |
| Probability Floor: dominant=0.152 < 0.18 (high gap but no edge) | 8 | 0.1% |
| Probability Floor: dominant=0.144 < 0.18 (high gap but no edge) | 8 | 0.1% |
| Probability Floor: dominant=0.145 < 0.18 (high gap but no edge) | 8 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.120 S=0.046, dominant=0.120 < 0.2, MPM=BALANCED) | 8 | 0.1% |
| Probability Floor: dominant=0.076 < 0.18 (high gap but no edge) | 8 | 0.1% |
| Probability Floor: dominant=0.101 < 0.18 (high gap but no edge) | 8 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.139 S=0.040, dominant=0.139 < 0.2, MPM=BALANCED) | 8 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.143 S=0.040, dominant=0.143 < 0.2, MPM=BALANCED) | 8 | 0.1% |
| Signal Integrity: BUY side collapsed (B=0.030 S=0.153, dominant=0.153 < 0.2, MPM=BALANCED) | 8 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.090 S=0.049, dominant=0.090 < 0.2, MPM=BALANCED) | 8 | 0.1% |
| Gate Filter: BAD_STRUCTURE_EXPANDING | 7 | 0.1% |
| Probability Floor: dominant=0.115 < 0.18 (high gap but no edge) | 7 | 0.1% |
| Probability Floor: dominant=0.156 < 0.18 (high gap but no edge) | 7 | 0.1% |
| Probability Floor: dominant=0.170 < 0.18 (high gap but no edge) | 7 | 0.1% |
| Probability Floor: dominant=0.130 < 0.18 (high gap but no edge) | 7 | 0.1% |
| Probability Floor: dominant=0.112 < 0.18 (high gap but no edge) | 7 | 0.1% |
| Probability Floor: dominant=0.094 < 0.18 (high gap but no edge) | 7 | 0.1% |
| Probability Floor: dominant=0.096 < 0.18 (high gap but no edge) | 6 | 0.1% |
| Probability Floor: dominant=0.114 < 0.18 (high gap but no edge) | 6 | 0.1% |
| Probability Floor: dominant=0.082 < 0.18 (high gap but no edge) | 6 | 0.1% |
| Signal Integrity: BUY side collapsed (B=0.035 S=0.155, dominant=0.155 < 0.2, MPM=BALANCED) | 6 | 0.1% |
| Signal Integrity: BUY side collapsed (B=0.038 S=0.190, dominant=0.190 < 0.2, MPM=BALANCED) | 6 | 0.1% |
| Probability Floor: dominant=0.164 < 0.18 (high gap but no edge) | 6 | 0.1% |
| Probability Floor: dominant=0.167 < 0.18 (high gap but no edge) | 6 | 0.1% |
| Probability Floor: dominant=0.173 < 0.18 (high gap but no edge) | 6 | 0.1% |
| Probability Floor: dominant=0.149 < 0.18 (high gap but no edge) | 6 | 0.1% |
| Signal Integrity: BUY side collapsed (B=0.044 S=0.079, dominant=0.079 < 0.2, MPM=BALANCED) | 6 | 0.1% |
| Signal Integrity: BUY side collapsed (B=0.043 S=0.107, dominant=0.107 < 0.2, MPM=BALANCED) | 6 | 0.1% |
| Probability Floor: dominant=0.124 < 0.18 (high gap but no edge) | 6 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.113 S=0.045, dominant=0.113 < 0.2, MPM=BALANCED) | 6 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.137 S=0.045, dominant=0.137 < 0.2, MPM=BALANCED) | 6 | 0.1% |
| Signal Integrity: BUY side collapsed (B=0.049 S=0.125, dominant=0.125 < 0.2, MPM=BALANCED) | 6 | 0.1% |
| Probability Floor: dominant=0.116 < 0.18 (high gap but no edge) | 6 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.178 S=0.045, dominant=0.178 < 0.2, MPM=BALANCED) | 6 | 0.1% |
| Probability Floor: dominant=0.161 < 0.18 (high gap but no edge) | 6 | 0.1% |
| Probability Floor: dominant=0.175 < 0.18 (high gap but no edge) | 6 | 0.1% |
| Signal Integrity: SELL side collapsed (B=0.148 S=0.040, dominant=0.148 < 0.2, MPM=BALANCED) | 6 | 0.1% |
| Signal Integrity: BUY side collapsed (B=0.044 S=0.157, dominant=0.157 < 0.2, MPM=BALANCED) | 5 | 0.1% |
| Probability Floor: dominant=0.158 < 0.18 (high gap but no edge) | 5 | 0.1% |
| Probability Floor: dominant=0.132 < 0.18 (high gap but no edge) | 5 | 0.1% |
| Probability Floor: dominant=0.122 < 0.18 (high gap but no edge) | 5 | 0.1% |
| Signal Integrity: BUY side collapsed (B=0.021 S=0.135, dominant=0.135 < 0.15, MPM=DEFENSIVE) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.021 S=0.133, dominant=0.133 < 0.15, MPM=DEFENSIVE) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.045 S=0.161, dominant=0.161 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.032 S=0.156, dominant=0.156 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.050 S=0.158, dominant=0.158 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.036 S=0.166, dominant=0.166 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.032 S=0.163, dominant=0.163 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.048 S=0.157, dominant=0.157 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.040 S=0.191, dominant=0.191 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Probability Floor: dominant=0.159 < 0.18 (high gap but no edge) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.037 S=0.194, dominant=0.194 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.037 S=0.176, dominant=0.176 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Probability Floor: dominant=0.165 < 0.18 (high gap but no edge) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.037 S=0.196, dominant=0.196 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.038 S=0.196, dominant=0.196 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.038 S=0.198, dominant=0.198 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.130 S=0.049, dominant=0.130 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.132 S=0.049, dominant=0.132 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.105 S=0.049, dominant=0.105 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.133 S=0.049, dominant=0.133 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.135 S=0.049, dominant=0.135 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.129 S=0.049, dominant=0.129 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.142 S=0.044, dominant=0.142 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.111 S=0.049, dominant=0.111 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Probability Floor: dominant=0.131 < 0.18 (high gap but no edge) | 4 | 0.0% |
| Probability Floor: dominant=0.150 < 0.18 (high gap but no edge) | 4 | 0.0% |
| Probability Floor: dominant=0.151 < 0.18 (high gap but no edge) | 4 | 0.0% |
| Probability Floor: dominant=0.155 < 0.18 (high gap but no edge) | 4 | 0.0% |
| Probability Floor: dominant=0.154 < 0.18 (high gap but no edge) | 4 | 0.0% |
| Probability Floor: dominant=0.176 < 0.18 (high gap but no edge) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.120 S=0.045, dominant=0.120 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.044 S=0.071, dominant=0.071 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.044 S=0.072, dominant=0.072 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.044 S=0.081, dominant=0.081 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.012 S=0.157, dominant=0.157 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Probability Floor: dominant=0.100 < 0.18 (high gap but no edge) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.082, dominant=0.082 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.044 S=0.123, dominant=0.123 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.045 S=0.123, dominant=0.123 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.043 S=0.121, dominant=0.121 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.043 S=0.135, dominant=0.135 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.135 S=0.045, dominant=0.135 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.162 S=0.045, dominant=0.162 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.181 S=0.045, dominant=0.181 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.174 S=0.045, dominant=0.174 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.186 S=0.045, dominant=0.186 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.182 S=0.045, dominant=0.182 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.193 S=0.045, dominant=0.193 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.171 S=0.040, dominant=0.171 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.142 S=0.040, dominant=0.142 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.138 S=0.040, dominant=0.138 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.165 S=0.040, dominant=0.165 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.140 S=0.040, dominant=0.140 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.141 S=0.040, dominant=0.141 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.144 S=0.040, dominant=0.144 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.080, dominant=0.080 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.172 S=0.035, dominant=0.172 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.182 S=0.036, dominant=0.182 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.048 S=0.114, dominant=0.114 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.132 S=0.033, dominant=0.132 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.078 S=0.046, dominant=0.078 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.076 S=0.046, dominant=0.076 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.034 S=0.158, dominant=0.158 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.034 S=0.184, dominant=0.184 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.084, dominant=0.084 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.044 S=0.119, dominant=0.119 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.167 S=0.040, dominant=0.167 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.160 S=0.040, dominant=0.160 < 0.2, MPM=BALANCED) | 4 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.026 S=0.108, dominant=0.108 < 0.15, MPM=DEFENSIVE) | 3 | 0.0% |
| Probability Floor: dominant=0.083 < 0.18 (high gap but no edge) | 3 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.035 S=0.156, dominant=0.156 < 0.2, MPM=BALANCED) | 3 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.042 S=0.190, dominant=0.190 < 0.2, MPM=BALANCED) | 3 | 0.0% |
| Probability Floor: dominant=0.168 < 0.18 (high gap but no edge) | 3 | 0.0% |
| Probability Floor: dominant=0.088 < 0.18 (high gap but no edge) | 3 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.044 S=0.116, dominant=0.116 < 0.2, MPM=BALANCED) | 3 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.043 S=0.134, dominant=0.134 < 0.2, MPM=BALANCED) | 3 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.042 S=0.116, dominant=0.116 < 0.2, MPM=BALANCED) | 3 | 0.0% |
| Gate Filter: PEV_TOO_LOW | 3 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.103 S=0.045, dominant=0.103 < 0.2, MPM=BALANCED) | 3 | 0.0% |
| Probability Floor: dominant=0.166 < 0.18 (high gap but no edge) | 3 | 0.0% |
| Probability Floor: dominant=0.117 < 0.18 (high gap but no edge) | 3 | 0.0% |
| Probability Floor: dominant=0.148 < 0.18 (high gap but no edge) | 3 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.012 S=0.148, dominant=0.148 < 0.15, MPM=DEFENSIVE) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.012 S=0.142, dominant=0.142 < 0.15, MPM=DEFENSIVE) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.023 S=0.134, dominant=0.134 < 0.15, MPM=DEFENSIVE) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.023 S=0.138, dominant=0.138 < 0.15, MPM=DEFENSIVE) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.023 S=0.139, dominant=0.139 < 0.15, MPM=DEFENSIVE) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.021 S=0.131, dominant=0.131 < 0.15, MPM=DEFENSIVE) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.021 S=0.137, dominant=0.137 < 0.15, MPM=DEFENSIVE) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.030 S=0.108, dominant=0.108 < 0.15, MPM=DEFENSIVE) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.038 S=0.156, dominant=0.156 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.043 S=0.158, dominant=0.158 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.031 S=0.148, dominant=0.148 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.038 S=0.182, dominant=0.182 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.037 S=0.166, dominant=0.166 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.035 S=0.149, dominant=0.149 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.040 S=0.149, dominant=0.149 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.032 S=0.165, dominant=0.165 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.050 S=0.157, dominant=0.157 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.034 S=0.185, dominant=0.185 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.037 S=0.174, dominant=0.174 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.039 S=0.191, dominant=0.191 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.037 S=0.193, dominant=0.193 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.035 S=0.173, dominant=0.173 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.038 S=0.193, dominant=0.193 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.039 S=0.193, dominant=0.193 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.037 S=0.187, dominant=0.187 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.040 S=0.168, dominant=0.168 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.036 S=0.187, dominant=0.187 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.037 S=0.188, dominant=0.188 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.037 S=0.190, dominant=0.190 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.036 S=0.190, dominant=0.190 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.043 S=0.170, dominant=0.170 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.041 S=0.171, dominant=0.171 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.036 S=0.174, dominant=0.174 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.042 S=0.175, dominant=0.175 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.035 S=0.175, dominant=0.175 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.043 S=0.175, dominant=0.175 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.036 S=0.175, dominant=0.175 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.037 S=0.199, dominant=0.199 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.038 S=0.199, dominant=0.199 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.036 S=0.198, dominant=0.198 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.170 S=0.049, dominant=0.170 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.154 S=0.049, dominant=0.154 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.151 S=0.049, dominant=0.151 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.152 S=0.049, dominant=0.152 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.104 S=0.049, dominant=0.104 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.107 S=0.049, dominant=0.107 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.115 S=0.049, dominant=0.115 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.141 S=0.044, dominant=0.141 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.139 S=0.044, dominant=0.139 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Probability Floor: dominant=0.171 < 0.18 (high gap but no edge) | 2 | 0.0% |
| Probability Floor: dominant=0.129 < 0.18 (high gap but no edge) | 2 | 0.0% |
| Probability Floor: dominant=0.133 < 0.18 (high gap but no edge) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.154, dominant=0.154 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.112 S=0.047, dominant=0.112 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.138 S=0.043, dominant=0.138 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.120 S=0.043, dominant=0.120 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.120 S=0.044, dominant=0.120 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.120 S=0.042, dominant=0.120 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.044 S=0.078, dominant=0.078 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.044 S=0.076, dominant=0.076 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.044 S=0.075, dominant=0.075 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.157 S=0.012, dominant=0.157 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.044 S=0.083, dominant=0.083 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.044 S=0.080, dominant=0.080 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Probability Floor: dominant=0.073 < 0.18 (high gap but no edge) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.074, dominant=0.074 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.078, dominant=0.078 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Probability Floor: dominant=0.079 < 0.18 (high gap but no edge) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.042 S=0.131, dominant=0.131 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.042 S=0.121, dominant=0.121 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.105 S=0.045, dominant=0.105 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.043 S=0.123, dominant=0.123 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.116, dominant=0.116 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.042 S=0.123, dominant=0.123 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.042 S=0.114, dominant=0.114 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.129, dominant=0.129 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.044 S=0.124, dominant=0.124 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.147 S=0.045, dominant=0.147 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.101 S=0.045, dominant=0.101 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.154 S=0.045, dominant=0.154 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.112 S=0.045, dominant=0.112 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.111 S=0.045, dominant=0.111 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.142 S=0.045, dominant=0.142 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.138 S=0.045, dominant=0.138 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.136 S=0.045, dominant=0.136 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.108 S=0.045, dominant=0.108 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.164 S=0.045, dominant=0.164 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.050 S=0.144, dominant=0.144 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.044 S=0.107, dominant=0.107 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.047 S=0.107, dominant=0.107 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.134 S=0.045, dominant=0.134 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.048 S=0.107, dominant=0.107 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.132 S=0.045, dominant=0.132 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.119, dominant=0.119 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.146 S=0.045, dominant=0.146 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.047 S=0.135, dominant=0.135 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.049 S=0.157, dominant=0.157 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.049 S=0.120, dominant=0.120 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Probability Floor: dominant=0.138 < 0.18 (high gap but no edge) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.048 S=0.138, dominant=0.138 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.109 S=0.045, dominant=0.109 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.043 S=0.116, dominant=0.116 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.045 S=0.138, dominant=0.138 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.110 S=0.045, dominant=0.110 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.165 S=0.045, dominant=0.165 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.161 S=0.045, dominant=0.161 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.175 S=0.045, dominant=0.175 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.192 S=0.045, dominant=0.192 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.187 S=0.045, dominant=0.187 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.166 S=0.045, dominant=0.166 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.180 S=0.045, dominant=0.180 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.194 S=0.040, dominant=0.194 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.185 S=0.045, dominant=0.185 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.192 S=0.040, dominant=0.192 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.188 S=0.045, dominant=0.188 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.190 S=0.040, dominant=0.190 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.184 S=0.045, dominant=0.184 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.173 S=0.045, dominant=0.173 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.169 S=0.045, dominant=0.169 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.195 S=0.040, dominant=0.195 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.137 S=0.040, dominant=0.137 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.173 S=0.040, dominant=0.173 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.188 S=0.040, dominant=0.188 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.186 S=0.040, dominant=0.186 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.180 S=0.040, dominant=0.180 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.178 S=0.040, dominant=0.178 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.127 S=0.040, dominant=0.127 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.131, dominant=0.131 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.045 S=0.131, dominant=0.131 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.044 S=0.131, dominant=0.131 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.077, dominant=0.077 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.154 S=0.030, dominant=0.154 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.199 S=0.041, dominant=0.199 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.186 S=0.048, dominant=0.186 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.170 S=0.035, dominant=0.170 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.190 S=0.048, dominant=0.190 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.181 S=0.042, dominant=0.181 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.191 S=0.048, dominant=0.191 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.184 S=0.036, dominant=0.184 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.169 S=0.030, dominant=0.169 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.186 S=0.041, dominant=0.186 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.189 S=0.041, dominant=0.189 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.190 S=0.041, dominant=0.190 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.177 S=0.036, dominant=0.177 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.175 S=0.039, dominant=0.175 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.184 S=0.039, dominant=0.184 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.174 S=0.033, dominant=0.174 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.197 S=0.038, dominant=0.197 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.176 S=0.036, dominant=0.176 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.154 S=0.033, dominant=0.154 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.158 S=0.030, dominant=0.158 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.159 S=0.030, dominant=0.159 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.099 S=0.049, dominant=0.099 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.048 S=0.115, dominant=0.115 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.048 S=0.112, dominant=0.112 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.048 S=0.117, dominant=0.117 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.132 S=0.030, dominant=0.132 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.074 S=0.046, dominant=0.074 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.079, dominant=0.079 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.077 S=0.046, dominant=0.077 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.030 S=0.161, dominant=0.161 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.040 S=0.190, dominant=0.190 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.034 S=0.176, dominant=0.176 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.034 S=0.167, dominant=0.167 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.034 S=0.174, dominant=0.174 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.039 S=0.181, dominant=0.181 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.039 S=0.179, dominant=0.179 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.039 S=0.182, dominant=0.182 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.189, dominant=0.189 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.086, dominant=0.086 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.108 S=0.049, dominant=0.108 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.034 S=0.146, dominant=0.146 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.035 S=0.151, dominant=0.151 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.030 S=0.155, dominant=0.155 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.030 S=0.151, dominant=0.151 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.030 S=0.150, dominant=0.150 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.045 S=0.119, dominant=0.119 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.130 S=0.045, dominant=0.130 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.030 S=0.171, dominant=0.171 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.030 S=0.146, dominant=0.146 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.030 S=0.174, dominant=0.174 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.155 S=0.030, dominant=0.155 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.151 S=0.030, dominant=0.151 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.153 S=0.030, dominant=0.153 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.199 S=0.040, dominant=0.199 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.183 S=0.040, dominant=0.183 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.147 S=0.040, dominant=0.147 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.198 S=0.040, dominant=0.198 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.146 S=0.040, dominant=0.146 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.145 S=0.040, dominant=0.145 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.174 S=0.040, dominant=0.174 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.157 S=0.040, dominant=0.157 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.170 S=0.040, dominant=0.170 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.151 S=0.040, dominant=0.151 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.130 S=0.040, dominant=0.130 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.132 S=0.040, dominant=0.132 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.135 S=0.040, dominant=0.135 < 0.2, MPM=BALANCED) | 2 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.023 S=0.133, dominant=0.133 < 0.15, MPM=DEFENSIVE) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.021 S=0.134, dominant=0.134 < 0.15, MPM=DEFENSIVE) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.021 S=0.132, dominant=0.132 < 0.15, MPM=DEFENSIVE) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.030 S=0.107, dominant=0.107 < 0.15, MPM=DEFENSIVE) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.031 S=0.121, dominant=0.121 < 0.151734, MPM=DEFENSIVE) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.031 S=0.121, dominant=0.121 < 0.151756, MPM=DEFENSIVE) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.037 S=0.135, dominant=0.135 < 0.159302, MPM=DEFENSIVE) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.029 S=0.137, dominant=0.137 < 0.160556, MPM=DEFENSIVE) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.029 S=0.137, dominant=0.137 < 0.1606, MPM=DEFENSIVE) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.030 S=0.148, dominant=0.148 < 0.173008, MPM=DEFENSIVE) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.030 S=0.148, dominant=0.148 < 0.17305199999999998, MPM=DEFENSIVE) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.043 S=0.155, dominant=0.155 < 0.17333800000000002, MPM=DEFENSIVE) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.043 S=0.155, dominant=0.155 < 0.17336000000000001, MPM=DEFENSIVE) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.155, dominant=0.155 < 0.173404, MPM=DEFENSIVE) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.046 S=0.155, dominant=0.155 < 0.173426, MPM=DEFENSIVE) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.031 S=0.160, dominant=0.160 < 0.173602, MPM=DEFENSIVE) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.031 S=0.160, dominant=0.160 < 0.173712, MPM=DEFENSIVE) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.031 S=0.161, dominant=0.161 < 0.173734, MPM=DEFENSIVE) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.031 S=0.161, dominant=0.161 < 0.17377800000000002, MPM=DEFENSIVE) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.031 S=0.161, dominant=0.161 < 0.1738, MPM=DEFENSIVE) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.032 S=0.161, dominant=0.161 < 0.173822, MPM=DEFENSIVE) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.032 S=0.161, dominant=0.161 < 0.173866, MPM=DEFENSIVE) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.033 S=0.161, dominant=0.161 < 0.173888, MPM=DEFENSIVE) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.033 S=0.161, dominant=0.161 < 0.173932, MPM=DEFENSIVE) | 1 | 0.0% |
| Probability Floor: dominant=0.081 < 0.15814 (high gap but no edge) | 1 | 0.0% |
| Probability Floor: dominant=0.081 < 0.15816 (high gap but no edge) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.031 S=0.161, dominant=0.161 < 0.17402, MPM=DEFENSIVE) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.031 S=0.161, dominant=0.161 < 0.174042, MPM=DEFENSIVE) | 1 | 0.0% |
| Probability Floor: dominant=0.082 < 0.15832000000000002 (high gap but no edge) | 1 | 0.0% |
| Probability Floor: dominant=0.082 < 0.15834 (high gap but no edge) | 1 | 0.0% |
| Probability Floor: dominant=0.082 < 0.15892 (high gap but no edge) | 1 | 0.0% |
| Probability Floor: dominant=0.082 < 0.15894 (high gap but no edge) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.031 S=0.160, dominant=0.160 < 0.17494400000000002, MPM=DEFENSIVE) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.031 S=0.160, dominant=0.160 < 0.174966, MPM=DEFENSIVE) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.044 S=0.167, dominant=0.167 < 0.175252, MPM=DEFENSIVE) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.037 S=0.167, dominant=0.167 < 0.17527399999999999, MPM=DEFENSIVE) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.032 S=0.167, dominant=0.167 < 0.17529599999999998, MPM=DEFENSIVE) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.032 S=0.167, dominant=0.167 < 0.175318, MPM=DEFENSIVE) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.032 S=0.167, dominant=0.167 < 0.17536200000000002, MPM=DEFENSIVE) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.032 S=0.167, dominant=0.167 < 0.175384, MPM=DEFENSIVE) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.044 S=0.160, dominant=0.160 < 0.17567, MPM=DEFENSIVE) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.044 S=0.160, dominant=0.160 < 0.175692, MPM=DEFENSIVE) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.045 S=0.160, dominant=0.160 < 0.175956, MPM=DEFENSIVE) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.045 S=0.160, dominant=0.160 < 0.17597800000000002, MPM=DEFENSIVE) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.044 S=0.156, dominant=0.156 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.032 S=0.149, dominant=0.149 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.032 S=0.151, dominant=0.151 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.035 S=0.185, dominant=0.185 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.037 S=0.192, dominant=0.192 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.040 S=0.192, dominant=0.192 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Gate Filter: REJECTED_LOW_EV_+0.26R | 1 | 0.0% |
| Gate Filter: REJECTED_LOW_EV_+0.33R | 1 | 0.0% |
| Gate Filter: CHOP_ZONE_ACTIVE | 1 | 0.0% |
| Gate Filter: REJECTED_LOW_EV_+0.27R | 1 | 0.0% |
| Gate Filter: REJECTED_SAME_STRUCTURAL_TREND | 1 | 0.0% |
| Gate Filter: LOW_CONFLUENCE | 1 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.138 S=0.044, dominant=0.138 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.044 S=0.134, dominant=0.134 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.042 S=0.134, dominant=0.134 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.124 S=0.045, dominant=0.124 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.043 S=0.119, dominant=0.119 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.043 S=0.137, dominant=0.137 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.158 S=0.045, dominant=0.158 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.160 S=0.045, dominant=0.160 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.119 S=0.045, dominant=0.119 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.159 S=0.040, dominant=0.159 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Probability Floor: dominant=0.162 < 0.18 (high gap but no edge) | 1 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.189 S=0.040, dominant=0.189 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.192 S=0.041, dominant=0.192 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.192 S=0.048, dominant=0.192 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.194 S=0.048, dominant=0.194 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Probability Floor: dominant=0.075 < 0.18 (high gap but no edge) | 1 | 0.0% |
| Gate Filter: REJECTED_REGIME_GRADE_B+_IN_SQUEEZE | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.045 S=0.107, dominant=0.107 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Probability Floor: dominant=0.178 < 0.18 (high gap but no edge) | 1 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.199 S=0.045, dominant=0.199 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.183 S=0.042, dominant=0.183 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.049 S=0.135, dominant=0.135 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: SELL side collapsed (B=0.148 S=0.045, dominant=0.148 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Signal Integrity: BUY side collapsed (B=0.045 S=0.124, dominant=0.124 < 0.2, MPM=BALANCED) | 1 | 0.0% |
| Gate Filter: LOW_CONFIDENCE | 1 | 0.0% |
| **Total Engine Cycles** | **8,245** | **100.0%** |

**Observed Market Regimes (Engine Telemetry)**:

| Regime | Cycles | % of Session |
| :--- | ---: | ---: |
| SQUEEZE | 4,027 | 48.8% |
| WEAK_TREND_UP | 1,662 | 20.2% |
| WEAK_TREND_DOWN | 1,068 | 13.0% |
| STRONG_TREND_DOWN | 652 | 7.9% |
| RANGING | 418 | 5.1% |
| STRONG_TREND_UP | 418 | 5.1% |
| **Total Cycles** | **8,245** | **100.0%** |

**Predictive Rejection Breakdown**:

| Reason | Count | % of Rejections |
| :--- | ---: | ---: |
| BAD_STRUCTURE_EXPANDING | 15 | 40.5% |
| PEV_TOO_LOW | 6 | 16.2% |
| LOW_CONFIDENCE | 4 | 10.8% |
| LOW_CONFLUENCE | 3 | 8.1% |
| REJECTED_REGIME_GRADE_B+_IN_SQUEEZE | 2 | 5.4% |
| REJECTED_LOW_EV_+0.15R | 1 | 2.7% |
| REJECTED_LOW_EV_+0.38R | 1 | 2.7% |
| REJECTED_LOW_EV_+0.26R | 1 | 2.7% |
| REJECTED_LOW_EV_+0.33R | 1 | 2.7% |
| CHOP_ZONE_ACTIVE | 1 | 2.7% |
| REJECTED_LOW_EV_+0.27R | 1 | 2.7% |
| REJECTED_SAME_STRUCTURAL_TREND | 1 | 2.7% |
| **Total Predictive Rejections** | **37** | **100.0%** |

## 5. Execution Quality

| Metric | Value |
| :--- | ---: |
| Effective Participation | 41.9% |
| Neutral Abstention | 58.1% |
| Average Confidence | 46.8% |
| Average EV | 0.25R |
| Precision | 0.333 |
| Recall | 0.071 |
| Balanced Accuracy | 0.497 |
| F1 Score | 0.118 |
| MCC | -0.01 |

## 6. Shadow Opportunity Summary (Strategy Quality Evaluation)

*Note: Shadow layer tracks counterfactual hold-to-exit performance using decision-time structural levels.*

Evaluated candidates: 40
Shadow-eligible opportunities: 40
Rejected opportunities: 37

Genuinely bad: 0
Marginal: 37

Rejected opportunities that became profitable: 13
Rejected opportunities that became unprofitable: 24

Positive R available: +24.77R
Positive R captured: +2.00R
Positive expectancy captured: 8.1%

Negative R available: -25.00R
Negative R eliminated: -23.00R
Negative expectancy eliminated: 92.0%

Opportunity cost: +22.77R

### Gate Attribution Analysis

| Gate | Rejected | Profitable | Unprofitable | Missed Profit | Saved Loss | Net Counterfactual R |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| BAD_STRUCTURE_EXPANDING | 15 | 8 | 6 | +12.79R | -6.00R | +6.79R |
| CHOP_ZONE_ACTIVE | 1 | 0 | 1 | +0.00R | -1.00R | -1.00R |
| LOW_CONFIDENCE | 4 | 2 | 2 | +4.00R | -2.00R | +2.00R |
| LOW_CONFLUENCE | 3 | 0 | 3 | +0.00R | -3.00R | -3.00R |
| PEV_TOO_LOW | 6 | 2 | 4 | +3.99R | -4.00R | -0.01R |
| REJECTED_LOW_EV_+0.15R | 1 | 0 | 1 | +0.00R | -1.00R | -1.00R |
| REJECTED_LOW_EV_+0.26R | 1 | 0 | 1 | +0.00R | -1.00R | -1.00R |
| REJECTED_LOW_EV_+0.27R | 1 | 0 | 1 | +0.00R | -1.00R | -1.00R |
| REJECTED_LOW_EV_+0.33R | 1 | 1 | 0 | +1.99R | +0.00R | +1.99R |
| REJECTED_LOW_EV_+0.38R | 1 | 0 | 1 | +0.00R | -1.00R | -1.00R |
| REJECTED_REGIME_GRADE_B+_IN_SQUEEZE | 2 | 0 | 2 | +0.00R | -2.00R | -2.00R |
| REJECTED_SAME_STRUCTURAL_TREND | 1 | 0 | 1 | +0.00R | -1.00R | -1.00R |

## 6a. Executed Trades

No executed trades today.

## 7. V2 Validation Campaign Status

| Milestone | Status |
| :--- | :--- |
| Structural Leg Generation | 🟢 FROZEN |
| Simulation Execution Lifecycle | 🟢 VERIFIED |
| Raw Decision Capture | 🟢 IMPLEMENTED |
| Capture Integrity | 🟢 TESTED |
| Historical Replay Dataset | 🟡 ACCUMULATING (0/20 economic sessions, 3 capture-valid) |
| Economic Scarcity Validation | ⏸️ PAUSED |
| Live Deployment | 🔴 BLOCKED |

**Campaign Status**: 🛑 NOT READY (20 sessions remaining)

## 8. Issues Detected

**Issues:** 🟠 DATA / LINEAGE INTEGRITY ISSUE — NON-FATAL
> [!WARNING]
> Execution Ledger & PositionManager reconciliation contradiction identified. 5 OMS orders were routed and filled, but PositionManager in-memory state was decoupled upon process restart, causing execution reconciliation mismatches.

**Operational Health:** 🟢 Nominal (8,245 cycles evaluated, 0 fatal runtime errors, 0 recoverable errors)
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
| Capture-Valid Observed Sessions | 3 |
| Replay Expectancy (Today) | -0.01R |
| Runtime Errors (Today) | 0 fatal, 0 recoverable |
| Consecutive Healthy Sessions | 9 |

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
**Campaign Progress**: 0 / 20 economic-valid (3 capture-valid)

---
*Report generated automatically at 2026-09-09T14:23:35.680527 by `tools/generate_daily_audit.py`*