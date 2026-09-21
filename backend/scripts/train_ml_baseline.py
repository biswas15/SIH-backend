"""
scripts/train_ml_baseline.py
=============================
HeatSense - Phase 5 Part 2: Transparent ML Baseline for 6-Hour HTSI Forecasting.

PURPOSE
-------
Train a Random Forest regressor to forecast HTSI 6 hours ahead using the
ward x hourly historical dataset from Phase 5 Part 1.

This is a PROTOTYPE BASELINE, not a production forecasting system.
The deterministic HTSI engine remains the authoritative current-risk calculation.
ML is only an experimental future-risk forecasting layer.

SCIENTIFIC LIMITATIONS
----------------------
- Dataset is only 30 days of Haldia regional meteorological observations.
- Weather fetched per ward polygon centroid (26 individual Open-Meteo requests).
  ERA5/reanalysis native resolution (~9 km) may yield identical values for geographically
  close ward centroids, so this does NOT represent 26 independent meteorological stations.
- outdoor_worker_ratio and built_up_ratio are unavailable (dropped, not imputed).
- This is a hackathon prototype baseline, not clinically or production validated.

DO NOT MODIFY
-------------
- main.py, app/engine/*, existing API routes, existing tests.
"""

import json
import math
import os
import sys
import warnings
from datetime import datetime

# ---------------------------------------------------------------------------
# Ensure workspace root is on sys.path for app.engine imports
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# ---------------------------------------------------------------------------
# Third-party imports
# ---------------------------------------------------------------------------
try:
    import pandas as pd
    import numpy as np
except ModuleNotFoundError as e:
    sys.exit(f"[FATAL] Missing dependency: {e.name}. Run: pip install pandas numpy")

try:
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.metrics import mean_absolute_error, root_mean_squared_error, r2_score
    from sklearn.metrics import confusion_matrix, classification_report
except ModuleNotFoundError:
    sys.exit("[FATAL] scikit-learn not installed. Run: pip install scikit-learn")

try:
    import joblib
except ModuleNotFoundError:
    sys.exit("[FATAL] joblib not installed. Run: pip install joblib")

# ---------------------------------------------------------------------------
# Import the HTSI risk classifier from the existing deterministic engine.
# This is the ONLY engine import -- we use it to map predicted HTSI -> risk.
# We do NOT reimplement or alter the thresholds.
# ---------------------------------------------------------------------------
from app.engine.htsi import classify_risk

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DATA_DIR = os.path.join(REPO_ROOT, "data")
MODELS_DIR = os.path.join(REPO_ROOT, "models")
INPUT_CSV = os.path.join(DATA_DIR, "ml_features_baseline.csv")
FEATURE_IMPORTANCE_CSV = os.path.join(DATA_DIR, "ml_feature_importance.csv")
TEST_PREDICTIONS_CSV = os.path.join(DATA_DIR, "ml_test_predictions.csv")
MODEL_PATH = os.path.join(MODELS_DIR, "htsi_forecast_rf.joblib")
FEATURES_PATH = os.path.join(MODELS_DIR, "htsi_forecast_features.json")
METRICS_PATH = os.path.join(MODELS_DIR, "ml_baseline_metrics.json")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
FORECAST_HORIZON = 6       # hours ahead
TRAIN_FRAC = 0.70
VAL_FRAC = 0.15
TEST_FRAC = 0.15

RF_CONFIG = {
    "n_estimators": 300,
    "max_depth": 12,
    "random_state": 42,
    "n_jobs": -1,
    "min_samples_leaf": 5,
}

REQUIRED_COLUMNS = [
    "timestamp", "ward_id", "population_density",
    "temperature_c", "rh_pct", "wind_speed_kmh",
    "shortwave_radiation_wm2", "wbgt_proxy", "heat_index",
    "htsi_score", "risk_label",
]


# ===========================================================================
# Step 1 -- Load and Validate
# ===========================================================================

