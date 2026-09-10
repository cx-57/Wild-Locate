#!/usr/bin/env python3
"""
Wild-Locate: automated Annual NLCD downloader.

Downloads Massachusetts subsets of:
  1) Annual NLCD Land Cover
  2) Annual NLCD Fractional Impervious Surface

Uses the official MRLC/USGS Annual NLCD WCS in its native
CONUS Albers projection (EPSG:5070) at 30 m resolution.

Outputs:
    data/raw/nlcd/landcover_2025.tif
    data/raw/nlcd/impervious_2025.tif

Install:
    pip install requests rasterio pyproj

Run from the Wild-Locate repo root:
    python src/data/nlcd/download.py
"""

from __future__ import annotations

import argparse
import math
import shutil
import tempfile
from pathlib import Path

import requests
import rasterio
from rasterio.merge import merge
from pyproj import Transformer


# ---------------------------------------------------------
# Official MRLC / USGS Annual NLCD services
# ---------------------------------------------------------

LANDCOVER_WORKSPACE = "mrlc_Land-Cover-Native_conus_year_data"
IMPERVIOUS_WORKSPACE = "mrlc_Fractional-Impervious-Surface-Native_conus_year_data"

BASE = "https://dmsdata.cr.usgs.gov/geoserver"

LANDCOVER_WCS = f"{BASE}/{LANDCOVER_WORKSPACE}/wcs"
IMPERVIOUS_WCS = f"{BASE}/{IMPERVIOUS_WORKSPACE}/wcs"

# WCS 1.0.0 coverage names are workspace:layer
LANDCOVER_COVERAGE = (
    f"{LANDCOVER_WORKSPACE}:"
    "Land-Cover-Native_conus_year_data"
)

IMPERVIOUS_COVERAGE = (
    f"{IMPERVIOUS_WORKSPACE}:"
    "Fractional-Impervious-Surface-Native_conus_year_data"
)

# Massachusetts bounding box in WGS84.
# Slightly padded to include Cape Cod + islands.
MASS_BBOX_WGS84 = (-73.60, 41.10, -69.80, 42.95)

# Native Annual NLCD CRS / resolution
NLCD_CRS = "EPSG:5070"
NLCD_RESOLUTION_M = 30

TIMEOUT = 240


# ---------------------------------------------------------
# Coordinate conversion
# ---------------------------------------------------------

def mass_bbox_5070():
    """
    Convert Massachusetts WGS84 bounding box into EPSG:5070.
    """
    xmin, ymin, xmax, ymax = MASS_BBOX_WGS84

    transformer = Transformer.from_crs(
        "EPSG:4326",
        NLCD_CRS,
        always_xy=True,
    )

    corners = [
        transformer.transform(xmin, ymin),
        transformer.transform(xmin, ymax),
        transformer.transform(xmax, ymin),
        transformer.transform(xmax, ymax),
    ]

    xs = [p[0] for p in corners]
    ys = [p[1] for p in corners]

    return (
        min(xs),
        min(ys),
        max(xs),
        max(ys),
    )


# ---------------------------------------------------------
# Tiling
# ---------------------------------------------------------

def tile_bbox(bbox, tiles_x, tiles_y):
    xmin, ymin, xmax, ymax = bbox

    dx = (xmax - xmin) / tiles_x
    dy = (ymax - ymin) / tiles_y

    for row in range(tiles_y):
        for col in range(tiles_x):
            x0 = xmin + col * dx
            x1 = xmin + (col + 1) * dx

            y0 = ymin + row * dy
            y1 = ymin + (row + 1) * dy

            yield row, col, (x0, y0, x1, y1)


# ---------------------------------------------------------
# WCS downloading
# ---------------------------------------------------------

def download_tile(
    wcs_url,
    coverage,
    bbox,
    year,
    output_path,
):
    xmin, ymin, xmax, ymax = bbox

    params = {
        "service": "WCS",
        "version": "1.0.0",
        "request": "GetCoverage",
        "coverage": coverage,
        "CRS": NLCD_CRS,
        "BBOX": f"{xmin},{ymin},{xmax},{ymax}",
        "time": f"{year}-01-01T00:00:00.000Z",
        "format": "image/geotiff",
        "resx": NLCD_RESOLUTION_M,
        "resy": NLCD_RESOLUTION_M,
    }

    print(
        "    ",
        f"{xmin:.0f},{ymin:.0f},"
        f"{xmax:.0f},{ymax:.0f}",
    )

    with requests.get(
        wcs_url,
        params=params,
        stream=True,
        timeout=TIMEOUT,
    ) as response:

        response.raise_for_status()

        content_type = (
            response.headers
            .get("content-type", "")
            .lower()
        )

        # GeoServer sometimes returns XML errors with HTTP 200.
        if "xml" in content_type or "text" in content_type:
            message = response.text[:4000]
            raise RuntimeError(
                "\nMRLC returned an error instead of GeoTIFF:\n\n"
                + message
            )

        with output_path.open("wb") as f:
            for chunk in response.iter_content(
                chunk_size=1024 * 1024
            ):
                if chunk:
                    f.write(chunk)

    # Make sure the result is actually a raster.
    try:
        with rasterio.open(output_path) as src:
            if src.count < 1:
                raise RuntimeError("Raster has zero bands.")
    except Exception as exc:
        raise RuntimeError(
            f"Downloaded file is not a valid GeoTIFF: {output_path}"
        ) from exc


