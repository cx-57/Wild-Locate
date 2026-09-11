#!/usr/bin/env python3

import argparse
import math
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from pyproj import Transformer

from wildlocate.core.data.inaturalist import resolve_species

API_BASE = "https://api.inaturalist.org/v1"
MAMMAL_POOL_FILE = Path("data/processed/samples/massachusetts_mammal_pool.csv")
DEFAULT_MAX_MAMMAL_POOL = 50000


def species_slug(species_name):
    slug = re.sub(r"[^a-z0-9]+", "_", species_name.strip().lower())
    slug = slug.strip("_")
    if not slug:
        raise ValueError("Species name is required.")
    return slug


def api_get(endpoint, params=None):
    response = requests.get(f"{API_BASE}{endpoint}", params=params, timeout=60)
    response.raise_for_status()
    data = response.json()
    if "error" in data:
        raise RuntimeError(data["error"])
    return data


def find_place_id(place_name):
    place_name = place_name.strip()
    if not place_name:
        raise ValueError("Place name is required.")

    data = api_get("/places/autocomplete", {"q": place_name, "per_page": 20})
    results = data.get("results", [])
    if not results:
        raise RuntimeError(f"Could not find place: {place_name}")
    return int(results[0]["id"])


def download_mammal_pool(place_name="Massachusetts", progress=None):
    mammals = resolve_species("Mammalia")
    place_id = find_place_id(place_name)

    rows = []
    id_above = 0
    total_rows = 0

    while total_rows < DEFAULT_MAX_MAMMAL_POOL:
        params = {
            "taxon_id": mammals["taxon_id"],
            "place_id": place_id,
            "quality_grade": "research",
            "verifiable": "true",
            "captive": "false",
            "per_page": 200,
            "order_by": "id",
            "order": "asc",
            "id_above": id_above,
        }

        data = api_get("/observations", params)
        batch = data.get("results", [])
        if not batch:
            break

        for obs in batch:
            geojson = obs.get("geojson") or {}
            coords = geojson.get("coordinates")
            if not coords or len(coords) < 2:
                continue

            longitude, latitude = coords[:2]
            try:
                latitude = float(latitude)
                longitude = float(longitude)
            except (TypeError, ValueError):
                continue

            if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
                continue

            taxon = obs.get("taxon") or {}
            rows.append(
                {
                    "observation_id": obs.get("id"),
                    "taxon_id": taxon.get("id"),
                    "taxon_name": taxon.get("scientific_name") or taxon.get("name"),
                    "common_name": taxon.get("preferred_common_name") or taxon.get("common_name"),
                    "latitude": latitude,
                    "longitude": longitude,
                    "positional_accuracy": obs.get("positional_accuracy"),
                    "observed_on": obs.get("observed_on"),
                    "coordinates_obscured": bool(obs.get("obscured", False)),
                }
            )

            total_rows += 1
            if total_rows >= DEFAULT_MAX_MAMMAL_POOL:
                break

        if len(batch) < params["per_page"]:
            break

        id_above = batch[-1]["id"]
        if progress:
            progress(f"Downloaded {total_rows:,} Massachusetts background observations…")

    if not rows:
        raise RuntimeError("No usable Massachusetts Mammalia observations were found.")

    df = pd.DataFrame(rows)
    df["observation_id"] = pd.to_numeric(df["observation_id"], errors="coerce")
    df["taxon_id"] = pd.to_numeric(df["taxon_id"], errors="coerce")
    df["positional_accuracy"] = pd.to_numeric(df["positional_accuracy"], errors="coerce")

    return df


def load_or_create_mammal_pool(refresh_pool=False, pool_file=None, progress=None):
    pool_file = Path(pool_file) if pool_file is not None else MAMMAL_POOL_FILE
    if pool_file.exists() and not refresh_pool:
        pool_df = pd.read_csv(pool_file)
        required_columns = {
            "observation_id", "taxon_id", "taxon_name", "common_name",
            "latitude", "longitude", "positional_accuracy", "observed_on",
            "coordinates_obscured",
        }
        missing = required_columns.difference(pool_df.columns)
        if missing:
            raise ValueError(
                f"Existing mammal pool at {pool_file} is missing required columns: {sorted(missing)}"
            )
        return pool_df

    pool_df = download_mammal_pool(progress=progress)
    pool_file.parent.mkdir(parents=True, exist_ok=True)
    pool_df.to_csv(pool_file, index=False)
    return pool_df


