from fastapi import APIRouter, Depends

from app.models.schemas import (
    AnomalyModelStatusResponse,
    AuthenticatedUserResponse,
    PredictionModelsStatusResponse,
    PredictionResponse,
)
from app.services.anomaly import anomaly_model_service
from app.services.auth import auth_service
from app.services.model_registry import MODELS
from app.services.prediction import prediction_service
from app.services.prognostics import failure_model_service, rul_model_service

router = APIRouter()


@router.get("/model/status", response_model=AnomalyModelStatusResponse)
def get_anomaly_model_status(
    _: AuthenticatedUserResponse = Depends(auth_service.get_current_user),
) -> AnomalyModelStatusResponse:
    return anomaly_model_service.status()


@router.get("/models/status", response_model=PredictionModelsStatusResponse)
def get_prediction_models_status(
    _: AuthenticatedUserResponse = Depends(auth_service.get_current_user),
) -> PredictionModelsStatusResponse:
    return PredictionModelsStatusResponse(
        anomaly=anomaly_model_service.status(),
        failure=failure_model_service.status(),
        rul=rul_model_service.status(),
        profiles={
            profile: {"anomaly": models.anomaly.status(), "failure": models.failure.status(), "rul": models.rul.status()}
            for profile, models in MODELS.items()
        },
    )


@router.get("/assets/{asset_id}/latest", response_model=PredictionResponse)
def get_latest_prediction(
    asset_id: str,
    _: AuthenticatedUserResponse = Depends(auth_service.get_current_user),
) -> PredictionResponse:
    return prediction_service.get_latest(asset_id)
