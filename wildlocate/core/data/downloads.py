"""Environmental dataset download helpers used by setup and regional caching."""

import shutil
import tempfile
import zipfile
from pathlib import Path

import rasterio
import requests
from pyproj import Transformer
from rasterio.merge import merge

LANDCOVER_WORKSPACE = "mrlc_Land-Cover-Native_conus_year_data"
IMPERVIOUS_WORKSPACE = "mrlc_Fractional-Impervious-Surface-Native_conus_year_data"
BASE = "https://dmsdata.cr.usgs.gov/geoserver"
LANDCOVER_WCS = f"{BASE}/{LANDCOVER_WORKSPACE}/wcs"
IMPERVIOUS_WCS = f"{BASE}/{IMPERVIOUS_WORKSPACE}/wcs"
LANDCOVER_COVERAGE = f"{LANDCOVER_WORKSPACE}:Land-Cover-Native_conus_year_data"
IMPERVIOUS_COVERAGE = f"{IMPERVIOUS_WORKSPACE}:Fractional-Impervious-Surface-Native_conus_year_data"
MASS_BBOX_WGS84 = (-73.60, 41.10, -69.80, 42.95)
NLCD_CRS = "EPSG:5070"
NLCD_RESOLUTION_M = 30
TIMEOUT = 240
ELEVATION_URL = "https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage"
HYDROGRAPHY_URL = "https://s3.us-east-1.amazonaws.com/download.massgis.digital.mass.gov/shapefiles/state/hydro25k.zip"
ROADS_URL = "https://s3.us-east-1.amazonaws.com/download.massgis.digital.mass.gov/shapefiles/state/MassDOT_Roads_SHP.zip"


def mass_bbox_5070():
    xmin, ymin, xmax, ymax = MASS_BBOX_WGS84
    transformer = Transformer.from_crs("EPSG:4326", NLCD_CRS, always_xy=True)
    corners = [
        transformer.transform(xmin, ymin),
        transformer.transform(xmin, ymax),
        transformer.transform(xmax, ymin),
        transformer.transform(xmax, ymax),
    ]
    xs, ys = zip(*corners)
    return min(xs), min(ys), max(xs), max(ys)


def tile_bbox(bbox, tiles_x, tiles_y):
    xmin, ymin, xmax, ymax = bbox
    dx, dy = (xmax - xmin) / tiles_x, (ymax - ymin) / tiles_y
    for row in range(tiles_y):
        for col in range(tiles_x):
            yield row, col, (
                xmin + col * dx,
                ymin + row * dy,
                xmin + (col + 1) * dx,
                ymin + (row + 1) * dy,
            )


def download_tile(wcs_url, coverage, bbox, year, output_path):
    xmin, ymin, xmax, ymax = bbox
    params = {
        "service": "WCS", "version": "1.0.0", "request": "GetCoverage",
        "coverage": coverage, "CRS": NLCD_CRS,
        "BBOX": f"{xmin},{ymin},{xmax},{ymax}",
        "time": f"{year}-01-01T00:00:00.000Z",
        "format": "image/geotiff", "resx": NLCD_RESOLUTION_M, "resy": NLCD_RESOLUTION_M,
    }
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(wcs_url, params=params, stream=True, timeout=TIMEOUT) as response:
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").lower()
        if "xml" in content_type or "text" in content_type:
            raise RuntimeError("MRLC returned an error instead of GeoTIFF:\n" + response.text[:4000])
        with output_path.open("wb") as stream:
            for chunk in response.iter_content(1024 * 1024):
                if chunk:
                    stream.write(chunk)
    try:
        with rasterio.open(output_path) as src:
            if src.count < 1:
                raise RuntimeError("Raster has zero bands.")
    except Exception as exc:
        raise RuntimeError(f"Downloaded file is not a valid GeoTIFF: {output_path}") from exc


def _mosaic(tile_paths, output_path):
    datasets = [rasterio.open(path) for path in tile_paths]
    try:
        mosaic, transform = merge(datasets)
        profile = datasets[0].profile.copy()
        profile.update(
            height=mosaic.shape[1], width=mosaic.shape[2], transform=transform,
            compress="deflate", tiled=True, BIGTIFF="IF_SAFER",
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(output_path, "w", **profile) as dst:
            dst.write(mosaic)
    finally:
        for dataset in datasets:
            dataset.close()


def _download_nlcd_product(wcs_url, coverage, year, output_path, bbox, tiles):
    temporary_dir = Path(tempfile.mkdtemp(prefix="wild_locate_nlcd_"))
    paths = []
    try:
        for row, col, tile in tile_bbox(bbox, tiles, tiles):
            path = temporary_dir / f"tile_{row}_{col}.tif"
            download_tile(wcs_url, coverage, tile, year, path)
            paths.append(path)
        _mosaic(paths, Path(output_path))
    finally:
        shutil.rmtree(temporary_dir, ignore_errors=True)


def download_nlcd(output_dir, year=2025, tiles=4):
    if not 1985 <= year <= 2025:
        raise ValueError("Annual NLCD currently covers 1985-2025.")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    bbox = mass_bbox_5070()
    _download_nlcd_product(
        LANDCOVER_WCS, LANDCOVER_COVERAGE, year,
        output_dir / f"landcover_{year}.tif", bbox, tiles,
    )
    _download_nlcd_product(
        IMPERVIOUS_WCS, IMPERVIOUS_COVERAGE, year,
        output_dir / f"impervious_{year}.tif", bbox, tiles,
    )


def download_elevation(bbox, output_path, width=2400, height=2400):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    params = {
        "bbox": ",".join(str(value) for value in bbox), "bboxSR": 4326,
        "size": f"{width},{height}", "imageSR": 4326, "format": "tiff",
        "pixelType": "F32", "noData": "-9999", "interpolation": "NearestNeighbor",
        "f": "image",
    }
    with requests.get(ELEVATION_URL, params=params, timeout=TIMEOUT, stream=True) as response:
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").lower()
        if "xml" in content_type or "text" in content_type:
            raise RuntimeError("The 3DEP service returned an error instead of a GeoTIFF:\n" + response.text[:4000])
        with output_path.open("wb") as stream:
            for chunk in response.iter_content(1024 * 1024):
                if chunk:
                    stream.write(chunk)
    with rasterio.open(output_path):
        pass


def _download_zip(url, output_path):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, timeout=TIMEOUT) as response:
        response.raise_for_status()
        output_path.write_bytes(response.content)
    with zipfile.ZipFile(output_path) as archive:
        archive.extractall(output_path.parent)


def download_hydrography(output_path):
    _download_zip(HYDROGRAPHY_URL, output_path)


def download_roads(output_path):
    _download_zip(ROADS_URL, output_path)
