"""
이메일 연동 API 라우터
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.a.database import get_db
from app.a.models.email_account import EmailAccountModel, ConsentEmailModel
from app.a.schemas.email import (
    EmailAccountCreate,
    EmailAccountResponse,
    ConsentEmailResponse,
    EmailSyncRequest,
    EmailSyncResponse,
)
from app.a.pipeline import process_document

logger = logging.getLogger(__name__)
router = APIRouter()


def transform_email_account(model: EmailAccountModel) -> EmailAccountResponse:
    """EmailAccountModel을 EmailAccountResponse로 변환"""
    return EmailAccountResponse(
        id=model.id,
        email=model.email,
        provider=model.provider,
        is_active=model.is_active,
        last_sync_at=model.last_sync_at,
        created_at=model.created_at or datetime.utcnow(),
    )


def transform_consent_email(model: ConsentEmailModel) -> ConsentEmailResponse:
    """ConsentEmailModel을 ConsentEmailResponse로 변환"""
    return ConsentEmailResponse(
        id=model.id,
        subject=model.subject,
        sender=model.sender,
        received_at=model.received_at,
        category=model.category,
        is_consent_related=model.is_consent_related,
        receipt_id=model.receipt_id,
        analysis_json=model.analysis_json,
    )


# ── POST /api/email/accounts ────────────────────────────────────────────────
@router.post("/email/accounts", response_model=EmailAccountResponse)
def create_email_account(
    req: EmailAccountCreate,
    db: Session = Depends(get_db),
):
    """이메일 계정 연결"""
    # 기존 계정 확인
    existing = db.query(EmailAccountModel).filter(EmailAccountModel.email == req.email).first()
    if existing:
        # 업데이트
        existing.access_token = req.access_token
        existing.refresh_token = req.refresh_token
        existing.token_expires_at = req.token_expires_at
        existing.is_active = True
        existing.updated_at = datetime.utcnow()
        db.commit()
        return transform_email_account(existing)
    
    # 새 계정 생성
    account = EmailAccountModel(
        id=str(uuid.uuid4()),
        user_id="default_user",  # TODO: 실제 사용자 인증 구현 시 변경
        email=req.email,
        provider=req.provider,
        access_token=req.access_token,
        refresh_token=req.refresh_token,
        token_expires_at=req.token_expires_at,
        is_active=True,
    )
    db.add(account)
    db.commit()
    logger.info("Created email account: %s", req.email)
    return transform_email_account(account)


# ── GET /api/email/accounts ─────────────────────────────────────────────────
@router.get("/email/accounts", response_model=List[EmailAccountResponse])
def list_email_accounts(db: Session = Depends(get_db)):
    """연결된 이메일 계정 목록"""
    try:
        accounts = db.query(EmailAccountModel).filter(EmailAccountModel.is_active == True).all()
        
        # 더미 데이터가 없으면 생성
        if len(accounts) == 0:
            logger.info("No email accounts found, creating dummy accounts...")
            accounts = create_dummy_accounts(db)
            # 생성 후 다시 조회
            accounts = db.query(EmailAccountModel).filter(EmailAccountModel.is_active == True).all()
        
        logger.info("Returning %d email accounts", len(accounts))
        return [transform_email_account(acc) for acc in accounts]
    except Exception as e:
        logger.error("Error in list_email_accounts: %s", e, exc_info=True)
        # 에러 발생 시에도 더미 계정 생성 시도
        try:
            accounts = create_dummy_accounts(db)
            return [transform_email_account(acc) for acc in accounts]
        except Exception as e2:
            logger.error("Failed to create dummy accounts: %s", e2, exc_info=True)
            return []


def create_dummy_accounts(db: Session) -> List[EmailAccountModel]:
    """더미 이메일 계정 생성"""
    dummy_accounts = [
        {
            "email": "user@gmail.com",
            "provider": "gmail",
        },
        {
            "email": "user@outlook.com",
            "provider": "outlook",
        },
    ]
    
    created = []
    try:
        for acc_data in dummy_accounts:
            # 이미 존재하는지 확인 (is_active 여부와 관계없이)
            existing = db.query(EmailAccountModel).filter(EmailAccountModel.email == acc_data["email"]).first()
            if existing:
                # 기존 계정이 비활성화되어 있으면 활성화
                if not existing.is_active:
                    existing.is_active = True
                    existing.last_sync_at = datetime.utcnow()
                    db.commit()
                created.append(existing)
                continue
            
            account = EmailAccountModel(
                id=str(uuid.uuid4()),
                user_id="default_user",
                email=acc_data["email"],
                provider=acc_data["provider"],
                access_token="dummy_token",
                refresh_token="dummy_refresh_token",
                is_active=True,
                last_sync_at=datetime.utcnow(),
            )
            db.add(account)
            created.append(account)
        
        db.commit()
        logger.info("Created %d dummy email accounts", len(created))
    except Exception as e:
        logger.error("Error creating dummy accounts: %s", e, exc_info=True)
        db.rollback()
        raise
    
    return created


# ── POST /api/email/sync ────────────────────────────────────────────────────
@router.post("/email/sync", response_model=EmailSyncResponse)
def sync_emails(
    req: EmailSyncRequest,
    db: Session = Depends(get_db),
):
    """이메일 동기화 (실제 메일 API 호출은 추후 구현)"""
    account = db.query(EmailAccountModel).filter(EmailAccountModel.id == req.email_account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Email account not found")
    
    # TODO: 실제 메일 API 연동 (Gmail API, Outlook API 등)
    # 현재는 더미 구현
    logger.info("Syncing emails for account: %s (max: %d)", account.email, req.max_emails)
    
    # 더미 동의 이메일 생성
    dummy_emails = create_dummy_consent_emails(db, category=None)
    
    # 최근 동기화 시간 업데이트
    account.last_sync_at = datetime.utcnow()
    db.commit()
    
    return EmailSyncResponse(
        synced_count=len(dummy_emails),
        consent_emails_found=len(dummy_emails),
        emails=[transform_consent_email(email) for email in dummy_emails],
    )


# ── POST /api/email/consent-emails/{email_id}/analyze ──────────────────────
@router.post("/email/consent-emails/{email_id}/analyze", response_model=ConsentEmailResponse)
def analyze_consent_email(
    email_id: str,
    db: Session = Depends(get_db),
    force_reanalyze: bool = Query(False, description="기존 영수증 삭제 후 재분석"),
):
    """동의 이메일 분석 및 영수증 생성"""
    email = db.query(ConsentEmailModel).filter(ConsentEmailModel.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    
    # 이미 분석된 경우 (force_reanalyze가 False일 때만)
    if email.receipt_id and not force_reanalyze:
        return transform_consent_email(email)
    
    # 기존 영수증이 있고 재분석인 경우 삭제
    if email.receipt_id and force_reanalyze:
        from app.a.models.receipt import ReceiptModel
        existing_receipt = db.query(ReceiptModel).filter(ReceiptModel.id == email.receipt_id).first()
        if existing_receipt:
            db.delete(existing_receipt)
            email.receipt_id = None
            email.analysis_json = None
    
    # 문서 분석
    receipt, extract_result = process_document(email.body_text, source_type="email")
    
    # 영수증 저장 (receipts 테이블에 저장)
    from app.a.models.receipt import ReceiptModel
    receipt_record = ReceiptModel(
        id=receipt.receipt_id,
        created_at=receipt.created_at,
        source_type="email",
        document_type=receipt.document_type,
        raw_text=email.body_text,
        content_hash=receipt.content_hash,
        extract_result_json=extract_result.model_dump(),
        receipt_json=receipt.model_dump(),
    )
    db.add(receipt_record)
    
    # 이메일 업데이트
    email.receipt_id = receipt.receipt_id
    email.is_consent_related = True
    
    # 카테고리 추정
    category = infer_category(extract_result)
    email.category = category
    
    # 분석 결과 저장
    email.analysis_json = {
        "signals": [s.model_dump() for s in extract_result.signals],
        "document_type": extract_result.document_type,
    }
    
    db.commit()
    logger.info("Analyzed consent email: %s -> receipt: %s", email_id, receipt.receipt_id)
    
    return transform_consent_email(email)


def infer_category(extract_result) -> str:
    """추출 결과에서 카테고리를 추론"""
    fields = extract_result.fields
    field_keys = " ".join(fields.keys()).lower()
    
    if any(kw in field_keys for kw in ["주거", "임대", "부동산"]):
        return "주거"
    if any(kw in field_keys for kw in ["금융", "은행", "카드", "대출"]):
        return "금융"
    if any(kw in field_keys for kw in ["통신", "이동통신", "인터넷"]):
        return "통신"
    if any(kw in field_keys for kw in ["복지", "보험", "건강"]):
        return "복지"
    if any(kw in field_keys for kw in ["취업", "채용", "구직"]):
        return "취업"
    
    return "기타"


# ── GET /api/email/consent-emails ───────────────────────────────────────────
@router.get("/email/consent-emails", response_model=List[ConsentEmailResponse])
def list_consent_emails(
    category: str | None = None,
    db: Session = Depends(get_db),
):
    """동의 이메일 목록"""
    query = db.query(ConsentEmailModel)
    
    if category:
        query = query.filter(ConsentEmailModel.category == category)
    
    emails = query.order_by(ConsentEmailModel.received_at.desc()).all()
    
    # 더미 데이터가 없으면 생성
    if len(emails) == 0:
        emails = create_dummy_consent_emails(db, category)
    
    return [transform_consent_email(email) for email in emails]


def create_dummy_consent_emails(db: Session, category: str | None = None) -> List[ConsentEmailModel]:
    """더미 동의 이메일 생성"""
    # 이메일 계정이 없으면 생성
    accounts = db.query(EmailAccountModel).filter(EmailAccountModel.is_active == True).all()
    if len(accounts) == 0:
        accounts = create_dummy_accounts(db)
    
    account_id = accounts[0].id
    
    # 이미 더미 이메일이 있는지 확인
    existing_emails = db.query(ConsentEmailModel).filter(
        ConsentEmailModel.email_account_id == account_id
    ).all()
    
    # 기존 이메일 중 영수증이 없는 것들에 대해 영수증 생성
    for existing_email in existing_emails:
        if not existing_email.receipt_id:
            try:
                receipt, extract_result = process_document(existing_email.body_text, source_type="email")
                
                # 영수증 저장
                from app.a.models.receipt import ReceiptModel
                receipt_record = ReceiptModel(
                    id=receipt.receipt_id,
                    created_at=receipt.created_at,
                    source_type="email",
                    document_type=receipt.document_type,
                    raw_text=existing_email.body_text,
                    content_hash=receipt.content_hash,
                    extract_result_json=extract_result.model_dump(),
                    receipt_json=receipt.model_dump(),
                )
                db.add(receipt_record)
                
                # 이메일과 영수증 연결
                existing_email.receipt_id = receipt.receipt_id
                
                # 카테고리 추정
                inferred_category = infer_category(extract_result)
                if not existing_email.category:
                    existing_email.category = inferred_category
                
                # 분석 결과 저장
                existing_email.analysis_json = {
                    "signals": [s.model_dump() for s in extract_result.signals],
                    "document_type": extract_result.document_type,
                }
            except Exception as e:
                logger.warning("Failed to create receipt for existing email %s: %s", existing_email.id, e)
    
    if len(existing_emails) > 0:
        db.commit()
        # 기존 이메일 반환 (카테고리 필터링 적용)
        query = db.query(ConsentEmailModel).filter(ConsentEmailModel.email_account_id == account_id)
        if category:
            query = query.filter(ConsentEmailModel.category == category)
        return query.order_by(ConsentEmailModel.received_at.desc()).all()
    
    dummy_emails_data = [
        {
            "subject": "[KB국민은행] 개인정보 처리방침 변경 안내",
            "sender": "kb@kbstar.com",
            "category": "금융",
            "body_text": """안녕하세요, KB국민은행입니다.

