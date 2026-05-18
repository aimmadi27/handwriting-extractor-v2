import base64
import hashlib
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from jose import JWTError, jwt
from pydantic import BaseModel

from database import AsyncSessionLocal
from dependencies import get_current_user
from logger import get_logger
from models import User
from storage import (
    store_pkce, pop_pkce,
    store_auth_code, pop_auth_code,
    store_refresh_token, get_refresh_token, revoke_refresh_token,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert

router = APIRouter()
log = get_logger(__name__)

GOOGLE_AUTH_URL  = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

COOKIE_SECURE   = os.getenv("COOKIE_SECURE", "false").lower() == "true"
ACCESS_MAX_AGE  = int(os.getenv("JWT_EXPIRY_HOURS", "1")) * 3600
REFRESH_MAX_AGE = int(os.getenv("REFRESH_TOKEN_DAYS", "7")) * 86400


# ── Helpers ───────────────────────────────────────────────────────────────────

def _pkce_pair() -> tuple[str, str]:
    verifier  = base64.urlsafe_b64encode(secrets.token_bytes(40)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return verifier, challenge


def _new_state() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(24)).rstrip(b"=").decode()


def _make_access_token(user_info: dict) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {**user_info, "iat": now, "exp": now + timedelta(seconds=ACCESS_MAX_AGE)},
        os.getenv("JWT_SECRET"),
        algorithm="HS256",
    )


def _make_refresh_token(token_id: str, user_sub: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "token_id": token_id,
            "sub": user_sub,
            "iat": now,
            "exp": now + timedelta(seconds=REFRESH_MAX_AGE),
        },
        os.getenv("JWT_SECRET"),
        algorithm="HS256",
    )


def _set_access_cookie(response, token: str) -> None:
    response.set_cookie(
        "access_token", token,
        httponly=True, secure=COOKIE_SECURE, samesite="lax",
        max_age=ACCESS_MAX_AGE, path="/",
    )


def _set_refresh_cookie(response, token: str) -> None:
    # Scoped to the refresh endpoint so the token is never sent to other routes
    response.set_cookie(
        "refresh_token", token,
        httponly=True, secure=COOKIE_SECURE, samesite="lax",
        max_age=REFRESH_MAX_AGE, path="/api/auth/refresh",
    )


def _clear_cookies(response) -> None:
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/api/auth/refresh")


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/login")
async def login():
    """Return the Google OAuth authorisation URL for the frontend to redirect to."""
    client_id    = os.getenv("GOOGLE_CLIENT_ID")
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
    verifier, challenge = _pkce_pair()
    state = _new_state()
    await store_pkce(state, verifier)
    params = {
        "client_id":             client_id,
        "redirect_uri":          redirect_uri,
        "response_type":         "code",
        "scope":                 "openid email profile",
        "state":                 state,
        "code_challenge":        challenge,
        "code_challenge_method": "S256",
        "prompt":                "consent",
    }
    url = GOOGLE_AUTH_URL + "?" + "&".join(f"{k}={v}" for k, v in params.items())
    return {"url": url}


@router.get("/callback")
async def callback(code: str, state: str):
    """
    Google redirects here. Exchanges the code for Google tokens, stores user
    info behind a short-lived one-time code, then sends the frontend to
    /auth/callback?code=<one_time_code>.

    The frontend exchanges this code via POST /auth/token, which sets
    httpOnly cookies — the JWT never appears in any URL or log.
    """
    verifier = await pop_pkce(state)
    if not verifier:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state.")

    client_id     = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    redirect_uri  = os.getenv("GOOGLE_REDIRECT_URI")
    frontend_url  = os.getenv("FRONTEND_URL", "http://localhost:5173")

    async with httpx.AsyncClient() as client:
        resp = await client.post(GOOGLE_TOKEN_URL, data={
            "code":          code,
            "client_id":     client_id,
            "client_secret": client_secret,
            "redirect_uri":  redirect_uri,
            "grant_type":    "authorization_code",
            "code_verifier": verifier,
        })
        resp.raise_for_status()
        tokens = resp.json()

    idinfo = id_token.verify_oauth2_token(
        tokens["id_token"], google_requests.Request(), client_id,
    )

    user_info = {
        "sub":     idinfo["sub"],
        "email":   idinfo["email"],
        "name":    idinfo.get("name", idinfo["email"]),
        "picture": idinfo.get("picture"),
    }

    auth_code = secrets.token_urlsafe(32)
    await store_auth_code(auth_code, user_info)

    log.info("oauth success email=%s", user_info["email"])
    return RedirectResponse(url=f"{frontend_url}/auth/callback?code={auth_code}")


