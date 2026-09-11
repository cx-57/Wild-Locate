#!/usr/bin/env python3

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from pyproj import Transformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

OUTPUT_DIR = Path("data/processed/models")
TARGET_COLUMN = "presence"
RANDOM_STATE = 42
N_FOLDS = 5
DEFAULT_BLOCK_SIZE_M = 10000
EXCLUDED_COLUMNS = {
    "latitude",
    "longitude",
    "presence",
    "species",
    "species_name",
    "observation_id",
    "taxon_id",
    "species_slug",
}
MODEL_COMPLEXITY = {"LogisticRegression": 0, "RandomForest": 1, "XGBoost": 2}


def species_slug(species):
    return species.strip().lower().replace(" ", "_")


def load_dataset(dataset_file):
    df = pd.read_csv(dataset_file)
    if TARGET_COLUMN not in df.columns:
        raise ValueError(f"Target column '{TARGET_COLUMN}' not found in {dataset_file}")
    return df


def infer_feature_columns(df):
    feature_columns = [
        column
        for column in df.columns
        if column not in EXCLUDED_COLUMNS and column != TARGET_COLUMN
    ]

    if not feature_columns:
        raise ValueError("No predictor columns were found in the feature dataset.")

    leakage_columns = [
        column
        for column in feature_columns
        if column.lower() in {"latitude", "longitude", "presence", "species", "species_name", "observation_id", "taxon_id"}
    ]
    if leakage_columns:
        raise ValueError(
            "Feature leakage detected: the following columns were incorrectly included as predictors: "
            + ", ".join(leakage_columns)
        )

    return feature_columns


def build_spatial_groups(df, block_size_m):
    if block_size_m <= 0:
        raise ValueError("block_size_m must be positive.")

    transformer = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)
    lon_values = df["longitude"].to_numpy(dtype=float)
    lat_values = df["latitude"].to_numpy(dtype=float)
    x_m, y_m = transformer.transform(lon_values, lat_values)

    block_x = np.floor(x_m / block_size_m).astype(int)
    block_y = np.floor(y_m / block_size_m).astype(int)
    groups = np.char.add(block_x.astype(str), np.char.add("_", block_y.astype(str)))
    return groups


def build_estimator(model_name):
    if model_name == "LogisticRegression":
        return Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
                (
                    "model",
                    LogisticRegression(
                        max_iter=5000,
                        class_weight="balanced",
                        random_state=RANDOM_STATE,
                        solver="lbfgs",
                    ),
                ),
            ]
        )

    if model_name == "RandomForest":
        return Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                (
                    "model",
                    RandomForestClassifier(
                        n_estimators=300,
                        max_depth=None,
                        min_samples_leaf=2,
                        class_weight="balanced",
                        random_state=RANDOM_STATE,
                        n_jobs=-1,
                    ),
                ),
            ]
        )

    if model_name == "XGBoost":
        try:
            from xgboost import XGBClassifier
        except Exception as exc:
            raise RuntimeError("XGBoost is not available.") from exc

        return Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                (
                    "model",
                    XGBClassifier(
                        n_estimators=300,
                        max_depth=4,
                        learning_rate=0.05,
                        subsample=0.8,
                        colsample_bytree=0.8,
                        reg_alpha=0.5,
                        reg_lambda=1.0,
                        min_child_weight=2,
                        objective="binary:logistic",
                        eval_metric="logloss",
                        random_state=RANDOM_STATE,
                        n_jobs=-1,
                        use_label_encoder=False,
                    ),
                ),
            ]
        )

    raise ValueError(f"Unsupported model type: {model_name}")


def build_models():
    models = [
        {"name": "LogisticRegression", "estimator": None},
        {"name": "RandomForest", "estimator": None},
    ]

    try:
        from xgboost import XGBClassifier  # noqa: F401
        models.append({"name": "XGBoost", "estimator": None})
    except Exception:
        print("XGBoost not available; skipping XGBoost model.")

    return models


def select_spatial_splits(df, feature_columns, y):
    candidate_block_sizes = [10000, 15000, 20000, 25000, 30000, 40000, 50000]
    last_error = None

    X = df[feature_columns]

    for block_size_m in candidate_block_sizes:
        groups = build_spatial_groups(df, block_size_m=block_size_m)
        splitter = StratifiedGroupKFold(n_splits=N_FOLDS, shuffle=True, random_state=RANDOM_STATE)

        try:
            splits = list(splitter.split(X, y, groups))
        except Exception as exc:
            last_error = exc
            continue

        fold_validity_errors = []
        for fold_index, (train_idx, val_idx) in enumerate(splits, start=1):
            y_train = y.iloc[train_idx]
            y_val = y.iloc[val_idx]

            train_classes = np.unique(y_train.to_numpy(dtype=int))
            val_classes = np.unique(y_val.to_numpy(dtype=int))

            if len(train_classes) < 2:
                fold_validity_errors.append(
                    f"Fold {fold_index} training split contains only one class; block size {block_size_m}m is too coarse."
                )
                continue
            if len(val_classes) < 2:
                fold_validity_errors.append(
                    f"Fold {fold_index} validation split contains only one class; block size {block_size_m}m is too coarse."
                )
                continue

        if fold_validity_errors:
            last_error = RuntimeError("; ".join(fold_validity_errors))
            continue

        notes = [
            f"Used spatial 10 km x 10 km blocks for cross-validation." if block_size_m == DEFAULT_BLOCK_SIZE_M else f"Used spatial {block_size_m}m blocks because the default 10 km grid produced invalid folds."
        ]
        return groups, splits, block_size_m, notes

    if last_error is None:
        raise RuntimeError("Unable to build any valid spatial cross-validation splits.")

    raise RuntimeError(
        "Unable to build valid spatial cross-validation splits with the requested 10 km blocks. "
        f"Last error: {last_error}"
    )


