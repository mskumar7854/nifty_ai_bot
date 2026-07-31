# Pre-Tuning Diagnostics Report

## 1. Missing Data Detection
Total Snapshots: 141
Snapshots using fallback friction (Missing Tick Data): 141

## 2. Confluence Component Distribution
Averages by Total Score Bin:
| Total Score | Trend | Momentum | Options | Structure |
| --- | --- | --- | --- | --- |
| 30-35 | 0.0 | 0.0 | 0.0 | 0.0 |
| 35-40 | 0.0 | 0.0 | 0.0 | 0.0 |
| 40-45 | 0.0 | 0.0 | 0.0 | 0.0 |
| 45-50 | 0.0 | 0.0 | 0.0 | 0.0 |
| 50-55 | 0.0 | 0.0 | 0.0 | 0.0 |
| 55-60 | 0.0 | 0.0 | 0.0 | 0.0 |
| 60-65 | 0.0 | 0.0 | 0.0 | 0.0 |
| 65-70 | 0.0 | 0.0 | 0.0 | 0.0 |
| 70-75 | 0.0 | 0.0 | 0.0 | 0.0 |
| 75-80 | 0.0 | 0.0 | 0.0 | 0.0 |
| 80-85 | 0.0 | 0.0 | 0.0 | 0.0 |
| 85-90 | 0.0 | 0.0 | 0.0 | 0.0 |
| 90-95 | 0.0 | 0.0 | 0.0 | 0.0 |
| 95-100 | 0.0 | 0.0 | 0.0 | 0.0 |

## 3. Maximum Possible Score Analysis
- Maximum Observed Trend Score: 0.0
- Maximum Observed Momentum Score: 0.0
- Maximum Observed Options Score: 0.0
- Maximum Observed Structure Score: 0.0
- **Conclusion on Confluence**: If agent scores max out significantly below 100, the threshold must be lowered to reflect mathematical reality.

## 4. EV Breakdown & Dependency Analysis
| EV Range (R) | Avg Raw Conf | Avg Calib P(win) | Avg Friction |
| --- | --- | --- | --- |
| -2.0 to -1.0 | 0.0% | 0.0% | 0.0R |
| -1.0 to -0.5 | 0.0% | 0.0% | 0.0R |
| -0.5 to 0.0 | 0.0% | 0.0% | 0.0R |
| 0.0 to 0.2 | 0.0% | 0.0% | 0.0R |
| 0.2 to 0.5 | 54.33% | 52.0% | 0.0R |
| 0.5 to 1.0 | 52.51% | 56.00000000000001% | 0.0R |

## 5. Sample Per-Trade Diagnostics
| Trade ID | Raw Conf | Calib P(win) | Confluence | EV (R) | Final Decision |
| --- | --- | --- | --- | --- | --- |
| SNAP_20260522_142005_2882 | 37.6% | 0.55 | 37.6 | 0.52R | Rejected (LOW_CONFIDENCE) |
| SNAP_20260522_142210_0463 | 42.4% | 0.55 | 42.4 | 0.52R | Rejected (LOW_CONFIDENCE) |
| SNAP_20260522_142301_9989 | 42.1% | 0.55 | 42.1 | 0.52R | Rejected (LOW_CONFIDENCE) |
| SNAP_20260527_102801_5738 | 47.7% | 0.55 | 47.7 | 0.52R | Rejected (LOW_CONFIDENCE) |
| SNAP_20260601_105001_3448 | 56.1% | 0.55 | 56.1 | 0.52R | Rejected (LOW_CONFLUENCE) |
| SNAP_20260601_105101_5245 | 50.7% | 0.55 | 50.7 | 0.52R | Rejected (LOW_CONFIDENCE) |
| SNAP_20260601_105200_8486 | 60.4% | 0.55 | 60.4 | 0.52R | Rejected (LOW_CONFLUENCE) |
| SNAP_20260601_105300_8795 | 60.9% | 0.55 | 60.9 | 0.52R | Rejected (LOW_CONFLUENCE) |
| SNAP_20260601_105401_4975 | 48.6% | 0.55 | 48.6 | 0.52R | Rejected (LOW_CONFIDENCE) |
| SNAP_20260601_105501_5863 | 48.5% | 0.55 | 48.5 | 0.52R | Rejected (LOW_CONFIDENCE) |
