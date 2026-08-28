> **⚠️ PRELIMINARY DIAGNOSTIC — Based on 6 valid sessions (292 snapshots)**
>
> All ablation conclusions are preliminary. Even if an apparently excellent variant is discovered,
> it requires prospective validation before deployment.

# Zero-Trade Gate-Ablation Diagnostic

**Generated**: 2026-08-27 20:48:51  
**Campaign**: 2026-08-SHADOW-V2  
**Code Freeze**: ACTIVE — No production changes  
**Dataset**: 292 candidates across 7 sessions  

---

## 1. Executive Summary

| Metric | Value |
| :--- | ---: |
| Total Candidates | 292 |
| Strategy-Approved | 3 |
| Rejected | 289 |
| Rejection Rate | 99.0% |
| Pre-Gate Blocked (Unknown Regime) | 27 |
| Multi-Gate Failures | 188 (65% of rejections) |
| Profitable Candidates Missed (FN) | 115 |
| Unprofitable Candidates Blocked (TN) | 174 |
| Total Missed Profit | +229.93R |
| OMS Trades Executed | 0 |

### Per-Session Breakdown

| Date | Candidates | Rejected | FN (Profitable Missed) | TN (Blocked Bad) | Approved |
| :--- | ---: | ---: | ---: | ---: | ---: |
| 2026-08-19 | 43 | 40 | 9 | 31 | 3 |
| 2026-08-20 | 52 | 52 | 20 | 32 | 0 |
| 2026-08-21 | 49 | 49 | 22 | 27 | 0 |
| 2026-08-24 | 40 | 40 | 21 | 19 | 0 |
| 2026-08-25 | 33 | 33 | 20 | 13 | 0 |
| 2026-08-26 | 24 | 24 | 7 | 17 | 0 |
| 2026-08-27 | 51 | 51 | 16 | 35 | 0 |

---

## 2. Gate Failure Frequency (All Sessions)

| Gate | Total Fails | Primary Blocker | Contributing Blocker | Fail % |
| :--- | ---: | ---: | ---: | ---: |
| Expected Value (EV) | 187 | 13 | 174 | 64.7% |
| Regime-Aware Grade | 170 | 12 | 158 | 58.8% |
| Cost/Breakeven (PEV) | 116 | 0 | 116 | 40.1% |
| Structure Reset | 108 | 41 | 67 | 37.4% |
| Structure | 63 | 8 | 55 | 21.8% |
| Confidence | 32 | 0 | 32 | 11.1% |
| Strike Policy: Unknown Regime | 27 | 27 | 0 | 9.3% |
| Chop Zone | 17 | 0 | 17 | 5.9% |
| Confluence | 2 | 0 | 2 | 0.7% |

**Primary Blocker**: The only failing gate (removing it alone would unlock the candidate)  
**Contributing Blocker**: One of multiple failing gates (removing it alone would NOT unlock the candidate)  

---

## 3. Single-Gate Ablation Analysis

*What would happen if each gate were individually removed from V2?*

### A. Policy Qualification (Unconstrained)

| Policy Variant | Qualified | W | L | Net R | Avg R | Median R | Win% | PF | Max Consec L |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Current V2 (frozen) | 3 | 1 | 2 | +0.00R | +0.00R | -1.00R | 33.3% | 1.00 | 1 |
| V2 − Structure | 11 | 4 | 7 | +0.99R | +0.09R | -1.00R | 36.4% | 1.14 | 3 |
| V2 − StructReset | 44 | 25 | 19 | +31.01R | +0.70R | +1.99R | 56.8% | 2.63 | 4 |
| V2 − PEV | 3 | 1 | 2 | +0.00R | +0.00R | -1.00R | 33.3% | 1.00 | 1 |
| V2 − EV | 16 | 3 | 13 | -7.00R | -0.44R | -1.00R | 18.8% | 0.46 | 7 |
| V2 − RegimeGrade | 15 | 5 | 10 | -0.01R | -0.00R | -1.00R | 33.3% | 1.00 | 3 |
| V2 − Chop | 3 | 1 | 2 | +0.00R | +0.00R | -1.00R | 33.3% | 1.00 | 1 |
| V2 − Confidence | 3 | 1 | 2 | +0.00R | +0.00R | -1.00R | 33.3% | 1.00 | 1 |
| V2 − Confluence | 3 | 1 | 2 | +0.00R | +0.00R | -1.00R | 33.3% | 1.00 | 1 |
| V2 − UnknownRegime | 30 | 8 | 22 | -5.99R | -0.20R | -1.00R | 26.7% | 0.73 | 9 |

### B. OMS-Constrained Sequential Execution

*With max_active_positions = 1 (production constraint)*