개인정보 처리방침이 변경되어 안내드립니다.

[변경 사항]
- 개인정보 보유기간: 5년 → 7년
- 제3자 제공: 마케팅 목적으로 제3자 제공 가능

자세한 내용은 홈페이지에서 확인하실 수 있습니다.
문의: 1588-9999""",
            "days_ago": 2,
        },
        {
            "subject": "[SK텔레콤] 통신 서비스 이용약관 개정 안내",
            "sender": "sktelecom@sktelecom.com",
            "category": "통신",
            "body_text": """안녕하세요, SK텔레콤입니다.

통신 서비스 이용약관이 개정되었습니다.

[주요 변경사항]
- 위치정보 수집 및 이용 동의
- 마케팅 정보 수신 동의 (선택)

동의하지 않으셔도 서비스 이용에는 제한이 없습니다.
문의: 114""",
            "days_ago": 5,
        },
        {
            "subject": "[공공임대주택] 입주자 개인정보 수집·이용 동의서",
            "sender": "lh@lh.or.kr",
            "category": "주거",
            "body_text": """안녕하세요, 한국토지주택공사입니다.

입주자 개인정보 수집·이용에 대한 동의가 필요합니다.

[수집 항목]
- 주민등록번호
- 소득 증빙 서류
- 가족 구성원 정보

