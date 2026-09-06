# 🔬 Shadow Variant Experiment Report

> **PRELIMINARY DATA** — Simulated counterfactual outcomes.
> *Do not confuse 'Qualified Candidates' with actual live executions.*

## Policy Qualification vs. Execution

| Variant | Description | Qualified | Executed (OMS) | Net R (Exec) | Win% (Exec) | Main Blocker |
|---------|-------------|----------:|---------------:|-------------:|------------:|--------------|
| V2-Control      | Immutable control |         3 |              3 |        0.00R |       33.3% | Cost/Breakeven (PEV) |
| V2.1-NoStructReset | Primary hypothesis |        44 |             27 |       15.01R |       51.9% | Cost/Breakeven (PEV) |
| V2.2-NoStructReset-NoStruct | Test structural o... |        56 |             37 |       18.00R |       48.6% | Cost/Breakeven (PEV) |
| V2.3-NoStructReset-NoRegimeGrade | Test interaction ... |        60 |             39 |       18.00R |       48.7% | Cost/Breakeven (PEV) |
| V2.4-SweetSpot  | Broader relaxation |        78 |             51 |       24.99R |       49.0% | Cost/Breakeven (PEV) |
| V2.5-NoStructReset-NoChop | Test whether Chop... |        44 |             27 |       15.01R |       51.9% | Cost/Breakeven (PEV) |
| V2.6-NoStructReset-NoPEV | Confirm PEV redun... |        44 |             27 |       15.01R |       51.9% | Regime-Aware Grade |

## Cumulative R by Session

| Session | V2-Control | V2.1-NoStructReset | V2.2-NoStructReset-NoStruct | V2.3-NoStructReset-NoRegimeGrade | V2.4-SweetSpot | V2.5-NoStructReset-NoChop | V2.6-NoStructReset-NoPEV |
|--------|------------|--------------------|-----------------------------|----------------------------------|----------------|---------------------------|--------------------------|
| 2026-08-19 |       0.00R |               1.00R |                        2.00R |                            -1.00R |          -1.00R |                      1.00R |                     1.00R |
| 2026-08-20 |       0.00R |               5.00R |                        7.00R |                             4.00R |           7.00R |                      5.00R |                     5.00R |
| 2026-08-21 |       0.00R |               4.00R |                        7.00R |                             3.00R |           7.00R |                      4.00R |                     4.00R |
| 2026-08-24 |       0.00R |               7.00R |                       10.00R |                             8.00R |          14.00R |                      7.00R |                     7.00R |
| 2026-08-25 |       0.00R |              15.01R |                       17.01R |                            17.02R |          23.02R |                     15.01R |                    15.01R |
| 2026-08-26 |       0.00R |              14.01R |                       16.01R |                            16.02R |          22.02R |                     14.01R |                    14.01R |
| 2026-08-27 |       0.00R |              15.01R |                       18.00R |                            18.00R |          24.99R |                     15.01R |                    15.01R |

## Variant Details

### V2-Control
*Immutable control — identical to frozen V2*

- **Qualified Candidates:** 3 (W: 1, L: 2)
- **Counterfactual Executions:** 3 (W: 1, L: 2)
- **Net R:** 0.00R
- **Win Rate:** 33.3%
- **Profit Factor:** 1.00
- **Avg R / Trade:** 0.00R
- **Median R:** -1.00R
- **Max Drawdown (R):** -1.00R
- **Max Consec Losses:** 1

Top Rejection Reasons:
- Cost/Breakeven (PEV): 62
- Structure: 51
- Regime-Aware Grade: 44

### V2.1-NoStructReset
*Primary hypothesis — remove dominant over-filter*

- **Qualified Candidates:** 44 (W: 25, L: 19)
- **Counterfactual Executions:** 27 (W: 14, L: 13)
- **Net R:** 15.01R
- **Win Rate:** 51.9%
- **Profit Factor:** 2.15
- **Avg R / Trade:** 0.56R
- **Median R:** 1.99R
- **Max Drawdown (R):** -1.00R
- **Max Consec Losses:** 3

Top Rejection Reasons:
- Cost/Breakeven (PEV): 62
- Structure: 51
- Regime-Aware Grade: 44

### V2.2-NoStructReset-NoStruct
*Test structural over-filtering*

- **Qualified Candidates:** 56 (W: 30, L: 25)
- **Counterfactual Executions:** 37 (W: 18, L: 19)
- **Net R:** 18.00R
- **Win Rate:** 48.6%
- **Profit Factor:** 2.00
- **Avg R / Trade:** 0.49R
- **Median R:** 0.00R
- **Max Drawdown (R):** -1.00R
- **Max Consec Losses:** 4

Top Rejection Reasons:
- Cost/Breakeven (PEV): 80
- Regime-Aware Grade: 63
- Expected Value (EV): 26

### V2.3-NoStructReset-NoRegimeGrade
*Test interaction with regime grading*

- **Qualified Candidates:** 60 (W: 31, L: 29)
- **Counterfactual Executions:** 39 (W: 19, L: 20)
- **Net R:** 18.00R
- **Win Rate:** 48.7%
- **Profit Factor:** 1.90
- **Avg R / Trade:** 0.46R
- **Median R:** -1.00R
- **Max Drawdown (R):** -1.00R
- **Max Consec Losses:** 4

Top Rejection Reasons:
- Cost/Breakeven (PEV): 62
- Expected Value (EV): 52
- Structure: 51

### V2.4-SweetSpot
*Broader relaxation — ablation sweet spot*

- **Qualified Candidates:** 78 (W: 39, L: 38)
- **Counterfactual Executions:** 51 (W: 25, L: 26)
- **Net R:** 24.99R
- **Win Rate:** 49.0%
- **Profit Factor:** 2.00
- **Avg R / Trade:** 0.49R
- **Median R:** 0.00R
- **Max Drawdown (R):** -1.00R
- **Max Consec Losses:** 4

Top Rejection Reasons:
- Cost/Breakeven (PEV): 80
- Expected Value (EV): 67
- Confidence: 23

### V2.5-NoStructReset-NoChop
*Test whether Chop compounds the over-filter*

- **Qualified Candidates:** 44 (W: 25, L: 19)
- **Counterfactual Executions:** 27 (W: 14, L: 13)
- **Net R:** 15.01R
- **Win Rate:** 51.9%
- **Profit Factor:** 2.15
- **Avg R / Trade:** 0.56R
- **Median R:** 1.99R
- **Max Drawdown (R):** -1.00R
- **Max Consec Losses:** 3

Top Rejection Reasons:
- Cost/Breakeven (PEV): 63
- Structure: 55
- Regime-Aware Grade: 44

### V2.6-NoStructReset-NoPEV
*Confirm PEV redundancy hypothesis*

- **Qualified Candidates:** 44 (W: 25, L: 19)
- **Counterfactual Executions:** 27 (W: 14, L: 13)
- **Net R:** 15.01R
- **Win Rate:** 51.9%
- **Profit Factor:** 2.15
- **Avg R / Trade:** 0.56R
- **Median R:** 1.99R
- **Max Drawdown (R):** -1.00R
- **Max Consec Losses:** 3

Top Rejection Reasons:
- Regime-Aware Grade: 101
- Structure: 51
- Expected Value (EV): 29
