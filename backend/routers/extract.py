import asyncio
import json
import os
import uuid
from datetime import date, timezone, datetime, timedelta
from typing import List, Optional

import redis.asyncio as aioredis
from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from database import AsyncSessionLocal
from dependencies import get_current_user
from limiter import limiter
from logger import get_logger
from models import Document
import storage

router = APIRouter()
log = get_logger(__name__)

REDIS_URL          = os.getenv("REDIS_URL", "redis://localhost:6379/0")
MAX_PAGES_PER_DAY  = int(os.getenv("MAX_PAGES_PER_DAY", "100"))
ARQ_REDIS_SETTINGS = RedisSettings.from_dsn(REDIS_URL)
SSE_TIMEOUT_SECS   = 600  # 10-minute hard cap on open SSE connections


class ExtractRequest(BaseModel):
    upload_id:   str
    document_id: Optional[str] = None
    page_nums:   List[int]


def _event(data: dict) -> dict:
    return {"data": json.dumps(data)}


def _quota_reset_iso() -> str:
    today    = date.today()
    midnight = datetime(today.year, today.month, today.day, tzinfo=timezone.utc)
    return (midnight + timedelta(days=1)).isoformat()


@router.post("")
@limiter.limit("10/minute")
async def extract(
    request: Request,
    body: ExtractRequest,
    user: dict = Depends(get_current_user),
):
    """
    Enqueue page-extraction jobs in the ARQ worker and stream progress via SSE.
    Extraction continues in the background even if the SSE connection drops.

    Event types:
      {"type": "progress",       "page": N, "stage": "parsing"|"validating"}
      {"type": "result",         "page": N, "data": { ...page result... }}
      {"type": "error",          "page": N, "error": "message"}
      {"type": "quota_exceeded", "daily_limit": N, "reset_at": "<iso>"}
      {"type": "done"}
    """
    user_sub = user.get("sub", "anonymous")

    if not await storage.upload_owned_by(body.upload_id, user_sub):
        raise HTTPException(status_code=404, detail="Upload not found. Please upload the file first.")

    meta = await storage.get_upload_meta(body.upload_id)

    # ── Quota check ───────────────────────────────────────────────────────────
    daily_used      = await storage.get_daily_usage(user_sub)
    remaining_quota = max(0, MAX_PAGES_PER_DAY - daily_used)
    valid_pages     = [p for p in sorted(body.page_nums) if 1 <= p <= meta["total_pages"]]

    # ── Reconnect: pages already cached in Redis skip re-enqueuing ────────────
    already_done: dict[int, dict] = {}
    needs_processing: list[int]   = []
    for page_num in valid_pages:
        cached = await storage.get_result(body.upload_id, page_num)
        if cached:
            already_done[page_num] = cached
        else:
            needs_processing.append(page_num)

    quota_hit        = len(needs_processing) > remaining_quota
    pages_to_enqueue = needs_processing[:remaining_quota]
    total_enqueued   = len(pages_to_enqueue)

    # ── Mark document as extracting ───────────────────────────────────────────
    if body.document_id and pages_to_enqueue:
        async with AsyncSessionLocal() as db:
            doc = await db.get(Document, uuid.UUID(body.document_id))
            if doc:
                doc.status = "extracting"
                await db.commit()

    # ── Enqueue jobs (set counter BEFORE enqueuing to avoid race) ─────────────
    if pages_to_enqueue:
        r = aioredis.Redis.from_url(REDIS_URL)
        await r.set(f"extraction:{body.upload_id}:remaining", total_enqueued, ex=3600)
        await r.aclose()

        pool = await create_pool(ARQ_REDIS_SETTINGS)
        for page_num in pages_to_enqueue:
            await pool.enqueue_job(
                "extract_page",
                body.upload_id,
                body.document_id,
                page_num,
                user_sub,
            )
        await pool.aclose()

    log.info(
        "extraction queued upload_id=%s document_id=%s enqueued=%s reconnect_pages=%s user=%s",
        body.upload_id, body.document_id, pages_to_enqueue,
        list(already_done.keys()), user.get("email"),
    )

    # ── SSE stream ────────────────────────────────────────────────────────────
    async def generator():
        # Re-emit cached results immediately (supports browser reconnect)
        for page_num, result in sorted(already_done.items()):
            yield _event({"type": "result", "page": page_num, "data": result})

        if not pages_to_enqueue:
            if quota_hit:
                yield _event({
                    "type":        "quota_exceeded",
                    "daily_limit": MAX_PAGES_PER_DAY,
                    "reset_at":    _quota_reset_iso(),
                })
            yield _event({"type": "done"})
            return

        # Subscribe to Redis pub/sub channel — worker publishes events here
        r = aioredis.Redis.from_url(REDIS_URL)
        pubsub = r.pubsub()
        await pubsub.subscribe(f"extraction:{body.upload_id}")

        received = 0
        loop     = asyncio.get_event_loop()
        deadline = loop.time() + SSE_TIMEOUT_SECS

        try:
            async for message in pubsub.listen():
                if loop.time() > deadline:
                    log.warning("SSE timeout upload_id=%s", body.upload_id)
                    break
                if message["type"] != "message":
                    continue

                data = json.loads(message["data"])
                yield _event(data)

                if data["type"] in ("result", "error"):
                    received += 1
                    if received >= total_enqueued:
                        break

        finally:
            await pubsub.unsubscribe(f"extraction:{body.upload_id}")
            await r.aclose()

        if quota_hit:
            yield _event({
                "type":        "quota_exceeded",
                "daily_limit": MAX_PAGES_PER_DAY,
                "reset_at":    _quota_reset_iso(),
            })

        yield _event({"type": "done"})
        log.info("extraction stream complete upload_id=%s", body.upload_id)

    return EventSourceResponse(generator())