def evaluate_models(df, feature_columns, splits, progress=None):
    X = df[feature_columns]
    y = df[TARGET_COLUMN].astype(int)

    model_specs = build_models()
    model_results = []

    for model_info in model_specs:
        model_name = model_info["name"]
        fold_metrics = []
        fold_roc_values = []
        fold_pr_values = []

        for fold_index, (train_idx, val_idx) in enumerate(splits, start=1):
            if progress:
                progress(f"Evaluating {model_name}: spatial fold {fold_index} of {len(splits)}…")
            X_train = X.iloc[train_idx].copy()
            y_train = y.iloc[train_idx].copy().astype(int)
            X_val = X.iloc[val_idx].copy()
            y_val = y.iloc[val_idx].copy().astype(int)

            if y_train.nunique() < 2 or y_val.nunique() < 2:
                raise RuntimeError(
                    f"Model {model_name} fold {fold_index} does not contain both classes after spatial splitting."
                )

            estimator = build_estimator(model_name)
            estimator.fit(X_train, y_train)
            val_proba = estimator.predict_proba(X_val)[:, 1]

            roc_auc = float(roc_auc_score(y_val, val_proba))
            pr_auc = float(average_precision_score(y_val, val_proba))

            if not np.isfinite(roc_auc) or not np.isfinite(pr_auc):
                raise RuntimeError(
                    f"Non-finite metric encountered for {model_name} in fold {fold_index}."
                )

            fold_roc_values.append(roc_auc)
            fold_pr_values.append(pr_auc)
            fold_metrics.append(
                {
                    "fold": fold_index,
                    "roc_auc": roc_auc,
                    "pr_auc": pr_auc,
                    "train_presence": int(y_train.sum()),
                    "train_background": int((1 - y_train).sum()),
                    "val_presence": int(y_val.sum()),
                    "val_background": int((1 - y_val).sum()),
                }
            )

        model_results.append(
            {
                "model": model_name,
                "fold_metrics": fold_metrics,
                "mean_roc_auc": float(np.mean(fold_roc_values)),
                "std_roc_auc": float(np.std(fold_roc_values, ddof=0)),
                "mean_pr_auc": float(np.mean(fold_pr_values)),
                "std_pr_auc": float(np.std(fold_pr_values, ddof=0)),
                "roc_auc_folds": [float(value) for value in fold_roc_values],
                "pr_auc_folds": [float(value) for value in fold_pr_values],
            }
        )

    return model_results, {"models": model_results}


def pick_best_model(model_results):
    sorted_results = sorted(
        model_results,
        key=lambda item: (
            -item["mean_pr_auc"],
            -item["mean_roc_auc"],
            MODEL_COMPLEXITY.get(item["model"], 99),
        ),
    )
    return sorted_results[0]


def top_features_for_model(model_name, fitted_pipeline, feature_columns, top_n=5):
    if model_name == "LogisticRegression":
        coefficients = fitted_pipeline.named_steps["model"].coef_[0]
        ranked = sorted(
            zip(feature_columns, np.abs(coefficients), coefficients),
            key=lambda item: item[1],
            reverse=True,
        )
        return [
            {
                "feature": feature,
                "absolute_coefficient": float(abs_coefficient),
                "coefficient": float(coefficient),
            }
            for feature, abs_coefficient, coefficient in ranked[:top_n]
        ]

    if model_name in {"RandomForest", "XGBoost"}:
        importances = fitted_pipeline.named_steps["model"].feature_importances_
        ranked = sorted(
            zip(feature_columns, importances),
            key=lambda item: item[1],
            reverse=True,
        )
        return [
            {
                "feature": feature,
                "importance": float(importance),
            }
            for feature, importance in ranked[:top_n]
        ]

    raise ValueError(f"Unsupported model for feature interpretation: {model_name}")


def save_metrics_json(metrics_path, payload):
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(json.dumps(payload, indent=2))


