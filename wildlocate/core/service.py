import logging
import math
from threading import Lock

from wildlocate.core.registry import available_species
from wildlocate.core.predict import predict_area, predict_species, validate_lat_lon

logger = logging.getLogger(__name__)
# The existing extractor caches open raster handles. Serialize calls without
# changing extraction or sharing those handles across concurrent predictions.
_prediction_lock = Lock()


class PredictionError(Exception):
    def __init__(self, message, code, status_code=422):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def assess_habitat(species, latitude, longitude, region="MA", *, username=None, radius_km=None):
    from wildlocate.core.regions import get_region
    try:
        selected_region = get_region(region)
    except ValueError as exc:
        raise PredictionError(str(exc), "unsupported_region") from exc
    region = selected_region.code
    species = species.strip() if isinstance(species, str) else ""
    canonical = next((name for name in available_species(region, username=username) if name.casefold() == species.casefold()), None)
    if canonical is None:
        raise PredictionError("Choose an available species, or enable a trained model in Manage species.", "unsupported_species")
    try:
        if isinstance(latitude, bool) or isinstance(longitude, bool):
            raise ValueError
        latitude, longitude = float(latitude), float(longitude)
        validate_lat_lon(latitude, longitude)
    except (ValueError, TypeError, OverflowError) as exc:
        raise PredictionError(
            "Enter a latitude from −90 to 90 and a longitude from −180 to 180.",
            "invalid_coordinates",
        ) from exc

    if radius_km is not None and (isinstance(radius_km, bool) or radius_km not in (10, 25, 50)):
        raise PredictionError("Choose a radius of 10, 25 or 50 km.", "invalid_radius")
    try:
        with _prediction_lock:
            if radius_km is not None:
                return predict_area(canonical, latitude, longitude, radius_km, region, username=username)
            result = predict_species(canonical, latitude, longitude, region, username=username)
        if not all(math.isfinite(value) for value in result["features"].values()):
            raise ValueError("Environmental feature extraction returned missing values")
        return result
    except FileNotFoundError as exc:
        logger.exception("Required prediction files are unavailable")
        if str(exc).startswith("No trained model found"):
            raise PredictionError(
                f"The saved model for {canonical} is unavailable. Restore its model and metadata files.",
                "model_unavailable", 503,
            ) from exc
        raise PredictionError(
            "Required environmental or comparison data is missing. Run 'wildlocate init' to download datasets.",
            "data_unavailable", 503,
        ) from exc
    except ValueError as exc:
        logger.exception("Prediction could not evaluate the location")
        if str(exc).startswith(("Requested coordinate cannot be evaluated", "Environmental feature extraction returned missing values")):
            raise PredictionError(
                f"This location is outside the available {selected_region.name} coverage or has incomplete data. Try another location in {selected_region.name}.",
                "location_unavailable",
            ) from exc
        raise PredictionError(
            "The location could not be analyzed with the saved model and environmental data. Check the local data files and try again.",
            "prediction_failed", 500,
        ) from exc
    except Exception as exc:
        logger.exception("Habitat prediction failed")
        raise PredictionError(
            "The habitat analysis could not be completed. Check that the model and environmental files are available, then try again.",
            "prediction_failed", 500,
        ) from exc
