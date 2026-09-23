#!/usr/bin/env python3

import argparse
from pathlib import Path

import pandas as pd

from wildlocate.core.environment_features import extract_features
from wildlocate.core.data.inaturalist import species_slug

DEFAULT_INPUT_DIR = Path("data/processed/samples")
DEFAULT_OUTPUT_DIR = Path("data/processed/features/species")
DEFAULT_FAILURE_THRESHOLD = 0.05


def validate_training_points(df):
    required_columns = {"latitude", "longitude", "presence"}
    missing = sorted(required_columns.difference(df.columns))
    if missing:
        raise ValueError(
            f"Training points file is missing required columns: {missing}"
        )

    df["presence"] = pd.to_numeric(df["presence"], errors="coerce")
    if df["presence"].isna().any():
        raise ValueError("Training points file contains non-numeric or missing presence values.")

    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")

    if df[["latitude", "longitude"]].isna().any().any():
        raise ValueError("Training points file contains missing latitude/longitude values.")


def build_species_dataset(
    species_name,
    training_points_file=None,
    output_file=None,
    progress=None,
    region="MA",
):
    slug = species_slug(species_name)
    training_path = Path(training_points_file) if training_points_file else DEFAULT_INPUT_DIR / f"{slug}_training_points.csv"

    if not training_path.exists():
        raise FileNotFoundError(
            f"Could not find training points at {training_path}. Run the Phase 4 background step first."
        )

    training_df = pd.read_csv(training_path)
    validate_training_points(training_df)
    if region != "MA":
        from wildlocate.core.data.regional import prefetch_training_tiles
        prefetch_training_tiles(training_df, region, progress)

    output_path = Path(output_file) if output_file else DEFAULT_OUTPUT_DIR / f"{slug}_features.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    successful_rows = []
    failed_rows = []

    total_rows = len(training_df)
    presence_count = int((training_df["presence"] == 1).sum())
    background_count = int((training_df["presence"] == 0).sum())

    feature_columns = None

    for row_idx, row in training_df.iterrows():
        if progress and (row_idx % 25 == 0 or row_idx == total_rows - 1):
            progress(f"Extracting environmental features: {row_idx + 1:,} of {total_rows:,} locations…")
        latitude = float(row["latitude"])
        longitude = float(row["longitude"])
        presence = int(row["presence"])

        try:
            if region == "MA":
                features = extract_features(latitude, longitude)
            else:
                from wildlocate.core.data.regional import extract_regional_features
                features = extract_regional_features(latitude, longitude, region, progress)
        except Exception as exc:
            failed_rows.append(
                {
                    "row_index": int(row_idx),
                    "latitude": latitude,
                    "longitude": longitude,
                    "presence": presence,
                    "error": str(exc),
                }
            )
            continue

        if feature_columns is None:
            feature_columns = list(features.keys())

        combined_row = {
            "latitude": latitude,
            "longitude": longitude,
            "presence": presence,
        }
        combined_row.update(features)
        successful_rows.append(combined_row)

    if not successful_rows:
        raise RuntimeError("No rows were successfully processed; feature dataset could not be built.")

    output_df = pd.DataFrame(successful_rows)

    output_columns = ["latitude", "longitude", "presence", *feature_columns]
    output_df = output_df.reindex(columns=output_columns)

    output_df.to_csv(output_path, index=False)

    failed_presence_rows = sum(1 for row in failed_rows if int(row["presence"]) == 1)
    failed_background_rows = sum(1 for row in failed_rows if int(row["presence"]) == 0)

    overall_failure_rate = len(failed_rows) / total_rows
    presence_failure_rate = failed_presence_rows / presence_count if presence_count else 0.0
    background_failure_rate = failed_background_rows / background_count if background_count else 0.0

    class_failure_disproportionate = False
    if presence_count and background_count:
        max_rate = max(presence_failure_rate, background_failure_rate)
        min_rate = min(presence_failure_rate, background_failure_rate)
        class_failure_disproportionate = max_rate > 0.0 and max_rate >= (2.0 * min_rate) and max_rate > DEFAULT_FAILURE_THRESHOLD

    if (
        overall_failure_rate > DEFAULT_FAILURE_THRESHOLD
        or presence_failure_rate > DEFAULT_FAILURE_THRESHOLD
        or background_failure_rate > DEFAULT_FAILURE_THRESHOLD
        or class_failure_disproportionate
    ):
        raise RuntimeError(
            "Feature build failed because failure thresholds were exceeded: "
            f"overall={overall_failure_rate:.4f}, presence={presence_failure_rate:.4f}, "
            f"background={background_failure_rate:.4f}, class_disproportionate={class_failure_disproportionate}."
        )

    print(f"Saved feature dataset to: {output_path}")
    print(f"Input rows: {total_rows}")
    print(f"Output rows: {len(output_df)}")
    print(f"Failed rows: {len(failed_rows)}")

    if failed_rows:
        print("Sample failures:")
        for failure in failed_rows[:10]:
            print(
                f"  row_index={failure['row_index']} presence={failure['presence']} "
                f"lat={failure['latitude']} lon={failure['longitude']} error={failure['error']}"
            )

    return output_df, pd.DataFrame(failed_rows)


def main():
    parser = argparse.ArgumentParser(
        description="Build a species-specific ML feature table by running the canonical environmental extractor on every training-point row.",
    )
    parser.add_argument("--species", required=True)
    parser.add_argument("--training-points", default=None)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    build_species_dataset(
        species_name=args.species,
        training_points_file=args.training_points,
        output_file=args.output,
    )


if __name__ == "__main__":
    main()
