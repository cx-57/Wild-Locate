#!/usr/bin/env python3

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

import requests

DEFAULT_OUTPUT = Path("data/raw/massdot_roads/massachusetts_roads.zip")


def download_roads(output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)

    url = "https://s3.us-east-1.amazonaws.com/download.massgis.digital.mass.gov/shapefiles/state/MassDOT_Roads_SHP.zip"
    print("Downloading MassDOT roads package from MassGIS...")
    response = requests.get(url, timeout=240)
    response.raise_for_status()

    with output_path.open("wb") as f:
        f.write(response.content)

    print("Saved:", output_path)

    print("Extracting shapefiles...")
    with zipfile.ZipFile(output_path, "r") as zf:
        zf.extractall(output_path.parent)

    print("Extracted to:", output_path.parent)


def main():
    parser = argparse.ArgumentParser(description="Download MassDOT roads data package.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    download_roads(Path(args.output))


if __name__ == "__main__":
    main()
