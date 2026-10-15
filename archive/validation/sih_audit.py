import os
import sys
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.metrics import mean_absolute_error, root_mean_squared_error, r2_score, confusion_matrix, precision_recall_fscore_support

def classify_risk(htsi):
    if htsi <= 25: return "LOW"
    if htsi <= 50: return "MODERATE"
    if htsi <= 75: return "HIGH"
    return "EXTREME"

def main():
    data_path = 'data/ml_features_baseline.csv'
    df = pd.read_csv(data_path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    
    print("==================================================")
    print("STEP 1 - WEATHER SPATIAL REDUNDANCY AUDIT")
    print("==================================================")
    
    weather_cols = ["temperature_c", "rh_pct", "wind_speed_kmh", "shortwave_radiation_wm2"]
    
    unique_counts = []
    for ts, group in df.groupby("timestamp"):
        n_unique = group[weather_cols].drop_duplicates().shape[0]
        unique_counts.append(n_unique)
        
    unique_counts = np.array(unique_counts)
    
    print(f"Number of wards = 26")
    print(f"Total timestamps = {len(unique_counts)}")
    print(f"Unique weather combinations per timestamp:")
    print(f"  Min: {unique_counts.min()}")
    print(f"  Max: {unique_counts.max()}")
    print(f"  Mean: {unique_counts.mean():.2f}")
    print(f"  Median: {np.median(unique_counts)}")
    
    all_same_count = (unique_counts == 1).sum()
    print(f"Timestamps where all 26 wards share the same weather: {all_same_count} ({(all_same_count/len(unique_counts))*100:.2f}%)")
    
    print("\n==================================================")
    print("PREPARATION for ML (Same splits as original)")
    print("==================================================")
    
    # Feature engineering as done in the original script
    df["hour"] = df["timestamp"].dt.hour
    df["day_of_week"] = df["timestamp"].dt.dayofweek
    df["day_of_year"] = df["timestamp"].dt.dayofyear
    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)
    df["day_of_year_sin"] = np.sin(2 * np.pi * df["day_of_year"] / 365)
    df["day_of_year_cos"] = np.cos(2 * np.pi * df["day_of_year"] / 365)
    
    grouped = df.groupby("ward_id")
    df["htsi_lag_1"] = grouped["htsi_score"].shift(1)
    df["htsi_lag_3"] = grouped["htsi_score"].shift(3)
    df["htsi_lag_6"] = grouped["htsi_score"].shift(6)
    df["heat_index_lag_1"] = grouped["heat_index"].shift(1)
    df["temperature_lag_1"] = grouped["temperature_c"].shift(1)
    df["rh_lag_1"] = grouped["rh_pct"].shift(1)
    
    df["htsi_score_lead_6"] = grouped["htsi_score"].shift(-6)
    
    lag_and_target_cols = [
        "htsi_lag_1", "htsi_lag_3", "htsi_lag_6",
        "heat_index_lag_1", "temperature_lag_1", "rh_lag_1",
        "htsi_score_lead_6",
    ]
    df = df.dropna(subset=lag_and_target_cols).reset_index(drop=True)
    
    # Chronological Split
    unique_ts = sorted(df["timestamp"].unique())
    n_ts = len(unique_ts)
    train_end_idx = int(n_ts * 0.70)
    val_end_idx = int(n_ts * (0.70 + 0.15))
    
    train_ts = set(unique_ts[:train_end_idx])
    val_ts = set(unique_ts[train_end_idx:val_end_idx])
    test_ts = set(unique_ts[val_end_idx:])
    
    df_train = df[df["timestamp"].isin(train_ts)].copy()
    df_val = df[df["timestamp"].isin(val_ts)].copy()
    df_test = df[df["timestamp"].isin(test_ts)].copy()
    
    # Features
    FEATURE_COLS_FULL = [
        "population_density", "temperature_c", "rh_pct", "wind_speed_kmh", 
        "shortwave_radiation_wm2", "wbgt_proxy", "heat_index", "htsi_score",
        "hour", "day_of_week", "day_of_year", "hour_sin", "hour_cos", 
        "day_of_year_sin", "day_of_year_cos",
        "htsi_lag_1", "htsi_lag_3", "htsi_lag_6",
        "heat_index_lag_1", "temperature_lag_1", "rh_lag_1"
    ]
    
    time_persistence_feats = [
        "hour", "hour_sin", "hour_cos", 
        "day_of_week", "day_of_year", "day_of_year_sin", "day_of_year_cos",
        "htsi_lag_1", "htsi_lag_3", "htsi_lag_6"
    ]
    
    FEATURE_COLS_ABLATED = [f for f in FEATURE_COLS_FULL if f not in time_persistence_feats]
    
    TARGET_COL = "htsi_score_lead_6"
    
    RF_CONFIG = {
        "n_estimators": 300,
        "max_depth": 12,
        "random_state": 42,
        "n_jobs": -1,
        "min_samples_leaf": 5,
    }
    
    def evaluate_model(model, features, is_classifier=False):
        # We train on train + val for these tests to match original behavior where train was train, evaluated on val, then evaluated on test.
        # Actually original just trained on train. We will train on train.
        X_train = df_train[features].values
        
        if is_classifier:
            # Create risk labels
            y_train = np.array([classify_risk(int(round(v))) for v in df_train[TARGET_COL].values])
            y_test = np.array([classify_risk(int(round(v))) for v in df_test[TARGET_COL].values])
        else:
            y_train = df_train[TARGET_COL].values
            y_test_num = df_test[TARGET_COL].values
            y_test = np.array([classify_risk(int(round(v))) for v in y_test_num])
            
        model.fit(X_train, y_train)
        
        X_test = df_test[features].values
        y_pred = model.predict(X_test)
        
        if is_classifier:
            y_pred_risk = y_pred
            mae, rmse = None, None
        else:
            mae = mean_absolute_error(y_test_num, y_pred)
            rmse = root_mean_squared_error(y_test_num, y_pred)
            y_pred_risk = np.array([classify_risk(int(round(v))) for v in y_pred])
            
        # Accuracy
        acc = (y_test == y_pred_risk).mean()
        
        # Confusion matrix & metrics
        labels = ["LOW", "MODERATE", "HIGH", "EXTREME"]
        cm = confusion_matrix(y_test, y_pred_risk, labels=labels)
        precision, recall, f1, _ = precision_recall_fscore_support(y_test, y_pred_risk, labels=labels, zero_division=0)
        
        high_idx = labels.index("HIGH")
        
        return {
            "mae": mae, "rmse": rmse, "acc": acc,
            "high_p": precision[high_idx], "high_r": recall[high_idx], "high_f1": f1[high_idx],
            "cm": cm
        }

    print("\n==================================================")
    print("STEP 2 - FEATURE ABLATION STUDY")
    print("==================================================")
    model_a = RandomForestRegressor(**RF_CONFIG)
    res_a = evaluate_model(model_a, FEATURE_COLS_FULL)
    
    print("Model A (Full Features):")
    print(f"  Accuracy: {res_a['acc']:.4f}")
    print(f"  MAE: {res_a['mae']:.4f}, RMSE: {res_a['rmse']:.4f}")
    print(f"  HIGH - Precision: {res_a['high_p']:.4f}, Recall: {res_a['high_r']:.4f}, F1: {res_a['high_f1']:.4f}")
    print(f"  CM:\n{res_a['cm']}")
    
    model_b = RandomForestRegressor(**RF_CONFIG)
    res_b = evaluate_model(model_b, FEATURE_COLS_ABLATED)
    
    print("\nModel B (Ablated Features):")
    print(f"  Accuracy: {res_b['acc']:.4f}")
    print(f"  MAE: {res_b['mae']:.4f}, RMSE: {res_b['rmse']:.4f}")
    print(f"  HIGH - Precision: {res_b['high_p']:.4f}, Recall: {res_b['high_r']:.4f}, F1: {res_b['high_f1']:.4f}")
    print(f"  CM:\n{res_b['cm']}")

    print("\n==================================================")
    print("STEP 3 - DIRECT RISK CLASSIFICATION EXPERIMENT")
    print("==================================================")
    RF_CONFIG_CLF = RF_CONFIG.copy()
    RF_CONFIG_CLF["class_weight"] = "balanced"
    model_c = RandomForestClassifier(**RF_CONFIG_CLF)
    res_c = evaluate_model(model_c, FEATURE_COLS_FULL, is_classifier=True)
    
    print("Model C (Direct Classifier - Full Features):")
    print(f"  Accuracy: {res_c['acc']:.4f}")
    print(f"  HIGH - Precision: {res_c['high_p']:.4f}, Recall: {res_c['high_r']:.4f}, F1: {res_c['high_f1']:.4f}")
    print(f"  CM:\n{res_c['cm']}")
    
    print("\n==================================================")
    print("STEP 4 - COMPARE AGAINST PERSISTENCE")
    print("==================================================")
    
    y_test_num = df_test[TARGET_COL].values
    y_test_risk = np.array([classify_risk(int(round(v))) for v in y_test_num])
    
    y_persist_num = df_test["htsi_score"].values
    y_persist_risk = np.array([classify_risk(int(round(v))) for v in y_persist_num])
    
    p_mae = mean_absolute_error(y_test_num, y_persist_num)
    p_rmse = root_mean_squared_error(y_test_num, y_persist_num)
    p_acc = (y_test_risk == y_persist_risk).mean()
    
    labels = ["LOW", "MODERATE", "HIGH", "EXTREME"]
    high_idx = labels.index("HIGH")
    p_cm = confusion_matrix(y_test_risk, y_persist_risk, labels=labels)
    p_prec, p_rec, p_f1, _ = precision_recall_fscore_support(y_test_risk, y_persist_risk, labels=labels, zero_division=0)
    
    print(f"{'Model':<25} | {'Accuracy':<8} | {'MAE':<8} | {'HIGH Recall':<12} | {'HIGH Precision':<15}")
    print("-" * 75)
    print(f"{'1. RF Regressor (Full)':<25} | {res_a['acc']:.4f}   | {res_a['mae']:.4f}   | {res_a['high_r']:.4f}       | {res_a['high_p']:.4f}")
    print(f"{'2. RF Regressor (Ablated)':<25} | {res_b['acc']:.4f}   | {res_b['mae']:.4f}   | {res_b['high_r']:.4f}       | {res_b['high_p']:.4f}")
    print(f"{'3. RF Classifier (Direct)':<25} | {res_c['acc']:.4f}   | {'N/A':<8} | {res_c['high_r']:.4f}       | {res_c['high_p']:.4f}")
    print(f"{'4. Persistence':<25} | {p_acc:.4f}   | {p_mae:.4f}   | {p_rec[high_idx]:.4f}       | {p_prec[high_idx]:.4f}")
    
    print("\nPersistence CM:")
    print(p_cm)
    
if __name__ == '__main__':
    main()
