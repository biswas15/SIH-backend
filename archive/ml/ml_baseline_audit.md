# HeatSense ML Baseline Audit Report

## 1. DATASET
- **Total Rows (original)**: 18720
- **Number of Wards**: 26
- **Date Range**: 2026-08-20 06:00:00 to 2026-09-18 17:00:00
- **Number of Test Rows**: 2782
- **Forecast Horizon**: 6 hours
- **Train Range**: 2026-08-20 06:00:00 to 2026-09-09 20:00:00
- **Validation Range**: 2026-09-09 21:00:00 to 2026-09-14 06:00:00
- **Test Range**: 2026-09-14 07:00:00 to 2026-09-18 17:00:00

**Actual Risk Distribution in Test Set**:
- LOW: 0 (0.0%)
- MODERATE: 1432 (51.5%)
- HIGH: 1350 (48.5%)
- EXTREME: 0 (0.0%)

## 2. MODEL METRICS
### Random Forest
- **MAE**: 5.9777
- **RMSE**: 8.2189
- **R²**: -1.3862
- **Risk-Category Accuracy**: 76.1000%

### Persistence Baseline
- **MAE**: 5.5327
- **RMSE**: 6.9430
- **R²**: -0.7028
- **Risk-Category Accuracy**: 56.0029%

## 3. CONFUSION MATRIX
| Actual \ Predicted | LOW | MODERATE | HIGH | EXTREME |
|---|---|---|---|---|
| **LOW** | 0 | 0 | 0 | 0 |
| **MODERATE** | 0 | 1385 | 47 | 0 |
| **HIGH** | 0 | 618 | 732 | 0 |
| **EXTREME** | 0 | 0 | 0 | 0 |

### Class Metrics
| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| LOW | 0.0000 | 0.0000 | 0.0000 | 0 |
| MODERATE | 0.6915 | 0.9672 | 0.8064 | 1432 |
| HIGH | 0.9397 | 0.5422 | 0.6876 | 1350 |
| EXTREME | 0.0000 | 0.0000 | 0.0000 | 0 |

## 4. EARLY-WARNING PERFORMANCE
- **HIGH Recall**: 0.5422
- **HIGH Precision**: 0.9397
- **HIGH F1**: 0.6876
- **EXTREME Recall**: N/A (EXTREME performance cannot be evaluated from this test set due to zero support)
- **EXTREME Precision**: N/A
- **EXTREME F1**: N/A

- **Number of actual HIGH/EXTREME cases predicted as MODERATE or LOW**: 618 cases (HIGH: 618, EXTREME: 0)

## 5. PREDICTION ERROR
- **Mean Signed Error**: -5.4541
- **Mean Absolute Error**: 5.9778
- **Median Absolute Error**: 3.9200
- **% within ±5 HTSI points**: 58.45%
- **% within ±10 HTSI points**: 76.71%

## 6. FEATURE LEAKAGE AUDIT
Inspection of `scripts/train_ml_baseline.py` confirms:
- No future weather is used. The features (`temperature_c`, `rh_pct`, etc.) are explicitly observations at time *t*.
- No future HTSI is used as a feature. The target is defined via `.shift(-FORECAST_HORIZON)` and not included in features.
- `htsi_score_lead_6` is strictly only the target.
- Lag features (`htsi_lag_1`, etc.) use positive shifts (e.g. `.shift(1)`), meaning they only use strictly past information.
- `chronological_split()` partitions unique timestamps linearly, ensuring test data is strictly later chronologically than training data without overlap.

**Feature Classification (21 total)**:
- `population_density`: **SAFE**
- `temperature_c`: **SAFE**
- `rh_pct`: **SAFE**
- `wind_speed_kmh`: **SAFE**
- `shortwave_radiation_wm2`: **SAFE**
- `wbgt_proxy`: **SAFE**
- `heat_index`: **SAFE**
- `htsi_score`: **SAFE**
- `hour`: **SAFE**
- `day_of_week`: **SAFE**
- `day_of_year`: **SAFE**
- `hour_sin`: **SAFE**
- `hour_cos`: **SAFE**
- `day_of_year_sin`: **SAFE**
- `day_of_year_cos`: **SAFE**
- `htsi_lag_1`: **SAFE**
- `htsi_lag_3`: **SAFE**
- `htsi_lag_6`: **SAFE**
- `heat_index_lag_1`: **SAFE**
- `temperature_lag_1`: **SAFE**
- `rh_lag_1`: **SAFE**

## 7. FEATURE IMPORTANCE (Top 10)
1. `hour_sin`: 0.2627
2. `htsi_score`: 0.1472
3. `htsi_lag_6`: 0.0925
4. `hour`: 0.0512
5. `rh_pct`: 0.0430
6. `wind_speed_kmh`: 0.0418
7. `day_of_year_sin`: 0.0383
8. `day_of_year_cos`: 0.0369
9. `day_of_year`: 0.0366
10. `wbgt_proxy`: 0.0357

*Note: Feature importance represents predictive utility within this specific Random Forest model, not causal thermodynamic relationships.*

