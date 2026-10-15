import re

def main():
    path = "scripts/train_ml_baseline.py"
    with open(path, "r") as f:
        content = f.read()
        
    # 1. Imports
    content = content.replace(
        "from sklearn.ensemble import RandomForestRegressor\n    from sklearn.metrics import mean_absolute_error, root_mean_squared_error, r2_score",
        "from sklearn.ensemble import RandomForestClassifier\n    from sklearn.metrics import accuracy_score, precision_recall_fscore_support"
    )
    
    # 2. Config
    content = content.replace(
        '"n_estimators": 300,\n    "max_depth": 12,\n    "random_state": 42,\n    "n_jobs": -1,\n    "min_samples_leaf": 5,',
        '"n_estimators": 300,\n    "max_depth": 12,\n    "class_weight": "balanced",\n    "random_state": 42,\n    "n_jobs": -1,'
    )
    
    # 3. Target mapping
    old_target = 'df["htsi_score_lead_6"] = df.groupby("ward_id")["htsi_score"].shift(-FORECAST_HORIZON)\n\n    n_target_nan = df["htsi_score_lead_6"].isna().sum()'
    new_target = 'df["htsi_score_lead_6"] = df.groupby("ward_id")["htsi_score"].shift(-FORECAST_HORIZON)\n    df["risk_label_lead_6"] = df["htsi_score_lead_6"].apply(lambda x: classify_risk(int(round(x))) if pd.notna(x) else np.nan)\n\n    n_target_nan = df["htsi_score_lead_6"].isna().sum()'
    content = content.replace(old_target, new_target)
    
    content = content.replace('TARGET_COL = "htsi_score_lead_6"', 'TARGET_COL = "risk_label_lead_6"')
    
    # 4. evaluate_persistence
    old_persist = '''def evaluate_persistence(df_test: pd.DataFrame) -> dict:
    """Persistence baseline: predict HTSI(t+6) = HTSI(t)."""
    print("\\n" + "=" * 60)
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
            "predictions": y_persistence}'''
            
    new_persist = '''def evaluate_persistence(df_test: pd.DataFrame) -> dict:
    """Persistence baseline: predict risk(t+6) = risk(t)."""
    print("\\n" + "=" * 60)
    print("Step 8 -- Persistence Baseline (predict t+6 = t)")
    print("=" * 60)

    y_actual = df_test[TARGET_COL].values
    y_persistence_htsi = df_test["htsi_score"].values
    y_persistence = [classify_risk(int(round(v))) for v in y_persistence_htsi]

    acc = accuracy_score(y_actual, y_persistence)
    print(f"  Persistence Accuracy: {acc:.4f}")

    return {"acc": round(acc, 4), "predictions": y_persistence}'''
    content = content.replace(old_persist, new_persist)
    
    # 5. train_random_forest
    old_train = '''def train_random_forest(df_train: pd.DataFrame, df_val: pd.DataFrame):
    """Train RandomForestRegressor and evaluate on validation set."""
    print("\\n" + "=" * 60)
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
    print(f"\\n  Training in progress ...")

    model = RandomForestRegressor(**RF_CONFIG)
    model.fit(X_train, y_train)

    # Validation metrics
    y_val_pred = model.predict(X_val)
    val_mae = mean_absolute_error(y_val, y_val_pred)
    val_rmse = root_mean_squared_error(y_val, y_val_pred)
    val_r2 = r2_score(y_val, y_val_pred)

    print(f"\\n  Validation MAE:  {val_mae:.4f}")
    print(f"  Validation RMSE: {val_rmse:.4f}")
    print(f"  Validation R2:   {val_r2:.4f}")

    return model'''
    
    new_train = '''def train_random_forest(df_train: pd.DataFrame, df_val: pd.DataFrame):
    """Train RandomForestClassifier and evaluate on validation set."""
    print("\\n" + "=" * 60)
    print("Step 9-10 -- Train Random Forest Classifier")
    print("=" * 60)

    X_train = df_train[FEATURE_COLS].values
    y_train = df_train[TARGET_COL].values
    X_val = df_val[FEATURE_COLS].values
    y_val = df_val[TARGET_COL].values

    print(f"  Training samples:   {len(X_train):,}")
    print(f"  Validation samples: {len(X_val):,}")
    print(f"  Features:           {len(FEATURE_COLS)}")
    print(f"  Config: {RF_CONFIG}")
    print(f"\\n  Training in progress ...")

    model = RandomForestClassifier(**RF_CONFIG)
    model.fit(X_train, y_train)

    # Validation metrics
    y_val_pred = model.predict(X_val)
    val_acc = accuracy_score(y_val, y_val_pred)

    print(f"\\n  Validation Accuracy: {val_acc:.4f}")

    return model'''
    content = content.replace(old_train, new_train)
    
    # 6. evaluate_on_test & print_comparison
    old_test = '''def evaluate_on_test(model, df_test: pd.DataFrame) -> dict:
    """Evaluate RF model on the held-out test set."""
    print("\\n" + "=" * 60)
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
    print("\\n  " + "-" * 55)
    print(f"  {'MODEL':<25s} {'MAE':>8s}   {'RMSE':>8s}   {'R2':>8s}")
    print("  " + "-" * 55)
    print(f"  {'Persistence':<25s} {persist_metrics['mae']:>8.4f}   "
          f"{persist_metrics['rmse']:>8.4f}   {persist_metrics['r2']:>8.4f}")
    print(f"  {'Random Forest':<25s} {rf_metrics['mae']:>8.4f}   "
          f"{rf_metrics['rmse']:>8.4f}   {rf_metrics['r2']:>8.4f}")
    print("  " + "-" * 55)

    if rf_metrics["mae"] < persist_metrics["mae"]:
        improvement = (1 - rf_metrics["mae"] / persist_metrics["mae"]) * 100
        print(f"\\n  Random Forest beats persistence by {improvement:.1f}% MAE reduction.")
    elif rf_metrics["mae"] > persist_metrics["mae"]:
        print(f"\\n  [NOTE] Persistence baseline outperforms Random Forest on MAE.")
        print(f"  This is informative -- persistence is a strong baseline for short horizons.")
    else:
        print(f"\\n  Random Forest and persistence perform identically on MAE.")'''
        
    new_test = '''def evaluate_on_test(model, df_test: pd.DataFrame) -> dict:
    """Evaluate RF model on the held-out test set."""
    print("\\n" + "=" * 60)
    print("Step 11 -- Random Forest Test Evaluation")
    print("=" * 60)

    X_test = df_test[FEATURE_COLS].values
    y_actual = df_test[TARGET_COL].values
    y_pred = model.predict(X_test)

    acc = accuracy_score(y_actual, y_pred)
    print(f"  Random Forest Accuracy: {acc:.4f}")

    return {"acc": round(acc, 4), "predictions": y_pred}


def print_comparison(persist_metrics: dict, rf_metrics: dict) -> None:
    """Print side-by-side comparison of persistence vs RF."""
    print("\\n  " + "-" * 45)
    print(f"  {'MODEL':<25s} {'ACCURACY':>8s}")
    print("  " + "-" * 45)
    print(f"  {'Persistence':<25s} {persist_metrics['acc']:>8.4f}")
    print(f"  {'Random Forest':<25s} {rf_metrics['acc']:>8.4f}")
    print("  " + "-" * 45)

    if rf_metrics["acc"] > persist_metrics["acc"]:
        improvement = (rf_metrics["acc"] - persist_metrics["acc"]) * 100
        print(f"\\n  Random Forest beats persistence by {improvement:.1f}% accuracy.")
    else:
        print(f"\\n  Persistence matches or beats Random Forest.")'''
    content = content.replace(old_test, new_test)

    # 7. evaluate_risk_categories
    old_risk = '''def evaluate_risk_categories(y_actual_htsi, y_pred_htsi, label: str) -> float:
    """Convert predicted HTSI to risk categories using the existing engine."""
    print(f"\\n  Risk category evaluation ({label}):")

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
    print(f"\\n    Confusion Matrix (rows=actual, cols=predicted):")
    header = "              " + "  ".join(f"{l:>10s}" for l in present_labels)
    print(f"    {header}")
    for i, row_label in enumerate(present_labels):
        row_str = "  ".join(f"{cm[i, j]:>10d}" for j in range(len(present_labels)))
        print(f"    {row_label:>12s}  {row_str}")

    return accuracy'''
    
    new_risk = '''def evaluate_risk_categories(actual_risk, pred_risk, label: str) -> float:
    """Evaluate risk categories using classification metrics."""
    print(f"\\n  Risk category evaluation ({label}):")

    acc = accuracy_score(actual_risk, pred_risk)
    correct = sum(1 for a, p in zip(actual_risk, pred_risk) if a == p)
    print(f"    Category accuracy: {acc:.4f} ({correct}/{len(actual_risk)})")

    labels = ["LOW", "MODERATE", "HIGH", "EXTREME"]
    present_labels = sorted(set(actual_risk) | set(pred_risk),
                            key=lambda x: labels.index(x) if x in labels else 99)

    cm = confusion_matrix(actual_risk, pred_risk, labels=present_labels)
    print(f"\\n    Confusion Matrix (rows=actual, cols=predicted):")
    header = "              " + "  ".join(f"{l:>10s}" for l in present_labels)
    print(f"    {header}")
    for i, row_label in enumerate(present_labels):
        row_str = "  ".join(f"{cm[i, j]:>10d}" for j in range(len(present_labels)))
        print(f"    {row_label:>12s}  {row_str}")

    precision, recall, f1, _ = precision_recall_fscore_support(
        actual_risk, pred_risk, labels=present_labels, zero_division=0
    )
    print("\\n    Class Metrics:")
    for i, row_label in enumerate(present_labels):
        print(f"      {row_label:>10s} - Precision: {precision[i]:.4f} | Recall: {recall[i]:.4f} | F1: {f1[i]:.4f}")

    return acc'''
    content = content.replace(old_risk, new_risk)
    
    # 8. save_model
    content = content.replace('"model_type": "RandomForestRegressor"', '"model_type": "RandomForestClassifier"')
    
    # 9. save_metrics
    old_save_metrics = '''def save_metrics(
    df, df_train, df_val, df_test,
    persist_metrics, rf_metrics, risk_accuracy
) -> None:
    """Save comprehensive metrics JSON."""
    print("\\n" + "=" * 60)
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
    }'''
    
    new_save_metrics = '''def save_metrics(
    df, df_train, df_val, df_test,
    persist_metrics, rf_metrics, risk_accuracy
) -> None:
    """Save comprehensive metrics JSON."""
    print("\\n" + "=" * 60)
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
            "acc": persist_metrics["acc"],
        },
        "random_forest": {
            "config": RF_CONFIG,
            "acc": rf_metrics["acc"],
        },
        "rf_beats_persistence": rf_metrics["acc"] > persist_metrics["acc"],
        "generated_at": datetime.now().isoformat(),
    }'''
    content = content.replace(old_save_metrics, new_save_metrics)
    
    # 10. save_predictions
    old_save_preds = '''def save_predictions(
    df_test: pd.DataFrame,
    rf_predictions,
    persist_predictions,
) -> None:
    """Save test set predictions for later analysis."""
    print("\\n" + "=" * 60)
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
    })'''
    
    new_save_preds = '''def save_predictions(
    df_test: pd.DataFrame,
    rf_predictions,
    persist_predictions,
) -> None:
    """Save test set predictions for later analysis."""
    print("\\n" + "=" * 60)
    print("Step 16 -- Save Test Predictions")
    print("=" * 60)

    y_actual = df_test[TARGET_COL].values
    y_actual_htsi = df_test["htsi_score_lead_6"].values

    pred_df = pd.DataFrame({
        "timestamp": df_test["timestamp"].values,
        "ward_id": df_test["ward_id"].values,
        "actual_htsi": y_actual_htsi,
        "actual_risk": y_actual,
        "predicted_risk": rf_predictions,
        "persistence_prediction": persist_predictions,
    })'''
    content = content.replace(old_save_preds, new_save_preds)
    
    # Main function changes (lines 729-735)
    content = content.replace(
        '''    y_actual_test = df_test[TARGET_COL].values
    risk_accuracy_rf = evaluate_risk_categories(
        y_actual_test, rf_metrics["predictions"], "Random Forest"
    )
    _ = evaluate_risk_categories(
        y_actual_test, persist_metrics["predictions"], "Persistence"
    )''',
        '''    y_actual_test = df_test[TARGET_COL].values
    risk_accuracy_rf = evaluate_risk_categories(
        y_actual_test, rf_metrics["predictions"], "Random Forest Classifier"
    )
    _ = evaluate_risk_categories(
        y_actual_test, persist_metrics["predictions"], "Persistence"
    )'''
    )
    
    content = content.replace(
        '''print(f"\\n  RF beats persistence: {rf_metrics['mae'] < persist_metrics['mae']}")''',
        '''print(f"\\n  RF beats persistence: {rf_metrics['acc'] > persist_metrics['acc']}")'''
    )

    with open(path, "w") as f:
        f.write(content)

if __name__ == "__main__":
    main()
