# Florida and Arizona Regional Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish and harden Florida and Arizona habitat training/prediction while preserving Massachusetts behavior.

**Architecture:** Massachusetts remains the reference extractor and keeps its current state-specific vector data. Florida and Arizona share `regional-raster-v1`, with state-isolated models and validated on-demand raster tiles feeding the existing observation, background, training, model-selection, registry, prediction, and GUI flows.

**Tech Stack:** Python 3.10+, unittest, rasterio, numpy, pandas, shapely, pyproj, scikit-learn, requests, PyQt6.

**Spec:** `docs/superpowers/specs/2026-09-12-regional-states-design.md`

## Global Constraints

- Massachusetts extraction and bundled-model behavior must remain unchanged.
- Florida and Arizona models must never cross-load between regions.
- Non-Massachusetts models must use feature schema `regional-raster-v1`.
- Existing training requirements remain 25 cleaned observations, 3:1 background target, 1 km exclusion, 500 m thinning, and five spatial validation folds.
- Regional raster files are EPSG:5070 and published atomically only after validation.
- Do not add national road/hydrography vector layers in this change.

---

### Task 1: Validate and repair regional raster cache entries

**Files:**
- Modify: `tests/test_regions.py`
- Modify: `wildlocate/core/data/regional.py`

**Interfaces:**
- Consumes: `tile_paths(region, x, y, progress=None)`
- Produces: `_validate_raster(path, x, y) -> bool` behavior used before cache reuse and before atomic publication.

- [ ] **Step 1: Write failing tests**

Add tests that create a zero-byte/corrupt cached raster and assert `tile_paths()` invokes the relevant downloader and replaces it, and another test that creates valid synthetic cached rasters and asserts no downloader is called.

- [ ] **Step 2: Run the regional tests and verify RED**

Run: `python -m unittest tests.test_regions -v`
Expected: the corrupt-cache test fails because current `tile_paths()` trusts any existing path.

- [ ] **Step 3: Implement minimal cache validation**

Add a focused validator that opens the GeoTIFF, requires EPSG:5070, one band, nonzero dimensions, finite/nondegenerate bounds, and coverage of the requested projected point. Existing invalid files are removed before download; temporary files pass the same validator before `os.replace`.

- [ ] **Step 4: Run regional tests and verify GREEN**

Run: `python -m unittest tests.test_regions -v`
Expected: all regional tests pass.

- [ ] **Step 5: Commit**

Commit message: `fix: validate regional raster cache`

### Task 2: Verify regional feature extraction independently of network services

**Files:**
- Modify: `tests/test_regions.py`
- Modify only if required by failing behavior: `wildlocate/core/data/regional.py`

**Interfaces:**
- Consumes: `extract_regional_features(latitude, longitude, region, progress=None)`
- Produces: complete finite `regional-raster-v1` feature dictionary.

- [ ] **Step 1: Write a failing synthetic-raster test**

Create small EPSG:5070 land-cover, impervious, and elevation GeoTIFFs around a known Florida point, patch `tile_paths()` to return them, call `extract_regional_features`, and assert exact schema keys, finite values, valid land-cover fractions, and expected elevation.

- [ ] **Step 2: Run the single test and verify RED if extraction has a defect**

Run: `python -m unittest tests.test_regions.RegionalRasterTests.test_extract_regional_features_from_synthetic_rasters -v`
Expected: fail only if the current extraction path violates the documented schema or numeric guarantees.

- [ ] **Step 3: Apply the smallest extraction fix required**

Do not alter Massachusetts helpers. Fix only regional handling required by the failing test, such as nodata masking or deterministic schema ordering.

- [ ] **Step 4: Run all tests**

Run: `python -m unittest discover -s tests -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

Commit message: `test: cover regional raster extraction`

### Task 3: Regression-test state isolation and Massachusetts behavior

**Files:**
- Modify: `tests/test_regions.py`
- Modify only on a demonstrated regression: `wildlocate/core/registry.py`, `wildlocate/core/predict.py`, `wildlocate/core/training.py`

**Interfaces:**
- Consumes: `available_species(region)`, `resolve_model(species, region)`, `predict_species(..., region)`, `TrainingSession(..., region)`
- Produces: stable MA defaults and strict FL/AZ isolation.

- [ ] **Step 1: Extend tests**

Assert MA is the default region, bundled MA species remain discoverable, regional custom models require matching metadata/schema, and wrong-state predictions fail before using another state's extractor.

- [ ] **Step 2: Run tests and verify behavior**

Run: `python -m unittest tests.test_regions -v`
Expected: pass if current isolation is complete; otherwise fail at the exact leaking interface.

- [ ] **Step 3: Make only evidence-driven fixes**

Preserve existing MA paths. Any fix must tighten region/schema checks rather than duplicate models or change MA artifacts.

- [ ] **Step 4: Run complete suite**

Run: `python -m unittest discover -s tests -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

Commit message: `test: protect regional model isolation`

### Task 4: Add repeatable CI verification for this branch

**Files:**
- Create: `.github/workflows/tests.yml`
- Modify if dependency verification exposes packaging omissions: `pyproject.toml`

**Interfaces:**
- Consumes: project package metadata and unittest suite.
- Produces: automated test result on pushes and pull requests.

- [ ] **Step 1: Add CI workflow**

Use Python 3.12, install the project with `python -m pip install -e .`, and run `python -m unittest discover -s tests -v` with `QT_QPA_PLATFORM=offscreen`.

- [ ] **Step 2: Observe CI**

Expected: dependency installation and all tests pass in a clean environment.

- [ ] **Step 3: If installation fails, fix package metadata rather than CI**

Any imported runtime dependency required by the tested package must be declared in `pyproject.toml`; do not paper over missing dependencies with workflow-only installs.

- [ ] **Step 4: Re-run CI**

Expected: clean install plus green test suite.

- [ ] **Step 5: Commit**

Commit message: `ci: verify Wild-Locate test suite`

### Task 5: Final branch verification

**Files:**
- Review: `README.md`
- Review: `wildlocate/core/data/regional.py`
- Review: `wildlocate/core/regions.py`
- Review: `wildlocate/core/training.py`
- Review: `wildlocate/core/predict.py`
- Review: `wildlocate/core/registry.py`
- Review: `wildlocate/gui/app.py`
- Review: `wildlocate/gui/species_manager.py`

**Interfaces:**
- Produces: one coherent regional-state feature branch ready for a real Florida/Arizona pilot run.

- [ ] **Step 1: Run the complete unit suite**

Run: `python -m unittest discover -s tests -v`
Expected: zero failures and zero errors.

- [ ] **Step 2: Confirm branch diff**

Check that production changes are limited to evidence-backed regional hardening, package metadata if required, and CI/docs/tests.

- [ ] **Step 3: Confirm live-test boundary**

Document that unit/CI verification does not prove third-party NLCD/USGS service availability; a real one-point extraction and one small Florida pilot remain the final external-service smoke tests on the user's machine.

- [ ] **Step 4: Commit any documentation correction only if needed**

Commit message: `docs: clarify regional verification`
