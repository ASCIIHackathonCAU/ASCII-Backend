"""
ReceiptOS API endpoints.

POST /api/ingest          — process document → receipt + extract result
GET  /api/receipts        — list all receipts
GET  /api/receipts/{id}   — get one receipt
POST /api/diff            — compare two receipts / raw texts
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.a.database import get_db
from app.a.models.receipt import ReceiptModel
from app.a.pipeline import process_document
from app.a.pipeline.differ import diff_extract_results
from app.a.schemas import (
    DiffRequest,
    DiffResult,
    ExtractResult,
    IngestRequest,
    IngestResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ── POST /api/ingest ─────────────────────────────────────────────────────
@router.post("/ingest", response_model=IngestResponse)
def ingest(req: IngestRequest, db: Session = Depends(get_db)):
    if not req.raw_text.strip():
        raise HTTPException(status_code=400, detail="raw_text must not be empty")

    logger.info("Ingest: source_type=%s  len=%d", req.source_type, len(req.raw_text))

    receipt, extract_result = process_document(req.raw_text, req.source_type)

    record = ReceiptModel(
        id=receipt.receipt_id,
        created_at=receipt.created_at,
        source_type=receipt.source_type,
        document_type=receipt.document_type,
        raw_text=req.raw_text,
        content_hash=receipt.content_hash,
        extract_result_json=extract_result.model_dump(),
        receipt_json=receipt.model_dump(),
    )
    db.add(record)
    db.commit()
    logger.info("Stored receipt %s", receipt.receipt_id)

    return IngestResponse(receipt=receipt, extract_result=extract_result)


# ── GET /api/receipts ────────────────────────────────────────────────────
@router.get("/receipts")
def list_receipts(db: Session = Depends(get_db)):
    rows = (
        db.query(ReceiptModel)
        .order_by(ReceiptModel.created_at.desc())
        .all()
    )
    logger.info("Found %d receipts in database", len(rows))
    return [r.receipt_json for r in rows]


# ── GET /api/receipts/{receipt_id} ───────────────────────────────────────
@router.get("/receipts/{receipt_id}")
def get_receipt(receipt_id: str, db: Session = Depends(get_db)):
    logger.info("Fetching receipt: %s", receipt_id)
    row = db.query(ReceiptModel).filter(ReceiptModel.id == receipt_id).first()
    if not row:
        logger.warning("Receipt not found: %s", receipt_id)
        raise HTTPException(status_code=404, detail="Receipt not found")
    logger.info("Receipt found: %s", receipt_id)
    return row.receipt_json


# ── DELETE /api/receipts/{receipt_id} ─────────────────────────────────────
@router.delete("/receipts/{receipt_id}")
def delete_receipt(receipt_id: str, db: Session = Depends(get_db)):
    row = db.query(ReceiptModel).filter(ReceiptModel.id == receipt_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Receipt not found")
    
    # 연결된 이메일의 receipt_id를 null로 업데이트
    from app.a.models.email_account import ConsentEmailModel
    emails = db.query(ConsentEmailModel).filter(ConsentEmailModel.receipt_id == receipt_id).all()
    for email in emails:
        email.receipt_id = None
        email.analysis_json = None
    
    db.delete(row)
    db.commit()
    logger.info("Deleted receipt %s and unlinked %d emails", receipt_id, len(emails))
    return {"message": "Receipt deleted successfully", "receipt_id": receipt_id}


# ── POST /api/diff ───────────────────────────────────────────────────────
@router.post("/diff", response_model=DiffResult)
def diff(req: DiffRequest, db: Session = Depends(get_db)):
    # --- resolve side A ---
    if req.receipt_id_a:
        row_a = db.query(ReceiptModel).filter(ReceiptModel.id == req.receipt_id_a).first()
        if not row_a:
            raise HTTPException(404, detail=f"Receipt A not found: {req.receipt_id_a}")
        result_a = ExtractResult(**row_a.extract_result_json)
        rid_a = req.receipt_id_a
    elif req.raw_text_a:
        _, result_a = process_document(req.raw_text_a)
        rid_a = None
    else:
        raise HTTPException(400, detail="Provide receipt_id_a or raw_text_a")

    # --- resolve side B ---
    if req.receipt_id_b:
        row_b = db.query(ReceiptModel).filter(ReceiptModel.id == req.receipt_id_b).first()
        if not row_b:
            raise HTTPException(404, detail=f"Receipt B not found: {req.receipt_id_b}")
        result_b = ExtractResult(**row_b.extract_result_json)
        rid_b = req.receipt_id_b
    elif req.raw_text_b:
        _, result_b = process_document(req.raw_text_b)
        rid_b = None
    else:
        raise HTTPException(400, detail="Provide receipt_id_b or raw_text_b")

    return diff_extract_results(
        result_a=result_a.fields,
        result_b=result_b.fields,
        signals_a=result_a.signals,
        signals_b=result_b.signals,
        receipt_a_id=rid_a,
        receipt_b_id=rid_b,
    )
