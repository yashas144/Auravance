from fastapi import HTTPException

from app.models.schemas import PredictionResponse
from app.services.scoring import score_asset
from app.services.telemetry import telemetry_service


class PredictionService:
    def get_latest(self, asset_id: str) -> PredictionResponse:
        history = telemetry_service.get_history(asset_id, limit=12)
        if not history:
            raise HTTPException(status_code=404, detail=f"No telemetry found for asset '{asset_id}'.")
        return score_asset(asset_id, history)


prediction_service = PredictionService()
