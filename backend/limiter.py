import os
from dotenv import load_dotenv
from fastapi import Request
from jose import JWTError, jwt
from slowapi import Limiter

load_dotenv()


def _key_func(request: Request) -> str:
    """Rate-limit by authenticated user sub when available, fall back to IP."""
    token = request.cookies.get("access_token")
    if token:
        try:
            payload = jwt.decode(token, os.getenv("JWT_SECRET"), algorithms=["HS256"])
            sub = payload.get("sub")
            if sub:
                return f"user:{sub}"
        except JWTError:
            pass
    # Unauthenticated endpoints (e.g. /auth/login) fall back to IP
    forwarded = request.headers.get("X-Forwarded-For")
    return forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")


limiter = Limiter(
    key_func=_key_func,
    storage_uri=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
)
