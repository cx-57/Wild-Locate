# Wild-Locate

Explore wildlife habitat suitability using public observations, environmental data, and machine learning.

Choose a species and a location on the map to view a habitat assessment, explore environmental insights, or export results as JSON.

## Quick start

Requires Python 3.10 or newer. A virtual environment is recommended.

```bash
pip install wildlocate
wildlocate init
wildlocate
```

`wildlocate init` downloads the Massachusetts environmental datasets and requires internet access. Use `wildlocate status` to check dataset availability.

### From source

```bash
git clone https://github.com/cx-57/Wild-Locate.git
cd Wild-Locate
pip install -e .
wildlocate init
wildlocate
```

## Usage

1. Sign in and select a state.
2. Choose a species and click the map or enter coordinates.
3. Select **Analyze Habitat** to view the results.

Massachusetts includes models for bobcat, coyote, fisher, red fox, and North American river otter. To add a mammal, open **Manage species → Train a new species**, review the completed model, and enable it. Custom models are saved to your local account.

Florida and Arizona support is experimental and requires training and enabling a model for the selected state. Environmental tiles download on demand and are cached locally.

> Scores describe relative habitat suitability, not the probability that an animal is present. Habitat scenarios are exploratory model comparisons, not proven ecological effects.

## Built with

Python · PyQt6 · Leaflet · scikit-learn · FastAPI · GeoPandas · Rasterio

Data: iNaturalist, NLCD, USGS 3DEP, MassDEP, and MassDOT.