| Policy Variant | Executed | W | L | Net R | Avg R | Median R | Win% | PF | Max Consec L |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Current V2 (frozen) | 3 | 1 | 2 | +0.00R | +0.00R | -1.00R | 33.3% | 1.00 | 1 |
| V2 − Structure | 9 | 4 | 5 | +2.99R | +0.33R | -1.00R | 44.4% | 1.60 | 3 |
| V2 − StructReset | 27 | 14 | 13 | +15.01R | +0.56R | +1.99R | 51.9% | 2.15 | 3 |
| V2 − PEV | 3 | 1 | 2 | +0.00R | +0.00R | -1.00R | 33.3% | 1.00 | 1 |
| V2 − EV | 12 | 2 | 10 | -6.00R | -0.50R | -1.00R | 16.7% | 0.40 | 5 |
| V2 − RegimeGrade | 12 | 4 | 8 | -0.01R | -0.00R | -1.00R | 33.3% | 1.00 | 3 |
| V2 − Chop | 3 | 1 | 2 | +0.00R | +0.00R | -1.00R | 33.3% | 1.00 | 1 |
| V2 − Confidence | 3 | 1 | 2 | +0.00R | +0.00R | -1.00R | 33.3% | 1.00 | 1 |
| V2 − Confluence | 3 | 1 | 2 | +0.00R | +0.00R | -1.00R | 33.3% | 1.00 | 1 |
| V2 − UnknownRegime | 22 | 7 | 15 | -0.99R | -0.05R | -1.00R | 31.8% | 0.93 | 8 |

---

## 4. Cumulative Relaxation (Progressive Gate Removal)

*Gates removed in order of best single-gate Net R impact (descending).*

### A. Policy Qualification (Unconstrained)

| Policy Variant | Qualified | W | L | Net R | Avg R | Win% | PF | Gross +R | Gross −R |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **Current V2 (frozen)** | 0 | 0 | 0 | — | — | — | — | — | — |
| V2 − StructReset | 44 | 25 | 19 | +31.01R | +0.70R | 56.8% | 2.63 | +50.01R | -19.00R |
| V2 − StructReset − Structure | 56 | 30 | 26 | +35.00R | +0.62R | 53.6% | 2.40 | +60.00R | -25.00R |
| V2 − StructReset − Structure − PEV | 56 | 30 | 26 | +35.00R | +0.62R | 53.6% | 2.40 | +60.00R | -25.00R |
| V2 − StructReset − Structure − PEV − Chop | 56 | 30 | 26 | +35.00R | +0.62R | 53.6% | 2.40 | +60.00R | -25.00R |
| V2 − StructReset − Structure − PEV − Chop − Confidence | 56 | 30 | 26 | +35.00R | +0.62R | 53.6% | 2.40 | +60.00R | -25.00R |
| V2 − StructReset − Structure − PEV − Chop − Confidence − Confluence | 56 | 30 | 26 | +35.00R | +0.62R | 53.6% | 2.40 | +60.00R | -25.00R |
| V2 − StructReset − Structure − PEV − Chop − Confidence − Confluence − RegimeGrade | 78 | 39 | 39 | +39.99R | +0.51R | 50.0% | 2.05 | +77.99R | -38.00R |
| V2 − StructReset − Structure − PEV − Chop − Confidence − Confluence − RegimeGrade − EV | 265 | 109 | 156 | +63.43R | +0.24R | 41.1% | 1.41 | +217.92R | -154.49R |
| V2 − ALL gates − UnknownRegime | 292 | 116 | 176 | +57.44R | +0.20R | 39.7% | 1.33 | +231.93R | -174.49R |

### B. OMS-Constrained Sequential Execution

| Policy Variant | Executed | W | L | Net R | Avg R | Win% | PF | Gross +R | Gross −R |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **Current V2 (frozen)** | 0 | 0 | 0 | — | — | — | — | — | — |
| V2 − StructReset | 27 | 14 | 13 | +15.01R | +0.56R | 51.9% | 2.15 | +28.01R | -13.00R |
| V2 − StructReset − Structure | 37 | 18 | 19 | +18.00R | +0.49R | 48.6% | 2.00 | +36.00R | -18.00R |
| V2 − StructReset − Structure − PEV | 37 | 18 | 19 | +18.00R | +0.49R | 48.6% | 2.00 | +36.00R | -18.00R |
| V2 − StructReset − Structure − PEV − Chop | 37 | 18 | 19 | +18.00R | +0.49R | 48.6% | 2.00 | +36.00R | -18.00R |
| V2 − StructReset − Structure − PEV − Chop − Confidence | 37 | 18 | 19 | +18.00R | +0.49R | 48.6% | 2.00 | +36.00R | -18.00R |
| V2 − StructReset − Structure − PEV − Chop − Confidence − Confluence | 37 | 18 | 19 | +18.00R | +0.49R | 48.6% | 2.00 | +36.00R | -18.00R |
| V2 − StructReset − Structure − PEV − Chop − Confidence − Confluence − RegimeGrade | 51 | 25 | 26 | +24.99R | +0.49R | 49.0% | 2.00 | +49.99R | -25.00R |
| V2 − StructReset − Structure − PEV − Chop − Confidence − Confluence − RegimeGrade − EV | 121 | 45 | 76 | +14.49R | +0.12R | 37.2% | 1.19 | +89.98R | -75.49R |
| V2 − ALL gates − UnknownRegime | 131 | 46 | 85 | +7.49R | +0.06R | 35.1% | 1.09 | +91.98R | -84.49R |

---

## 5. Profitable Missed Candidates (False Negatives) — Deep Dive

**115 profitable candidates were rejected**, representing **+229.93R** in missed opportunity.

### Blocking Gate Combinations (Profitable Candidates Only)

