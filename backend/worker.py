import asyncio
import json
import os
import uuid
from datetime import datetime, timezone

import redis.asyncio as aioredis
from arq.connections import RedisSettings
from dotenv import load_dotenv

load_dotenv()

from database import AsyncSessionLocal
from llm_handler import LLMHandler
from logger import get_logger, setup_logging
from models import Document, Page
from orchestrator import Orchestrator
from sqlalchemy.dialects.postgresql import insert as pg_insert
import storage

setup_logging()
log = get_logger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


# ── DB helpers ────────────────────────────────────────────────────────────────

async def _upsert_page(document_id: str, page_num: int, result: dict) -> None:
    doc_uuid = uuid.UUID(document_id)
    async with AsyncSessionLocal() as db:
        stmt = (
            pg_insert(Page)
            .values(
                document_id=doc_uuid,
                page_num=page_num,
                doc_type=result["doc_type"],
                title=result["title"],
                sections=result["sections"],
                validation=result["validation"],
            )
            .on_conflict_do_update(
                index_elements=["document_id", "page_num"],
                set_={
                    "doc_type":   result["doc_type"],
                    "title":      result["title"],
                    "sections":   result["sections"],
                    "validation": result["validation"],
                    "updated_at": datetime.now(timezone.utc),
                },
            )
        )
        await db.execute(stmt)
        await db.commit()


async def _mark_document_done(document_id: str) -> None:
    doc_uuid = uuid.UUID(document_id)
    async with AsyncSessionLocal() as db:
        doc = await db.get(Document, doc_uuid)
        if doc:
            doc.status     = "done"
            doc.updated_at = datetime.now(timezone.utc)
            await db.commit()


# ── Retry helper ──────────────────────────────────────────────────────────────

async def _retry(loop, fn, *args, max_retries: int = 3):
    for attempt in range(max_retries):
        try:
            return await loop.run_in_executor(None, fn, *args)
        except Exception:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)


# ── Job ───────────────────────────────────────────────────────────────────────

async def extract_page(
    ctx,
    upload_id: str,
    document_id: str | None,
    page_num: int,
    user_sub: str,
) -> None:
    """Parse + validate one page and publish SSE-compatible events to Redis pub/sub."""
    redis: aioredis.Redis = ctx["redis"]
    orchestrator: Orchestrator = ctx["orchestrator"]
    channel = f"extraction:{upload_id}"
    loop    = asyncio.get_event_loop()

    try:
        img_bytes = await storage.get_page_image(upload_id, page_num)
        if img_bytes is None:
            await redis.publish(channel, json.dumps({
                "type": "error", "page": page_num, "error": "Page image not found.",
            }))
            return

        # Parsing
        await redis.publish(channel, json.dumps({
            "type": "progress", "page": page_num, "stage": "parsing",
        }))
        parsed = await _retry(loop, orchestrator.parser.parse, img_bytes, page_num)

        # Validating
        await redis.publish(channel, json.dumps({
            "type": "progress", "page": page_num, "stage": "validating",
        }))
        validated = await _retry(loop, orchestrator.validator.validate, parsed, page_num)

        # Usage logging
        parser_usage    = parsed.pop("_usage", {})
        validator_usage = validated.pop("_usage", {})
        log.info(
            "page_usage upload_id=%s page=%d tokens_in=%d tokens_out=%d cost_usd=%.4f",
            upload_id, page_num,
            parser_usage.get("input_tokens", 0) + validator_usage.get("input_tokens", 0),
            parser_usage.get("output_tokens", 0) + validator_usage.get("output_tokens", 0),
            parser_usage.get("cost_usd", 0.0) + validator_usage.get("cost_usd", 0.0),
        )

        # Build result
        document = validated.get("document", parsed)
        result = {
            "doc_type":   document.get("doc_type", "other"),
            "title":      document.get("title", f"Page {page_num}"),
            "sections":   document.get("sections", []),
            "validation": validated.get("validation", {
                "overall_confidence": 1.0, "section_issues": [],
            }),
        }

        await storage.store_result(upload_id, page_num, result)
        await storage.increment_daily_usage(user_sub)

        if document_id:
            await _upsert_page(document_id, page_num, result)

        log.info("page extracted upload_id=%s page=%d", upload_id, page_num)
        await redis.publish(channel, json.dumps({
            "type": "result", "page": page_num, "data": result,
        }))

    except Exception as e:
        log.error("extract_page failed upload_id=%s page=%d error=%s", upload_id, page_num, e)
        await redis.publish(channel, json.dumps({
            "type": "error", "page": page_num, "error": str(e),
        }))

    finally:
        # Decrement remaining counter; mark document done when all pages finish
        remaining = await redis.decr(f"extraction:{upload_id}:remaining")
        if remaining <= 0 and document_id:
            await _mark_document_done(document_id)
            log.info("document marked done document_id=%s", document_id)


# ── Worker lifecycle ──────────────────────────────────────────────────────────

async def startup(ctx) -> None:
    ctx["redis"] = aioredis.Redis.from_url(REDIS_URL)
    ctx["orchestrator"] = Orchestrator(LLMHandler())
    log.info("worker started")


async def shutdown(ctx) -> None:
    await ctx["redis"].aclose()
    log.info("worker shutdown")


class WorkerSettings:
    functions   = [extract_page]
    on_startup  = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(REDIS_URL)
    max_jobs    = 5    # concurrent pages per worker process
    job_timeout = 120  # seconds per page
    keep_result = 300  # keep job result metadata for 5 min
