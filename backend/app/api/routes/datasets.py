from fastapi import APIRouter, Depends

from app.models.schemas import AuthenticatedUserResponse, DatasetResponse
from app.services.auth import MANAGEMENT_ROLES, auth_service, require_roles
from app.services.datasets import list_datasets

router = APIRouter()


@router.get("", response_model=list[DatasetResponse])
def get_datasets(_: AuthenticatedUserResponse = Depends(require_roles(*MANAGEMENT_ROLES))) -> list[DatasetResponse]:
    return list_datasets()
