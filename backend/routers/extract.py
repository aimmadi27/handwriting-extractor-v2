import asyncio
import json
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from dependencies import get_current_user
from llm_handler import LLMHandler
from orchestrator import Orchestrator
from storage import pdf_store, result_store

router = APIRouter()


class ExtractRequest(BaseModel):
    upload_id: str
    page_nums: List[int]


def _event(data: dict) -> dict:
    """Wrap a dict as an SSE data event."""
    return {"data": json.dumps(data)}


@router.post("")
async def extract(
    body: ExtractRequest,
    user: dict = Depends(get_current_user),
):
    """
    Run the Parser + Validator agents on the requested pages and stream
    progress events back to the client via Server-Sent Events (SSE).

    Event types emitted:
      {"type": "progress", "page": N, "stage": "parsing"|"validating"}
      {"type": "result",   "page": N, "data": { ...page result... }}
      {"type": "error",    "page": N, "error": "message"}
      {"type": "done"}
    """
    if body.upload_id not in pdf_store:
        raise HTTPException(status_code=404, detail="Upload not found. Please upload the PDF first.")

    store = pdf_store[body.upload_id]

    try:
        llm          = LLMHandler()
        orchestrator = Orchestrator(llm)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM initialisation failed: {e}")

    loop = asyncio.get_event_loop()

    async def generator():
        for page_num in sorted(body.page_nums):
            if page_num < 1 or page_num > store["total_pages"]:
                yield _event({"type": "error", "page": page_num, "error": "Page number out of range."})
                continue

            img_bytes = store["page_images"][page_num - 1]

            # ── Parser ────────────────────────────────────────────────────
            yield _event({"type": "progress", "page": page_num, "stage": "parsing"})
            try:
                parsed = await loop.run_in_executor(
                    None, orchestrator.parser.parse, img_bytes, page_num
                )
            except Exception as e:
                yield _event({"type": "error", "page": page_num, "error": str(e)})
                continue

            # ── Validator ─────────────────────────────────────────────────
            yield _event({"type": "progress", "page": page_num, "stage": "validating"})
            try:
                validated = await loop.run_in_executor(
                    None, orchestrator.validator.validate, parsed, page_num
                )
            except Exception as e:
                yield _event({"type": "error", "page": page_num, "error": str(e)})
                continue

            # ── Build result ──────────────────────────────────────────────
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
            result_store[body.upload_id][page_num] = result

            yield _event({"type": "result", "page": page_num, "data": result})

        yield _event({"type": "done"})

    return EventSourceResponse(generator())