class TokenRequest(BaseModel):
    code: str


async def _upsert_user(user_info: dict) -> uuid.UUID:
    """Upsert the user in Postgres and return their DB UUID."""
    async with AsyncSessionLocal() as db:
        stmt = (
            pg_insert(User)
            .values(
                google_sub=user_info["sub"],
                email=user_info["email"],
                name=user_info.get("name"),
                picture=user_info.get("picture"),
            )
            .on_conflict_do_update(
                index_elements=["google_sub"],
                set_={
                    "last_seen": datetime.now(timezone.utc),
                    "name":      user_info.get("name"),
                    "picture":   user_info.get("picture"),
                },
            )
            .returning(User.id)
        )
        result = await db.execute(stmt)
        await db.commit()
        return result.scalar_one()


@router.post("/token")
async def token(body: TokenRequest):
    """
    Exchange the one-time auth code (from /auth/callback?code=) for
    httpOnly access + refresh token cookies.
    """
    user_info = await pop_auth_code(body.code)
    if not user_info:
        raise HTTPException(status_code=400, detail="Invalid or expired auth code.")

    # Upsert user in Postgres; embed their DB UUID in the token for fast lookups
    user_db_id = await _upsert_user(user_info)
    user_info["user_id"] = str(user_db_id)

    access_token  = _make_access_token(user_info)
    token_id      = str(uuid.uuid4())
    refresh_token = _make_refresh_token(token_id, user_info["sub"])
    await store_refresh_token(token_id, user_info)

    response = JSONResponse({"ok": True})
    _set_access_cookie(response, access_token)
    _set_refresh_cookie(response, refresh_token)

    log.info("session created email=%s", user_info.get("email"))
    return response


@router.post("/refresh")
async def refresh(request: Request):
    """
    Validate the refresh token cookie, issue a new access token, and rotate
    the refresh token (old token revoked, new one issued).
    """
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token.")

    secret = os.getenv("JWT_SECRET")
    try:
        payload = jwt.decode(refresh_token, secret, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token.")

    token_id  = payload.get("token_id", "")
    user_info = await get_refresh_token(token_id)
    if not user_info:
        raise HTTPException(status_code=401, detail="Refresh token revoked.")

    # Rotate: revoke old token, issue new pair
    await revoke_refresh_token(token_id)
    new_token_id      = str(uuid.uuid4())
    new_refresh_token = _make_refresh_token(new_token_id, user_info["sub"])
    await store_refresh_token(new_token_id, user_info)
    new_access_token  = _make_access_token(user_info)

    response = JSONResponse({"ok": True})
    _set_access_cookie(response, new_access_token)
    _set_refresh_cookie(response, new_refresh_token)
    return response


@router.post("/logout")
async def logout(request: Request):
    """Revoke the refresh token and clear both auth cookies."""
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        try:
            payload = jwt.decode(refresh_token, os.getenv("JWT_SECRET"), algorithms=["HS256"])
            await revoke_refresh_token(payload.get("token_id", ""))
        except JWTError:
            pass  # Already invalid — clear cookies anyway

    response = JSONResponse({"ok": True})
    _clear_cookies(response)
    return response


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
    return {
        "email":   user.get("email"),
        "name":    user.get("name"),
        "picture": user.get("picture"),
    }