| Gate Combination | Count | Total Missed R | Avg Missed R |
| :--- | ---: | ---: | ---: |
| Structure Reset | 24 | +48.01R | +2.00R |
| Expected Value (EV) + Regime-Aware Grade | 11 | +22.01R | +2.00R |
| Cost/Breakeven (PEV) + Expected Value (EV) + Regime-Aware Grade + Structure Reset | 10 | +19.99R | +2.00R |
| Cost/Breakeven (PEV) + Expected Value (EV) + Regime-Aware Grade | 10 | +20.01R | +2.00R |
| Strike Policy: Unknown Regime | 7 | +14.01R | +2.00R |
| Cost/Breakeven (PEV) + Expected Value (EV) + Regime-Aware Grade + Structure + Structure Reset | 4 | +7.99R | +2.00R |
| Regime-Aware Grade | 4 | +7.99R | +2.00R |
| Confidence + Cost/Breakeven (PEV) + Expected Value (EV) + Regime-Aware Grade | 4 | +7.99R | +2.00R |
| Expected Value (EV) + Structure Reset | 4 | +7.97R | +1.99R |
| Cost/Breakeven (PEV) + Expected Value (EV) + Regime-Aware Grade + Structure | 4 | +7.99R | +2.00R |
| Structure | 3 | +5.99R | +2.00R |
| Expected Value (EV) + Regime-Aware Grade + Structure | 3 | +5.99R | +2.00R |
| Regime-Aware Grade + Structure | 3 | +6.00R | +2.00R |
| Expected Value (EV) + Regime-Aware Grade + Structure Reset | 3 | +6.00R | +2.00R |
| Confidence + Cost/Breakeven (PEV) + Expected Value (EV) + Regime-Aware Grade + Structure Reset | 2 | +4.00R | +2.00R |
| Expected Value (EV) | 2 | +4.00R | +2.00R |
| Expected Value (EV) + Structure | 2 | +4.01R | +2.00R |
| Structure + Structure Reset | 2 | +4.00R | +2.00R |
| Cost/Breakeven (PEV) + Expected Value (EV) | 2 | +3.99R | +2.00R |
| Chop Zone + Confidence + Cost/Breakeven (PEV) + Expected Value (EV) + Structure | 2 | +4.00R | +2.00R |
| Regime-Aware Grade + Structure Reset | 2 | +4.00R | +2.00R |
| Confidence + Cost/Breakeven (PEV) + Expected Value (EV) + Regime-Aware Grade + Structure | 1 | +2.00R | +2.00R |
| Chop Zone + Expected Value (EV) | 1 | +2.00R | +2.00R |
| Chop Zone + Cost/Breakeven (PEV) + Expected Value (EV) + Regime-Aware Grade + Structure Reset | 1 | +2.00R | +2.00R |
| Chop Zone + Cost/Breakeven (PEV) + Expected Value (EV) + Regime-Aware Grade + Structure | 1 | +2.00R | +2.00R |
| Expected Value (EV) + Regime-Aware Grade + Structure + Structure Reset | 1 | +2.00R | +2.00R |
| Chop Zone + Confluence + Expected Value (EV) + Regime-Aware Grade + Structure | 1 | +2.00R | +2.00R |
| Chop Zone + Confidence + Cost/Breakeven (PEV) + Expected Value (EV) + Regime-Aware Grade + Structure | 1 | +1.99R | +1.99R |

### Individual False Negative Candidates

