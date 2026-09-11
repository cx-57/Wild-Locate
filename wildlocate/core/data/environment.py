import os
from pathlib import Path

import platformdirs


def get_user_data_dir() -> Path:
    """Directory where downloaded environmental datasets are stored."""
    override = os.environ.get("WILDLOCATE_DATA_DIR")
    return Path(override).expanduser().resolve() if override else Path(platformdirs.user_data_dir("wildlocate"))


class DatasetPaths:
    def __init__(self, root=None):
        root = Path(root) if root is not None else get_user_data_dir()

        self.nlcd_landcover = root / "raw" / "nlcd" / "landcover_2025.tif"
        self.nlcd_impervious = root / "raw" / "nlcd" / "impervious_2025.tif"
        self.usgs_3dep_elevation = root / "raw" / "usgs_3dep" / "elevation_3dep.tif"
        self.massdep_hydrography_poly = root / "raw" / "massdep_hydrography" / "HYDRO25K_POLY.shp"
        self.massdep_hydrography_arc = root / "raw" / "massdep_hydrography" / "HYDRO25K_ARC.shp"
        self.massdot_roads = root / "raw" / "massdot_roads" / "EOTROADS_ARC.shp"

    def validate(self):
        resolved = {
            "NLCD land cover": self.nlcd_landcover,
            "NLCD impervious surface": self.nlcd_impervious,
            "USGS 3DEP elevation": self.usgs_3dep_elevation,
            "MassDEP hydrography POLY": self.massdep_hydrography_poly,
            "MassDEP hydrography ARC": self.massdep_hydrography_arc,
            "MassDOT roads": self.massdot_roads,
        }

        missing = []
        for label, path in resolved.items():
            if not path.exists():
                missing.append(f"{label}: {path}")

        if missing:
            missing_text = "\n".join(missing)
            raise FileNotFoundError(
                "Missing required raw environmental datasets. Run 'wildlocate init' to download them.\n"
                + missing_text
            )

        return resolved


ENVIRONMENT_PATHS = DatasetPaths()


if __name__ == "__main__":
    resolved = ENVIRONMENT_PATHS.validate()
    print("PASS")
    for label, path in resolved.items():
        print(f"{label}: {path}")
