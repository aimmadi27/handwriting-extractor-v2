import base64
import io
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pdf2image import convert_from_bytes

from dependencies import get_current_user
from storage import pdf_store

router = APIRouter()

THUMBNAIL_MAX = (420, 600)  # px — sent to frontend for page picker


@router.post("")
async def upload_pdf(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    """
    Accept a PDF, convert every page to PNG, store full-res images server-side,
    and return base64 thumbnails so the frontend can render the page picker.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    pdf_bytes = await file.read()

    try:
        pages = convert_from_bytes(pdf_bytes, dpi=150)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not parse PDF: {e}")

    upload_id   = str(uuid.uuid4())
    page_images = []
    thumbnails  = []

    for page in pages:
        # Full-resolution PNG stored server-side for LLM extraction
        full_buf = io.BytesIO()
        page.save(full_buf, "PNG")
        page_images.append(full_buf.getvalue())

        # Downscaled thumbnail returned to frontend
        thumb = page.copy()
        thumb.thumbnail(THUMBNAIL_MAX)
        thumb_buf = io.BytesIO()
        thumb.save(thumb_buf, "PNG")
        thumbnails.append(base64.b64encode(thumb_buf.getvalue()).decode())

    pdf_store[upload_id] = {
        "filename":    file.filename,
        "page_images": page_images,
        "total_pages": len(pages),
    }

    return {
        "upload_id":   upload_id,
        "filename":    file.filename,
        "total_pages": len(pages),
        "thumbnails":  thumbnails,   # list of base64 PNG strings, one per page
    }


@router.delete("/{upload_id}")
def delete_upload(upload_id: str, user: dict = Depends(get_current_user)):
    """Free server-side memory once the frontend is done with a session."""
    pdf_store.pop(upload_id, None)
    return {"deleted": upload_id}
