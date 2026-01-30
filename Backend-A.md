# BACKEND.md — Python Backend 설계 (FastAPI)

## 1) 목표
- 입력(텍스트/PDF/이메일/코드) → 분석(LLM) → 구조화 저장 → 영수증 해시 → 검증/잠금 → 알림/통계
- LLM은 교체 가능(지금은 LLM 더미/규칙 기반도 가능)

## 2) 기술 스택(권장)
- API: FastAPI
- DB: PostgreSQL (해커톤이면 SQLite로 시작 가능)
- Queue(선택): Redis + RQ / Celery (비동기 분석)
- Auth(선택): OAuth2 (Google/Microsoft 메일), 또는 IMAP 프록시 자격증명 보관
- PDF 텍스트 추출: pypdf / pdfplumber (OCR은 최후)
- Hash/서명: hashlib(SHA-256), PyNaCl 또는 jose(jwt) (서명 토큰)
- LLM 래퍼: 단일 인터페이스(예: `LLMClient.analyze(text)->AnalysisResult`)

## 3) 주요 도메인 모델
### 3.1 테이블(예시)
- users
- sources (email oauth, imap, upload)
- documents
  - id, user_id, source_id, doc_type, raw_text_ref, created_at
- analyses
  - doc_id, summary_json, risk_json, extracted_slots_json, model_meta
- receipts
  - receipt_id, doc_id, canonical_json, sha256_hash, created_at
- verifications
  - doc_id, method(qr|code), code_hash, status, verified_at
- notifications
  - user_id, doc_id, type, payload_json, status

> raw 원문은 저장하더라도: (1) 민감정보 마스킹 (2) at-rest 암호화 (3) 최소 보관 원칙

## 4) API 설계(최소)
### 4.1 Ingestion
- POST /ingest/text
  - { text, source_label }
- POST /ingest/pdf
  - multipart file
- POST /ingest/email/pull
  - OAuth 토큰 기반 IMAP fetch (또는 프록시)
- POST /ingest/receipt-code/verify
  - { doc_id, code6 | signed_token }

### 4.2 Analysis
- POST /analyze/{doc_id}
  - 분석 실행(동기/비동기)
- GET /documents
- GET /documents/{doc_id}
- GET /documents/{doc_id}/card
- GET /documents/{doc_id}/receipt
- GET /stats/overview

### 4.3 Guardrail / Lock
- GET /documents/{doc_id}/lock-state
- POST /documents/{doc_id}/unlock-request
  - 검증 성공해야 unlock=true

### 4.4 MyData(선택)
- GET /mydata/consents
- POST /mydata/revoke/{consent_id}

## 5) 분석 파이프라인(구현 순서)
1) `classify_doc(text) -> doc_type`
2) `extract_slots(text) -> extracted_slots_json (+evidence spans)`
3) `generate_summary_card(extracted_slots) -> summary_json`
4) `detect_risks(text, extracted_slots) -> risk_json`
5) `build_receipt(extracted_slots, meta) -> canonical_json`
6) `hash_receipt(canonical_json) -> sha256`
7) `evaluate_notifications(analysis) -> notifications`

## 6) 요청 검증(핵심)
### 6.1 데모 프로토콜
- 서버가 “기관 요청 영수증”을 발급한다고 가정(해커톤)
  - (A) QR: 서명 토큰(JWT/PASETO 등)에 doc_id + exp + issuer 포함
  - (B) 6자리 코드: 서버가 doc_id에 대해 code6 생성 → 저장(해시로) → 사용자 입력 검증

### 6.2 정책
- 검증 성공 전:
  - `lock_state.sensitive_input_locked = true`
- 검증 성공 후:
  - unlock 토글 + 로그 남김(누가/언제/어떤 방법)

## 7) LLM 인터페이스(교체 가능)
- `LLMClient.analyze(text) -> {doc_type, extracted_slots, summary_card, risk_flags}`
- 개발 초기엔 규칙 기반으로 대체 가능:
  - 키워드: “위탁/수탁/제3자/제공/보관기간/파기/철회/고객센터/OTP/계좌/주민번호”
  - 정규식 스팬 추출

## 8) 더미 메일 데이터(해커톤)
- fixtures/emails/*.eml
- fixtures/texts/*.txt
- fixtures/receipts/*.json (signed token 예시, code6 매핑)

## 9) 보안/프라이버시 체크리스트
- 민감정보 마스킹(저장 전)
- receipt hash는 원문이 아니라 canonical JSON 기반(재현 가능)
- OAuth 토큰은 최소 권한, 서버에서 암호화 저장
- 감사 로그(검증/해제/회수 액션)

## 10) 로컬 실행(예시)
- uvicorn app.main:app --reload
- alembic upgrade head
- pytest