| Date | Time | Signal | R | Conf% | MFE R | MAE R | Blocking Gates | Primary Reason |
| :--- | :--- | :--- | ---: | ---: | ---: | ---: | :--- | :--- |
| 2026-08-25 | 11:50 | BUY_CE | +2.01R | 62.3 | 2.08 | 0.00 | Regime-Aware Grade | REJECTED_REGIME_GRADE_B+_IN_SQUEEZE |
| 2026-08-25 | 13:16 | BUY_CE | +2.01R | 74.4 | 2.92 | 0.92 | Structure Reset | REJECTED_SAME_STRUCTURAL_TREND |
| 2026-08-25 | 13:42 | BUY_CE | +2.01R | 62.1 | 3.22 | 0.00 | Strike Policy: Unknown Regime | Execution Blocked: Strike Policy Blocked: Unknown  |
| 2026-08-25 | 13:53 | BUY_CE | +2.01R | 53.8 | 3.62 | 0.59 | Expected Value (EV), Regime-Aware Grade | REJECTED_REGIME_GRADE_B+_IN_SQUEEZE |
| 2026-08-25 | 14:49 | BUY_CE | +2.01R | 73.7 | 2.48 | 0.00 | Structure Reset | REJECTED_SAME_STRUCTURAL_TREND |
| 2026-08-25 | 14:54 | BUY_CE | +2.01R | 73.1 | 2.68 | 0.00 | Structure Reset | REJECTED_SAME_STRUCTURAL_TREND |
| 2026-08-26 | 13:24 | BUY_CE | +2.01R | 54.2 | 2.03 | 0.00 | Expected Value (EV), Structure | BAD_STRUCTURE_EXPANDING |
| 2026-08-26 | 14:12 | BUY_CE | +2.01R | 48.4 | 2.42 | 0.00 | Expected Value (EV), Regime-Aware Grade | REJECTED_REGIME_GRADE_B+_IN_SQUEEZE |
| 2026-08-27 | 12:34 | BUY_CE | +2.01R | 32.5 | 2.57 | 0.00 | Cost/Breakeven (PEV), Expected Value (EV), Regime-Aware Grade | PEV_TOO_LOW |
| 2026-08-27 | 13:00 | BUY_CE | +2.01R | 58.3 | 2.38 | 0.26 | Structure Reset | REJECTED_SAME_STRUCTURAL_TREND |
| 2026-08-27 | 14:01 | BUY_CE | +2.01R | 59.6 | 2.21 | 0.69 | Structure Reset | REJECTED_SAME_STRUCTURAL_TREND |
| 2026-08-27 | 14:06 | BUY_CE | +2.01R | 67.4 | 2.76 | 0.19 | Structure Reset | REJECTED_SAME_STRUCTURAL_TREND |
| 2026-08-27 | 14:14 | BUY_CE | +2.01R | 37.6 | 2.72 | 0.00 | Cost/Breakeven (PEV), Expected Value (EV), Regime-Aware Grade, Structure Reset | PEV_TOO_LOW |
| 2026-08-19 | 09:38 | BUY_CE | +2.00R | 67.0 | 2.91 | 0.00 | Structure Reset | REJECTED_SAME_STRUCTURAL_TREND |
| 2026-08-19 | 09:40 | BUY_CE | +2.00R | 68.4 | 2.07 | 0.00 | Strike Policy: Unknown Regime | Execution Blocked: Premium Fetch Failed |
| 2026-08-19 | 10:26 | BUY_PE | +2.00R | 70.5 | 2.17 | 0.00 | Structure | BAD_STRUCTURE_EXPANDING |
| 2026-08-19 | 11:05 | BUY_CE | +2.00R | 36.1 | 3.13 | 0.00 | Cost/Breakeven (PEV), Expected Value (EV), Regime-Aware Grade, Structure Reset | PEV_TOO_LOW |
| 2026-08-19 | 11:10 | BUY_CE | +2.00R | 33.9 | 3.11 | 0.00 | Confidence, Cost/Breakeven (PEV), Expected Value (EV), Regime-Aware Grade, Structure Reset | LOW_CONFIDENCE |
| 2026-08-19 | 11:17 | BUY_CE | +2.00R | 34.8 | 2.45 | 0.18 | Cost/Breakeven (PEV), Expected Value (EV), Regime-Aware Grade, Structure, Structure Reset | BAD_STRUCTURE_EXPANDING |
| 2026-08-19 | 11:58 | BUY_PE | +2.00R | 50.7 | 2.12 | 0.00 | Expected Value (EV) | REJECTED_LOW_EV_+0.35R |
| 2026-08-19 | 12:24 | BUY_PE | +2.00R | 61.3 | 2.12 | 0.00 | Regime-Aware Grade | REJECTED_REGIME_GRADE_B+_IN_SQUEEZE |
| 2026-08-19 | 13:17 | BUY_CE | +2.00R | 47.7 | 15.38 | 0.32 | Expected Value (EV), Regime-Aware Grade, Structure | BAD_STRUCTURE_EXPANDING |
| 2026-08-20 | 09:28 | BUY_CE | +2.00R | 49.9 | 2.18 | 0.37 | Expected Value (EV), Structure | BAD_STRUCTURE_UNDEFINED |
| 2026-08-20 | 09:33 | BUY_CE | +2.00R | 60.3 | 2.02 | 0.00 | Strike Policy: Unknown Regime | Execution Blocked: Strike Policy Blocked: Unknown  |
| 2026-08-20 | 09:52 | BUY_CE | +2.00R | 78.3 | 2.17 | 0.00 | Structure Reset | REJECTED_SAME_STRUCTURAL_TREND |
| 2026-08-20 | 10:23 | BUY_PE | +2.00R | 67.0 | 2.33 | 0.00 | Structure Reset | REJECTED_SAME_STRUCTURAL_TREND |
| 2026-08-20 | 11:19 | BUY_CE | +2.00R | 52.2 | 5.05 | 0.40 | Expected Value (EV), Regime-Aware Grade | REJECTED_REGIME_GRADE_B+_IN_SQUEEZE |
| 2026-08-20 | 12:00 | BUY_CE | +2.00R | 64.9 | 3.49 | 0.80 | Structure Reset | REJECTED_SAME_STRUCTURAL_TREND |
| 2026-08-20 | 12:13 | BUY_CE | +2.00R | 37.3 | 3.54 | 0.75 | Cost/Breakeven (PEV), Expected Value (EV), Regime-Aware Grade, Structure Reset | PEV_TOO_LOW |
| 2026-08-20 | 12:51 | BUY_PE | +2.00R | 66.2 | 2.04 | 0.00 | Structure, Structure Reset | BAD_STRUCTURE_EXPANDING |
| 2026-08-20 | 12:57 | BUY_PE | +2.00R | 57.9 | 2.65 | 0.62 | Structure, Structure Reset | BAD_STRUCTURE_EXPANDING |
| 2026-08-20 | 13:25 | BUY_PE | +2.00R | 41.3 | 2.06 | 0.03 | Cost/Breakeven (PEV), Expected Value (EV), Regime-Aware Grade, Structure, Structure Reset | BAD_STRUCTURE_EXPANDING |
| 2026-08-20 | 13:37 | BUY_PE | +2.00R | 35.4 | 2.10 | 0.00 | Cost/Breakeven (PEV), Expected Value (EV), Regime-Aware Grade, Structure Reset | PEV_TOO_LOW |
| 2026-08-20 | 13:45 | BUY_PE | +2.00R | 32.2 | 2.54 | 0.25 | Confidence, Cost/Breakeven (PEV), Expected Value (EV), Regime-Aware Grade | LOW_CONFIDENCE |
| 2026-08-20 | 13:50 | BUY_PE | +2.00R | 43.3 | 2.42 | 0.37 | Cost/Breakeven (PEV), Expected Value (EV), Regime-Aware Grade | PEV_TOO_LOW |
| 2026-08-20 | 14:25 | BUY_PE | +2.00R | 50.3 | 2.29 | 0.50 | Expected Value (EV), Regime-Aware Grade, Structure | BAD_STRUCTURE_EXPANDING |
| 2026-08-20 | 14:32 | BUY_PE | +2.00R | 57.1 | 2.79 | 0.00 | Regime-Aware Grade, Structure | BAD_STRUCTURE_EXPANDING |
| 2026-08-20 | 14:37 | BUY_PE | +2.00R | 30.2 | 2.53 | 0.00 | Confidence, Cost/Breakeven (PEV), Expected Value (EV), Regime-Aware Grade, Structure | LOW_CONFIDENCE |
| 2026-08-20 | 14:50 | BUY_PE | +2.00R | 57.8 | 2.80 | 0.07 | Regime-Aware Grade | REJECTED_REGIME_GRADE_B+_IN_SQUEEZE |
| 2026-08-20 | 14:56 | BUY_PE | +2.00R | 41.0 | 2.86 | 0.00 | Cost/Breakeven (PEV), Expected Value (EV), Regime-Aware Grade | PEV_TOO_LOW |
| 2026-08-20 | 15:12 | BUY_CE | +2.00R | 67.1 | 2.84 | 0.00 | Strike Policy: Unknown Regime | Execution Blocked: Strike Policy Blocked: Unknown  |
| 2026-08-20 | 15:17 | BUY_CE | +2.00R | 57.8 | 3.38 | 0.19 | Cost/Breakeven (PEV), Expected Value (EV), Regime-Aware Grade, Structure, Structure Reset | BAD_STRUCTURE_EXPANDING |
| 2026-08-21 | 09:35 | BUY_CE | +2.00R | 44.9 | 3.31 | 0.00 | Expected Value (EV), Regime-Aware Grade | REJECTED_REGIME_GRADE_B+_IN_SQUEEZE |
| 2026-08-21 | 10:07 | BUY_CE | +2.00R | 42.4 | 2.19 | 0.11 | Cost/Breakeven (PEV), Expected Value (EV) | PEV_TOO_LOW |
| 2026-08-21 | 10:13 | BUY_CE | +2.00R | 51.9 | 2.30 | 0.00 | Expected Value (EV), Regime-Aware Grade | REJECTED_REGIME_GRADE_B+_IN_SQUEEZE |
| 2026-08-21 | 10:18 | BUY_CE | +2.00R | 43.1 | 2.30 | 0.00 | Cost/Breakeven (PEV), Expected Value (EV), Regime-Aware Grade | PEV_TOO_LOW |
| 2026-08-21 | 10:29 | BUY_PE | +2.00R | 31.6 | 2.33 | 0.73 | Confidence, Cost/Breakeven (PEV), Expected Value (EV), Regime-Aware Grade | LOW_CONFIDENCE |
| 2026-08-21 | 10:34 | BUY_PE | +2.00R | 45.1 | 2.20 | 0.86 | Expected Value (EV) | REJECTED_LOW_EV_+0.20R |
| 2026-08-21 | 10:42 | BUY_PE | +2.00R | 41.7 | 2.48 | 0.58 | Cost/Breakeven (PEV), Expected Value (EV), Regime-Aware Grade | PEV_TOO_LOW |
| 2026-08-21 | 10:47 | BUY_PE | +2.00R | 69.8 | 2.06 | 0.52 | Strike Policy: Unknown Regime | Execution Blocked: Strike Policy Blocked: Unknown  |
| 2026-08-21 | 10:52 | BUY_PE | +2.00R | 49.9 | 2.11 | 0.20 | Expected Value (EV), Structure Reset | REJECTED_LOW_EV_+0.33R |
| 2026-08-21 | 10:57 | BUY_PE | +2.00R | 37.8 | 2.14 | 0.00 | Confidence, Cost/Breakeven (PEV), Expected Value (EV), Regime-Aware Grade, Structure Reset | LOW_CONFIDENCE |
| 2026-08-21 | 11:24 | BUY_PE | +2.00R | 53.8 | 2.28 | 0.61 | Expected Value (EV), Regime-Aware Grade | REJECTED_REGIME_GRADE_B+_IN_SQUEEZE |
| 2026-08-21 | 11:34 | BUY_PE | +2.00R | 40.9 | 2.14 | 0.00 | Cost/Breakeven (PEV), Expected Value (EV), Regime-Aware Grade | PEV_TOO_LOW |
| 2026-08-21 | 11:39 | BUY_PE | +2.00R | 44.0 | 2.00 | 0.00 | Cost/Breakeven (PEV), Expected Value (EV), Regime-Aware Grade | PEV_TOO_LOW |
| 2026-08-21 | 11:44 | BUY_PE | +2.00R | 53.5 | 2.14 | 0.00 | Expected Value (EV), Regime-Aware Grade | REJECTED_REGIME_GRADE_B+_IN_SQUEEZE |
| 2026-08-21 | 12:10 | BUY_CE | +2.00R | 40.2 | 3.57 | 0.85 | Chop Zone, Confidence, Cost/Breakeven (PEV), Expected Value (EV), Structure | CHOP_ZONE_ACTIVE |
| 2026-08-21 | 12:15 | BUY_CE | +2.00R | 41.5 | 3.84 | 0.58 | Chop Zone, Confidence, Cost/Breakeven (PEV), Expected Value (EV), Structure | CHOP_ZONE_ACTIVE |
| 2026-08-21 | 12:20 | BUY_CE | +2.00R | 62.1 | 3.50 | 0.92 | Structure | BAD_STRUCTURE_UNDEFINED |
| 2026-08-21 | 13:02 | BUY_CE | +2.00R | 54.0 | 3.49 | 0.93 | Expected Value (EV), Regime-Aware Grade, Structure Reset | REJECTED_REGIME_GRADE_B+_IN_SQUEEZE |
| 2026-08-21 | 14:04 | BUY_CE | +2.00R | 44.5 | 4.42 | 0.00 | Cost/Breakeven (PEV), Expected Value (EV), Regime-Aware Grade, Structure | BAD_STRUCTURE_EXPANDING |
| 2026-08-21 | 14:09 | BUY_CE | +2.00R | 44.8 | 4.40 | 0.00 | Cost/Breakeven (PEV), Expected Value (EV), Regime-Aware Grade, Structure | BAD_STRUCTURE_EXPANDING |
| 2026-08-21 | 15:02 | BUY_CE | +2.00R | 32.6 | 3.48 | 0.44 | Confidence, Cost/Breakeven (PEV), Expected Value (EV), Regime-Aware Grade | LOW_CONFIDENCE |
| 2026-08-21 | 15:10 | BUY_CE | +2.00R | 50.3 | 3.92 | 0.00 | Strike Policy: Unknown Regime | Weekend Buffer: no new trades after 15:10:00 on Fr |
| 2026-08-24 | 10:44 | BUY_PE | +2.00R | 38.8 | 3.09 | 0.00 | Cost/Breakeven (PEV), Expected Value (EV), Regime-Aware Grade, Structure | BAD_STRUCTURE_EXPANDING |
| 2026-08-24 | 10:50 | BUY_PE | +2.00R | 59.3 | 4.24 | 0.00 | Regime-Aware Grade, Structure | BAD_STRUCTURE_EXPANDING |
| 2026-08-24 | 10:56 | BUY_PE | +2.00R | 58.0 | 4.10 | 0.00 | Regime-Aware Grade, Structure | BAD_STRUCTURE_EXPANDING |
| 2026-08-24 | 11:22 | BUY_PE | +2.00R | 58.5 | 3.16 | 0.00 | Structure Reset | REJECTED_SAME_STRUCTURAL_TREND |
| 2026-08-24 | 11:27 | BUY_PE | +2.00R | 61.5 | 2.17 | 0.00 | Structure Reset | REJECTED_SAME_STRUCTURAL_TREND |
| 2026-08-24 | 11:32 | BUY_PE | +2.00R | 49.9 | 2.15 | 0.88 | Expected Value (EV), Structure Reset | REJECTED_LOW_EV_+0.33R |
| 2026-08-24 | 11:44 | BUY_PE | +2.00R | 60.5 | 3.12 | 0.85 | Structure Reset | REJECTED_SAME_STRUCTURAL_TREND |
| 2026-08-24 | 11:46 | BUY_PE | +2.00R | 45.3 | 2.35 | 0.00 | Chop Zone, Expected Value (EV) | CHOP_ZONE_ACTIVE |
| 2026-08-24 | 11:54 | BUY_PE | +2.00R | 32.7 | 3.39 | 0.39 | Chop Zone, Cost/Breakeven (PEV), Expected Value (EV), Regime-Aware Grade, Structure Reset | CHOP_ZONE_ACTIVE |
| 2026-08-24 | 12:21 | BUY_PE | +2.00R | 42.5 | 2.02 | 0.00 | Cost/Breakeven (PEV), Expected Value (EV), Regime-Aware Grade | PEV_TOO_LOW |
| 2026-08-24 | 12:34 | BUY_PE | +2.00R | 58.0 | 2.70 | 0.00 | Regime-Aware Grade, Structure Reset | REJECTED_REGIME_GRADE_B+_IN_SQUEEZE |
| 2026-08-24 | 12:40 | BUY_PE | +2.00R | 38.3 | 2.36 | 0.28 | Cost/Breakeven (PEV), Expected Value (EV), Regime-Aware Grade, Structure Reset | PEV_TOO_LOW |
| 2026-08-24 | 12:45 | BUY_PE | +2.00R | 51.2 | 2.37 | 0.27 | Expected Value (EV), Regime-Aware Grade, Structure Reset | REJECTED_REGIME_GRADE_B+_IN_SQUEEZE |
| 2026-08-24 | 12:53 | BUY_PE | +2.00R | 40.6 | 2.64 | 0.00 | Cost/Breakeven (PEV), Expected Value (EV), Regime-Aware Grade, Structure Reset | PEV_TOO_LOW |
| 2026-08-24 | 13:08 | BUY_CE | +2.00R | 59.1 | 2.38 | 0.00 | Structure Reset | REJECTED_SAME_STRUCTURAL_TREND |
| 2026-08-24 | 13:29 | BUY_PE | +2.00R | 36.3 | 2.10 | 0.00 | Chop Zone, Cost/Breakeven (PEV), Expected Value (EV), Regime-Aware Grade, Structure | CHOP_ZONE_ACTIVE |
| 2026-08-24 | 13:32 | BUY_PE | +2.00R | 54.6 | 2.60 | 0.00 | Expected Value (EV), Regime-Aware Grade, Structure, Structure Reset | BAD_STRUCTURE_EXPANDING |
| 2026-08-24 | 14:16 | BUY_CE | +2.00R | 66.8 | 2.43 | 0.00 | Regime-Aware Grade, Structure Reset | REJECTED_REGIME_GRADE_B+_IN_SQUEEZE |
| 2026-08-24 | 14:31 | BUY_PE | +2.00R | 54.1 | 2.24 | 0.78 | Expected Value (EV), Regime-Aware Grade | REJECTED_REGIME_GRADE_B+_IN_SQUEEZE |
| 2026-08-24 | 14:36 | BUY_PE | +2.00R | 42.8 | 3.19 | 0.57 | Cost/Breakeven (PEV), Expected Value (EV), Regime-Aware Grade | PEV_TOO_LOW |
| 2026-08-24 | 14:59 | BUY_PE | +2.00R | 47.5 | 3.16 | 0.59 | Expected Value (EV), Regime-Aware Grade | REJECTED_REGIME_GRADE_B+_IN_SQUEEZE |
| 2026-08-25 | 13:32 | BUY_CE | +2.00R | 68.1 | 2.63 | 0.00 | Structure Reset | REJECTED_SAME_STRUCTURAL_TREND |
| 2026-08-25 | 13:37 | BUY_CE | +2.00R | 41.7 | 3.01 | 0.00 | Cost/Breakeven (PEV), Expected Value (EV), Regime-Aware Grade, Structure Reset | PEV_TOO_LOW |
| 2026-08-25 | 14:11 | BUY_CE | +2.00R | 55.5 | 3.61 | 0.00 | Expected Value (EV), Regime-Aware Grade, Structure Reset | REJECTED_REGIME_GRADE_B+_IN_SQUEEZE |
| 2026-08-25 | 14:44 | BUY_CE | +2.00R | 78.9 | 2.74 | 0.00 | Structure Reset | REJECTED_SAME_STRUCTURAL_TREND |
| 2026-08-25 | 14:59 | BUY_CE | +2.00R | 77.6 | 10.70 | 0.28 | Structure Reset | REJECTED_SAME_STRUCTURAL_TREND |
| 2026-08-25 | 15:04 | BUY_CE | +2.00R | 84.2 | 10.51 | 0.20 | Structure Reset | REJECTED_SAME_STRUCTURAL_TREND |
| 2026-08-25 | 15:09 | BUY_CE | +2.00R | 70.0 | 11.80 | 0.00 | Structure Reset | REJECTED_SAME_STRUCTURAL_TREND |
| 2026-08-25 | 15:14 | BUY_CE | +2.00R | 66.9 | 9.62 | 0.00 | Structure Reset | REJECTED_SAME_STRUCTURAL_TREND |
| 2026-08-26 | 13:19 | BUY_CE | +2.00R | 46.8 | 2.38 | 0.63 | Chop Zone, Confluence, Expected Value (EV), Regime-Aware Grade, Structure | CHOP_ZONE_ACTIVE |
| 2026-08-26 | 13:53 | BUY_CE | +2.00R | 45.6 | 2.47 | 0.00 | Cost/Breakeven (PEV), Expected Value (EV), Regime-Aware Grade | PEV_TOO_LOW |
| 2026-08-27 | 12:08 | BUY_CE | +2.00R | 35.2 | 3.19 | 0.00 | Cost/Breakeven (PEV), Expected Value (EV), Regime-Aware Grade, Structure Reset | PEV_TOO_LOW |
| 2026-08-27 | 12:49 | BUY_CE | +2.00R | 60.3 | 2.21 | 0.00 | Strike Policy: Unknown Regime | Execution Blocked: Strike Policy Blocked: Unknown  |
| 2026-08-27 | 13:11 | BUY_CE | +2.00R | 48.8 | 2.97 | 0.00 | Expected Value (EV), Regime-Aware Grade | REJECTED_REGIME_GRADE_B+_IN_SQUEEZE |
| 2026-08-25 | 11:54 | BUY_CE | +1.99R | 49.9 | 2.46 | 0.00 | Expected Value (EV), Regime-Aware Grade | REJECTED_REGIME_GRADE_B+_IN_SQUEEZE |
| 2026-08-25 | 13:27 | BUY_CE | +1.99R | 72.1 | 2.48 | 0.00 | Structure Reset | REJECTED_SAME_STRUCTURAL_TREND |
| 2026-08-25 | 14:04 | BUY_CE | +1.99R | 41.1 | 2.70 | 0.00 | Cost/Breakeven (PEV), Expected Value (EV) | PEV_TOO_LOW |
| 2026-08-25 | 14:29 | BUY_CE | +1.99R | 42.3 | 2.86 | 0.00 | Cost/Breakeven (PEV), Expected Value (EV), Regime-Aware Grade, Structure Reset | PEV_TOO_LOW |
| 2026-08-25 | 14:39 | BUY_CE | +1.99R | 49.7 | 2.25 | 0.00 | Expected Value (EV), Structure Reset | REJECTED_LOW_EV_+0.32R |
| 2026-08-26 | 13:29 | BUY_CE | +1.99R | 32.2 | 2.31 | 0.00 | Chop Zone, Confidence, Cost/Breakeven (PEV), Expected Value (EV), Regime-Aware Grade, Structure | CHOP_ZONE_ACTIVE |
| 2026-08-26 | 13:35 | BUY_CE | +1.99R | 37.0 | 2.31 | 0.00 | Cost/Breakeven (PEV), Expected Value (EV), Regime-Aware Grade, Structure | BAD_STRUCTURE_EXPANDING |
| 2026-08-26 | 14:17 | BUY_CE | +1.99R | 30.2 | 2.51 | 0.00 | Confidence, Cost/Breakeven (PEV), Expected Value (EV), Regime-Aware Grade | LOW_CONFIDENCE |
| 2026-08-27 | 10:59 | BUY_CE | +1.99R | 79.5 | 2.40 | 0.00 | Structure Reset | REJECTED_SAME_STRUCTURAL_TREND |
| 2026-08-27 | 11:20 | BUY_CE | +1.99R | 69.5 | 2.46 | 0.23 | Structure Reset | REJECTED_SAME_STRUCTURAL_TREND |
| 2026-08-27 | 11:25 | BUY_CE | +1.99R | 36.1 | 3.72 | 0.00 | Cost/Breakeven (PEV), Expected Value (EV), Regime-Aware Grade, Structure Reset | PEV_TOO_LOW |
| 2026-08-27 | 12:21 | BUY_CE | +1.99R | 45.2 | 2.77 | 0.00 | Cost/Breakeven (PEV), Expected Value (EV), Regime-Aware Grade, Structure, Structure Reset | BAD_STRUCTURE_EXPANDING |
| 2026-08-27 | 14:18 | BUY_CE | +1.99R | 50.7 | 2.15 | 0.00 | Expected Value (EV), Regime-Aware Grade, Structure | BAD_STRUCTURE_EXPANDING |
| 2026-08-27 | 14:23 | BUY_CE | +1.99R | 63.4 | 2.00 | 0.64 | Structure | BAD_STRUCTURE_EXPANDING |
| 2026-08-25 | 13:21 | BUY_CE | +1.98R | 65.4 | 2.34 | 0.08 | Structure Reset | REJECTED_SAME_STRUCTURAL_TREND |
| 2026-08-27 | 11:30 | BUY_CE | +1.98R | 52.9 | 2.73 | 0.00 | Expected Value (EV), Structure Reset | REJECTED_LOW_EV_+0.41R |
| 2026-08-27 | 12:39 | BUY_CE | +1.98R | 60.4 | 2.64 | 0.29 | Regime-Aware Grade | REJECTED_REGIME_GRADE_B+_IN_SQUEEZE |

