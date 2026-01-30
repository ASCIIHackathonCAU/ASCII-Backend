# BACKEND_B.md — Eraser & Revocation Concierge (Python/FastAPI)

## 1) 목표
- 삭제/철회 요청을 “작성→어디로→상태추적→증빙”까지 지원
- 시스템이 직접 삭제 권한이 없음을 전제로, 제출 가능한 산출물(PDF/텍스트/CSV) 제공

## 2) 기술 스택(권장)
- FastAPI + Pydantic
- DB: PostgreSQL (해커톤은 SQLite 가능)
- PDF 생성: WeasyPrint(HTML→PDF) 또는 reportlab
- 파일 저장: 로컬(/data) 또는 S3 호환
- LLM: 추출/문장 생성 보조(교체 가능)

## 3) 데이터 모델(핵심 테이블)
- revocation_requests
  - id, user_id, doc_id(optional), service_name, entity_name, entity_type
  - request_type, scope_json, routing_json, status, created_at, updated_at
- letters
  - id, request_id, subject, body_text, rendered_pdf_path(optional), created_at
- timelines
  - id, request_id, at, event(CREATED/SENT/WAITING/DONE/REJECTED/NEED_MORE_INFO), note
- evidence_packs
  - id, request_id, manifest_json, zip_path(optional), created_at
- routing_presets
  - key(service/entity), type, channels(email/url/etc), instructions_json, updated_at

> A 모듈 receipts/documents 테이블이 있다면 doc_id로 연결해서 “동의 영수증”을 증빙에 포함

## 4) 라우팅 설계(현실형)
### 4.1 프리셋 DB 우선
- 자주 나오는 기관/플랫폼(Top 10~20)에 대해:
  - email / webform url / 고객센터 경로 / 민원 채널
  - 제출 시 요구되는 최소 정보(계정 이메일 등)
- 프리셋 없으면:
  - LLM이 “문의/고객센터/개인정보” 키워드로 원문에서 채널 후보 추출(A 문서 분석 결과 활용)
  - 그래도 없으면 “사용자가 직접 확인해야 함”으로 표시

### 4.2 라우팅 결과 스키마
routing_json = {
  "primary_channel": "email|webform|civil_petition|call_center",
  "destination": "...",
  "instructions": ["..."],
  "confidence": 0~1,
  "source": "preset|extracted|manual"
}

## 5) 요청서(템플릿) 생성
### 5.1 템플릿 3종(최소)
- WITHDRAW_CONSENT: 동의 철회/마케팅 수신 거부
- DELETE: 개인정보 삭제 요청
- STOP_THIRD_PARTY: 제3자 제공/위탁 중단 요청(가능 범위 내)

### 5.2 생성 파이프라인
1) 입력 수집(서비스/요청유형/계정 식별자 최소)
2) 라우팅 결정(preset→extracted→manual)
3) 템플릿 렌더(placeholder 최소)
4) 산출물 생성:
   - body_text (복사/메일 발송용)
   - pdf (첨부용)
5) timeline event: CREATED

## 6) 상태 트래킹(중요 UX를 백엔드로 보장)
- PATCH /revocations/{id}/status
  - 사용자가 “보냈음” 체크하면 SENT로 변경 + 시간 기록
  - 답변 수신 시 WAITING→DONE/REJECTED/NEED_MORE_INFO로 전환

권장 이벤트:
- CREATED, EXPORTED, SENT, WAITING, DONE, REJECTED, NEED_MORE_INFO

## 7) 증빙 패키지(Evidence Pack)
### 7.1 구성
- receipt(있으면) + request letter + timeline + CSV 한 줄 요약
- manifest.json:
  - 포함 파일 목록, 해시, 생성 시각

### 7.2 내보내기
- ZIP 다운로드(해커톤이면 zip optional, 파일 링크만 제공해도 OK)
- CSV export:
  - GET /exports/revocations.csv?from=...&to=...

## 8) API 엔드포인트(제안)
### 8.1 생성/조회
- POST /revocations
- GET /revocations
- GET /revocations/{id}

### 8.2 라우팅
- POST /revocations/{id}/route (재계산)
- GET /routing/presets (관리자/디버그)

### 8.3 요청서 산출물
- POST /revocations/{id}/letter (템플릿 생성/재생성)
- GET /revocations/{id}/letter (텍스트)
- GET /revocations/{id}/letter.pdf

### 8.4 상태/타임라인
- PATCH /revocations/{id}/status
- GET /revocations/{id}/timeline

### 8.5 증빙/내보내기
- POST /revocations/{id}/evidence-pack
- GET /revocations/{id}/evidence-pack.zip
- GET /exports/revocations.csv

## 9) 프라이버시/보안
- 요청서에 주민번호/계좌/OTP 절대 넣지 않도록 가드(서버 검증)
- 원문/첨부 파일은 필요 최소 기간만 저장(해커톤은 TTL 배치)
- 다운로드 링크는 서명 URL 또는 단기 토큰

## 10) 더미 데이터(해커톤)
- routing_presets: 네이버/카카오/통신사/금융 등 예시 10개
- revocation_requests 더미 20개(상태 다양화)
