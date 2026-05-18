import base64
import io
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from pdf2image import convert_from_bytes
from PIL import Image

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

_ACCEPTED_EXT  = {".pdf", ".jpg", ".jpeg", ".png", ".webp", ".tiff", ".tif"}
_ACCEPTED_MIME = {
    "application/pdf",
    "image/jpeg", "image/jpg", "image/png", "image/webp", "image/tiff",
}


def _ext(filename: str) -> str:
    return os.path.splitext(filename.lower())[1]


def _accepted(filename: str, content_type: str) -> bool:
    return _ext(filename) in _ACCEPTED_EXT or content_type in _ACCEPTED_MIME


@router.post("")
@limiter.limit("20/minute")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    if not _accepted(file.filename, file.content_type or ""):
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Please upload a PDF or image (JPG, PNG, WEBP, TIFF).",
        )

    file_bytes = await file.read()

    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum allowed size is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
        )

    if _ext(file.filename) == ".pdf":
        try:
            pil_pages = convert_from_bytes(file_bytes, dpi=150)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Could not parse PDF: {e}")
    else:
        try:
            pil_pages = [Image.open(io.BytesIO(file_bytes)).convert("RGB")]
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Could not open image: {e}")

    if len(pil_pages) > MAX_PAGES:
        raise HTTPException(
            status_code=422,
            detail=f"Document has {len(pil_pages)} pages. Maximum allowed is {MAX_PAGES}.",
        )

    upload_id   = str(uuid.uuid4())
    page_images = []
    thumbnails  = []

    for page in pil_pages:
        full_buf = io.BytesIO()
        page.save(full_buf, "PNG")
        page_images.append(full_buf.getvalue())

        thumb = page.copy()
        thumb.thumbnail(THUMBNAIL_MAX)
        thumb_buf = io.BytesIO()
        thumb.save(thumb_buf, "PNG")
        thumbnails.append(base64.b64encode(thumb_buf.getvalue()).decode())

    await storage.store_upload(upload_id, file.filename, page_images)

    user_db_id = uuid.UUID(user["user_id"])
    doc = Document(user_id=user_db_id, filename=file.filename, total_pages=len(pil_pages), status="uploaded")
    async with AsyncSessionLocal() as db:
        db.add(doc)
        await db.commit()
        await db.refresh(doc)

    log.info(
        "upload stored upload_id=%s document_id=%s pages=%d user=%s",
        upload_id, doc.id, len(pil_pages), user.get("email"),
    )

    return {
        "upload_id":   upload_id,
        "document_id": str(doc.id),
        "filename":    file.filename,
        "total_pages": len(pil_pages),
        "thumbnails":  thumbnails,
    }


@router.delete("/{upload_id}")
async def delete_upload(upload_id: str, user: dict = Depends(get_current_user)):
    await storage.delete_upload(upload_id)
    log.info("upload deleted upload_id=%s user=%s", upload_id, user.get("email"))
    return {"deleted": upload_id}
