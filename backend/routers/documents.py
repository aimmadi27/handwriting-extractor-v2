import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from dependencies import get_current_user
from limiter import limiter
from logger import get_logger
from models import Document, Page, User

router = APIRouter()
log = get_logger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_user_row(db: AsyncSession, google_sub: str) -> Optional[User]:
    return await db.scalar(select(User).where(User.google_sub == google_sub))


async def _require_document(db: AsyncSession, document_id: str, user_row: User) -> Document:
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Document not found.")

    doc = await db.scalar(
        select(Document)
        .where(Document.id == doc_uuid, Document.user_id == user_row.id)
        .options(selectinload(Document.pages))
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    return doc


def _page_to_dict(p: Page) -> dict:
    return {
        "doc_type":   p.doc_type,
        "title":      p.title,
        "sections":   p.sections,
        "validation": p.validation,
        "edited":     p.edited,
        "updated_at": p.updated_at.isoformat(),
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("")
@limiter.limit("60/minute")
async def list_documents(
    request: Request,
    page: int = 1,
    per_page: int = 20,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return a paginated list of the user's documents, newest first."""
    user_row = await _get_user_row(db, user["sub"])
    if not user_row:
        return {"items": [], "total": 0, "page": page, "per_page": per_page}

    total = await db.scalar(
        select(func.count()).select_from(Document).where(Document.user_id == user_row.id)
    )

    rows = (await db.execute(
        select(Document)
        .where(Document.user_id == user_row.id)
        .options(selectinload(Document.pages))
        .order_by(Document.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )).scalars().all()

    return {
        "items": [
            {
                "id":              str(d.id),
                "filename":        d.filename,
                "total_pages":     d.total_pages,
                "extracted_pages": len(d.pages),
                "status":          d.status,
                "created_at":      d.created_at.isoformat(),
            }
            for d in rows
        ],
        "total":    total,
        "page":     page,
        "per_page": per_page,
    }


@router.get("/{document_id}")
@limiter.limit("60/minute")
async def get_document(
    request: Request,
    document_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return a document and all its extracted pages."""
    user_row = await _get_user_row(db, user["sub"])
    if not user_row:
        raise HTTPException(status_code=404, detail="Document not found.")

    doc = await _require_document(db, document_id, user_row)

    return {
        "id":          str(doc.id),
        "filename":    doc.filename,
        "total_pages": doc.total_pages,
        "status":      doc.status,
        "created_at":  doc.created_at.isoformat(),
        "pages":       {str(p.page_num): _page_to_dict(p) for p in doc.pages},
    }


class DocumentRenameRequest(BaseModel):
    filename: str


@router.patch("/{document_id}")
@limiter.limit("30/minute")
async def rename_document(
    request: Request,
    document_id: str,
    body: DocumentRenameRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_row = await _get_user_row(db, user["sub"])
    if not user_row:
        raise HTTPException(status_code=404, detail="Document not found.")

    doc = await _require_document(db, document_id, user_row)
    name = body.filename.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Filename cannot be empty.")

    doc.filename   = name
    doc.updated_at = datetime.now(timezone.utc)
    await db.commit()
    log.info("document renamed document_id=%s user=%s", document_id, user.get("email"))
    return {"ok": True}


@router.delete("/{document_id}")
@limiter.limit("20/minute")
async def delete_document(
    request: Request,
    document_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_row = await _get_user_row(db, user["sub"])
    if not user_row:
        raise HTTPException(status_code=404, detail="Document not found.")

    doc = await _require_document(db, document_id, user_row)
    await db.delete(doc)
    await db.commit()

    log.info("document deleted document_id=%s user=%s", document_id, user.get("email"))
    return {"deleted": document_id}


@router.get("/{document_id}/status")
@limiter.limit("60/minute")
async def get_document_status(
    request: Request,
    document_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lightweight status check — used by the frontend when SSE reconnects."""
    user_row = await _get_user_row(db, user["sub"])
    if not user_row:
        raise HTTPException(status_code=404, detail="Document not found.")

    doc = await _require_document(db, document_id, user_row)

    return {
        "status":          doc.status,
        "total_pages":     doc.total_pages,
        "extracted_pages": len(doc.pages),
    }


class PageUpdateRequest(BaseModel):
    title: str
    sections: List[Any]
    validation: dict


@router.patch("/{document_id}/pages/{page_num}")
@limiter.limit("120/minute")
async def update_page(
    request: Request,
    document_id: str,
    page_num: int,
    body: PageUpdateRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Auto-save endpoint — persists inline edits from the review UI."""
    user_row = await _get_user_row(db, user["sub"])
    if not user_row:
        raise HTTPException(status_code=404, detail="Document not found.")

    doc = await _require_document(db, document_id, user_row)

    page = next((p for p in doc.pages if p.page_num == page_num), None)
    if not page:
        raise HTTPException(status_code=404, detail=f"Page {page_num} not found.")

    page.title      = body.title
    page.sections   = body.sections
    page.validation = body.validation
    page.edited     = True
    page.updated_at = datetime.now(timezone.utc)

    await db.commit()
    return {"ok": True}