def train_species(species, dataset_file=None, output_dir=OUTPUT_DIR, progress=None):
    species = species.strip()
    slug = species_slug(species)
    dataset_file = Path(dataset_file) if dataset_file is not None else Path(f"data/processed/features/species/{slug}_features.csv")
    output_dir = Path(output_dir)

    if not dataset_file.exists():
        raise FileNotFoundError(f"Could not find species feature dataset at {dataset_file}.")

    print(f"Loading species feature dataset for {species} from {dataset_file}...")
    df = load_dataset(dataset_file)

    feature_columns = infer_feature_columns(df)
    if "latitude" not in df.columns or "longitude" not in df.columns:
        raise ValueError("Latitude and longitude must be present in the feature dataset.")

    missing_values = {
        column: int(df[column].isna().sum())
        for column in feature_columns
        if df[column].isna().any()
    }
    if missing_values:
        print("Detected missing values in predictor columns; median imputation will be used inside each training fold.")
        print(json.dumps(missing_values, indent=2))

    print("\nPreparing spatial cross-validation...")
    y = df[TARGET_COLUMN].astype(int)
    groups, splits, block_size_m, split_notes = select_spatial_splits(df, feature_columns, y)

    print(f"Using spatial block size: {block_size_m} meters")
    for note in split_notes:
        print(note)

    print(f"Spatial folds generated: {len(splits)}")
    for fold_index, (_, val_idx) in enumerate(splits, start=1):
        y_val = y.iloc[val_idx]
        print(f"Fold {fold_index}: presence={int(y_val.sum())}, background={int((1 - y_val).sum())}")

    if any((y.iloc[val_idx].sum() == 0) or ((1 - y.iloc[val_idx]).sum() == 0) for _, val_idx in splits):
        raise RuntimeError("At least one spatial fold is missing one of the target classes.")

    print("\nRunning spatial cross-validation for each candidate model...")
    model_results, _ = evaluate_models(df, feature_columns, splits, progress=progress)

    best_result = pick_best_model(model_results)

    print("\nModel comparison summary:")
    print(
        pd.DataFrame(
            [
                {
                    "Model": item["model"],
                    "Mean ROC-AUC": item["mean_roc_auc"],
                    "Mean PR-AUC": item["mean_pr_auc"],
                }
                for item in model_results
            ]
        )
        .sort_values(["Mean PR-AUC", "Mean ROC-AUC"], ascending=False)
        .to_string(index=False)
    )

    print(f"\nSelected model: {best_result['model']}")

    X_full = df[feature_columns]
    y_full = df[TARGET_COLUMN].astype(int)
    selected_pipeline = build_estimator(best_result["model"])
    if progress:
        progress(f"Fitting the selected {best_result['model']} model on all training locations…")
    selected_pipeline.fit(X_full, y_full)

    selected_features = top_features_for_model(best_result["model"], selected_pipeline, feature_columns)

    output_dir.mkdir(parents=True, exist_ok=True)
    model_path = output_dir / f"{slug}.joblib"
    metrics_path = output_dir / f"{slug}_metrics.json"

    joblib.dump(selected_pipeline, model_path)

    metrics_payload = {
        "species": species,
        "species_slug": slug,
        "total_rows": int(len(df)),
        "presence_count": int(y_full.sum()),
        "background_count": int((1 - y_full).sum()),
        "predictor_names": feature_columns,
        "spatial_block_size_m": int(block_size_m),
        "number_of_folds": N_FOLDS,
        "random_state": RANDOM_STATE,
        "selected_model": best_result["model"],
        "candidate_models": [item["model"] for item in model_results],
        "leakage_check": {
            "excluded_columns": sorted(EXCLUDED_COLUMNS),
            "evidence": {
                "latitude_not_predictor": "latitude" not in feature_columns,
                "longitude_not_predictor": "longitude" not in feature_columns,
                "presence_not_predictor": TARGET_COLUMN not in feature_columns,
            },
        },
        "split_notes": split_notes,
        "metrics_by_model": [],
        "selected_model_top_features": selected_features,
    }

    for item in model_results:
        metrics_payload["metrics_by_model"].append(
            {
                "model": item["model"],
                "mean_roc_auc": item["mean_roc_auc"],
                "std_roc_auc": item["std_roc_auc"],
                "mean_pr_auc": item["mean_pr_auc"],
                "std_pr_auc": item["std_pr_auc"],
                "roc_auc_folds": item["roc_auc_folds"],
                "pr_auc_folds": item["pr_auc_folds"],
                "fold_metrics": item["fold_metrics"],
            }
        )

    save_metrics_json(metrics_path, metrics_payload)

    print(f"\nSaved trained model to: {model_path}")
    print(f"Saved metrics metadata to: {metrics_path}")
    return model_path, metrics_path, metrics_payload


def main():
    parser = argparse.ArgumentParser(description="Train and evaluate species-specific habitat suitability models using spatial CV.")
    parser.add_argument("--species", required=True)
    parser.add_argument("--dataset", default=None)
    args = parser.parse_args()
    train_species(args.species, args.dataset)


if __name__ == "__main__":
    main()
