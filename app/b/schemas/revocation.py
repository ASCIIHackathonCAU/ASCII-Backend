"""
철회/삭제 요청 관련 스키마
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class RoutingInfo(BaseModel):
    """라우팅 정보"""
    primary_channel: str = Field(..., description="email|webform|civil_petition|call_center")
    destination: str = Field(..., description="이메일 주소 또는 URL")
    instructions: List[str] = Field(default_factory=list)
    confidence: int = Field(default=100, ge=0, le=100)
    source: str = Field(default="preset", description="preset|extracted|manual")


class RequestScope(BaseModel):
    """요청 범위"""
    accounts: Optional[List[str]] = None  # 이메일 주소 등
    data_items: Optional[List[str]] = None  # 삭제할 데이터 항목
    time_range: Optional[str] = None  # 시간 범위 (optional)


class RevocationRequestCreate(BaseModel):
    """철회 요청 생성"""
    receipt_id: Optional[str] = None
    service_name: str
    entity_name: str
    entity_type: Optional[str] = None  # platform, private, public
    request_type: str = Field(..., description="DELETE|WITHDRAW_CONSENT|STOP_THIRD_PARTY|LIMIT_PROCESSING")
    scope: Optional[RequestScope] = None


class RevocationRequestResponse(BaseModel):
    """철회 요청 응답"""
    id: str
    receipt_id: Optional[str] = None
    service_name: str
    entity_name: str
    entity_type: Optional[str] = None
    request_type: str
    scope: Optional[RequestScope] = None
    routing: Optional[RoutingInfo] = None
    status: str
    created_at: datetime
    updated_at: datetime


class RevocationLetterResponse(BaseModel):
    """철회 요청서 응답"""
    id: str
    request_id: str
    subject: str
    body_text: str
    rendered_pdf_path: Optional[str] = None
    created_at: datetime


class RevocationTimelineEvent(BaseModel):
    """타임라인 이벤트"""
    id: str
    request_id: str
    event: str
    note: Optional[str] = None
    occurred_at: datetime


class RevocationRequestGenerateLetter(BaseModel):
    """요청서 생성 요청"""
    request_id: str
    template_type: Optional[str] = Field(default="standard", description="standard|minimal|detailed")


class RoutingPresetCreate(BaseModel):
    """라우팅 프리셋 생성"""
    service_name: str
    entity_name: str
    entity_type: Optional[str] = None
    primary_channel: str
    destination: str
    instructions: List[str] = Field(default_factory=list)


class RoutingPresetResponse(BaseModel):
    """라우팅 프리셋 응답"""
    id: str
    service_name: str
    entity_name: str
    entity_type: Optional[str] = None
    primary_channel: str
    destination: str
    instructions: List[str]
    confidence: int
    source: str
    created_at: datetime
    updated_at: datetime