def project_to_5070(df):
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)
    x_5070, y_5070 = transformer.transform(df["longitude"].to_numpy(), df["latitude"].to_numpy())

    projected = df.copy()
    projected["x_5070"] = x_5070
    projected["y_5070"] = y_5070
    return projected


def filter_mammal_pool(pool_df, target_taxon_id):
    if pool_df is None or pool_df.empty:
        return pool_df

    filtered = pool_df.copy()

    filtered = filtered.dropna(subset=["latitude", "longitude"]).copy()
    filtered["latitude"] = pd.to_numeric(filtered["latitude"], errors="coerce")
    filtered["longitude"] = pd.to_numeric(filtered["longitude"], errors="coerce")
    filtered = filtered.dropna(subset=["latitude", "longitude"]).copy()

    filtered["coordinates_obscured"] = (
        filtered["coordinates_obscured"].fillna(False).astype(str).str.lower() == "true"
    )
    filtered = filtered[~filtered["coordinates_obscured"]].copy()

    filtered["positional_accuracy"] = pd.to_numeric(filtered["positional_accuracy"], errors="coerce")
    filtered = filtered[
        filtered["positional_accuracy"].isna() | (filtered["positional_accuracy"] <= 250)
    ].copy()

    filtered = filtered.drop_duplicates(subset=["observation_id"]).copy()
    filtered = filtered.drop_duplicates(subset=["latitude", "longitude"]).copy()

    if target_taxon_id is not None:
        filtered = filtered[filtered["taxon_id"] != target_taxon_id].copy()

    return filtered


def compute_min_distance_to_presence(candidate_x, candidate_y, presence_x, presence_y):
    distances = np.full(candidate_x.shape[0], np.inf, dtype=float)

    for idx, (cx, cy) in enumerate(zip(candidate_x, candidate_y)):
        diff_x = presence_x - cx
        diff_y = presence_y - cy
        distances[idx] = np.sqrt(np.min(diff_x**2 + diff_y**2))

    return distances


def spatial_thin(df, thinning_distance_m, random_state):
    if df.empty:
        return df

    projected = project_to_5070(df)
    projected["grid_x"] = np.floor(projected["x_5070"] / thinning_distance_m).astype(int)
    projected["grid_y"] = np.floor(projected["y_5070"] / thinning_distance_m).astype(int)

    rng = np.random.default_rng(random_state)
    order = rng.permutation(len(projected))
    kept = []
    seen_cells = set()

    for idx in order:
        row = projected.iloc[idx]
        cell = (int(row["grid_x"]), int(row["grid_y"]))
        if cell in seen_cells:
            continue
        seen_cells.add(cell)
        kept.append(idx)

    return projected.iloc[kept].reset_index(drop=True)


