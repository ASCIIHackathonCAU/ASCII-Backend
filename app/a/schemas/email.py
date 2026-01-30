"""
이메일 연동 관련 스키마
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class EmailAccountCreate(BaseModel):
    """이메일 계정 연결 요청"""
    email: str
    provider: str = Field(..., description="gmail, outlook, etc")
    access_token: str
    refresh_token: Optional[str] = None
    token_expires_at: Optional[datetime] = None


class EmailAccountResponse(BaseModel):
    """이메일 계정 응답"""
    id: str
    email: str
    provider: str
    is_active: bool
    last_sync_at: Optional[datetime] = None
    created_at: datetime


class ConsentEmailResponse(BaseModel):
    """동의 이메일 응답"""
    id: str
    subject: str
    sender: str
    received_at: datetime
    category: Optional[str] = None
    is_consent_related: bool = False
    receipt_id: Optional[str] = None
    analysis_json: Optional[dict] = None


class EmailSyncRequest(BaseModel):
    """이메일 동기화 요청"""
    email_account_id: str
    max_emails: int = Field(default=50, ge=1, le=500)


class EmailSyncResponse(BaseModel):
    """이메일 동기화 응답"""
    synced_count: int
    consent_emails_found: int
    emails: list[ConsentEmailResponse]

