# WildLocate

## Installation

Install WildLocate

```pip install wildlocate```

Download Base Sets

```wildlocate init```

Start UI

```wildlocate```

## Installation From Source

Clone

```git clone https://github.com/cx-57/Wild-Locate```

Create Virtual Environment

```python -m venv .venv```

Install WildLocate (Installs Deps)

```pip install -e .```

Setup & Run

Download Datasets

```wildlocate init```

Launch

```wildlocate```

## Train a species in the desktop app

Open **Manage species → Train a new species**. Enter an exact common or scientific
name, select **Find species**, and confirm the matched mammal. The app checks local
environmental datasets and downloads research-grade observations from iNaturalist.
If environmental data is missing, use **Download environmental data**, then check
the species again.

After cleaning, at least 25 observations are required to attempt training; their
spatial distribution and the available background samples can still prevent valid
five-fold evaluation. Select **Start training** to prepare background locations,
extract habitat features, compare models and fit the selected model. Downloads
require internet access. Training runs in a separate process, reports progress and
can be cancelled.

Completed models appear under **Your models**. Review the observation counts and
spatial validation results, then select **Enable model** to add the species to the
analysis dropdown. Validation scores are not probabilities of wildlife presence
or a guarantee of ecological reliability. Retraining creates a separate model;
the current model stays enabled until a replacement is explicitly enabled.
Custom models can be deleted, and bundled models can be re-enabled at any time.

Custom models, training files and enabled-model selections are stored separately
for each signed-in WildLocate account under `accounts/<account-id>` in the
`wildlocate` application-data directory. Bundled example models remain available
to every account. Environmental datasets and the background-observation cache
are shared. `WILDLOCATE_DATA_DIR` optionally overrides the application-data
directory. Completed models must include their model, metadata and comparison
dataset before they can be enabled.

The API and command-line predictions have no account sign-in and expose only
bundled models. Previously shared custom models have no recorded owner: their
files are preserved, but they are no longer listed or enabled for any account.
Sign in and retrain a species to save a model to your account.

Massachusetts uses the original habitat features. Experimental Florida and Arizona
mammal support is described below; other regions and animal groups remain unsupported.

## Tests

```powershell
python -m unittest discover -s tests -v
```

Tests use isolated storage under `artifacts/test-runs`, mock external downloads,
train and reload a real model, and exercise the desktop workflow and regional
pipeline. Live regional smoke tests and pilot workflows are manual-only.

## Florida and Arizona (experimental)

Use the **State** selector at the top of the desktop app. Massachusetts remains
selected by default and retains its existing datasets, predictors and bundled
models. Florida and Arizona have separate model selections and comparison
populations; a model from one state is never used to score another state.

Open **Manage species** after selecting a state to train a mammal there. Models
must finish five-fold spatial evaluation and be enabled under **Your models**.
The original minimum of 25 cleaned observations and 3:1 background target remain
unchanged. Suggested starting species include Marsh Rabbit in Florida and
Black-tailed Jackrabbit in Arizona. A new state with no enabled model shows an
empty-state message rather than borrowing a Massachusetts model.

The experimental states use a separate `regional-raster-v1` feature schema:
forest, wetland, developed land, open water, shrubland, grassland, bare ground and
agricultural land fractions at 250 m and 1 km; impervious surface at both radii;
elevation, slope at both radii, and terrain ruggedness at 1 km. They do not use
Massachusetts road or hydrography distances. These models are exploratory and
have not established ecological reliability across either state.

National rasters download on demand in reusable 120 km tiles with a 1.2 km margin.
NLCD data is requested at 30 m and elevation at 90 m. First-time training or
analysis requires internet access and can download substantial data. Subsequent
locations in cached tiles work offline. Downloads publish only validated,
complete GeoTIFFs; interrupted or corrupt tiles are downloaded again. Regional
files are stored below the application-data directory in `regions/FL` and
`regions/AZ`. Existing Massachusetts files are not moved or overwritten.

```bash
python -m wildlocate status --region FL
python -m wildlocate status --region AZ
python -m wildlocate init --region FL
```

For these states, `init` prepares regional storage; it does not pre-download the
whole state. The API accepts an optional `region` (`MA`, `FL`, `AZ`) on `/predict`
and `/species?region=FL`; omitting it preserves Massachusetts behavior.

The development pilot command trains a reviewable model without enabling it:

```bash
python scripts/train_region_pilot.py --region FL --species "Marsh Rabbit" --observations 400
python scripts/train_region_pilot.py --region AZ --species "Black-tailed Jackrabbit" --observations 400
```

Pilot sampling is limited to the requested observation count; this is a
development sample, not a representative survey. Review the saved observation
counts and spatial-validation results before enabling a model.

Sources: [USGS/MRLC national land-cover services](https://www.mrlc.gov/data-services-page),
[USGS 3DEP elevation service](https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer),
[Census TIGERweb state boundaries](https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/0),
and [iNaturalist API](https://api.inaturalist.org/v1/docs/).
The bundled Florida/Arizona boundary geometry was retrieved from Census TIGERweb
on 2026-09-12. State IDs are fixed explicitly (MA: 2, FL: 21, AZ: 40) to avoid
ambiguous place-name search results.
