import asyncio
import json
import os
from datetime import date, timezone, datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from dependencies import get_current_user
from limiter import limiter
from llm_handler import LLMHandler
from logger import get_logger
from orchestrator import Orchestrator
import storage

router = APIRouter()
log = get_logger(__name__)

MAX_PAGES_PER_DAY = int(os.getenv("MAX_PAGES_PER_DAY", "100"))


class ExtractRequest(BaseModel):
    upload_id: str
    page_nums: List[int]


def _event(data: dict) -> dict:
    return {"data": json.dumps(data)}


def _quota_reset_iso() -> str:
    """ISO timestamp for midnight tonight UTC."""
    today = date.today()
    midnight = datetime(today.year, today.month, today.day, tzinfo=timezone.utc)
    from datetime import timedelta
    return (midnight + timedelta(days=1)).isoformat()


@router.post("")
@limiter.limit("10/minute")
async def extract(
    request: Request,
    body: ExtractRequest,
    user: dict = Depends(get_current_user),
):
    """
    Run the Parser + Validator agents on the requested pages and stream
    progress events back to the client via Server-Sent Events (SSE).

    Event types:
      {"type": "progress",       "page": N, "stage": "parsing"|"validating"}
      {"type": "result",         "page": N, "data": { ...page result... }}
      {"type": "error",          "page": N, "error": "message"}
      {"type": "quota_exceeded", "daily_limit": N, "reset_at": "<iso>"}
      {"type": "done"}
    """
    if not await storage.upload_exists(body.upload_id):
        raise HTTPException(status_code=404, detail="Upload not found. Please upload the PDF first.")

    meta     = await storage.get_upload_meta(body.upload_id)
    user_sub = user.get("sub", "anonymous")

    try:
        llm          = LLMHandler()
        orchestrator = Orchestrator(llm)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM initialisation failed: {e}")

    loop = asyncio.get_event_loop()

    log.info(
        "extraction started upload_id=%s pages=%s user=%s",
        body.upload_id, body.page_nums, user.get("email"),
    )

    async def generator():
        for page_num in sorted(body.page_nums):
            # ── Quota check (per page, atomic increment) ──────────────────────
            daily_used = await storage.get_daily_usage(user_sub)
            if daily_used >= MAX_PAGES_PER_DAY:
                log.warning(
                    "quota exceeded user=%s daily_used=%d limit=%d",
                    user_sub, daily_used, MAX_PAGES_PER_DAY,
                )
                yield _event({
                    "type":        "quota_exceeded",
                    "daily_limit": MAX_PAGES_PER_DAY,
                    "reset_at":    _quota_reset_iso(),
                })
                break

            if page_num < 1 or page_num > meta["total_pages"]:
                yield _event({"type": "error", "page": page_num, "error": "Page number out of range."})
                continue

            img_bytes = await storage.get_page_image(body.upload_id, page_num)
            if img_bytes is None:
                yield _event({"type": "error", "page": page_num, "error": "Page image not found."})
                continue

            # ── Parser ────────────────────────────────────────────────────────
            yield _event({"type": "progress", "page": page_num, "stage": "parsing"})
            try:
                parsed = await loop.run_in_executor(
                    None, orchestrator.parser.parse, img_bytes, page_num
                )
            except Exception as e:
                log.error("parser failed page=%d error=%s", page_num, e)
                yield _event({"type": "error", "page": page_num, "error": str(e)})
                continue

            # ── Validator ─────────────────────────────────────────────────────
            yield _event({"type": "progress", "page": page_num, "stage": "validating"})
            try:
                validated = await loop.run_in_executor(
                    None, orchestrator.validator.validate, parsed, page_num
                )
            except Exception as e:
                log.error("validator failed page=%d error=%s", page_num, e)
                yield _event({"type": "error", "page": page_num, "error": str(e)})
                continue

            # ── Extract usage stats before building result ─────────────────────
            parser_usage    = parsed.pop("_usage", {})
            validator_usage = validated.pop("_usage", {})

            total_in  = parser_usage.get("input_tokens",  0) + validator_usage.get("input_tokens",  0)
            total_out = parser_usage.get("output_tokens", 0) + validator_usage.get("output_tokens", 0)
            total_cost = parser_usage.get("cost_usd", 0.0) + validator_usage.get("cost_usd", 0.0)

            log.info(
                "page_usage upload_id=%s page=%d tokens_in=%d tokens_out=%d cost_usd=%.4f",
                body.upload_id, page_num, total_in, total_out, total_cost,
            )

            # ── Build result ──────────────────────────────────────────────────
            document = validated.get("document", parsed)
            result = {
                "doc_type":   document.get("doc_type", "other"),
                "title":      document.get("title", f"Page {page_num}"),
                "sections":   document.get("sections", []),
                "validation": validated.get("validation", {
                    "overall_confidence": 1.0,
                    "section_issues": [],
                }),
            }

            await storage.store_result(body.upload_id, page_num, result)
            await storage.increment_daily_usage(user_sub)

            log.info(
                "page extracted upload_id=%s page=%d confidence=%.2f",
                body.upload_id, page_num,
                result["validation"].get("overall_confidence", 0),
            )

            yield _event({"type": "result", "page": page_num, "data": result})

        yield _event({"type": "done"})
        log.info("extraction complete upload_id=%s", body.upload_id)

    return EventSourceResponse(generator())