[보유 기간]
- 입주 기간 동안 보유

문의: 1600-1004""",
            "days_ago": 7,
        },
        {
            "subject": "[국민건강보험공단] 건강보험료 납부 안내 및 개인정보 처리",
            "sender": "nhis@nhis.or.kr",
            "category": "복지",
            "body_text": """안녕하세요, 국민건강보험공단입니다.

건강보험료 납부와 관련하여 개인정보를 처리합니다.

[처리 항목]
- 소득 정보
- 가족 관계 정보
- 건강 정보

[보유 기간]
- 법정 보유기간 준수

문의: 1577-1000""",
            "days_ago": 10,
        },
        {
            "subject": "[잡코리아] 채용 공고 알림 서비스 이용약관",
            "sender": "jobkorea@jobkorea.co.kr",
            "category": "취업",
            "body_text": """안녕하세요, 잡코리아입니다.

채용 공고 알림 서비스 이용을 위해 약관 동의가 필요합니다.

[수집 항목]
- 이메일 주소
- 희망 직종
- 경력 정보

[제3자 제공]
- 제휴 채용 사이트에 정보 제공 가능

문의: 1588-9350""",
            "days_ago": 12,
        },
        {
            "subject": "[네이버] 개인정보 처리방침 변경 안내",
            "sender": "privacy@naver.com",
            "category": "기타",
            "body_text": """안녕하세요, 네이버입니다.

