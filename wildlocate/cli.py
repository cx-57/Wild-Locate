import argparse
import os
import sys
from pathlib import Path


def _configure_qt_runtime():
    if sys.platform != "darwin":
        return

    try:
        import PyQt6
    except Exception:
        return

    pyqt_root = Path(PyQt6.__file__).resolve().parent
    qt_root = pyqt_root / "Qt6"
    frameworks_dir = qt_root / "lib"
    platforms_dir = qt_root / "plugins" / "platforms"

    if platforms_dir.exists():
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(platforms_dir)

    if frameworks_dir.exists():
        existing = os.environ.get("DYLD_FRAMEWORK_PATH", "")
        paths = [str(frameworks_dir)] + [p for p in existing.split(":") if p]
        os.environ["DYLD_FRAMEWORK_PATH"] = ":".join(dict.fromkeys(paths))


def cmd_gui(args):
    _configure_qt_runtime()
    from wildlocate.gui.app import main as gui_main
    gui_main()


def cmd_init(args):
    if getattr(args, "region", "MA") != "MA":
        from wildlocate.core.data.regional import initialize
        initialize(args.region)
        return
    from wildlocate.core.data.environment import get_user_data_dir
    data_dir = get_user_data_dir()
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
    if getattr(args, "region", "MA") != "MA":
        from wildlocate.core.regions import get_region, region_root
        from wildlocate.core.registry import available_species
        region = get_region(args.region)
        root = region_root(region)
        print(f"{region.name} · experimental raster models")
        print(f"Cached raster files: {len(list((root / 'raster-v1').glob('*/*.tif')))}")
        print(f"Enabled species: {', '.join(available_species(region.code)) or 'None — train and enable a model'}")
        print("Missing raster tiles download on demand; internet access is required for uncached locations.")
        return
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
        description="Wild-Locate habitat explorer for Massachusetts, Florida and Arizona",
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("gui", help="Launch the GUI (default)")
    for command, help_text in (("init", "Set up environmental datasets"), ("status", "Check dataset availability")):
        sub = subparsers.add_parser(command, help=help_text)
        sub.add_argument("--region", choices=("MA", "FL", "AZ"), default="MA")

    args = parser.parse_args()

    if args.command in (None, "gui"):
        cmd_gui(args)
    elif args.command == "init":
        cmd_init(args)
    elif args.command == "status":
        cmd_status(args)
