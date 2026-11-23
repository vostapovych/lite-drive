from fastapi import APIRouter, Depends, HTTPException

from server.deps import bearer_token, get_auth_service
from server.models import LoginIn, TokenOut
from server.services import AuthService
from server.supabase_client import SupabaseError

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, auth: AuthService = Depends(get_auth_service)):
    try:
        return auth.login(body.email, body.password)
    except SupabaseError as e:
        raise HTTPException(401 if e.status in (400, 401) else 502, e.message)


@router.post("/logout", status_code=204)
def logout(token: str = Depends(bearer_token), auth: AuthService = Depends(get_auth_service)):
    auth.logout(token)
