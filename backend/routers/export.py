import json
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel

from dependencies import get_current_user
from limiter import limiter
from exporters.pdf_export import export_pdf
from exporters.word_export import export_word
from exporters.excel_export import export_excel

router = APIRouter()


class ExportRequest(BaseModel):
    review_data: Dict[str, Any]


def _int_keys(d: Dict[str, Any]) -> Dict[int, Any]:
    return {int(k): v for k, v in d.items()}


@router.post("/pdf")
@limiter.limit("30/minute")
def export_as_pdf(request: Request, body: ExportRequest, user: dict = Depends(get_current_user)):
    try:
        pdf_bytes = export_pdf(_int_keys(body.review_data))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF export failed: {e}")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=extracted.pdf"},
    )


@router.post("/word")
@limiter.limit("30/minute")
def export_as_word(request: Request, body: ExportRequest, user: dict = Depends(get_current_user)):
    try:
        docx_bytes = export_word(_int_keys(body.review_data))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Word export failed: {e}")
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": "attachment; filename=extracted.docx"},
    )


@router.post("/excel")
@limiter.limit("30/minute")
def export_as_excel(request: Request, body: ExportRequest, user: dict = Depends(get_current_user)):
    try:
        xlsx_bytes = export_excel(_int_keys(body.review_data))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Excel export failed: {e}")
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=extracted.xlsx"},
    )


@router.post("/json")
@limiter.limit("30/minute")
def export_as_json(request: Request, body: ExportRequest, user: dict = Depends(get_current_user)):
    return Response(
        content=json.dumps(body.review_data, indent=2, ensure_ascii=False),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=extracted.json"},
    )
