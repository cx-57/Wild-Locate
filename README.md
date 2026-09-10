# Wild-Locate

A minimal PyQt6 desktop interface for the existing wildlife habitat-suitability backend, plus an optional FastAPI service. All assessments come from the shared Python prediction function. Scores describe **relative habitat suitability**, not the probability that a species is present.

## Start the desktop app

From the project directory in PowerShell:

```powershell
# Only needed when setting up a new environment:
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-desktop.txt

# Open the app:
.\.venv\Scripts\python.exe -m web.app
```

For a launch without a console window, run `./Start-WildLocate.ps1`. It explicitly uses the project's virtual environment. `launch.pyw` is also available; its file association must use a Python environment with the project dependencies installed.

On macOS/Linux, use `.venv/bin/python` in place of `.\.venv\Scripts\python.exe`.

Choose Bobcat, Fisher, North American River Otter, Red Fox, or Coyote; enter latitude and longitude in decimal degrees; then select **Analyze Habitat**. Example coordinates are inputs only: loading an example never creates a prediction. The app makes no network requests.

The result presents the backend's category and percentile, relative score, model, training-observation count, and location. Expand **Environmental Conditions** for readable measurements, or export the completed assessment as JSON with its full-precision values and interpretation. Editing any input clears the previous assessment.

- **Ctrl+Enter** analyzes the current inputs.
- **Escape** cancels an active analysis.
- **How it works** opens the methodology section.
- The layout stacks vertically in smaller windows and supports scrolling.

The first analysis can take longer while the existing backend reads local environmental datasets. Work runs in a separate, persistent Python process so the window stays responsive and the extractor can reuse its existing cache. Cancel closes that process; the next analysis starts a new one. Closing the app also closes its worker. No API server is required for desktop use.

## Optional HTTP API

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-api.txt
.\.venv\Scripts\python.exe -m uvicorn src.api:app --host 127.0.0.1 --port 8000
```

Interactive API documentation is at <http://127.0.0.1:8000/docs>.

`POST /predict` accepts:

```json
{
  "species": "Red Fox",
  "latitude": 42.28,
  "longitude": -71.35
}
```

The response contains `species`, `latitude`, `longitude`, `score`, `percentile`, `category`, `model`, `training_observations`, and `features`. The endpoint returns the shared backend result directly, without recalculating or rounding the score. Values are rounded only for desktop display.

Additional endpoints:

- `GET /species`: the five supported species names.
- `GET /health`: process liveness only; it does not validate model or dataset availability.

Errors use `{"detail": "Readable message", "code": "error_code"}`. Invalid input and locations without usable raster coverage return HTTP 422. Missing model/data files return 503. Other extraction or model failures return 500 with a readable message; internal traceback details stay in server logs. Predictions are serialized because the existing extractor caches raster handles. This local API has no authentication; the documented launch binds only to the local computer.

## Backend integration

```python
from src.predict import predict_species

assessment = predict_species("North American River Otter", 42.3718, -72.2820)
```

The existing CLI syntax is preserved:

```powershell
.\.venv\Scripts\python.exe src/predict.py --species "North American River Otter" --lat 42.3718 --lon -72.2820
```

The CLI, API, and desktop all call the same calculation. Prediction code was extracted from `main()` into `predict_species()`; its model invocation, comparison scores, percentile calculation, and category thresholds are unchanged. Model and comparison paths now resolve relative to the repository, so launching from another working directory works.

The existing `data/processed/models/`, `data/processed/features/species/`, and raw environmental datasets must be available. Training, feature definitions, environmental extraction, background generation, and datasets were not changed. The existing extractor retains its original behavior, including preparing the projected elevation raster if it is absent.

The `web/` directory contains the PyQt presentation layer, following the handoff's frontend directory convention. React/Vite was replaced by PyQt as requested. The API and desktop both use `src/service.py` for input normalization, error handling, and serialized access to `src/predict.py`.

## Checks

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
.\.venv\Scripts\python.exe tools/preview_desktop.py
```

These checks do **not** run the CLI or trained-model predictions. Tests cover HTTP validation, error handling, delegation to the shared service, coordinate validation, UI loading/error states, stale-result invalidation, compact layout, and environmental units. Layout previews of the real Qt widgets are written to ignored `artifacts/` files; they contain no fabricated prediction results.

Numerical regression checks against the two handoff locations were not continued after the request to leave the working CLI untested. The remaining end-to-end check is to run a real assessment in the app when desired.

PyQt installation reference: [Riverbank Computing](https://www.riverbankcomputing.com/software/pyqt/download). API framework reference: [FastAPI error handling](https://fastapi.tiangolo.com/tutorial/handling-errors/).
