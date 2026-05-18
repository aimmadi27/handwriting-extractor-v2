import json
import os
from typing import Optional

import redis.asyncio as aioredis

REDIS_URL   = os.getenv("REDIS_URL", "redis://localhost:6379/0")
UPLOAD_TTL  = int(os.getenv("UPLOAD_TTL_SECONDS", str(2 * 60 * 60)))  # 2 hours
PKCE_TTL    = 600  # 10 minutes

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
