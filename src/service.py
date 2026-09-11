import logging
import math
from threading import Lock

from src.catalog import SUPPORTED_SPECIES
from src.predict import predict_species, validate_lat_lon

logger = logging.getLogger(__name__)
# The existing extractor caches open raster handles. Serialize calls without
# changing extraction or sharing those handles across concurrent predictions.
_prediction_lock = Lock()


class PredictionError(Exception):
    def __init__(self, message, code, status_code=422):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def assess_habitat(species, latitude, longitude):
    species = species.strip() if isinstance(species, str) else ""
    canonical = next((name for name in SUPPORTED_SPECIES if name.casefold() == species.casefold()), None)
    if canonical is None:
        raise PredictionError("Choose one of the five supported species.", "unsupported_species")
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

    try:
        with _prediction_lock:
            result = predict_species(canonical, latitude, longitude)
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
            "Required environmental or comparison data is missing. Restore the project's local data files and try again.",
            "data_unavailable", 503,
        ) from exc
    except ValueError as exc:
        logger.exception("Prediction could not evaluate the location")
        if str(exc).startswith(("Requested coordinate cannot be evaluated", "Environmental feature extraction returned missing values")):
            raise PredictionError(
                "This location is outside the available environmental coverage or has incomplete data. Try another location in Massachusetts.",
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
