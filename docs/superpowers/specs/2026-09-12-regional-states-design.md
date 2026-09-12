# Florida and Arizona Regional Support Design

## Goal

Finish and harden Florida and Arizona support without changing the established Massachusetts habitat-model behavior.

## Architecture

Massachusetts remains the reference implementation and continues to use its existing environmental stack: NLCD land cover and imperviousness, USGS elevation/terrain, MassDEP hydrography, and MassDOT roads. Florida and Arizona use the same observation, background, training, validation, model-selection, registry, prediction, and GUI flows, but plug in a separate national raster feature provider.

The region registry is the source of truth for state identity, iNaturalist place IDs, map centers, boundaries, example species, and storage roots. Every custom model carries a region code. Non-Massachusetts models also carry a feature-schema identifier, and prediction refuses to cross-load a model from another state or schema.

## Regional Environmental Features

Florida and Arizona use `regional-raster-v1` with reusable EPSG:5070 raster tiles. The schema includes land-cover fractions for forest, wetland, developed land, open water, shrubland, grassland, barren land, and cropland at 250 m and 1 km; mean impervious surface at both radii; elevation; mean slope at both radii; and terrain ruggedness at 1 km.

Massachusetts-only MassDEP water-distance and MassDOT road-distance features are not synthesized for Florida or Arizona. Each regional model is trained and evaluated only against its own feature schema.

Tiles are cached by projected 120 km grid cell with at least a 1.2 km margin so the 1 km analysis window remains covered near tile edges. Cached files must be validated before reuse. Missing, empty, malformed, wrong-CRS, wrong-band-count, or non-covering cache files are treated as invalid and replaced atomically from a newly downloaded temporary file.

## Data and Training Flow

1. Resolve an exact mammal species through iNaturalist.
2. Download research-grade, non-captive observations restricted to the selected state.
3. Apply the existing coordinate, obscuration, positional-accuracy, and duplicate cleaning rules.
4. Require at least 25 cleaned observations.
5. Build the existing 3:1 target-group mammal background within the selected state, preserving the existing 1 km exclusion and 500 m thinning settings.
6. Prefetch distinct environmental raster tiles needed by training locations.
7. Extract the selected state's feature schema.
8. Reuse the existing five-fold spatial validation, candidate-model comparison, final fit, feature importance, and comparison-score dataset.
9. Save model, metrics, features, manifest, region, and schema together; incomplete artifacts never become selectable.

## Prediction and GUI

The state selector controls the species registry, map center, training state, and prediction state. A Florida model is never selectable in Massachusetts or Arizona, and vice versa. Prediction validates state boundaries, model region, model schema, feature completeness, and comparison data before returning a result.

Massachusetts bundled models and current Massachusetts extraction remain unchanged. Changing state invalidates any previous result and refreshes the species list. States with no enabled models show an explicit empty state rather than borrowing a Massachusetts model.

## Error Handling

Regional cache failures distinguish invalid local cache content from network/download failures. A failed download never replaces a known-good cached file. Temporary downloads are removed after either success or failure. Locations outside the selected state or with incomplete raster coverage return a location-unavailable error rather than a misleading suitability score.

## Testing

Regression tests must cover:

- Massachusetts remains the default region and bundled Massachusetts model discovery is unchanged.
- Florida and Arizona boundaries reject out-of-state points.
- Region-specific model activation and prediction cannot cross-load states.
- Regional feature extraction from synthetic rasters produces the expected schema and numeric values without network access.
- Invalid cached rasters are discarded and re-downloaded; valid cached rasters are reused without download.
- Failed or malformed downloads never publish a cache file.
- The regional training/prediction round trip preserves five spatial folds, region metadata, and feature-schema metadata.
- Package data includes state boundaries.

## Non-goals

This change does not add nationwide arbitrary-state support, national road/hydrography vector layers, new model families, hardware, a hosted web deployment, or claims of ecological validation beyond the current exploratory modeling workflow.
