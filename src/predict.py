#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

if __package__ in {None, ""}:
    ROOT = Path(__file__).resolve().parents[1]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

from src.features.extract import extract_features

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "data/processed/models"
FEATURES_DIR = ROOT / "data/processed/features/species"


def species_slug(species: str) -> str:
    return species.strip().lower().replace(" ", "_")


def format_model_name(model_name: str) -> str:
    if model_name == "RandomForest":
        return "Random Forest"
    return model_name


def load_model_and_metadata(species: str) -> tuple[Any, dict[str, Any]]:
    slug = species_slug(species)
    model_path = MODEL_DIR / f"{slug}.joblib"
    metrics_path = MODEL_DIR / f"{slug}_metrics.json"

    if not model_path.exists() or not metrics_path.exists():
        raise FileNotFoundError(
            f"No trained model found for {species}.\n"
            f"Train it first with:\n"
            f'python3 src/models/train_species.py --species "{species}"'
        )

    model = joblib.load(model_path)
    metrics = json.loads(metrics_path.read_text())
    return model, metrics


def validate_lat_lon(latitude: float, longitude: float) -> None:
    if latitude is None or longitude is None:
        raise ValueError("Latitude and longitude are required.")
    if not (-90 <= latitude <= 90):
        raise ValueError(f"Invalid latitude {latitude}. Latitude must be between -90 and 90.")
    if not (-180 <= longitude <= 180):
        raise ValueError(f"Invalid longitude {longitude}. Longitude must be between -180 and 180.")


def build_prediction_frame(features: dict[str, float], predictor_names: list[str]) -> pd.DataFrame:
    missing = [name for name in predictor_names if name not in features]
    if missing:
        raise ValueError(
            "Missing required predictors from environmental feature extraction: "
            + ", ".join(missing)
        )

    missing_values = [name for name in predictor_names if pd.isna(features[name])]
    if missing_values:
        raise ValueError(
            "Environmental feature extraction returned missing values for required predictors: "
            + ", ".join(missing_values)
        )

    return pd.DataFrame([[features[name] for name in predictor_names]], columns=predictor_names)


def load_comparison_scores(model: Any, predictor_names: list[str], species: str) -> tuple[np.ndarray, pd.DataFrame]:
    slug = species_slug(species)
    comparison_file = FEATURES_DIR / f"{slug}_features.csv"

    if not comparison_file.exists():
        raise FileNotFoundError(
            f"Could not find comparison feature dataset for {species} at {comparison_file}."
        )

    comparison_df = pd.read_csv(comparison_file)
    if predictor_names[0] not in comparison_df.columns:
        raise ValueError(
            f"Comparison dataset for {species} does not contain the expected predictor columns."
        )

    compare_X = comparison_df[predictor_names]
    scores = model.predict_proba(compare_X)[:, 1]
    return np.asarray(scores, dtype=float), comparison_df


def percentile_of_score(score: float, comparison_scores: np.ndarray) -> int:
    if comparison_scores.size == 0:
        raise ValueError("Cannot compute percentile because the comparison dataset is empty.")

    score_array = np.asarray(comparison_scores, dtype=float)
    below = float(np.mean(score_array < score))
    percentile = int(round(100 * below))
    return max(0, min(100, percentile))


def category_for_percentile(percentile: int) -> str:
    if percentile < 20:
        return "Very Low"
    if percentile < 40:
        return "Low"
    if percentile < 60:
        return "Moderate"
    if percentile < 80:
        return "High"
    return "Very High"


def print_results(
    species: str,
    latitude: float,
    longitude: float,
    score: float,
    percentile: int,
    category: str,
    model_name: str,
    presence_count: int,
    feature_values: dict[str, float],
    predictor_names: list[str],
) -> None:
    print("Wild-Locate Habitat Assessment")
    print("------------------------------")
    print()
    print(f"Species: {species}")
    print(f"Location: {latitude}, {longitude}")
    print()
    print(f"Relative habitat suitability score: {score:.3f}")
    print(f"Suitability percentile: {percentile}th")
    print(f"Category: {category}")
    print()
    print(f"Model: {format_model_name(model_name)}")
    print(f"Species observations used for training: {presence_count}")
    print()
    print("Interpretation:")
    print(
        f"This location received a higher habitat-suitability score than\n"
        f"approximately {percentile}% of comparison locations for this species."
    )
    print()
    print("The score is relative and should not be interpreted as a probability")
    print("that the species is currently present at this location.")
    print()
    print("Environmental conditions:")
    for name in predictor_names:
        print(f"{name}: {feature_values[name]}")


def predict_species(species: str, latitude: float, longitude: float) -> dict[str, Any]:
    """Run the existing prediction calculation for the CLI, API, and desktop app."""
    species = species.strip()
    if not species:
        raise ValueError("Species name cannot be empty.")

    validate_lat_lon(latitude, longitude)

    model, metrics = load_model_and_metadata(species)

    predictor_names = metrics.get("predictor_names")
    if not predictor_names:
        raise RuntimeError(
            f"Saved model metadata for {species} does not include predictor names. "
            "Please restore the model metadata."
        )

    extracted_features = extract_features(latitude, longitude)

    prediction_frame = build_prediction_frame(extracted_features, predictor_names)

    if not hasattr(model, "predict_proba"):
        raise RuntimeError(
            f"Saved model for {species} does not support predict_proba, so a relative suitability score cannot be computed."
        )

    predicted_score = float(model.predict_proba(prediction_frame)[0, 1])
    if not np.isfinite(predicted_score):
        raise RuntimeError("Prediction failed: the computed suitability score is not finite.")

    comparison_scores, _ = load_comparison_scores(model, predictor_names, species)
    percentile = percentile_of_score(predicted_score, comparison_scores)
    category = category_for_percentile(percentile)

    return {
        "species": species,
        "latitude": latitude,
        "longitude": longitude,
        "score": predicted_score,
        "percentile": percentile,
        "category": category,
        "model": format_model_name(metrics.get("selected_model", "Unknown Model")),
        "training_observations": int(metrics.get("presence_count", 0)),
        "features": {name: float(extracted_features[name]) for name in predictor_names},
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Predict relative habitat suitability for a species at a Massachusetts location.",
    )
    parser.add_argument("--species", required=True, help="Species name, for example Fisher or Bobcat.")
    parser.add_argument("--lat", required=True, type=float, help="Latitude in EPSG:4326.")
    parser.add_argument("--lon", required=True, type=float, help="Longitude in EPSG:4326.")
    args = parser.parse_args()
    result = predict_species(args.species, args.lat, args.lon)
    print_results(
        species=result["species"],
        latitude=result["latitude"],
        longitude=result["longitude"],
        score=result["score"],
        percentile=result["percentile"],
        category=result["category"],
        model_name=result["model"],
        presence_count=result["training_observations"],
        feature_values=result["features"],
        predictor_names=list(result["features"]),
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        raise SystemExit(f"Error: {exc}") from exc
