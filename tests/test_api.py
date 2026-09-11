from unittest.mock import Mock

from fastapi.testclient import TestClient
import pytest

from src import api
from src.service import PredictionError


@pytest.fixture
def client(monkeypatch):
    def forbidden_prediction(*args, **kwargs):
        pytest.fail("A transport test must not execute a prediction")
    monkeypatch.setattr(api, "assess_habitat", forbidden_prediction)
    with TestClient(api.app) as client:
        yield client


def test_catalog_and_liveness_do_not_predict(client):
    assert client.get("/health").json() == {"status": "ok"}
    species = client.get("/species").json()["species"]
    assert len(species) == 5
    assert "North American River Otter" in species


@pytest.mark.parametrize("payload", [
    {},
    {"species": "Red Fox", "latitude": 91, "longitude": -71},
    {"species": "Red Fox", "latitude": 42, "longitude": -181},
    {"species": "Red Fox", "latitude": True, "longitude": -71},
    {"species": "Red Fox", "latitude": "north", "longitude": -71},
    {"species": "Red Fox", "latitude": "42", "longitude": -71},
    {"species": "", "latitude": 42, "longitude": -71},
    {"species": "   ", "latitude": 42, "longitude": -71},
    {"species": "Red Fox", "latitude": 42, "longitude": -71, "extra": "ignored?"},
    [],
    None,
])
def test_invalid_request_is_readable(client, payload):
    response = client.post("/predict", json=payload)
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_request"
    assert isinstance(response.json()["detail"], str)


def test_request_schema_preserves_documented_validation(client):
    operation = client.get("/openapi.json").json()["paths"]["/predict"]["post"]
    body = operation["requestBody"]
    assert body["required"] is True
    schema = body["content"]["application/json"]["schema"]
    assert set(schema["required"]) == {"species", "latitude", "longitude"}
    assert schema["additionalProperties"] is False
    assert schema["properties"]["latitude"]["minimum"] == -90
    assert schema["properties"]["longitude"]["maximum"] == 180


def test_request_normalization_reaches_service(client, monkeypatch):
    assess = Mock(side_effect=PredictionError("Unavailable", "data_unavailable", 503))
    monkeypatch.setattr(api, "assess_habitat", assess)
    response = client.post("/predict", json={"species": " Red Fox ", "latitude": 42, "longitude": -71})
    assert response.status_code == 503
    assess.assert_called_once_with("Red Fox", 42.0, -71.0)


@pytest.mark.parametrize("status,code", [(422, "location_unavailable"), (503, "data_unavailable"), (500, "prediction_failed")])
def test_domain_errors_reach_http_without_tracebacks(client, monkeypatch, status, code):
    monkeypatch.setattr(api, "assess_habitat", Mock(side_effect=PredictionError("Readable message", code, status)))
    response = client.post("/predict", json={"species": "Red Fox", "latitude": 42, "longitude": -71})
    assert response.status_code == status
    assert response.json() == {"detail": "Readable message", "code": code}


def test_endpoint_delegates_without_transforming_result(monkeypatch):
    sentinel = object()
    assess = Mock(return_value=sentinel)
    monkeypatch.setattr(api, "assess_habitat", assess)
    request = api.PredictionRequest(species="Red Fox", latitude=42.28, longitude=-71.35)
    assert api.predict(request) is sentinel
    assess.assert_called_once_with("Red Fox", 42.28, -71.35)
