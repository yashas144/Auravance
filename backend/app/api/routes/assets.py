from fastapi import APIRouter, Depends

from app.models.schemas import AssetCreate, AssetResponse, AuthenticatedUserResponse
from app.services.auth import MANAGEMENT_ROLES, auth_service, require_roles
from app.services.assets import assets_service

router = APIRouter()


@router.get("", response_model=list[AssetResponse])
def list_assets(_: AuthenticatedUserResponse = Depends(auth_service.get_current_user)) -> list[AssetResponse]:
    return assets_service.list_assets()


@router.post("", response_model=AssetResponse)
def create_asset(
    payload: AssetCreate,
    _: AuthenticatedUserResponse = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> AssetResponse:
    return assets_service.create_asset(payload)
