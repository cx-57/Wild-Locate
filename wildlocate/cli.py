import argparse
import sys
from pathlib import Path


def cmd_gui(args):
    from wildlocate.gui.app import main as gui_main
    gui_main()


def cmd_init(args):
    import platformdirs
    data_dir = Path(platformdirs.user_data_dir("wildlocate"))
    raw_dir = data_dir / "raw"

    print(f"Wild-Locate: downloading environmental datasets to {data_dir}")
    print("This may take several minutes.\n")

    from wildlocate.core.data.nlcd.download import download_nlcd
    nlcd_dir = raw_dir / "nlcd"
    print("Downloading NLCD land cover and impervious surface...")
    download_nlcd(nlcd_dir, year=2025, tiles=4)
    print()

    from wildlocate.core.data.usgs_3dep.download import download_elevation
    usgs_dir = raw_dir / "usgs_3dep"
    print("Downloading USGS 3DEP elevation...")
    download_elevation(
        bbox=(-73.60, 41.10, -69.80, 42.95),
        output_path=usgs_dir / "elevation_3dep.tif",
    )
    print()

    from wildlocate.core.data.massdep_hydrography.download import download_hydrography
    hydro_dir = raw_dir / "massdep_hydrography"
    print("Downloading MassDEP hydrography...")
    download_hydrography(hydro_dir / "massachusetts_hydrography.zip")
    print()

    from wildlocate.core.data.massdot_roads.download import download_roads
    roads_dir = raw_dir / "massdot_roads"
    print("Downloading MassDOT roads...")
    download_roads(roads_dir / "massachusetts_roads.zip")
    print()

    print("All datasets downloaded. Run 'wildlocate' to launch the app.")


def cmd_status(args):
    from wildlocate.core.data.environment import DatasetPaths
    paths = DatasetPaths()
    datasets = {
        "NLCD land cover": paths.nlcd_landcover,
        "NLCD impervious surface": paths.nlcd_impervious,
        "USGS 3DEP elevation": paths.usgs_3dep_elevation,
        "MassDEP hydrography (poly)": paths.massdep_hydrography_poly,
        "MassDEP hydrography (arc)": paths.massdep_hydrography_arc,
        "MassDOT roads": paths.massdot_roads,
    }
    all_ok = True
    for name, path in datasets.items():
        status = "OK" if path.exists() else "MISSING"
        if not path.exists():
            all_ok = False
        print(f"  [{status}] {name}")
        print(f"         {path}")
    print()
    if all_ok:
        print("All datasets are available.")
    else:
        print("Some datasets are missing. Run 'wildlocate init' to download them.")


def main():
    parser = argparse.ArgumentParser(
        prog="wildlocate",
        description="Wild-Locate habitat explorer for Massachusetts wildlife",
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("gui", help="Launch the GUI (default)")
    subparsers.add_parser("init", help="Download required environmental datasets")
    subparsers.add_parser("status", help="Check dataset availability")

    args = parser.parse_args()

    if args.command in (None, "gui"):
        cmd_gui(args)
    elif args.command == "init":
        cmd_init(args)
    elif args.command == "status":
        cmd_status(args)
