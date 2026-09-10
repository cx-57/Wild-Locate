"""Exercise the application boundary with prediction explicitly replaced."""

from unittest.mock import Mock

import pytest

from src import service


@pytest.fixture(autouse=True)
def prevent_real_predictions(monkeypatch):
    monkeypatch.setattr(service, "predict_species", Mock(side_effect=AssertionError("Prediction execution is disabled in these tests")))


@pytest.mark.parametrize("species,latitude,longitude,code", [
    ("Unknown", 42, -71, "unsupported_species"),
    ("../../model", 42, -71, "unsupported_species"),
    ("Red Fox", float("nan"), -71, "invalid_coordinates"),
    ("Red Fox", 42, float("inf"), "invalid_coordinates"),
    ("Red Fox", None, -71, "invalid_coordinates"),
    ("Red Fox", 91, -71, "invalid_coordinates"),
    ("Red Fox", 42, -181, "invalid_coordinates"),
    ("Red Fox", True, -71, "invalid_coordinates"),
])
def test_invalid_inputs_never_reach_backend(species, latitude, longitude, code):
    with pytest.raises(service.PredictionError) as error:
        service.assess_habitat(species, latitude, longitude)
    assert error.value.code == code
    service.predict_species.assert_not_called()


def test_service_preserves_backend_response(monkeypatch):
    # Transport sentinel, deliberately not a fabricated prediction.
    response = {"features": {}}
    predict = Mock(return_value=response)
    monkeypatch.setattr(service, "predict_species", predict)
    assert service.assess_habitat(" red fox ", 42.28, -71.35) is response
    predict.assert_called_once_with("Red Fox", 42.28, -71.35)


@pytest.mark.parametrize("exception,code,status", [
    (FileNotFoundError("No trained model found for Fisher."), "model_unavailable", 503),
    (FileNotFoundError("C:/private/data/file.tif"), "data_unavailable", 503),
    (ValueError("Requested coordinate cannot be evaluated for elevation: outside raster"), "location_unavailable", 422),
    (ValueError("Environmental feature extraction returned missing values for required predictors: x"), "location_unavailable", 422),
    (RuntimeError("sensitive internal details"), "prediction_failed", 500),
])
def test_backend_errors_are_sanitized(monkeypatch, exception, code, status):
    monkeypatch.setattr(service, "predict_species", Mock(side_effect=exception))
    with pytest.raises(service.PredictionError) as error:
        service.assess_habitat("Fisher", 42, -71)
    assert error.value.code == code
    assert error.value.status_code == status
    assert "C:/private" not in str(error.value)
    assert "sensitive internal" not in str(error.value)