def load_and_validate() -> pd.DataFrame:
    """Load the baseline CSV and run mandatory integrity checks."""
    print("=" * 60)
    print("Step 1 -- Load and Validate Dataset")
    print("=" * 60)

    # 1. File exists
    if not os.path.isfile(INPUT_CSV):
        sys.exit(f"[FATAL] Dataset not found: {INPUT_CSV}")
    print(f"  File: {INPUT_CSV}")

    df = pd.read_csv(INPUT_CSV)

    # 2. Required columns
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        sys.exit(f"[FATAL] Missing required columns: {missing}")
    print(f"  [PASS] All required columns present")

    # 3. Parse timestamp
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    print(f"  [PASS] Timestamps parsed ({df['timestamp'].min()} -> {df['timestamp'].max()})")

    # 4. Exactly 26 unique ward IDs
    unique_wards = sorted(df["ward_id"].unique())
    if len(unique_wards) != 26:
        sys.exit(f"[FATAL] Expected 26 wards, got {len(unique_wards)}")
    print(f"  [PASS] 26 unique ward IDs")

    # 5. Ward IDs are 1-26
    if unique_wards != list(range(1, 27)):
        sys.exit(f"[FATAL] Ward IDs are not 1-26: {unique_wards}")
    print(f"  [PASS] Ward IDs = 1-26")

    # 6. No duplicate (timestamp, ward_id)
    dupes = df.duplicated(subset=["timestamp", "ward_id"], keep=False).sum()
    if dupes > 0:
        sys.exit(f"[FATAL] {dupes} duplicate (timestamp, ward_id) rows found")
    print(f"  [PASS] No duplicate (timestamp, ward_id) combinations")

    # 7. Sort chronologically within each ward
    df = df.sort_values(["ward_id", "timestamp"]).reset_index(drop=True)
    print(f"  [PASS] Sorted by (ward_id, timestamp)")

    print(f"\n  Dataset shape: {df.shape}")
    print(f"  Rows: {len(df):,}  |  Wards: 26  |  Hours: {df['timestamp'].nunique()}")
    return df


# ===========================================================================
# Step 2 -- Drop Unused Columns
# ===========================================================================

def drop_unused(df: pd.DataFrame) -> pd.DataFrame:
    """Drop columns that are 100% NaN and unverified."""
    print("\n" + "=" * 60)
    print("Step 2 -- Drop Unused Columns")
    print("=" * 60)

    cols_to_drop = ["outdoor_worker_ratio", "built_up_ratio"]
    existing_drops = [c for c in cols_to_drop if c in df.columns]
    df = df.drop(columns=existing_drops)
    print(f"  Dropped: {existing_drops}")
    print(f"  Remaining columns: {list(df.columns)}")
    return df


# ===========================================================================
# Step 3 -- Create Temporal Features
# ===========================================================================

