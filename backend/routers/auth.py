import base64
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from jose import jwt

from dependencies import get_current_user
from storage import store_pkce, pop_pkce

router = APIRouter()

GOOGLE_AUTH_URL  = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


def _pkce_pair() -> tuple[str, str]:
    verifier  = base64.urlsafe_b64encode(secrets.token_bytes(40)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return verifier, challenge


def _new_state() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(24)).rstrip(b"=").decode()


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
    Google redirects here after login.
    Exchanges the code for tokens, creates a JWT, then redirects to the
    React frontend with the token in the URL fragment (never sent to servers).
    """
    verifier = await pop_pkce(state)
    if not verifier:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state.")

    client_id     = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    redirect_uri  = os.getenv("GOOGLE_REDIRECT_URI")
    frontend_url  = os.getenv("FRONTEND_URL", "http://localhost:5173")
    jwt_secret    = os.getenv("JWT_SECRET")
    expiry_hours  = int(os.getenv("JWT_EXPIRY_HOURS", "8"))

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
        tokens["id_token"],
        google_requests.Request(),
        client_id,
    )

    now = datetime.now(timezone.utc)
    jwt_token = jwt.encode(
        {
            "sub":     idinfo["sub"],
            "email":   idinfo["email"],
            "name":    idinfo.get("name", idinfo["email"]),
            "picture": idinfo.get("picture"),
            "iat":     now,
            "exp":     now + timedelta(hours=expiry_hours),
        },
        jwt_secret,
        algorithm="HS256",
    )

    # Pass the token in the URL fragment — fragments are never sent to servers
    # or logged by proxies, unlike query parameters.
    return RedirectResponse(url=f"{frontend_url}/auth/callback#{jwt_token}")


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
    return {
        "email":   user.get("email"),
        "name":    user.get("name"),
        "picture": user.get("picture"),
    }
