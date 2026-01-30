"""
Cookie Receipt API endpoints.

POST /api/cookies          — create cookie receipt
GET  /api/cookies          — list all cookie receipts
GET  /api/cookies/{id}     — get one cookie receipt
DELETE /api/cookies/{id}   — delete cookie receipt
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.a.database import get_db
from app.a.models.receipt import CookieReceiptModel
from app.a.schemas import (
    CookieReceipt,
    CookieReceiptCreateRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def calculate_cookie_stats(cookies: list) -> dict:
    """쿠키 통계 계산"""
    from app.a.schemas import CookieInfo
    
    stats = {
        'total_cookies': len(cookies),
        'first_party_count': 0,
        'third_party_count': 0,
        'advertising_count': 0,
        'analytics_count': 0,
        'functional_count': 0,
        'session_count': 0,
        'persistent_count': 0,
    }
    
    for cookie in cookies:
        # CookieInfo 객체인지 dict인지 확인
        if isinstance(cookie, CookieInfo):
            party_type = cookie.party_type
            purpose = cookie.purpose
            duration = cookie.duration
        else:
            # dict인 경우
            party_type = cookie.get('party_type', '')
            purpose = cookie.get('purpose', '')
            duration = cookie.get('duration', '')
        
        # Party type
        if party_type == 'first_party':
            stats['first_party_count'] += 1
        elif party_type == 'third_party':
            stats['third_party_count'] += 1
        
        # Purpose
        if purpose == 'advertising':
            stats['advertising_count'] += 1
        elif purpose == 'analytics':
            stats['analytics_count'] += 1
        elif purpose == 'functional':
            stats['functional_count'] += 1
        
        # Duration
        if duration == 'session':
            stats['session_count'] += 1
        elif duration == 'persistent':
            stats['persistent_count'] += 1
    
    return stats


# ── POST /api/cookies ─────────────────────────────────────────────────────
@router.post("/cookies", response_model=CookieReceipt)
def create_cookie_receipt(req: CookieReceiptCreateRequest, db: Session = Depends(get_db)):
    """쿠키 영수증 생성"""
    from datetime import datetime, timezone
    import uuid
    
    receipt_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    
    # 쿠키 통계 계산
    stats = calculate_cookie_stats(req.cookies)
    
    # CookieReceipt 생성
    cookie_receipt = CookieReceipt(
        receipt_id=receipt_id,
        created_at=created_at,
        site_name=req.site_name,
        site_url=req.site_url,
        cookies=req.cookies,
        **stats
    )
    
    # DB 저장
    record = CookieReceiptModel(
        id=receipt_id,
        created_at=created_at,
        site_name=req.site_name,
        site_url=req.site_url,
        cookie_receipt_json=cookie_receipt.model_dump(),
    )
    db.add(record)
    db.commit()
    logger.info("Stored cookie receipt %s", receipt_id)
    
    return cookie_receipt


# ── GET /api/cookies ──────────────────────────────────────────────────────
@router.get("/cookies")
def list_cookie_receipts(db: Session = Depends(get_db)):
    """쿠키 영수증 목록 조회"""
    rows = (
        db.query(CookieReceiptModel)
        .order_by(CookieReceiptModel.created_at.desc())
        .all()
    )
    return [r.cookie_receipt_json for r in rows]


# ── GET /api/cookies/{receipt_id} ────────────────────────────────────────
@router.get("/cookies/{receipt_id}", response_model=CookieReceipt)
def get_cookie_receipt(receipt_id: str, db: Session = Depends(get_db)):
    """쿠키 영수증 조회"""
    row = db.query(CookieReceiptModel).filter(CookieReceiptModel.id == receipt_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Cookie receipt not found")
    return row.cookie_receipt_json


# ── DELETE /api/cookies/{receipt_id} ─────────────────────────────────────
@router.delete("/cookies/{receipt_id}")
def delete_cookie_receipt(receipt_id: str, db: Session = Depends(get_db)):
    """쿠키 영수증 삭제"""
    row = db.query(CookieReceiptModel).filter(CookieReceiptModel.id == receipt_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Cookie receipt not found")
    db.delete(row)
    db.commit()
    logger.info("Deleted cookie receipt %s", receipt_id)
    return {"message": "Cookie receipt deleted successfully", "receipt_id": receipt_id}

