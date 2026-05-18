import json
import os
import secrets
from datetime import date
from typing import Optional

import redis.asyncio as aioredis

REDIS_URL   = os.getenv("REDIS_URL", "redis://localhost:6379/0")
UPLOAD_TTL  = int(os.getenv("UPLOAD_TTL_SECONDS", str(2 * 60 * 60)))  # 2 hours
PKCE_TTL    = 600    # 10 minutes
AUTH_CODE_TTL   = 60         # 1 minute — one-time code after OAuth
REFRESH_TTL = 7 * 24 * 60 * 60  # 7 days

_pool = aioredis.ConnectionPool.from_url(REDIS_URL, max_connections=20)


def _r() -> aioredis.Redis:
    return aioredis.Redis(connection_pool=_pool)


# ── Upload store ──────────────────────────────────────────────────────────────

async def upload_exists(upload_id: str) -> bool:
    return bool(await _r().exists(f"upload:{upload_id}:meta"))


async def store_upload(upload_id: str, filename: str, page_images: list[bytes]) -> None:
    r = _r()
    pipe = r.pipeline()
    meta = json.dumps({"filename": filename, "total_pages": len(page_images)})
    pipe.set(f"upload:{upload_id}:meta", meta, ex=UPLOAD_TTL)
    for i, img in enumerate(page_images, start=1):
        pipe.set(f"upload:{upload_id}:page:{i}", img, ex=UPLOAD_TTL)
    await pipe.execute()


async def get_upload_meta(upload_id: str) -> Optional[dict]:
    raw = await _r().get(f"upload:{upload_id}:meta")
    return json.loads(raw) if raw else None


async def get_page_image(upload_id: str, page_num: int) -> Optional[bytes]:
    return await _r().get(f"upload:{upload_id}:page:{page_num}")


async def delete_upload(upload_id: str) -> None:
    meta = await get_upload_meta(upload_id)
    if not meta:
        return
    r = _r()
    pipe = r.pipeline()
    pipe.delete(f"upload:{upload_id}:meta")
    for i in range(1, meta["total_pages"] + 1):
        pipe.delete(f"upload:{upload_id}:page:{i}")
    await pipe.execute()


# ── Result store ──────────────────────────────────────────────────────────────

async def store_result(upload_id: str, page_num: int, result: dict) -> None:
    await _r().set(
        f"result:{upload_id}:{page_num}",
        json.dumps(result),
        ex=UPLOAD_TTL,
    )


async def get_result(upload_id: str, page_num: int) -> Optional[dict]:
    raw = await _r().get(f"result:{upload_id}:{page_num}")
    return json.loads(raw) if raw else None


# ── PKCE store ────────────────────────────────────────────────────────────────

async def store_pkce(state: str, verifier: str) -> None:
    await _r().set(f"pkce:{state}", verifier, ex=PKCE_TTL)


async def pop_pkce(state: str) -> Optional[str]:
    """Atomically read and delete the PKCE verifier for a given state."""
    r = _r()
    pipe = r.pipeline()
    pipe.get(f"pkce:{state}")
    pipe.delete(f"pkce:{state}")
    results = await pipe.execute()
    raw = results[0]
    return raw.decode() if raw else None


# ── One-time auth codes (post-OAuth token exchange) ───────────────────────────

async def store_auth_code(code: str, user_info: dict) -> None:
    await _r().set(f"authcode:{code}", json.dumps(user_info), ex=AUTH_CODE_TTL)


async def pop_auth_code(code: str) -> Optional[dict]:
    """Atomically read and delete a one-time auth code."""
    r = _r()
    pipe = r.pipeline()
    pipe.get(f"authcode:{code}")
    pipe.delete(f"authcode:{code}")
    results = await pipe.execute()
    raw = results[0]
    return json.loads(raw) if raw else None


# ── Refresh tokens ────────────────────────────────────────────────────────────

async def store_refresh_token(token_id: str, user_info: dict) -> None:
    await _r().set(f"refresh:{token_id}", json.dumps(user_info), ex=REFRESH_TTL)


async def get_refresh_token(token_id: str) -> Optional[dict]:
    raw = await _r().get(f"refresh:{token_id}")
    return json.loads(raw) if raw else None


async def revoke_refresh_token(token_id: str) -> None:
    await _r().delete(f"refresh:{token_id}")


# ── Daily usage counters ──────────────────────────────────────────────────────

async def get_daily_usage(user_sub: str) -> int:
    key = f"usage:pages:{user_sub}:{date.today().isoformat()}"
    val = await _r().get(key)
    return int(val) if val else 0


async def increment_daily_usage(user_sub: str) -> int:
    """Atomically increment and return the new count. Sets 25h TTL on first write."""
    key = f"usage:pages:{user_sub}:{date.today().isoformat()}"
    r = _r()
    pipe = r.pipeline()
    pipe.incr(key)
    pipe.expire(key, 25 * 60 * 60)
    results = await pipe.execute()
    return int(results[0])