def create_temporal_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add calendar and cyclical time features."""
    print("\n" + "=" * 60)
    print("Step 3 -- Create Temporal Features")
    print("=" * 60)

    df["hour"] = df["timestamp"].dt.hour
    df["day_of_week"] = df["timestamp"].dt.dayofweek
    df["day_of_year"] = df["timestamp"].dt.dayofyear

    # Cyclical encoding
    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)
    df["day_of_year_sin"] = np.sin(2 * np.pi * df["day_of_year"] / 365)
    df["day_of_year_cos"] = np.cos(2 * np.pi * df["day_of_year"] / 365)

    print(f"  Created: hour, day_of_week, day_of_year")
    print(f"  Created: hour_sin, hour_cos, day_of_year_sin, day_of_year_cos")
    return df


# ===========================================================================
# Step 4 -- Create Lag Features
# ===========================================================================

def create_lag_features(df: pd.DataFrame) -> pd.DataFrame:
    """Create per-ward lag features. Only past information at time t."""
    print("\n" + "=" * 60)
    print("Step 4 -- Create Lag Features (per ward)")
    print("=" * 60)

    grouped = df.groupby("ward_id")

    # HTSI lags
    df["htsi_lag_1"] = grouped["htsi_score"].shift(1)
    df["htsi_lag_3"] = grouped["htsi_score"].shift(3)
    df["htsi_lag_6"] = grouped["htsi_score"].shift(6)

    # Other lags
    df["heat_index_lag_1"] = grouped["heat_index"].shift(1)
    df["temperature_lag_1"] = grouped["temperature_c"].shift(1)
    df["rh_lag_1"] = grouped["rh_pct"].shift(1)

    lag_cols = [
        "htsi_lag_1", "htsi_lag_3", "htsi_lag_6",
        "heat_index_lag_1", "temperature_lag_1", "rh_lag_1",
    ]
    print(f"  Created lags: {lag_cols}")

    # Report NaN introduced by lags
    for col in lag_cols:
        n_nan = df[col].isna().sum()
        print(f"    {col:25s}: {n_nan:,} NaN rows (expected from initial hours)")
    return df


# ===========================================================================
# Step 5 -- Create Forecast Target
# ===========================================================================

def create_target(df: pd.DataFrame) -> pd.DataFrame:
    """Create htsi_score_lead_6 = HTSI at t+6, per ward."""
    print("\n" + "=" * 60)
    print("Step 5 -- Create Forecast Target (htsi_score_lead_6)")
    print("=" * 60)

    df["htsi_score_lead_6"] = df.groupby("ward_id")["htsi_score"].shift(-FORECAST_HORIZON)

    n_target_nan = df["htsi_score_lead_6"].isna().sum()
    print(f"  Target NaN (final {FORECAST_HORIZON} hours per ward): {n_target_nan:,}")

    # Drop rows where lags or target are NaN
    before = len(df)
    lag_and_target_cols = [
        "htsi_lag_1", "htsi_lag_3", "htsi_lag_6",
        "heat_index_lag_1", "temperature_lag_1", "rh_lag_1",
        "htsi_score_lead_6",
    ]
    df = df.dropna(subset=lag_and_target_cols).reset_index(drop=True)
    after = len(df)

    print(f"  Rows before dropping NaN: {before:,}")
    print(f"  Rows after dropping NaN:  {after:,}")
    print(f"  Rows removed:             {before - after:,}")
    return df


# ===========================================================================
# Step 6 -- Define Features (Prevent Leakage)
# ===========================================================================

FEATURE_COLS = [
    # Ward demographics
    "population_density",
    # Current weather (available at time t)
    "temperature_c",
    "rh_pct",
    "wind_speed_kmh",
    "shortwave_radiation_wm2",
    # Current derived metrics (computed from current weather at time t)
    "wbgt_proxy",
    "heat_index",
    "htsi_score",
    # Calendar / cyclical
    "hour",
    "day_of_week",
    "day_of_year",
    "hour_sin",
    "hour_cos",
    "day_of_year_sin",
    "day_of_year_cos",
    # Lag features (strictly past, no future leakage)
    "htsi_lag_1",
    "htsi_lag_3",
    "htsi_lag_6",
    "heat_index_lag_1",
    "temperature_lag_1",
    "rh_lag_1",
]

TARGET_COL = "htsi_score_lead_6"


def verify_no_leakage(df: pd.DataFrame) -> None:
    """Verify the target column is NOT in the feature list."""
    print("\n" + "=" * 60)
    print("Step 6 -- Feature List and Leakage Check")
    print("=" * 60)

    if TARGET_COL in FEATURE_COLS:
        sys.exit(f"[FATAL] DATA LEAKAGE: {TARGET_COL} is in the feature list!")

    # No future columns should appear
    future_keywords = ["lead", "future", "next", "forward"]
    for feat in FEATURE_COLS:
        for kw in future_keywords:
            if kw in feat.lower():
                sys.exit(f"[FATAL] Suspicious future-looking feature: {feat}")

    print(f"  [PASS] No data leakage detected")
    print(f"  Target: {TARGET_COL}")
    print(f"  Features ({len(FEATURE_COLS)}):")
    for f in FEATURE_COLS:
        print(f"    - {f}")

    # Verify all feature columns exist
    missing = [c for c in FEATURE_COLS if c not in df.columns]
    if missing:
        sys.exit(f"[FATAL] Missing feature columns in dataframe: {missing}")
    print(f"  [PASS] All feature columns present in dataframe")


# ===========================================================================
# Step 7 -- Chronological Split
# ===========================================================================

def chronological_split(df: pd.DataFrame):
    """Split by unique timestamps to prevent same-timestamp data leaking."""
    print("\n" + "=" * 60)
    print("Step 7 -- Chronological Train / Validation / Test Split")
    print("=" * 60)

    # Get sorted unique timestamps
    unique_ts = sorted(df["timestamp"].unique())
    n_ts = len(unique_ts)

    train_end_idx = int(n_ts * TRAIN_FRAC)
    val_end_idx = int(n_ts * (TRAIN_FRAC + VAL_FRAC))

    train_ts = set(unique_ts[:train_end_idx])
    val_ts = set(unique_ts[train_end_idx:val_end_idx])
    test_ts = set(unique_ts[val_end_idx:])

    df_train = df[df["timestamp"].isin(train_ts)].copy()
    df_val = df[df["timestamp"].isin(val_ts)].copy()
    df_test = df[df["timestamp"].isin(test_ts)].copy()

    # Report
    train_ts_sorted = sorted(train_ts)
    val_ts_sorted = sorted(val_ts)
    test_ts_sorted = sorted(test_ts)

    print(f"  Unique timestamps total: {n_ts}")
    print()
    print(f"  TRAIN:      {len(train_ts_sorted):4d} timestamps  |  {len(df_train):6,} rows")
    print(f"    Range:    {train_ts_sorted[0]}  ->  {train_ts_sorted[-1]}")
    print(f"  VALIDATION: {len(val_ts_sorted):4d} timestamps  |  {len(df_val):6,} rows")
    print(f"    Range:    {val_ts_sorted[0]}  ->  {val_ts_sorted[-1]}")
    print(f"  TEST:       {len(test_ts_sorted):4d} timestamps  |  {len(df_test):6,} rows")
    print(f"    Range:    {test_ts_sorted[0]}  ->  {test_ts_sorted[-1]}")

    # Verify no overlap
    assert not (train_ts & val_ts), "Train/Val timestamp overlap!"
    assert not (train_ts & test_ts), "Train/Test timestamp overlap!"
    assert not (val_ts & test_ts), "Val/Test timestamp overlap!"
    print(f"\n  [PASS] No timestamp overlap between splits")

    return df_train, df_val, df_test


# ===========================================================================
# Step 8 -- Persistence Baseline
# ===========================================================================

def evaluate_persistence(df_test: pd.DataFrame) -> dict:
    """Persistence baseline: predict HTSI(t+6) = HTSI(t)."""
    print("\n" + "=" * 60)
    print("Step 8 -- Persistence Baseline (predict t+6 = t)")
    print("=" * 60)

    y_actual = df_test[TARGET_COL].values
    y_persistence = df_test["htsi_score"].values  # current HTSI as prediction

    mae = mean_absolute_error(y_actual, y_persistence)
    rmse = root_mean_squared_error(y_actual, y_persistence)
    r2 = r2_score(y_actual, y_persistence)

    print(f"  Persistence MAE:  {mae:.4f}")
    print(f"  Persistence RMSE: {rmse:.4f}")
    print(f"  Persistence R2:   {r2:.4f}")

    return {"mae": round(mae, 4), "rmse": round(rmse, 4), "r2": round(r2, 4),
            "predictions": y_persistence}


# ===========================================================================
# Step 9-10 -- Train Random Forest
# ===========================================================================

def train_random_forest(df_train: pd.DataFrame, df_val: pd.DataFrame):
    """Train RandomForestRegressor and evaluate on validation set."""
    print("\n" + "=" * 60)
    print("Step 9-10 -- Train Random Forest Regressor")
    print("=" * 60)

    X_train = df_train[FEATURE_COLS].values
    y_train = df_train[TARGET_COL].values
    X_val = df_val[FEATURE_COLS].values
    y_val = df_val[TARGET_COL].values

    print(f"  Training samples:   {len(X_train):,}")
    print(f"  Validation samples: {len(X_val):,}")
    print(f"  Features:           {len(FEATURE_COLS)}")
    print(f"  Config: {RF_CONFIG}")
    print(f"\n  Training in progress ...")

    model = RandomForestRegressor(**RF_CONFIG)
    model.fit(X_train, y_train)

    # Validation metrics
    y_val_pred = model.predict(X_val)
    val_mae = mean_absolute_error(y_val, y_val_pred)
    val_rmse = root_mean_squared_error(y_val, y_val_pred)
    val_r2 = r2_score(y_val, y_val_pred)

    print(f"\n  Validation MAE:  {val_mae:.4f}")
    print(f"  Validation RMSE: {val_rmse:.4f}")
    print(f"  Validation R2:   {val_r2:.4f}")

    return model


# ===========================================================================
# Step 11 -- Test Evaluation
# ===========================================================================

def evaluate_on_test(model, df_test: pd.DataFrame) -> dict:
    """Evaluate RF model on the held-out test set."""
    print("\n" + "=" * 60)
    print("Step 11 -- Random Forest Test Evaluation")
    print("=" * 60)

    X_test = df_test[FEATURE_COLS].values
    y_actual = df_test[TARGET_COL].values
    y_pred = model.predict(X_test)

    mae = mean_absolute_error(y_actual, y_pred)
    rmse = root_mean_squared_error(y_actual, y_pred)
    r2 = r2_score(y_actual, y_pred)

    print(f"  Random Forest MAE:  {mae:.4f}")
    print(f"  Random Forest RMSE: {rmse:.4f}")
    print(f"  Random Forest R2:   {r2:.4f}")

    return {"mae": round(mae, 4), "rmse": round(rmse, 4), "r2": round(r2, 4),
            "predictions": y_pred}


def print_comparison(persist_metrics: dict, rf_metrics: dict) -> None:
    """Print side-by-side comparison of persistence vs RF."""
    print("\n  " + "-" * 55)
    print(f"  {'MODEL':<25s} {'MAE':>8s}   {'RMSE':>8s}   {'R2':>8s}")
    print("  " + "-" * 55)
    print(f"  {'Persistence':<25s} {persist_metrics['mae']:>8.4f}   "
          f"{persist_metrics['rmse']:>8.4f}   {persist_metrics['r2']:>8.4f}")
    print(f"  {'Random Forest':<25s} {rf_metrics['mae']:>8.4f}   "
          f"{rf_metrics['rmse']:>8.4f}   {rf_metrics['r2']:>8.4f}")
    print("  " + "-" * 55)

    if rf_metrics["mae"] < persist_metrics["mae"]:
        improvement = (1 - rf_metrics["mae"] / persist_metrics["mae"]) * 100
        print(f"\n  Random Forest beats persistence by {improvement:.1f}% MAE reduction.")
    elif rf_metrics["mae"] > persist_metrics["mae"]:
        print(f"\n  [NOTE] Persistence baseline outperforms Random Forest on MAE.")
        print(f"  This is informative -- persistence is a strong baseline for short horizons.")
    else:
        print(f"\n  Random Forest and persistence perform identically on MAE.")


# ===========================================================================
# Step 12 -- Risk Category Evaluation
# ===========================================================================

def evaluate_risk_categories(y_actual_htsi, y_pred_htsi, label: str) -> float:
    """Convert predicted HTSI to risk categories using the existing engine."""
    print(f"\n  Risk category evaluation ({label}):")

    # Use the existing deterministic classify_risk() -- no new thresholds
    actual_risk = [classify_risk(int(round(v))) for v in y_actual_htsi]
    pred_risk = [classify_risk(int(round(v))) for v in y_pred_htsi]

    correct = sum(1 for a, p in zip(actual_risk, pred_risk) if a == p)
    accuracy = correct / len(actual_risk)
    print(f"    Category accuracy: {accuracy:.4f} ({correct}/{len(actual_risk)})")

    # Confusion matrix
    labels = ["LOW", "MODERATE", "HIGH", "EXTREME"]
    # Only include labels that appear in either actual or predicted
    present_labels = sorted(set(actual_risk) | set(pred_risk),
                            key=lambda x: labels.index(x) if x in labels else 99)

    cm = confusion_matrix(actual_risk, pred_risk, labels=present_labels)
    print(f"\n    Confusion Matrix (rows=actual, cols=predicted):")
    header = "              " + "  ".join(f"{l:>10s}" for l in present_labels)
    print(f"    {header}")
    for i, row_label in enumerate(present_labels):
        row_str = "  ".join(f"{cm[i, j]:>10d}" for j in range(len(present_labels)))
        print(f"    {row_label:>12s}  {row_str}")

    return accuracy


# ===========================================================================
# Step 13 -- Feature Importance
# ===========================================================================

def save_feature_importance(model) -> pd.DataFrame:
    """Extract and save RF feature importances."""
    print("\n" + "=" * 60)
    print("Step 13 -- Feature Importance")
    print("=" * 60)

    importances = model.feature_importances_
    fi_df = pd.DataFrame({
        "feature": FEATURE_COLS,
        "importance": importances,
    }).sort_values("importance", ascending=False).reset_index(drop=True)

    fi_df.to_csv(FEATURE_IMPORTANCE_CSV, index=False)
    print(f"  Saved: {FEATURE_IMPORTANCE_CSV}")
    print(f"\n  Top 10 features:")
    for _, row in fi_df.head(10).iterrows():
        print(f"    {row['feature']:30s}  {row['importance']:.4f}")

    return fi_df


# ===========================================================================
# Step 14 -- Save Model
# ===========================================================================

def save_model(model) -> None:
    """Save trained model and feature list."""
    print("\n" + "=" * 60)
    print("Step 14 -- Save Model")
    print("=" * 60)

    os.makedirs(MODELS_DIR, exist_ok=True)

    joblib.dump(model, MODEL_PATH)
    print(f"  Model saved:    {MODEL_PATH}")

    features_meta = {
        "feature_columns": FEATURE_COLS,
        "target_column": TARGET_COL,
        "forecast_horizon_hours": FORECAST_HORIZON,
        "model_type": "RandomForestRegressor",
        "config": RF_CONFIG,
        "note": "Prototype temporal ML baseline. Not production validated.",
    }
    with open(FEATURES_PATH, "w", encoding="utf-8") as f:
        json.dump(features_meta, f, indent=2)
    print(f"  Features saved: {FEATURES_PATH}")


# ===========================================================================
# Step 15 -- Save Metrics
# ===========================================================================

def save_metrics(
    df, df_train, df_val, df_test,
    persist_metrics, rf_metrics, risk_accuracy
) -> None:
    """Save comprehensive metrics JSON."""
    print("\n" + "=" * 60)
    print("Step 15 -- Save Metrics")
    print("=" * 60)

    metrics = {
        "note": (
            "Prototype temporal ML baseline trained on 30 days of Haldia "
            "regional weather data. Not production validated."
        ),
        "dataset": {
            "source": "data/ml_features_baseline.csv",
            "total_rows_original": 18720,
            "total_rows_after_feature_engineering": len(df),
            "n_wards": 26,
            "ward_ids": list(range(1, 27)),
            "forecast_horizon_hours": FORECAST_HORIZON,
        },
        "splits": {
            "train_rows": len(df_train),
            "train_range": [
                str(df_train["timestamp"].min()),
                str(df_train["timestamp"].max()),
            ],
            "validation_rows": len(df_val),
            "validation_range": [
                str(df_val["timestamp"].min()),
                str(df_val["timestamp"].max()),
            ],
            "test_rows": len(df_test),
            "test_range": [
                str(df_test["timestamp"].min()),
                str(df_test["timestamp"].max()),
            ],
        },
        "feature_list": FEATURE_COLS,
        "n_features": len(FEATURE_COLS),
        "persistence_baseline": {
            "mae": persist_metrics["mae"],
            "rmse": persist_metrics["rmse"],
            "r2": persist_metrics["r2"],
        },
        "random_forest": {
            "config": RF_CONFIG,
            "mae": rf_metrics["mae"],
            "rmse": rf_metrics["rmse"],
            "r2": rf_metrics["r2"],
        },
        "risk_category_accuracy": round(risk_accuracy, 4),
        "rf_beats_persistence": rf_metrics["mae"] < persist_metrics["mae"],
        "generated_at": datetime.now().isoformat(),
    }

    os.makedirs(MODELS_DIR, exist_ok=True)
    with open(METRICS_PATH, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    print(f"  Saved: {METRICS_PATH}")


# ===========================================================================
# Step 16 -- Save Test Predictions
# ===========================================================================

def save_predictions(
    df_test: pd.DataFrame,
    rf_predictions,
    persist_predictions,
) -> None:
    """Save test set predictions for later analysis."""
    print("\n" + "=" * 60)
    print("Step 16 -- Save Test Predictions")
    print("=" * 60)

    y_actual = df_test[TARGET_COL].values

    pred_df = pd.DataFrame({
        "timestamp": df_test["timestamp"].values,
        "ward_id": df_test["ward_id"].values,
        "actual_htsi": y_actual,
        "predicted_htsi": np.round(rf_predictions, 2),
        "persistence_prediction": persist_predictions,
        "actual_risk": [classify_risk(int(round(v))) for v in y_actual],
        "predicted_risk": [classify_risk(int(round(v))) for v in rf_predictions],
    })

    pred_df.to_csv(TEST_PREDICTIONS_CSV, index=False)
    print(f"  Saved: {TEST_PREDICTIONS_CSV}")
    print(f"  Rows:  {len(pred_df):,}")
    print(f"\n  Preview (first 5 rows):")
    print(pred_df.head().to_string(index=False))


# ===========================================================================
# Main
# ===========================================================================

def main() -> None:
    print()
    print("=" * 60)
    print("HeatSense -- ML Baseline Training")
    print("Phase 5 Part 2: 6-Hour HTSI Forecast (Random Forest)")
    print("=" * 60)
    print()
    print("DISCLAIMER: Prototype baseline on 30 days of regional data.")
    print("Deterministic HTSI engine remains authoritative for current risk.")
    print()

    # Step 1
    df = load_and_validate()

    # Step 2
    df = drop_unused(df)

    # Step 3
    df = create_temporal_features(df)

    # Step 4
    df = create_lag_features(df)

    # Step 5
    df = create_target(df)

    # Step 6
    verify_no_leakage(df)

    # Step 7
    df_train, df_val, df_test = chronological_split(df)

    # Step 8
    persist_metrics = evaluate_persistence(df_test)

    # Step 9-10
    model = train_random_forest(df_train, df_val)

    # Step 11
    rf_metrics = evaluate_on_test(model, df_test)
    print_comparison(persist_metrics, rf_metrics)

    # Step 12
    print("\n" + "=" * 60)
    print("Step 12 -- Risk Category Evaluation")
    print("=" * 60)

    y_actual_test = df_test[TARGET_COL].values
    risk_accuracy_rf = evaluate_risk_categories(
        y_actual_test, rf_metrics["predictions"], "Random Forest"
    )
    _ = evaluate_risk_categories(
        y_actual_test, persist_metrics["predictions"], "Persistence"
    )

    # Step 13
    fi_df = save_feature_importance(model)

    # Step 14
    save_model(model)

    # Step 15
    save_metrics(df, df_train, df_val, df_test, persist_metrics,
                 rf_metrics, risk_accuracy_rf)

    # Step 16
    save_predictions(df_test, rf_metrics["predictions"],
                     persist_metrics["predictions"])

    # Final summary
    print("\n" + "=" * 60)
    print("COMPLETE -- Phase 5 Part 2 Summary")
    print("=" * 60)
    print(f"\n  Files created:")
    print(f"    Model:              {MODEL_PATH}")
    print(f"    Feature list:       {FEATURES_PATH}")
    print(f"    Metrics:            {METRICS_PATH}")
    print(f"    Feature importance: {FEATURE_IMPORTANCE_CSV}")
    print(f"    Test predictions:   {TEST_PREDICTIONS_CSV}")
    print(f"\n  RF beats persistence: {rf_metrics['mae'] < persist_metrics['mae']}")
    print()


if __name__ == "__main__":
    main()
