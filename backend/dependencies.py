import os
from fastapi import Request, HTTPException, status
from jose import JWTError, jwt


def get_current_user(request: Request) -> dict:
    """
    FastAPI dependency — reads the access_token httpOnly cookie and returns
    the decoded JWT payload. Raises 401 if the cookie is missing or invalid.
    """
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
        )
    secret = os.getenv("JWT_SECRET")
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
        )
