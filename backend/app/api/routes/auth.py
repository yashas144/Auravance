from fastapi import APIRouter, Depends

from app.models.schemas import AuthenticatedUserResponse, LoginRequest, LoginResponse
from app.services.auth import auth_service

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    return auth_service.authenticate(payload)


@router.get("/me", response_model=AuthenticatedUserResponse)
def me(current_user: AuthenticatedUserResponse = Depends(auth_service.get_current_user)) -> AuthenticatedUserResponse:
    return current_user
