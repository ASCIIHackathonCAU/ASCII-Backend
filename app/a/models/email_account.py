"""
이메일 계정 모델 (메일 API 연동)
"""
from sqlalchemy import Column, String, Text, JSON, DateTime, Boolean
from datetime import datetime
from app.a.database import Base


class EmailAccountModel(Base):
    """이메일 계정 정보"""
    __tablename__ = "email_accounts"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)  # 사용자 ID (현재는 단일 사용자 가정)
    email = Column(String, nullable=False, unique=True)
    provider = Column(String, nullable=False)  # gmail, outlook, etc
    access_token = Column(Text)  # 암호화된 토큰 (실제로는 암호화 필요)
    refresh_token = Column(Text)  # 암호화된 토큰
    token_expires_at = Column(DateTime)
    is_active = Column(Boolean, default=True)
    last_sync_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ConsentEmailModel(Base):
    """동의 관련 이메일"""
    __tablename__ = "consent_emails"
    
    id = Column(String, primary_key=True)
    email_account_id = Column(String, nullable=False, index=True)
    message_id = Column(String, nullable=False, unique=True)  # 이메일 메시지 ID
    subject = Column(String, nullable=False)
    sender = Column(String, nullable=False)
    received_at = Column(DateTime, nullable=False)
    body_text = Column(Text, nullable=False)
    body_html = Column(Text)
    
    # 분류 결과
    category = Column(String)  # 주거, 금융, 통신, 복지, 취업, 기타
    is_consent_related = Column(Boolean, default=False)
    receipt_id = Column(String)  # 연결된 영수증 ID (nullable)
    
    # 분석 결과 JSON
    analysis_json = Column(JSON)  # 위험 신호, 필수/선택 분리 등
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