---

## 6. Multi-Gate Overlap Matrix

*Cell (i,j) = number of candidates where both gate i and gate j failed.*  
*Diagonal = total failures for that gate.*

| Gate | Chop | Confidence | Confluence | PEV | EV | RegimeGrade | Structure | StructReset |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Chop | 17 | 9 | 2 | 13 | 17 | 11 | 10 | 6 |
| Confidence | 9 | 32 | 0 | 32 | 32 | 28 | 6 | 10 |
| Confluence | 2 | 0 | 2 | 0 | 2 | 2 | 2 | 0 |
| PEV | 13 | 32 | 0 | 116 | 116 | 105 | 27 | 38 |
| EV | 17 | 32 | 2 | 116 | 187 | 148 | 45 | 59 |
| RegimeGrade | 11 | 28 | 2 | 105 | 148 | 170 | 44 | 48 |
| Structure | 10 | 6 | 2 | 27 | 45 | 44 | 63 | 17 |
| StructReset | 6 | 10 | 0 | 38 | 59 | 48 | 17 | 108 |

---

## 7. Diagnostic Assessment

### Best Single-Gate Ablation

**V2 − StructReset**  
- Unlocks 44 candidates  
- Net R: +31.01R  
- Win Rate: 56.8%  
- Profit Factor: 2.63  

### Best Cumulative Relaxation (OMS-Constrained)

**V2 − StructReset − Structure − PEV − Chop − Confidence − Confluence − RegimeGrade**  
- Executable trades: 51  
- Net R: +24.99R  
- Win Rate: 49.0%  
- Profit Factor: 2.00  

### Preliminary Classification

> 🟢 **V2 appears too restrictive.** A targeted relaxation produces positive expectancy
> with meaningful trade frequency. Candidate for V2.1 revision after prospective validation.

---

## 8. Sanity Checks

| Check | Status |
| :--- | :--- |
| Baseline matches known state (3 approved) | ✅ PASS |
| All monotonicity checks | ✅ PASS |

---
*Report generated at 2026-08-27 20:48:51 by `tools/gate_ablation_analysis.py`*  
*CODE FREEZE: ACTIVE — This is a read-only diagnostic. No production code was modified.*
