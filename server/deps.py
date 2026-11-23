"""Dependency wiring. CurrentUser.resolve turns a Bearer token into the verified user."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from server.models import AuthUser
from server.services import AuthService, FileService, TransferService
from server.supabase_client import SupabaseError

_bearer = HTTPBearer(auto_error=False)


def get_sb(request: Request):
    return request.app.state.sb


def get_auth_service(request: Request) -> AuthService:
    return request.app.state.auth_service


def get_file_service(request: Request) -> FileService:
    return request.app.state.file_service


def get_transfer_service(request: Request) -> TransferService:
    return request.app.state.transfer_service


class CurrentUser:
    @staticmethod
    def resolve(
        creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
        auth: AuthService = Depends(get_auth_service),
    ) -> AuthUser:
        if creds is None:
            raise HTTPException(401, "Missing bearer token", headers={"WWW-Authenticate": "Bearer"})
        try:
            return auth.verify(creds.credentials)
        except SupabaseError:
            raise HTTPException(401, "Invalid or expired token", headers={"WWW-Authenticate": "Bearer"})


def bearer_token(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> str:
    if creds is None:
        raise HTTPException(401, "Missing bearer token")
    return creds.credentials
