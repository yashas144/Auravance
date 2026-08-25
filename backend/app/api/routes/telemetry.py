from fastapi import APIRouter, Depends, HTTPException

from app.models.schemas import AuthenticatedUserResponse, TelemetryIngestRequest, TelemetryIngestResponse, TelemetryRecord
from app.services.auth import auth_service
from app.services.telemetry import telemetry_service

router = APIRouter()


@router.post("/ingest", response_model=TelemetryIngestResponse)
def ingest_telemetry(payload: TelemetryIngestRequest) -> TelemetryIngestResponse:
    return telemetry_service.ingest(payload)


@router.get("/assets/{asset_id}/latest", response_model=TelemetryRecord)
def get_latest_telemetry(
    asset_id: str,
    _: AuthenticatedUserResponse = Depends(auth_service.get_current_user),
) -> TelemetryRecord:
    telemetry = telemetry_service.get_latest(asset_id)
    if telemetry is None:
        raise HTTPException(status_code=404, detail=f"No telemetry found for asset '{asset_id}'.")
    return telemetry


@router.get("/assets/{asset_id}/history", response_model=list[TelemetryRecord])
def get_telemetry_history(
    asset_id: str,
    limit: int = 50,
    _: AuthenticatedUserResponse = Depends(auth_service.get_current_user),
) -> list[TelemetryRecord]:
    return telemetry_service.get_history(asset_id, limit=limit)
