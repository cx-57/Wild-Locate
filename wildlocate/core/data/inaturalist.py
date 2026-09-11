#!/usr/bin/env python3

import argparse
import re
from pathlib import Path

import pandas as pd
import requests

API_BASE = "https://api.inaturalist.org/v1"
DEFAULT_MAX_OBSERVATIONS = 5000
OBSERVATION_COLUMNS = [
    "observation_id",
    "observed_on",
    "latitude",
    "longitude",
    "positional_accuracy",
    "quality_grade",
    "taxon_id",
    "taxon_name",
    "common_name",
    "coordinates_obscured",
    "uri",
]


def species_slug(species_name):
    slug = re.sub(r"[^a-z0-9]+", "_", species_name.strip().lower())
    slug = slug.strip("_")
    if not slug:
        raise ValueError("Species name is required.")
    return slug


def normalize_name(value):
    if value is None:
        return ""
    return re.sub(r"[^a-z0-9]+", " ", value.strip().lower()).strip()


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

    normalized_query = normalize_name(place_name)
    for result in results:
        if normalized_query in {
            normalize_name(result.get("display_name")),
            normalize_name(result.get("name")),
        }:
            return int(result["id"])

    return int(results[0]["id"])


def resolve_species(species_name):
    if species_name is None or not species_name.strip():
        raise ValueError("Species name is required.")

    normalized_query = normalize_name(species_name)
    data = api_get("/taxa/autocomplete", {"q": species_name, "per_page": 20})
    results = data.get("results", [])

    if not results:
        raise ValueError(
            f"Could not find a species match for '{species_name}'. Please provide a clearer common or scientific name."
        )

    exact_matches = []
    for taxon in results:
        taxon_names = [
            taxon.get("preferred_common_name"),
            taxon.get("common_name"),
            taxon.get("scientific_name"),
            taxon.get("name"),
        ]
        if any(normalize_name(name) == normalized_query for name in taxon_names if name):
            exact_matches.append(taxon)

    if not exact_matches:
        raise ValueError(
            f"Could not find a reasonable species match for '{species_name}'. "
            f"Try a more exact common or scientific name; available matches include: "
            f"{', '.join(sorted({(item.get('preferred_common_name') or item.get('name') or 'Unknown') for item in results[:5]}))}."
        )

    chosen = exact_matches[0]
    common_name = chosen.get("preferred_common_name") or chosen.get("common_name") or ""
    scientific_name = chosen.get("scientific_name") or chosen.get("name") or ""

    if not common_name or not scientific_name:
        raise ValueError(
            f"Could not resolve a usable common and scientific name for '{species_name}'."
        )

    return {
        "taxon_id": int(chosen["id"]),
        "scientific_name": scientific_name,
        "common_name": common_name,
        "rank": chosen.get("rank"),
        "iconic_taxon_name": chosen.get("iconic_taxon_name"),
    }


def extract_observation_row(obs):
    geojson = obs.get("geojson") or {}
    coordinates = geojson.get("coordinates")
    if not coordinates or len(coordinates) < 2:
        return None

    longitude, latitude = coordinates[:2]
    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except (TypeError, ValueError):
        return None

    if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
        return None

    taxon = obs.get("taxon") or {}
    common_name = taxon.get("preferred_common_name") or taxon.get("common_name") or ""
    taxon_name = taxon.get("scientific_name") or taxon.get("name") or ""

    return {
        "observation_id": obs.get("id"),
        "observed_on": obs.get("observed_on"),
        "latitude": latitude,
        "longitude": longitude,
        "positional_accuracy": obs.get("positional_accuracy"),
        "quality_grade": obs.get("quality_grade"),
        "taxon_id": taxon.get("id"),
        "taxon_name": taxon_name,
        "common_name": common_name,
        "coordinates_obscured": bool(obs.get("obscured", False)),
        "uri": obs.get("uri"),
    }


def download_species_observations(
    species_name,
    place_name="Massachusetts",
    max_observations=DEFAULT_MAX_OBSERVATIONS,
    *, taxon_id=None, progress=None,
):
    taxon_id = taxon_id if taxon_id is not None else resolve_species(species_name)["taxon_id"]
    place_id = find_place_id(place_name)

    if max_observations <= 0:
        raise ValueError("max_observations must be greater than 0.")

    rows = []
    id_above = 0

    while len(rows) < max_observations:
        params = {
            "taxon_id": taxon_id,
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
            if len(rows) >= max_observations:
                break
            row = extract_observation_row(obs)
            if row is not None:
                rows.append(row)

        if len(batch) < params["per_page"]:
            break

        id_above = batch[-1]["id"]
        if progress:
            progress(f"Downloaded {len(rows):,} observations…")

    if not rows:
        raise RuntimeError(
            f"No research-grade, non-captive observations were found for {species_name} in {place_name}."
        )

    raw_df = pd.DataFrame(rows, columns=OBSERVATION_COLUMNS)
    return raw_df


def clean_species_observations(df):
    if df is None or df.empty:
        return pd.DataFrame(columns=OBSERVATION_COLUMNS)

    cleaned = df.copy()

    cleaned = cleaned.dropna(subset=["latitude", "longitude"]).copy()

    cleaned["latitude"] = pd.to_numeric(cleaned["latitude"], errors="coerce")
    cleaned["longitude"] = pd.to_numeric(cleaned["longitude"], errors="coerce")
    cleaned = cleaned.dropna(subset=["latitude", "longitude"]).copy()

    cleaned["coordinates_obscured"] = (
        cleaned["coordinates_obscured"].fillna(False).astype(str).str.lower() == "true"
    )
    cleaned = cleaned[~cleaned["coordinates_obscured"]].copy()

    cleaned["positional_accuracy"] = pd.to_numeric(cleaned["positional_accuracy"], errors="coerce")
    cleaned = cleaned[
        cleaned["positional_accuracy"].isna() | (cleaned["positional_accuracy"] <= 250)
    ].copy()

    cleaned = cleaned.drop_duplicates(subset=["observation_id"]).copy()
    cleaned = cleaned.drop_duplicates(subset=["latitude", "longitude"]).copy()

    cleaned = cleaned.loc[:, OBSERVATION_COLUMNS].reset_index(drop=True)
    return cleaned


def save_cleaned_observations(df, species_name, output_dir="data/processed/samples"):
    output_path = Path(output_dir) / f"{species_slug(species_name)}_occurrences.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Resolve a species, download Massachusetts iNaturalist observations, and save cleaned occurrences.",
    )
    parser.add_argument("--species", required=True, help="Species to retrieve, e.g. 'Bobcat'.")
    parser.add_argument(
        "--place-name",
        default="Massachusetts",
        help="Place name to search within. Default: Massachusetts.",
    )
    parser.add_argument(
        "--max-observations",
        type=int,
        default=DEFAULT_MAX_OBSERVATIONS,
        help="Maximum number of raw observations to retrieve before cleaning. Default: 5000.",
    )
    args = parser.parse_args()

    try:
        species = resolve_species(args.species)
        print(
            f"Resolved species: {species['common_name']} ({species['scientific_name']})"
        )

        raw_df = download_species_observations(
            args.species,
            place_name=args.place_name,
            max_observations=args.max_observations,
        )
        print(f"Raw observation count: {len(raw_df)}")

        cleaned_df = clean_species_observations(raw_df)
        print(f"Cleaned observation count: {len(cleaned_df)}")

        output_path = save_cleaned_observations(cleaned_df, args.species)
        print(f"Saved cleaned observations to: {output_path}")

    except Exception as exc:
        raise SystemExit(f"Error: {exc}") from exc


if __name__ == "__main__":
    main()
