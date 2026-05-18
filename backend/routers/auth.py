import base64
import hashlib
import os
import secrets
import time

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from jose import jwt

from dependencies import get_current_user
from storage import pkce_store

router = APIRouter()

GOOGLE_AUTH_URL  = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


def _pkce_pair():
    verifier  = base64.urlsafe_b64encode(secrets.token_bytes(40)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return verifier, challenge


def _new_state():
    return base64.urlsafe_b64encode(secrets.token_bytes(24)).rstrip(b"=").decode()


@router.get("/login")
def login():
    """Return the Google OAuth authorisation URL for the frontend to redirect to."""
    client_id    = os.getenv("GOOGLE_CLIENT_ID")
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")

    verifier, challenge = _pkce_pair()
    state = _new_state()
    pkce_store[state] = {"verifier": verifier, "ts": time.time()}

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
def callback(code: str, state: str):
    """
    Google redirects here after login.
    Exchanges the code for tokens, creates a JWT, then redirects to the
    React frontend with the token in the URL so the SPA can store it.
    """
    # Prune expired PKCE entries (> 10 min)
    now = time.time()
    for s in list(pkce_store.keys()):
        if now - pkce_store[s]["ts"] > 600:
            pkce_store.pop(s, None)

    entry = pkce_store.pop(state, None)
    if not entry:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state.")

    client_id     = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    redirect_uri  = os.getenv("GOOGLE_REDIRECT_URI")
    frontend_url  = os.getenv("FRONTEND_URL", "http://localhost:5173")

    # Exchange authorisation code for tokens
    with httpx.Client() as client:
        resp = client.post(GOOGLE_TOKEN_URL, data={
            "code":          code,
            "client_id":     client_id,
            "client_secret": client_secret,
            "redirect_uri":  redirect_uri,
            "grant_type":    "authorization_code",
            "code_verifier": entry["verifier"],
        })
        resp.raise_for_status()
        tokens = resp.json()

    # Verify the ID token with Google
    idinfo = id_token.verify_oauth2_token(
        tokens["id_token"],
        google_requests.Request(),
        client_id,
    )

    # Mint a JWT for the frontend
    jwt_token = jwt.encode(
        {
            "sub":     idinfo["sub"],
            "email":   idinfo["email"],
            "name":    idinfo.get("name", idinfo["email"]),
            "picture": idinfo.get("picture"),
        },
        os.getenv("JWT_SECRET"),
        algorithm="HS256",
    )

    # Redirect to React with the token in the URL fragment
    # The fragment (#) is never sent to the server — safer than query params
    return RedirectResponse(url=f"{frontend_url}/auth/callback?token={jwt_token}")


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
    return {
        "email":   user.get("email"),
        "name":    user.get("name"),
        "picture": user.get("picture"),
    }
