"""
철회/삭제 요청 모델
"""
from sqlalchemy import Column, String, Text, JSON, DateTime, Integer, Boolean
from datetime import datetime
from app.b.database import Base


class RevocationRequestModel(Base):
    """철회/삭제 요청"""
    __tablename__ = "revocation_requests"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    receipt_id = Column(String, index=True)  # 연결된 영수증 ID (optional)
    
    # 대상 정보
    service_name = Column(String, nullable=False)
    entity_name = Column(String, nullable=False)
    entity_type = Column(String)  # platform, private, public
    
    # 요청 정보
    request_type = Column(String, nullable=False)  # DELETE, WITHDRAW_CONSENT, STOP_THIRD_PARTY, LIMIT_PROCESSING
    scope_json = Column(JSON)  # accounts, data_items, time_range 등
    
    # 라우팅 정보
    routing_json = Column(JSON)  # primary_channel, destination, instructions 등
    
    # 상태
    status = Column(String, nullable=False, default="DRAFT")  # DRAFT, SENT, WAITING, DONE, REJECTED, NEED_MORE_INFO
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class RevocationLetterModel(Base):
    """철회 요청서"""
    __tablename__ = "revocation_letters"
    
    id = Column(String, primary_key=True)
    request_id = Column(String, nullable=False, index=True)
    subject = Column(String, nullable=False)
    body_text = Column(Text, nullable=False)
    rendered_pdf_path = Column(String)  # PDF 파일 경로 (optional)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class RevocationTimelineModel(Base):
    """철회 요청 타임라인"""
    __tablename__ = "revocation_timelines"
    
    id = Column(String, primary_key=True)
    request_id = Column(String, nullable=False, index=True)
    event = Column(String, nullable=False)  # CREATED, SENT, WAITING, DONE, REJECTED, NEED_MORE_INFO
    note = Column(Text)
    occurred_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class RoutingPresetModel(Base):
    """기관별 라우팅 프리셋"""
    __tablename__ = "routing_presets"
    
    id = Column(String, primary_key=True)
    service_name = Column(String, index=True)
    entity_name = Column(String, index=True)
    entity_type = Column(String)  # platform, private, public
    
    # 라우팅 정보
    primary_channel = Column(String)  # email, webform, civil_petition, call_center
    destination = Column(String)  # 이메일 주소 또는 URL
    instructions_json = Column(JSON)  # 제출 방법 안내
    
    # 메타데이터
    confidence = Column(Integer, default=100)  # 0-100
    source = Column(String, default="preset")  # preset, extracted, manual
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EvidencePackModel(Base):
    """증빙 패키지"""
    __tablename__ = "evidence_packs"
    
    id = Column(String, primary_key=True)
    request_id = Column(String, nullable=False, index=True)
    manifest_json = Column(JSON, nullable=False)  # 패키지 구성 정보
    zip_path = Column(String)  # ZIP 파일 경로 (optional)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