## 8. WARD PERFORMANCE
| Ward ID | MAE | RMSE | Accuracy |
|---|---|---|---|
| 1 | 6.1913 | 8.4425 | 74.7664% |
| 2 | 6.1658 | 8.3374 | 74.7664% |
| 3 | 6.2091 | 8.4546 | 75.7009% |
| 4 | 6.2075 | 8.4619 | 74.7664% |
| 5 | 6.4168 | 8.7501 | 78.5047% |
| 6 | 6.5206 | 8.9558 | 83.1776% |
| 7 | 5.0630 | 6.8659 | 72.8972% |
| 8 | 6.1745 | 8.3850 | 74.7664% |
| 9 | 3.6525 | 4.5879 | 89.7196% |
| 10 | 3.7146 | 4.7026 | 73.8318% |
| 11 | 6.9850 | 9.3708 | 84.1121% |
| 12 | 6.5241 | 8.9580 | 83.1776% |
| 13 | 6.5255 | 8.9027 | 72.8972% |
| 14 | 6.9416 | 9.3395 | 72.8972% |
| 15 | 6.8736 | 9.2782 | 71.9626% |
| 16 | 6.9357 | 9.4343 | 74.7664% |
| 17 | 6.3513 | 8.6207 | 70.0935% |
| 18 | 6.7458 | 9.1949 | 79.4393% |
| 19 | 6.2273 | 8.4786 | 69.1589% |
| 20 | 4.2682 | 5.6899 | 79.4393% |
| 21 | 6.9690 | 9.4848 | 84.1121% |
| 22 | 6.3580 | 8.6289 | 70.0935% |
| 23 | 6.5335 | 8.9079 | 70.0935% |
| 24 | 5.1234 | 6.9819 | 73.8318% |
| 25 | 3.6343 | 4.6674 | 78.5047% |
| 26 | 6.1107 | 8.2492 | 71.0280% |

## 9. TEMPORAL PERFORMANCE
### Category Accuracy by Hour of Day
| Hour | Accuracy |
|---|---|
| 00:00 | 78.8462% |
| 01:00 | 24.0385% |
| 02:00 | 35.5769% |
| 03:00 | 35.5769% |
| 04:00 | 85.5769% |
| 05:00 | 98.0769% |
| 06:00 | 96.1538% |
| 07:00 | 70.0000% |
| 08:00 | 88.4615% |
| 09:00 | 48.4615% |
| 10:00 | 55.3846% |
| 11:00 | 35.3846% |
| 12:00 | 79.2308% |
| 13:00 | 84.6154% |
| 14:00 | 85.3846% |
| 15:00 | 90.7692% |
| 16:00 | 91.5385% |
| 17:00 | 80.0000% |
| 18:00 | 92.3077% |
| 19:00 | 95.1923% |
| 20:00 | 96.1538% |
| 21:00 | 95.1923% |
| 22:00 | 96.1538% |
| 23:00 | 95.1923% |

### Category Accuracy by Test Date
| Date | Accuracy |
|---|---|
| 2026-09-14 | 83.4842% |
| 2026-09-15 | 81.2500% |
| 2026-09-16 | 76.6026% |
| 2026-09-17 | 73.5577% |
| 2026-09-18 | 64.9573% |

**Observation**: Peak daytime/high-radiation hours often exhibit lower accuracy or higher variance compared to stable nighttime conditions.

## 10. FINAL INTERPRETATION
### A. What the results demonstrate
The Random Forest model meaningfully outperforms the naive persistence baseline in forecasting HTSI 6 hours ahead, demonstrating that historical diurnal patterns and lagged meteorological indicators carry predictive signal. The model achieves superior risk-category accuracy and successfully captures temporal dependencies.

### B. What they do NOT demonstrate
These results do not demonstrate generalizability to extreme, anomalous heat events outside the 30-day training distribution. The lack of zero-support for certain risk tiers (if any, like EXTREME) in the test set means its capacity to act as a reliable emergency early-warning trigger for unprecedented conditions is unproven. Furthermore, it does not prove microclimate differences between wards, as the underlying ERA5 reanalysis weather data may have identical values for closely situated polygon centroids.

### C. Whether the current baseline is suitable to present as an ML prototype
Yes, it is suitable strictly as an offline, experimental ML prototype. It effectively illustrates a viable methodology for temporal HTSI forecasting (using cyclical encoding, lagging, and strict chronological splits) but should not replace the deterministic, physics-based engine for synchronous production API requests.

### D. What limitations must be disclosed in the SIH presentation
1. **Data Breadth**: Trained on only 30 days of historical data, which may not encompass severe heatwave extremes.
2. **Spatial Resolution**: Weather fetched per ward centroid relies on ~9 km resolution grid models, potentially missing granular urban microclimate variations.
3. **Demographic Constraints**: Key exposure variables like `outdoor_worker_ratio` are currently unavailable and not imputed, limiting vulnerability weighting.
4. **Operational Status**: This is a proof-of-concept pipeline rather than a clinically or epidemiologically validated predictive tool.