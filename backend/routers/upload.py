import base64
import io
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from pdf2image import convert_from_bytes

from database import AsyncSessionLocal
from dependencies import get_current_user
from limiter import limiter
from logger import get_logger
from models import Document
import storage

router = APIRouter()
log = get_logger(__name__)

THUMBNAIL_MAX    = (420, 600)
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB",  "50")) * 1024 * 1024
MAX_PAGES        = int(os.getenv("MAX_PAGES", "50"))


@router.post("")
@limiter.limit("20/minute")
async def upload_pdf(
    request: Request,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    pdf_bytes = await file.read()

    if len(pdf_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum allowed size is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
        )

    try:
        pages = convert_from_bytes(pdf_bytes, dpi=150)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not parse PDF: {e}")

    if len(pages) > MAX_PAGES:
        raise HTTPException(
            status_code=422,
            detail=f"PDF has {len(pages)} pages. Maximum allowed is {MAX_PAGES}.",
        )

    upload_id   = str(uuid.uuid4())
    page_images = []
    thumbnails  = []

    for page in pages:
        full_buf = io.BytesIO()
        page.save(full_buf, "PNG")
        page_images.append(full_buf.getvalue())

        thumb = page.copy()
        thumb.thumbnail(THUMBNAIL_MAX)
        thumb_buf = io.BytesIO()
        thumb.save(thumb_buf, "PNG")
        thumbnails.append(base64.b64encode(thumb_buf.getvalue()).decode())

    await storage.store_upload(upload_id, file.filename, page_images)

    # Persist a document record so the extraction can be retrieved later
    user_db_id = uuid.UUID(user["user_id"])
    doc = Document(user_id=user_db_id, filename=file.filename, total_pages=len(pages), status="uploaded")
    async with AsyncSessionLocal() as db:
        db.add(doc)
        await db.commit()
        await db.refresh(doc)

    log.info(
        "upload stored upload_id=%s document_id=%s pages=%d user=%s",
        upload_id, doc.id, len(pages), user.get("email"),
    )

    return {
        "upload_id":   upload_id,
        "document_id": str(doc.id),
        "filename":    file.filename,
        "total_pages": len(pages),
        "thumbnails":  thumbnails,
    }


@router.delete("/{upload_id}")
async def delete_upload(upload_id: str, user: dict = Depends(get_current_user)):
    await storage.delete_upload(upload_id)
    log.info("upload deleted upload_id=%s user=%s", upload_id, user.get("email"))
    return {"deleted": upload_id}
