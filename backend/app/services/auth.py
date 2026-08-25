from __future__ import annotations

from contextlib import closing
from datetime import UTC, datetime

from fastapi import Depends, HTTPException, status

from app.core.db import get_connection
from app.core.security import create_access_token, decode_access_token, get_bearer_token, hash_password, verify_password
from app.models.schemas import AuthenticatedUserResponse, LoginRequest, LoginResponse


ADMIN_ROLES = {"Admin"}
MANAGEMENT_ROLES = {"Admin", "Plant Manager"}
EDITOR_ROLES = {"Admin", "Plant Manager", "Maintenance Planner", "Reliability Engineer", "Technician"}
VIEWER_ROLES = {"Admin", "Plant Manager", "Maintenance Planner", "Reliability Engineer", "Technician", "Viewer"}


def _row_to_user(row) -> AuthenticatedUserResponse:
    return AuthenticatedUserResponse(
        user_id=row["user_id"],
        full_name=row["full_name"],
        email=row["email"],
        role=row["role"],
        plant_scope=row["plant_scope"],
        status=row["status"],
        last_login=row["last_login"],
    )


class AuthService:
    def authenticate(self, payload: LoginRequest) -> LoginResponse:
        with closing(get_connection()) as connection:
            row = connection.execute(
                """
                SELECT user_id, full_name, email, role, plant_scope, status, last_login, password_hash
                FROM users
                WHERE lower(email) = lower(?)
                """,
                (payload.email.strip(),),
            ).fetchone()

            if row is None or not verify_password(payload.password, row["password_hash"]):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")

            if row["status"] != "Active":
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is not active.")

            last_login = datetime.now(UTC).strftime("%Y-%m-%d %H:%M")
            connection.execute(
                "UPDATE users SET last_login = ? WHERE user_id = ?",
                (last_login, row["user_id"]),
            )
            connection.commit()

            refreshed_row = connection.execute(
                """
                SELECT user_id, full_name, email, role, plant_scope, status, last_login
                FROM users
                WHERE user_id = ?
                """,
                (row["user_id"],),
            ).fetchone()

        token, expires_at = create_access_token(
            user_id=refreshed_row["user_id"],
            email=refreshed_row["email"],
            role=refreshed_row["role"],
            status_value=refreshed_row["status"],
        )
        return LoginResponse(
            access_token=token,
            expires_at=expires_at,
            user=_row_to_user(refreshed_row),
        )

    def get_current_user(self, token: str = Depends(get_bearer_token)) -> AuthenticatedUserResponse:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token.")

        with closing(get_connection()) as connection:
            row = connection.execute(
                """
                SELECT user_id, full_name, email, role, plant_scope, status, last_login
                FROM users
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()

        if row is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authenticated user no longer exists.")
        if row["status"] != "Active":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is not active.")
        return _row_to_user(row)

    def hash_password(self, password: str | None) -> str:
        return hash_password(password or "Welcome@123")


def require_roles(*roles: str):
    allowed = set(roles)

    def dependency(current_user: AuthenticatedUserResponse = Depends(auth_service.get_current_user)) -> AuthenticatedUserResponse:
        if current_user.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this resource.")
        return current_user

    return dependency


auth_service = AuthService()
