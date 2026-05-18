import asyncio
import json
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from dependencies import get_current_user
from llm_handler import LLMHandler
from logger import get_logger
from orchestrator import Orchestrator
import storage

router = APIRouter()
log = get_logger(__name__)


class ExtractRequest(BaseModel):
    upload_id: str
    page_nums: List[int]


def _event(data: dict) -> dict:
    return {"data": json.dumps(data)}


@router.post("")
async def extract(
    body: ExtractRequest,
    user: dict = Depends(get_current_user),
):
    """
    Run the Parser + Validator agents on the requested pages and stream
    progress events back to the client via Server-Sent Events (SSE).

    Event types:
      {"type": "progress", "page": N, "stage": "parsing"|"validating"}
      {"type": "result",   "page": N, "data": { ...page result... }}
      {"type": "error",    "page": N, "error": "message"}
      {"type": "done"}
    """
    if not await storage.upload_exists(body.upload_id):
        raise HTTPException(status_code=404, detail="Upload not found. Please upload the PDF first.")

    meta = await storage.get_upload_meta(body.upload_id)

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
            log.info(
                "page extracted upload_id=%s page=%d confidence=%.2f",
                body.upload_id, page_num,
                result["validation"].get("overall_confidence", 0),
            )

            yield _event({"type": "result", "page": page_num, "data": result})

        yield _event({"type": "done"})
        log.info("extraction complete upload_id=%s", body.upload_id)

    return EventSourceResponse(generator())
