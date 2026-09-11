from enum import Enum

from fastapi import Body, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ConfigDict, Field, ValidationError, create_model

from wildlocate.core.catalog import SUPPORTED_SPECIES
from wildlocate.core.service import PredictionError, assess_habitat

app = FastAPI(
    title="Wild-Locate",
    description="Relative habitat suitability for wildlife. Scores are not probabilities of species presence.",
    version="1.0.0",
)


PredictionRequest = create_model(
    "PredictionRequest",
    __config__=ConfigDict(extra="forbid", str_strip_whitespace=True),
    species=(str, Field(min_length=1, max_length=100)),
    latitude=(float, Field(ge=-90, le=90, allow_inf_nan=False, strict=True)),
    longitude=(float, Field(ge=-180, le=180, allow_inf_nan=False, strict=True)),
)

SuitabilityCategory = Enum("SuitabilityCategory", {
    "VERY_LOW": "Very Low", "LOW": "Low", "MODERATE": "Moderate",
    "HIGH": "High", "VERY_HIGH": "Very High",
}, type=str)

PredictionResponse = create_model(
    "PredictionResponse",
    species=(str, ...),
    latitude=(float, ...),
    longitude=(float, ...),
    score=(float, Field(allow_inf_nan=False)),
    percentile=(int, Field(ge=0, le=100)),
    category=(SuitabilityCategory, ...),
    model=(str, ...),
    training_observations=(int, ...),
    features=(dict[str, float], ...),
)


@app.exception_handler(PredictionError)
async def prediction_error_handler(request, exc):
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc), "code": exc.code})


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request, exc):
    fields = sorted({str(error["loc"][-1]) for error in exc.errors()})
    return JSONResponse(status_code=422, content={
        "detail": "Check the request: supply a species, latitude from −90 to 90, and longitude from −180 to 180 as numbers.",
        "code": "invalid_request", "fields": fields,
    })


@app.get("/species")
def species():
    return {"species": list(SUPPORTED_SPECIES)}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/predict", response_model=PredictionResponse, openapi_extra={
    "requestBody": {"content": {"application/json": {"schema": PredictionRequest.model_json_schema()}}},
})
def predict(request=Body(...)):
    try:
        request = PredictionRequest.model_validate(request)
    except ValidationError as exc:
        raise RequestValidationError([
            {**error, "loc": ("body", *error["loc"])} for error in exc.errors()
        ]) from exc
    return assess_habitat(request.species, request.latitude, request.longitude)
