# Wild-Locate

Wild-Locate is a desktop habitat-suitability explorer. It combines public wildlife observations, environmental data, and species-specific machine-learning models to score individual locations or a sampled region around a selected point.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
wildlocate init
wildlocate
```

`wildlocate init` downloads the Massachusetts environmental datasets. Florida and Arizona use experimental raster-only models and download reusable tiles on demand.

## What the application does

- **Point analysis:** extracts environmental conditions at one coordinate, scores the enabled species model, and reports a relative suitability percentile.
- **Regional analysis:** samples 81 locations inside a 10, 25, or 50 km radius and maps the score at each evaluable grid point. This is sampled coverage, not a continuous raster.
- **Habitat insights:** compares the selected point with the model's reference feature distribution and runs small exploratory feature-change scenarios. These are sensitivity checks, not causal ecological intervention estimates.
- **Species training:** downloads research-grade iNaturalist observations, builds target-group background samples, extracts predictors, evaluates candidate models with spatial cross-validation, and saves account-specific models for review and activation.

## Runtime architecture

```text
wildlocate/
├── cli.py
├── core/
│   ├── accounts.py
│   ├── dataset.py
│   ├── environment_features.py
│   ├── modeling.py
│   ├── predict.py
│   ├── regions.py
│   ├── registry.py
│   ├── service.py
│   ├── training.py
│   ├── worker.py
│   └── data/
│       ├── background.py
│       ├── downloads.py
│       ├── environment.py
│       ├── inaturalist.py
│       └── regional.py
└── gui/
    ├── app.py
    ├── components.py
    ├── dialogs.py
    ├── location_map.py
    ├── workers.py
    └── map/index.html
```

## Prediction flow

1. The GUI sends species, coordinates, state, and optional radius to `PredictionClient`.
2. `core.worker` runs raster/model work in a separate Python process so the GUI remains responsive.
3. `service.assess_habitat` validates the request and selects point or regional analysis.
4. `predict.py` resolves the active model, extracts the predictor schema expected by that model, calls `predict_proba`, and converts the score to a percentile relative to the saved comparison dataset.
5. The result returns as JSON to the GUI. Regional results are plotted as colored Leaflet markers.

## Environmental predictors

Massachusetts models use NLCD forest, wetland, developed land, open water, impervious surface, USGS elevation/slope/ruggedness, distance to MassDEP water, and distance to MassDOT roads. Florida and Arizona use a separate `regional-raster-v1` schema with national raster features and no Massachusetts-only road/water-distance predictors.

## Training flow

```text
iNaturalist occurrences
        ↓ clean / de-duplicate / accuracy filter
target-group background locations
        ↓ exclusion + spatial thinning
environmental feature table
        ↓ spatial grouped 5-fold CV
Logistic Regression / Random Forest / XGBoost
        ↓ select by PR-AUC, then ROC-AUC, then complexity
final fitted model + metrics + comparison feature table
```

Coordinates and labels are excluded from predictors. The saved comparison feature table is retained because runtime percentiles and insight references are computed against it.

## Bundled Massachusetts models

The repository bundles Bobcat, Coyote, Fisher, North American River Otter, and Red Fox models. Bundled models are discovered from their metadata files rather than a second hard-coded species list.

## Interpretation

A model score is **relative habitat suitability**, not the probability that the species is currently present. Percentiles compare one score with that species model's saved comparison locations. Regional analysis is a sampled grid. Scenario outputs are exploratory model sensitivity comparisons and should not be presented as proven ecological effects.

## Tests

```bash
python -m unittest discover -s tests -v
```

## Main data sources

- iNaturalist API — occurrence observations
- USGS/MRLC — NLCD land cover and impervious surface
- USGS 3DEP — elevation
- MassDEP — Massachusetts hydrography
- MassDOT — Massachusetts roads
- Census TIGERweb — bundled Florida/Arizona state boundary geometry

## Third-party notice: Leaflet

The map vendors Leaflet 1.9.4 under the BSD 2-Clause License:

BSD 2-Clause License

Copyright (c) 2010-2023, Volodymyr Agafonkin
Copyright (c) 2010-2011, CloudMade
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

## Local browser app

With the project environment activated, run:

```bash
wildlocate web
```

This opens **http://127.0.0.1:8765** in your browser. Keep the terminal running;
press **Ctrl+C** to stop the server and any active analysis. To choose another
port or skip automatically opening the browser, use
`wildlocate web --port 8766 --no-browser`.

Sign in with the same local account system used by the desktop app. The browser
now has a first-class **Species Studio** alongside the habitat explorer. Training a
new species is the primary workflow: resolve a mammal through iNaturalist, check
usable observations and environmental data, train candidate models with spatial
validation, then review the saved model before enabling it. A persistent model
library shows bundled and custom models, validation metrics, enable/retrain
controls, and custom-model deletion. The selected account is also passed to
habitat prediction so enabled custom models appear in the normal species dropdown.

Click the map or enter coordinates, then run a point analysis or an area analysis
with a 10/25/50 km radius. The browser uses your existing local datasets and
models. It uses a CARTO/OpenStreetMap basemap with an automatic fallback; manual
coordinates and local scoring still work if map tiles are unavailable. The score
table is collapsible, results can be exported as JSON, and active analysis or
training can be cancelled.

The web server binds only to this computer at `127.0.0.1`; it is not a hosted
public website.
