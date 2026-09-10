"""Thin HTTP interface. Run: python -m uvicorn src.api:app --host 127.0.0.1"""

from typing import Literal

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from src.catalog import SUPPORTED_SPECIES
from src.service import PredictionError, assess_habitat

app = FastAPI(
    title="Wild-Locate",
    description="Relative habitat suitability for wildlife. Scores are not probabilities of species presence.",
    version="1.0.0",
)


class PredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    species: str = Field(min_length=1, max_length=100)
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False, strict=True)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False, strict=True)


class PredictionResponse(BaseModel):
    species: str
    latitude: float
    longitude: float
    score: float = Field(allow_inf_nan=False)
    percentile: int = Field(ge=0, le=100)
    category: Literal["Very Low", "Low", "Moderate", "High", "Very High"]
    model: str
    training_observations: int
    features: dict[str, float]


@app.exception_handler(PredictionError)
async def prediction_error_handler(request: Request, exc: PredictionError):
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc), "code": exc.code})


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
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
    # Liveness only: do not imply that data/model availability was evaluated.
    return {"status": "ok"}


@app.post("/predict", response_model=PredictionResponse)
def predict(request: PredictionRequest):
    return assess_habitat(request.species, request.latitude, request.longitude)
