#!/usr/bin/env python3

from pathlib import Path

import rasterio
from rasterio.enums import Resampling
from rasterio.warp import calculate_default_transform, reproject

ROOT = Path(__file__).resolve().parents[2]


def ensure_projected_elevation_raster(root=None):
    root = Path(root) if root is not None else ROOT
    source_path = root / "data" / "raw" / "usgs_3dep" / "elevation_3dep.tif"
    target_path = root / "data" / "raw" / "usgs_3dep" / "elevation_3dep_5070.tif"

    if target_path.exists():
        return target_path

    if not source_path.exists():
        raise FileNotFoundError(
            f"Could not find source elevation raster at {source_path}."
        )

    with rasterio.open(source_path) as src:
        transform, width, height = calculate_default_transform(
            src.crs,
            "EPSG:5070",
            src.width,
            src.height,
            *src.bounds,
        )

        kwargs = src.meta.copy()
        kwargs.update(
            {
                "crs": "EPSG:5070",
                "transform": transform,
                "width": width,
                "height": height,
            }
        )

        with rasterio.open(target_path, "w", **kwargs) as dst:
            for band_index in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, band_index),
                    destination=rasterio.band(dst, band_index),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs="EPSG:5070",
                    resampling=Resampling.bilinear,
                )

    return target_path
