#!/usr/bin/env python3

import argparse
from pathlib import Path

import requests
import rasterio

SERVICE_URL = "https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage"
DEFAULT_BBOX = (-73.60, 41.10, -69.80, 42.95)
DEFAULT_OUTPUT = Path("data/raw/usgs_3dep/elevation_3dep.tif")


def download_elevation(bbox, output_path, width=2400, height=2400):
    output_path.parent.mkdir(parents=True, exist_ok=True)

    params = {
        "bbox": ",".join(str(v) for v in bbox),
        "bboxSR": 4326,
        "size": f"{width},{height}",
        "imageSR": 4326,
        "format": "tiff",
        "pixelType": "F32",
        "noData": "-9999",
        "interpolation": "NearestNeighbor",
        "f": "image",
    }

    print("Downloading 3DEP elevation GeoTIFF...")
    response = requests.get(SERVICE_URL, params=params, timeout=240, stream=True)
    response.raise_for_status()

    content_type = response.headers.get("content-type", "").lower()
    if "xml" in content_type or "text" in content_type:
        raise RuntimeError(
            "The 3DEP exportImage service returned an error instead of a GeoTIFF:\n"
            + response.text[:4000]
        )

    with output_path.open("wb") as f:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)

    with rasterio.open(output_path) as src:
        print("Saved:", output_path)
        print("Raster:", f"{src.width} x {src.height}")
        print("CRS:", src.crs)
        print("Bounds:", src.bounds)


def main():
    parser = argparse.ArgumentParser(description="Download USGS 3DEP elevation for Massachusetts.")
    parser.add_argument("--bbox", nargs=4, type=float, default=DEFAULT_BBOX)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--width", type=int, default=2400)
    parser.add_argument("--height", type=int, default=2400)
    args = parser.parse_args()

    output_path = Path(args.output)
    download_elevation(tuple(args.bbox), output_path, width=args.width, height=args.height)


if __name__ == "__main__":
    main()
