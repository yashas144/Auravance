from fastapi import APIRouter, Depends

from app.models.schemas import AlertResponse, AuthenticatedUserResponse
from app.services.auth import auth_service
from app.services.alerts import alerts_service

router = APIRouter()


@router.get("", response_model=list[AlertResponse])
def list_alerts(_: AuthenticatedUserResponse = Depends(auth_service.get_current_user)) -> list[AlertResponse]:
    return alerts_service.list_alerts()