# ---------------------------------------------------------
# Mosaic
# ---------------------------------------------------------

def mosaic_tiles(tile_paths, output_path):
    datasets = [
        rasterio.open(p)
        for p in tile_paths
    ]

    try:
        mosaic, transform = merge(datasets)

        profile = datasets[0].profile.copy()

        profile.update(
            {
                "height": mosaic.shape[1],
                "width": mosaic.shape[2],
                "transform": transform,
                "compress": "deflate",
                "tiled": True,
                "BIGTIFF": "IF_SAFER",
            }
        )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with rasterio.open(
            output_path,
            "w",
            **profile,
        ) as dst:
            dst.write(mosaic)

    finally:
        for ds in datasets:
            ds.close()


# ---------------------------------------------------------
# Product download
# ---------------------------------------------------------

def download_product(
    name,
    wcs_url,
    coverage,
    year,
    output_path,
    bbox,
    tiles,
):
    print()
    print("=" * 70)
    print(name)
    print("=" * 70)

    print("Coverage:", coverage)
    print("Year:", year)
    print(f"Downloading {tiles * tiles} tiles...")

    tmp_dir = Path(
        tempfile.mkdtemp(
            prefix="wild_locate_nlcd_"
        )
    )

    paths = []

    try:
        for row, col, tile in tile_bbox(
            bbox,
            tiles,
            tiles,
        ):
            path = tmp_dir / f"tile_{row}_{col}.tif"

            download_tile(
                wcs_url=wcs_url,
                coverage=coverage,
                bbox=tile,
                year=year,
                output_path=path,
            )

            paths.append(path)

        print("Mosaicking tiles...")

        mosaic_tiles(
            paths,
            output_path,
        )

        with rasterio.open(output_path) as src:
            print()
            print("Saved:", output_path)
            print("Size:", f"{src.width} x {src.height}")
            print("CRS:", src.crs)
            print("Resolution:", src.res)
            print(
                "File:",
                f"{output_path.stat().st_size / 1_000_000:.1f} MB",
            )

    finally:
        shutil.rmtree(
            tmp_dir,
            ignore_errors=True,
        )


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--year",
        type=int,
        default=2025,
    )

    parser.add_argument(
        "--output-dir",
        default="data/raw/nlcd",
    )

    parser.add_argument(
        "--tiles",
        type=int,
        default=4,
        help=(
            "Split Massachusetts into NxN requests. "
            "Use 5 or 6 if the server rejects a request."
        ),
    )

    args = parser.parse_args()

    if not 1985 <= args.year <= 2025:
        raise ValueError(
            "Annual NLCD currently covers 1985-2025."
        )

    output_dir = Path(args.output_dir)

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    bbox = mass_bbox_5070()

    print("Wild-Locate NLCD Downloader")
    print("Area: Massachusetts")
    print("Year:", args.year)
    print("CRS:", NLCD_CRS)
    print("Resolution:", NLCD_RESOLUTION_M, "m")
    print(
        "Massachusetts EPSG:5070 bbox:",
        tuple(round(x) for x in bbox),
    )

    download_product(
        name="Annual NLCD Land Cover",
        wcs_url=LANDCOVER_WCS,
        coverage=LANDCOVER_COVERAGE,
        year=args.year,
        output_path=(
            output_dir
            / f"landcover_{args.year}.tif"
        ),
        bbox=bbox,
        tiles=args.tiles,
    )

    download_product(
        name="Annual NLCD Fractional Impervious Surface",
        wcs_url=IMPERVIOUS_WCS,
        coverage=IMPERVIOUS_COVERAGE,
        year=args.year,
        output_path=(
            output_dir
            / f"impervious_{args.year}.tif"
        ),
        bbox=bbox,
        tiles=args.tiles,
    )

    print()
    print("=" * 70)
    print("DONE")
    print("=" * 70)

    print(
        output_dir
        / f"landcover_{args.year}.tif"
    )

    print(
        output_dir
        / f"impervious_{args.year}.tif"
    )


if __name__ == "__main__":
    main()
