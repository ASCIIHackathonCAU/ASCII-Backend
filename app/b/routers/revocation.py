"""
철회/삭제 요청 API 라우터
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.b.database import get_db
from app.b.models.revocation_request import (
    RevocationRequestModel,
    RevocationLetterModel,
    RevocationTimelineModel,
    RoutingPresetModel,
    EvidencePackModel,
)
from app.b.schemas.revocation import (
    RevocationRequestCreate,
    RevocationRequestResponse,
    RevocationLetterResponse,
    RevocationTimelineEvent,
    RevocationRequestGenerateLetter,
    RoutingInfo,
    RequestScope,
    RoutingPresetCreate,
    RoutingPresetResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def transform_request(model: RevocationRequestModel) -> RevocationRequestResponse:
    """RevocationRequestModel을 RevocationRequestResponse로 변환"""
    routing = None
    if model.routing_json:
        routing = RoutingInfo(**model.routing_json)
    
    scope = None
    if model.scope_json:
        scope = RequestScope(**model.scope_json)
    
    return RevocationRequestResponse(
        id=model.id,
        receipt_id=model.receipt_id,
        service_name=model.service_name,
        entity_name=model.entity_name,
        entity_type=model.entity_type,
        request_type=model.request_type,
        scope=scope,
        routing=routing,
        status=model.status,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


# ── POST /api/revocation/requests ────────────────────────────────────────────
@router.post("/revocation/requests", response_model=RevocationRequestResponse)
def create_revocation_request(
    req: RevocationRequestCreate,
    db: Session = Depends(get_db),
):
    """철회 요청 생성"""
    # 라우팅 정보 찾기
    routing = find_routing(db, req.service_name, req.entity_name, req.entity_type)
    
    # 요청 생성
    request = RevocationRequestModel(
        id=str(uuid.uuid4()),
        user_id="default_user",  # TODO: 실제 사용자 인증 구현 시 변경
        receipt_id=req.receipt_id,
        service_name=req.service_name,
        entity_name=req.entity_name,
        entity_type=req.entity_type,
        request_type=req.request_type,
        scope_json=req.scope.model_dump() if req.scope else None,
        routing_json=routing.model_dump() if routing else None,
        status="DRAFT",
    )
    db.add(request)
    
    # 타임라인 이벤트 추가
    timeline = RevocationTimelineModel(
        id=str(uuid.uuid4()),
        request_id=request.id,
        event="CREATED",
        note="요청서가 생성되었습니다.",
    )
    db.add(timeline)
    
    db.commit()
    logger.info("Created revocation request: %s", request.id)
    
    return transform_request(request)


def find_routing(
    db: Session,
    service_name: str,
    entity_name: str,
    entity_type: Optional[str] = None,
) -> Optional[RoutingInfo]:
    """라우팅 정보 찾기 (프리셋 우선, 없으면 추론)"""
    # 프리셋에서 찾기
    preset = db.query(RoutingPresetModel).filter(
        RoutingPresetModel.service_name == service_name,
        RoutingPresetModel.entity_name == entity_name,
    ).first()
    
    if preset:
        return RoutingInfo(
            primary_channel=preset.primary_channel,
            destination=preset.destination,
            instructions=preset.instructions_json or [],
            confidence=preset.confidence,
            source="preset",
        )
    
    # 프리셋이 없으면 기본값 반환 (사용자가 직접 확인 필요)
    return RoutingInfo(
        primary_channel="email",
        destination="고객센터 문의 필요",
        instructions=["서비스 고객센터에 직접 문의하시기 바랍니다."],
        confidence=0,
        source="manual",
    )


# ── GET /api/revocation/requests ────────────────────────────────────────────
@router.get("/revocation/requests", response_model=List[RevocationRequestResponse])
def list_revocation_requests(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """철회 요청 목록"""
    query = db.query(RevocationRequestModel)
    
    if status:
        query = query.filter(RevocationRequestModel.status == status)
    
    requests = query.order_by(RevocationRequestModel.created_at.desc()).all()
    return [transform_request(req) for req in requests]


# ── GET /api/revocation/requests/{request_id} ───────────────────────────────
@router.get("/revocation/requests/{request_id}", response_model=RevocationRequestResponse)
def get_revocation_request(
    request_id: str,
    db: Session = Depends(get_db),
):
    """철회 요청 조회"""
    request = db.query(RevocationRequestModel).filter(RevocationRequestModel.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    return transform_request(request)


# ── POST /api/revocation/requests/{request_id}/generate-letter ──────────────
@router.post("/revocation/requests/{request_id}/generate-letter", response_model=RevocationLetterResponse)
def generate_letter(
    request_id: str,
    req: RevocationRequestGenerateLetter,
    db: Session = Depends(get_db),
):
    """철회 요청서 생성"""
    request = db.query(RevocationRequestModel).filter(RevocationRequestModel.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    # 템플릿 기반 요청서 생성
    subject, body_text = generate_letter_template(request, req.template_type)
    
    # 요청서 저장
    letter = RevocationLetterModel(
        id=str(uuid.uuid4()),
        request_id=request_id,
        subject=subject,
        body_text=body_text,
    )
    db.add(letter)
    
    # 타임라인 이벤트 추가
    timeline = RevocationTimelineModel(
        id=str(uuid.uuid4()),
        request_id=request_id,
        event="CREATED",
        note="요청서가 생성되었습니다.",
    )
    db.add(timeline)
    
    db.commit()
    logger.info("Generated letter for request: %s", request_id)
    
    return RevocationLetterResponse(
        id=letter.id,
        request_id=letter.request_id,
        subject=letter.subject,
        body_text=letter.body_text,
        rendered_pdf_path=letter.rendered_pdf_path,
        created_at=letter.created_at,
    )


def generate_letter_template(request: RevocationRequestModel, template_type: str = "standard") -> tuple[str, str]:
    """요청서 템플릿 생성"""
    request_type_map = {
        "DELETE": "개인정보 삭제",
        "WITHDRAW_CONSENT": "동의 철회",
        "STOP_THIRD_PARTY": "제3자 제공 중단",
        "LIMIT_PROCESSING": "처리 제한",
    }
    
    request_type_kr = request_type_map.get(request.request_type, request.request_type)
    
    subject = f"[개인정보보호법] {request_type_kr} 요청"
    
    body_parts = [
        f"안녕하세요, {request.entity_name} 담당자님,",
        "",
        f"저는 {request.service_name} 서비스를 이용 중인 사용자입니다.",
        "",
        f"개인정보보호법 제30조(개인정보의 수집·이용 동의 등) 및 제37조(개인정보의 삭제·파기)에 따라",
        f"다음과 같이 {request_type_kr}를 요청드립니다.",
        "",
        "【요청 내용】",
        f"- 서비스명: {request.service_name}",
        f"- 요청 유형: {request_type_kr}",
    ]
    
    if request.scope_json:
        scope = RequestScope(**request.scope_json)
        if scope.accounts:
            body_parts.append(f"- 계정: {', '.join(scope.accounts)}")
        if scope.data_items:
            body_parts.append(f"- 삭제 항목: {', '.join(scope.data_items)}")
    
    body_parts.extend([
        "",
        "【법적 근거】",
        "- 개인정보보호법 제30조(개인정보의 수집·이용 동의 등)",
        "- 개인정보보호법 제37조(개인정보의 삭제·파기)",
        "",
        "위 요청에 대해 법정 기한 내에 처리해 주시기 바랍니다.",
        "",
        "감사합니다.",
        "",
        "[사용자 정보]",
        "- 요청일: " + datetime.utcnow().strftime("%Y년 %m월 %d일"),
    ])
    
    body_text = "\n".join(body_parts)
    
    return subject, body_text


# ── POST /api/revocation/requests/{request_id}/send ──────────────────────────
@router.post("/revocation/requests/{request_id}/send", response_model=RevocationRequestResponse)
def send_request(
    request_id: str,
    db: Session = Depends(get_db),
):
    """철회 요청 전송 (상태 변경)"""
    request = db.query(RevocationRequestModel).filter(RevocationRequestModel.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    # 요청서가 있어야 전송 가능
    letter = db.query(RevocationLetterModel).filter(RevocationLetterModel.request_id == request_id).first()
    if not letter:
        raise HTTPException(status_code=400, detail="Letter not generated. Please generate letter first.")
    
    # 상태 변경
    request.status = "SENT"
    request.updated_at = datetime.utcnow()
    
    # 타임라인 이벤트 추가
    timeline = RevocationTimelineModel(
        id=str(uuid.uuid4()),
        request_id=request_id,
        event="SENT",
        note="요청서가 전송되었습니다.",
    )
    db.add(timeline)
    
    # TODO: 실제 메일 전송 (SMTP 또는 메일 API 사용)
    logger.info("Sent revocation request: %s", request_id)
    
    db.commit()
    return transform_request(request)


# ── GET /api/revocation/requests/{request_id}/timeline ───────────────────────
@router.get("/revocation/requests/{request_id}/timeline", response_model=List[RevocationTimelineEvent])
def get_timeline(
    request_id: str,
    db: Session = Depends(get_db),
):
    """철회 요청 타임라인 조회"""
    request = db.query(RevocationRequestModel).filter(RevocationRequestModel.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    timeline = db.query(RevocationTimelineModel).filter(
        RevocationTimelineModel.request_id == request_id
    ).order_by(RevocationTimelineModel.occurred_at).all()
    
    return [
        RevocationTimelineEvent(
            id=t.id,
            request_id=t.request_id,
            event=t.event,
            note=t.note,
            occurred_at=t.occurred_at,
        )
        for t in timeline
    ]


# ── POST /api/revocation/routing/presets ────────────────────────────────────
@router.post("/revocation/routing/presets", response_model=RoutingPresetResponse)
def create_routing_preset(
    req: RoutingPresetCreate,
    db: Session = Depends(get_db),
):
    """라우팅 프리셋 생성"""
    preset = RoutingPresetModel(
        id=str(uuid.uuid4()),
        service_name=req.service_name,
        entity_name=req.entity_name,
        entity_type=req.entity_type,
        primary_channel=req.primary_channel,
        destination=req.destination,
        instructions_json=req.instructions,
        confidence=100,
        source="preset",
    )
    db.add(preset)
    db.commit()
    logger.info("Created routing preset: %s / %s", req.service_name, req.entity_name)
    
    return RoutingPresetResponse(
        id=preset.id,
        service_name=preset.service_name,
        entity_name=preset.entity_name,
        entity_type=preset.entity_type,
        primary_channel=preset.primary_channel,
        destination=preset.destination,
        instructions=preset.instructions_json or [],
        confidence=preset.confidence,
        source=preset.source,
        created_at=preset.created_at,
        updated_at=preset.updated_at,
    )


# ── GET /api/revocation/routing/presets ─────────────────────────────────────
@router.get("/revocation/routing/presets", response_model=List[RoutingPresetResponse])
def list_routing_presets(db: Session = Depends(get_db)):
    """라우팅 프리셋 목록"""
    presets = db.query(RoutingPresetModel).order_by(RoutingPresetModel.service_name).all()
    return [
        RoutingPresetResponse(
            id=p.id,
            service_name=p.service_name,
            entity_name=p.entity_name,
            entity_type=p.entity_type,
            primary_channel=p.primary_channel,
            destination=p.destination,
            instructions=p.instructions_json or [],
            confidence=p.confidence,
            source=p.source,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in presets
    ]

