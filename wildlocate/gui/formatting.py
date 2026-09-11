import math


def ordinal(value):
    suffix = "th" if 10 <= value % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")
    return f"{value}{suffix}"


def coordinates(latitude, longitude):
    return f"{abs(latitude):.4f}° {'N' if latitude >= 0 else 'S'}  /  {abs(longitude):.4f}° {'E' if longitude >= 0 else 'W'}"


def feature_display(name, value):
    radius = "250 m" if name.endswith("_250m") else "1 km"
    labels = {
        "forest_fraction": "Forest cover",
        "wetland_fraction": "Wetland cover",
        "developed_fraction": "Developed land",
        "open_water_fraction": "Open water",
        "mean_impervious": "Impervious surface",
        "mean_slope": "Average slope",
        "terrain_ruggedness": "Terrain ruggedness",
    }
    label = {
        "elevation_m": "Elevation",
        "distance_to_water_m": "Distance to nearest water",
        "distance_to_road_m": "Distance to nearest road",
    }.get(name)
    if label is None:
        prefix = name.rsplit("_", 1)[0]
        label = f"{labels[prefix]} within {radius}" if prefix in labels else name.replace("_", " ").capitalize()
    if not math.isfinite(value):
        return label, "Unavailable"
    if "_fraction_" in name:
        formatted = f"{value * 100:.1f}%"
    elif name.startswith("mean_impervious"):
        formatted = f"{value:.1f}%"
    elif name.startswith("mean_slope"):
        formatted = f"{value:.1f}°"
    elif name.endswith("_m") or name.startswith("terrain_ruggedness"):
        formatted = f"{value:,.0f} m"
    else:
        formatted = f"{value:,.2f}"
    return label, formatted
