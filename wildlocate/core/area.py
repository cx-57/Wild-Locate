"""Bounded, geodesic grid sampling with one model load per area assessment."""
import math

import numpy as np
from pyproj import Geod

from wildlocate.core.predict import (
    build_prediction_frame, category_for_percentile, extract_features,
    format_model_name, load_comparison_scores, load_model_and_metadata,
    percentile_of_score, resolve_model, validate_lat_lon,
)
from wildlocate.core.regions import get_region


def build_grid(latitude, longitude, radius_km):
    if isinstance(radius_km, bool) or radius_km not in (10, 25, 50):
        raise ValueError('Choose a radius of 10, 25 or 50 km.')
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (latitude, longitude)):
        raise ValueError('Enter finite latitude and longitude coordinates.')
    validate_lat_lon(latitude, longitude)
    geod = Geod(ellps='WGS84')
    spacing = radius_km * 1000 / 5
    points = []
    for north in range(-5, 6):
        for east in range(-5, 6):
            if north*north + east*east > 25:
                continue
            distance = math.hypot(east, north) * spacing
            lon, lat, _ = geod.fwd(longitude, latitude, math.degrees(math.atan2(east, north)), distance)
            points.append({'latitude': float(lat), 'longitude': float(lon)})
    return points


def predict_area(species, latitude, longitude, radius_km, region='MA', *, username=None):
    points = build_grid(latitude, longitude, radius_km)
    region = get_region(region).code
    record = resolve_model(species, region, username=username)
    model, metrics = load_model_and_metadata(record.species, record)
    predictors = metrics.get('predictor_names')
    if not predictors:
        raise RuntimeError('Saved model metadata does not include predictor names.')
    if not hasattr(model, 'predict_proba'):
        raise RuntimeError('Saved model does not support suitability scoring.')
    extractor = extract_features
    if region != 'MA':
        from wildlocate.core.data.regional import SCHEMA, extract_regional_features
        if metrics.get('feature_schema') != SCHEMA or metrics.get('region') != region:
            raise ValueError('This model is not compatible with the selected region.')
        extractor = lambda lat, lon: extract_regional_features(lat, lon, region)
    comparison_scores, _ = load_comparison_scores(model, predictors, record.species, record)
    for point in points:
        try:
            features = extractor(point['latitude'], point['longitude'])
            frame = build_prediction_frame(features, predictors)
            if not np.isfinite(frame.to_numpy(dtype=float)).all():
                raise ValueError('Environmental feature extraction returned missing values')
        except ValueError as exc:
            if not str(exc).startswith(('Requested coordinate cannot be evaluated', 'Environmental feature extraction returned missing values')):
                raise
            point.update(status='unavailable', reason='Outside model coverage or incomplete environmental data.')
            continue
        score = float(model.predict_proba(frame)[0, 1])
        if not math.isfinite(score):
            raise RuntimeError('Prediction returned a non-finite suitability score.')
        percentile = percentile_of_score(score, comparison_scores)
        point.update(status='ok', score=score, percentile=percentile, category=category_for_percentile(percentile))
    scored = [p for p in points if p['status'] == 'ok']
    return {
        'analysis_type': 'regional', 'species': record.species, 'region': region,
        'latitude': latitude, 'longitude': longitude, 'radius_km': radius_km,
        'grid_spacing_km': radius_km / 5, 'points': points,
        'evaluated_points': len(scored), 'unavailable_points': len(points) - len(scored),
        'mean_score': float(np.mean([p['score'] for p in scored])) if scored else None,
        'model': format_model_name(metrics.get('selected_model', 'Unknown Model')),
        'training_observations': int(metrics.get('presence_count', 0)),
    }