def generate_background(
    species_name,
    background_ratio=3.0,
    exclusion_distance_m=1000,
    thinning_distance_m=500,
    random_state=42,
    *, samples_dir="data/processed/samples", pool_file=None, taxon_id=None, progress=None,
):
    if background_ratio <= 0:
        raise ValueError("background_ratio must be greater than 0.")
    if exclusion_distance_m < 0:
        raise ValueError("exclusion_distance_m must be non-negative.")
    if thinning_distance_m <= 0:
        raise ValueError("thinning_distance_m must be greater than 0.")

    target_taxon_id = int(taxon_id if taxon_id is not None else resolve_species(species_name)["taxon_id"])

    species_slug_value = species_slug(species_name)
    samples_dir = Path(samples_dir)
    presence_file = samples_dir / f"{species_slug_value}_occurrences.csv"
    if not presence_file.exists():
        raise FileNotFoundError(
            f"Could not find cleaned presence file at {presence_file}. Run the Phase 3 species download first."
        )

    presence_df = pd.read_csv(presence_file)
    presence_df = presence_df.dropna(subset=["latitude", "longitude"]).copy()
    presence_df["latitude"] = pd.to_numeric(presence_df["latitude"], errors="coerce")
    presence_df["longitude"] = pd.to_numeric(presence_df["longitude"], errors="coerce")
    presence_df = presence_df.dropna(subset=["latitude", "longitude"]).copy()

    if presence_df.empty:
        raise RuntimeError(f"No usable presence points found in {presence_file}.")

    pool_df = load_or_create_mammal_pool(pool_file=pool_file, progress=progress)
    candidate_df = filter_mammal_pool(pool_df, target_taxon_id)

    if candidate_df.empty:
        raise RuntimeError(
            f"No usable mammal-pool candidates remain after quality filtering for {species_name}."
        )

    projected_presence = project_to_5070(presence_df)
    projected_candidates = project_to_5070(candidate_df)

    presence_x = projected_presence["x_5070"].to_numpy(dtype=float)
    presence_y = projected_presence["y_5070"].to_numpy(dtype=float)
    candidate_x = projected_candidates["x_5070"].to_numpy(dtype=float)
    candidate_y = projected_candidates["y_5070"].to_numpy(dtype=float)

    min_distances = compute_min_distance_to_presence(candidate_x, candidate_y, presence_x, presence_y)
    projected_candidates["distance_to_presence_m"] = min_distances

    projected_candidates = projected_candidates[
        projected_candidates["distance_to_presence_m"] >= exclusion_distance_m
    ].copy()

    if projected_candidates.empty:
        raise RuntimeError(
            f"No candidate background points remain after excluding all locations within {exclusion_distance_m} m of known {species_name} presences."
        )

    thinned_candidates = spatial_thin(
        projected_candidates[["latitude", "longitude", "observation_id", "taxon_id", "taxon_name", "common_name"]].copy(),
        thinning_distance_m,
        random_state,
    )

    required_background = int(round(len(presence_df) * background_ratio))

    if len(thinned_candidates) < required_background:
        raise RuntimeError(
            f"Too few candidate background points remain after filtering and thinning: {len(thinned_candidates)} available, {required_background} required."
        )

    rng = np.random.default_rng(random_state)
    sample_indices = rng.choice(len(thinned_candidates), size=required_background, replace=False)
    sample_df = thinned_candidates.iloc[sample_indices].reset_index(drop=True)

    sample_df = sample_df[["latitude", "longitude"]].copy()
    sample_df["presence"] = 0

    background_file = samples_dir / f"{species_slug_value}_background.csv"
    background_file.parent.mkdir(parents=True, exist_ok=True)
    sample_df.to_csv(background_file, index=False)

    training_df = pd.concat(
        [
            presence_df[["latitude", "longitude"]].copy().assign(presence=1),
            sample_df[["latitude", "longitude", "presence"]].copy(),
        ],
        ignore_index=True,
    )

    training_df = training_df.sample(frac=1, random_state=random_state).reset_index(drop=True)

    training_file = samples_dir / f"{species_slug_value}_training_points.csv"
    training_file.parent.mkdir(parents=True, exist_ok=True)
    training_df.to_csv(training_file, index=False)

    return sample_df


def main():
    parser = argparse.ArgumentParser(
        description="Generate target-group background points for a species in Massachusetts.",
    )
    parser.add_argument("--species", required=True, help="Species name, e.g. 'Fisher'.")
    parser.add_argument("--background-ratio", type=float, default=3.0)
    parser.add_argument("--exclusion-distance-m", type=float, default=1000)
    parser.add_argument("--thinning-distance-m", type=float, default=500)
    parser.add_argument("--refresh-pool", action="store_true")
    args = parser.parse_args()

    load_or_create_mammal_pool(refresh_pool=args.refresh_pool)

    background_df = generate_background(
        args.species,
        background_ratio=args.background_ratio,
        exclusion_distance_m=args.exclusion_distance_m,
        thinning_distance_m=args.thinning_distance_m,
    )

    species_slug_value = species_slug(args.species)
    background_file = Path(f"data/processed/samples/{species_slug_value}_background.csv")
    training_file = Path(f"data/processed/samples/{species_slug_value}_training_points.csv")

    print(f"Background points saved to: {background_file}")
    print(f"Training points saved to: {training_file}")
    print(f"Background rows: {len(background_df)}")


if __name__ == "__main__":
    main()