개인정보 처리방침이 변경되었습니다.

[주요 변경사항]
- 위치정보 수집 및 이용
- 맞춤형 광고를 위한 개인정보 활용
- 제3자 정보 제공 범위 확대

자세한 내용은 개인정보 처리방침을 확인해주세요.
문의: help.naver.com""",
            "days_ago": 15,
        },
    ]
    
    created = []
    receipt_errors = []
    
    for email_data in dummy_emails_data:
        # 카테고리 필터링
        if category and email_data["category"] != category:
            continue
        
        received_at = datetime.utcnow() - timedelta(days=email_data["days_ago"])
        
        # 영수증 먼저 생성 (이메일 생성 전에)
        receipt_id = None
        try:
            receipt, extract_result = process_document(email_data["body_text"], source_type="email")
            
            # 영수증 저장
            from app.a.models.receipt import ReceiptModel
            # 이미 존재하는지 확인
            existing_receipt = db.query(ReceiptModel).filter(ReceiptModel.id == receipt.receipt_id).first()
            if not existing_receipt:
                receipt_record = ReceiptModel(
                    id=receipt.receipt_id,
                    created_at=receipt.created_at,
                    source_type="email",
                    document_type=receipt.document_type,
                    raw_text=email_data["body_text"],
                    content_hash=receipt.content_hash,
                    extract_result_json=extract_result.model_dump(),
                    receipt_json=receipt.model_dump(),
                )
                db.add(receipt_record)
                # 영수증 먼저 커밋
                db.commit()
                logger.info("Created and committed receipt %s for email '%s'", receipt.receipt_id, email_data["subject"])
            else:
                logger.info("Receipt %s already exists, reusing", receipt.receipt_id)
            
            receipt_id = receipt.receipt_id
            
            # 영수증이 제대로 저장되었는지 확인
            verify_receipt = db.query(ReceiptModel).filter(ReceiptModel.id == receipt_id).first()
            if not verify_receipt:
                raise Exception(f"Receipt {receipt_id} was not saved to database")
            
            # 카테고리 추정 (영수증에서)
            inferred_category = infer_category(extract_result)
            final_category = email_data["category"] or inferred_category
            
            # 이메일 생성 (영수증 ID 포함)
            email = ConsentEmailModel(
                id=str(uuid.uuid4()),
                email_account_id=account_id,
                message_id=f"dummy_msg_{uuid.uuid4()}",
                subject=email_data["subject"],
                sender=email_data["sender"],
                received_at=received_at,
                body_text=email_data["body_text"],
                category=final_category,
                is_consent_related=True,
                receipt_id=receipt_id,  # 영수증 ID 바로 연결
                analysis_json={
                    "signals": [s.model_dump() for s in extract_result.signals],
                    "document_type": extract_result.document_type,
                },
            )
            db.add(email)
            created.append(email)
            logger.info("Created email %s with receipt_id %s", email.id, receipt_id)
            
        except Exception as e:
            logger.error("Failed to create receipt for dummy email '%s': %s", email_data["subject"], e, exc_info=True)
            receipt_errors.append(f"{email_data['subject']}: {str(e)}")
            # 영수증 생성 실패 시에도 이메일은 저장 (receipt_id 없이)
            email = ConsentEmailModel(
                id=str(uuid.uuid4()),
                email_account_id=account_id,
                message_id=f"dummy_msg_{uuid.uuid4()}",
                subject=email_data["subject"],
                sender=email_data["sender"],
                received_at=received_at,
                body_text=email_data["body_text"],
                category=email_data["category"],
                is_consent_related=True,
                receipt_id=None,  # 영수증 없음
            )
            db.add(email)
            created.append(email)
    
    try:
        # 이메일들 커밋 (영수증은 이미 커밋됨)
        db.commit()
        logger.info("Created %d dummy consent emails (with receipts: %d)", len(created), len([e for e in created if e.receipt_id]))
        if receipt_errors:
            logger.warning("Receipt creation errors: %s", "; ".join(receipt_errors))
        
        # 생성된 영수증 ID 확인
        from app.a.models.receipt import ReceiptModel
        for email in created:
            if email.receipt_id:
                verify = db.query(ReceiptModel).filter(ReceiptModel.id == email.receipt_id).first()
                if verify:
                    logger.info("Verified receipt %s exists in database", email.receipt_id)
                else:
                    logger.error("Receipt %s NOT found in database after commit!", email.receipt_id)
    except Exception as e:
        logger.error("Failed to commit dummy emails: %s", e, exc_info=True)
        db.rollback()
        raise
    
    return created

