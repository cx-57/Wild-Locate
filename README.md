# WildLocate

# Installation From Source

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
environmental datasets and downloads research-grade Massachusetts observations
from iNaturalist. If environmental data is missing, use **Download environmental
data**, then check the species again.

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

Custom models, training files and the background-observation cache are stored in
the per-user `wildlocate` application-data directory, not inside the installed
package. `WILDLOCATE_DATA_DIR` optionally overrides this directory. Completed
models must include their model, metadata and comparison dataset before they can
be enabled. The API and desktop dropdown use the same model registry.

This version supports training Massachusetts mammals using the existing habitat
features. Other regions and animal groups require additional data and modeling work.

## Tests

```powershell
python -m unittest discover -s tests -v
```

Tests use isolated storage under `artifacts/test-runs`, mock external downloads,
train and reload a real model, and exercise the desktop workflow and background
process cancellation. They do not require environmental downloads.
