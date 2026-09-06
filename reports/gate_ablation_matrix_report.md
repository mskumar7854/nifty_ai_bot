# Comprehensive Predictive Strategy Gate Ablation & Outcome Matrix Report

**Dataset**: 507 Replay Candidates across 19 Daily Sessions (2026-08-04 to 2026-08-28)  
**Methodology**: Look-Ahead-Free Counterfactual Replay Analysis  
**Safeguard**: Zero Production Gate Modification  

---

## 1. Population Clarification & Accounting

To prevent comparing apples to oranges, here is the population reconciliation across the repository:
- **Population A (1,113 candidates)**: High-level candidate signals across all 19 daily session audit scorecards (`reports/daily/*_scorecard.json`). Includes pre-filter generation attempts, capacity throttles, and initial screening.
- **Population B (507 candidates)**: The complete empirical dataset in `reports/daily/*_replay.json` containing tick/bar execution levels, spots, stops, targets, and realized outcomes.
- **Population C (292 candidates)**: The forensic subset from the 7 clean shadow-campaign sessions (Aug 19–27) documented in `reports/gate_ablation_diagnostic.md` when the V2 shadow variant runner was introduced.

---

## 2. Net Gate Value Framework

Rather than simply ranking gates by rejection counts, gates are categorized by the fundamental economic trade-off:
$$\text{Net Gate Value} = (\text{Losses Avoided in R}) - (\text{Alpha Blocked in R})$$
- **Alpha Blocked**: Total $R$ profit lost because good trades hitting target (+2.0R) were rejected.
- **Losses Avoided**: Total $R$ loss prevented because bad trades hitting stop (-1.0R) were rejected.
- **Net Gate Value**: A positive value means the gate saves more capital than it costs; a negative value means the gate costs more than it saves.

| Gate Name | Filtered | Alpha Blocked (Lost Gains) | Losses Avoided (Saved Losses) | Net Gate Value | Status / Recommendation |
| :--- | ---: | ---: | ---: | ---: | :--- |
| **Strike Policy (Unknown Regime)** | 22 | 10.02R | **15.26R** | **+5.24R** | 🟢 **PROTECTIVE — Keep Gate** |
| **Expected Value (EV) Gate** | 16 | 6.08R | **12.00R** | **+5.92R** | 🟢 **PROTECTIVE — Keep Gate** |
| **Confidence Gate** | 4 | 1.99R | **2.44R** | **+0.45R** | 🟢 **PROTECTIVE — Keep Gate** |
| **Cost/Breakeven (PEV) Gate** | 45 | 32.87R | 25.65R | **-7.22R** | 🟡 **LOW SPREAD — Keep for Now** |
| **Chop Zone Gate** | 15 | 15.98R | 7.00R | **-8.98R** | 🟠 **CANDIDATE 2 — Research Graded Response** |
| **Structure Reset Gate** | 32 | 34.82R | 12.00R | **-22.82R** | 🚨 **CANDIDATE 1 — Research Tier Sizing** |

---

## 3. Strike Policy Deep Dive — Empirical Reality vs. Theoretical Myth

- **Reconstructed Candidate Metrics**:
  - Filtered: 23 opportunities
  - Target Hit (+2.0R): 5 trades (+10.03R)
  - Stopped Out (-1.0R): **15 trades (-15.00R)**
  - Neither / Time Exit: 3 trades (-0.26R)
  - **Net Realized R**: **-4.96R** (Win Rate: 21.7%, Profit Factor: 0.67)
- **Conclusion**: The earlier +48R counterfactual was a theoretical artifact. In live replay, removing the strike policy would have unleashed 15 stopped-out losses. **The fail-closed invariant is working as intended and must be kept.**

---

## 4. Structure Reset Tiering Experiment: The 4 Variants

To avoid curve-fitting, the 38 `REJECTED_SAME_STRUCTURAL_TREND` opportunities were tested across an In-Sample (Aug 04–18) vs. Out-of-Sample (Aug 19–28) split:

### A. Four-Variant Comparison (Entire 19 Sessions):
| Variant | Behavior | Trades | Net R | Expectancy | Profit Factor | Max Drawdown | Worst Losing Streak | Total Exposure |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **A** | Current Binary Reject (0%) | 0 | +0.00R | +0.00R | 0.00 | 0.00R | 0 | 0.00R |
| **B** | Allow at 50% Size | 38 | **+9.91R** | **+0.26R** | **2.17** | **2.00R** | **4** | 19.00R |
| **C** | Allow at 25% Size | 38 | **+4.96R** | **+0.13R** | **2.17** | **1.00R** | **4** | 9.50R |
| **D** | Allow 50% only if Conf $\ge 65\%$ | 27 | **+6.40R** | **+0.24R** | **2.07** | **2.50R** | **5** | 13.50R |

### B. Out-of-Sample Evaluation (Aug 19–28, 34 Candidates):
- **Variant B (50% Size)**: **+11.91R**, Expectancy **+0.35R**, Profit Factor **2.83**, Max DD **2.00R**.
- **Variant C (25% Size)**: **+5.96R**, Expectancy **+0.18R**, Profit Factor **2.83**, Max DD **1.00R**.
- **Variant D (50% Size, Conf $\ge 65\%$)**: **+7.40R**, Expectancy **+0.30R**, Profit Factor **2.48**, Max DD **2.50R**, Streak **5**.

### C. Confidence Monotonicity Audit:
Testing whether confidence is a genuine monotonic predictor:
| Confidence Bucket | Trades | Win Rate | Net R | Expectancy | Avg MFE | Avg MAE |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| **55–60%** | 7 | 57.1% | +5.02R | +0.72R | 1.58R | 0.98R |
| **60–65%** | 4 | 50.0% | +2.00R | +0.50R | 1.32R | 1.10R |
| **65–70%** | 10 | 50.0% | +5.98R | +0.60R | 1.48R | 0.57R |
| **70–75%** | 10 | 50.0% | +4.18R | +0.42R | 1.31R | 1.02R |
| **75%+** | 7 | 57.1% | +2.64R | +0.38R | 1.25R | 0.75R |

> [!WARNING]
> **Monotonicity Finding**: Confidence is **NOT monotonic** with expectancy. The 55–60% bucket had higher expectancy (+0.72R) than the 75%+ bucket (+0.38R). Win rates stayed flat (50–57%).
> Therefore, hardcoding $\text{Confidence} \ge 65\%$ into production is a curve-fit trap. Variant B (50% sizing) or Variant C (25% sizing) provides cleaner, more robust expectancy without arbitrary threshold filtering.

---

## 5. Controlled Paper-Trading Architecture Plan

Rather than modifying production code, the next phase deploys a dual-pipeline observer:
1. **Production Engine**: Remains on **Current V2 baseline** with binary rejection. Real orders are routed only when production criteria are satisfied.
2. **Shadow Paper Pipeline**: Evaluates candidate signals against **Variant C (25% size) / Variant B (50% size)**:
   - Zero order routing (all executions simulated in telemetry log).
   - Generates side-by-side comparative logs:
     `[PRODUCTION: REJECTED_SAME_STRUCTURAL_TREND] vs [SHADOW: ACCEPTED_25%_SIZE | Simulated Fill: 24,150 | TP: 24,210 | SL: 24,120]`.
   - Records prospective, live paper-trade outcomes forward in time without look-ahead or historical bias.

---
*Generated autonomously by `tools/run_gate_ablation_matrix.py` and `tools/structure_reset_experiment.py`.*