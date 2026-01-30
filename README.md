# ASCII Backend

ASCII 해커톤 백엔드 레포지토리입니다. Backend-A와 Backend-B 모듈을 포함하는 통합 프로젝트입니다.

## 프로젝트 구조

```
ASCII-Backend/
├── app/                     # 통합 FastAPI 애플리케이션
│   ├── __init__.py
│   ├── main.py             # 통합 FastAPI 앱 진입점 (단일 실행)
│   ├── config.py           # 통합 설정 관리
│   ├── a/                  # Backend-A: Consent & Request Receipt Inbox 모듈
│   │   ├── __init__.py
│   │   ├── database.py     # Backend-A DB 연결
│   │   ├── models/         # 데이터베이스 모델
│   │   ├── routers/        # API 라우터
│   │   ├── services/       # 비즈니스 로직
│   │   └── utils/          # 모듈별 유틸리티 함수
│   ├── b/                  # Backend-B: Eraser & Revocation Concierge 모듈
│   │   ├── __init__.py
│   │   ├── database.py     # Backend-B DB 연결
│   │   ├── models/         # 데이터베이스 모델
│   │   ├── routers/        # API 라우터
│   │   ├── services/       # 비즈니스 로직
│   │   └── utils/          # 모듈별 유틸리티 함수
│   └── utils/              # 공통 유틸리티 함수
├── alembic/                 # DB 마이그레이션
├── data/                    # 데이터 저장 디렉토리
├── tests/                   # 테스트 코드
├── requirements.txt        # Python 의존성 (통합)
├── Dockerfile              # Docker 이미지 정의
├── docker-compose.yml      # Docker Compose 설정
├── env.example             # 환경 변수 예시
└── README.md              # 이 파일
```

## 모듈 개요

### Backend-A: Consent & Request Receipt Inbox
- 동의서 텍스트/PDF 업로드 및 분석
- 문자/카톡/이메일 내용 수집
- 요청 영수증 검증 (QR/서명 토큰/6자리 코드)
- LLM 기반 요약 카드 생성
- 위험 신호 감지
- 영수증 해시 생성 및 무결성 검증

**API 경로**: `/api/a/*`

### Backend-B: Eraser & Revocation Concierge
- 삭제/철회 요청서 자동 생성 (템플릿 기반)
- 기관별 처리 경로 라우팅 (프리셋 + LLM 추출)
- 진행상태 트래킹 (CREATED → SENT → WAITING → DONE 등)
- 증빙 패키지 생성 (ZIP, CSV)
- 요청서 PDF 생성 및 다운로드

**API 경로**: `/api/b/*`

## 설치 및 실행

### 1. 가상환경 설정 (로컬 개발)

```bash
# 가상환경 생성
python -m venv venv

# 가상환경 활성화
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 의존성 설치
pip install -r requirements.txt
```

### 2. 환경 변수 설정

```bash
# env.example을 복사하여 .env 파일 생성
cp env.example .env

# .env 파일을 편집하여 필요한 설정 입력
```

### 3. 데이터베이스 초기화

```bash
# Alembic 마이그레이션 실행 (각 모듈별로)
# Backend-A
alembic -x module=a upgrade head

# Backend-B
alembic -x module=b upgrade head
```

### 4. 로컬 실행

```bash
# 개발 서버 실행 (단일 프로세스로 두 모듈 모두 실행)
uvicorn app.main:app --reload --port 8000

# 또는
python -m uvicorn app.main:app --reload --port 8000
```

서버는 `http://localhost:8000`에서 실행되며, Backend-A와 Backend-B의 모든 API가 동일한 포트에서 제공됩니다.

#### Docker Compose 사용 (권장)

```bash
# 모든 서비스 시작
docker-compose up -d

# 로그 확인
docker-compose logs -f backend

# 서비스 중지
docker-compose down

# 볼륨까지 삭제
docker-compose down -v
```

## API 엔드포인트

모든 API는 `http://localhost:8000`에서 제공됩니다.

### 공통 엔드포인트

- `GET /` - 루트 엔드포인트 (모듈 정보 포함)
- `GET /health` - 헬스 체크

### Backend-A API (`/api/a/*`)

- `POST /api/a/ingest/text` - 텍스트 업로드
- `POST /api/a/ingest/pdf` - PDF 업로드
- `POST /api/a/ingest/email/pull` - 이메일 가져오기
- `POST /api/a/ingest/receipt-code/verify` - 영수증 코드 검증
- `POST /api/a/analyze/{doc_id}` - 문서 분석 실행
- `GET /api/a/documents` - 문서 목록 조회
- `GET /api/a/documents/{doc_id}` - 문서 상세 조회
- `GET /api/a/documents/{doc_id}/card` - 요약 카드 조회
- `GET /api/a/documents/{doc_id}/receipt` - 영수증 조회

### Backend-B API (`/api/b/*`)

- `POST /api/b/revocations` - 새 요청 생성
- `GET /api/b/revocations` - 요청 목록 조회
- `GET /api/b/revocations/{id}` - 요청 상세 조회
- `POST /api/b/revocations/{id}/route` - 라우팅 재계산
- `GET /api/b/routing/presets` - 프리셋 목록 조회
- `POST /api/b/revocations/{id}/letter` - 요청서 생성/재생성
- `GET /api/b/revocations/{id}/letter` - 요청서 텍스트 조회
- `GET /api/b/revocations/{id}/letter.pdf` - 요청서 PDF 다운로드
- `PATCH /api/b/revocations/{id}/status` - 상태 업데이트
- `GET /api/b/revocations/{id}/timeline` - 타임라인 조회
- `POST /api/b/revocations/{id}/evidence-pack` - 증빙 패키지 생성
- `GET /api/b/revocations/{id}/evidence-pack.zip` - 증빙 패키지 다운로드
- `GET /api/b/exports/revocations.csv` - CSV 내보내기

API 문서: `http://localhost:8000/docs`

## 개발 가이드

### 코드 포맷팅

```bash
# Black으로 코드 포맷팅
black app_a/ app_b/

# Flake8으로 린팅
flake8 app_a/ app_b/
```

### 테스트 실행

```bash
# 모든 테스트 실행
pytest

# 특정 모듈 테스트
pytest tests/test_a/
pytest tests/test_b/

# 커버리지 포함
pytest --cov=app_a --cov=app_b
```

### 데이터베이스 마이그레이션

```bash
# 새 마이그레이션 생성 (각 모듈별로)
# Backend-A용
alembic -x module=a revision --autogenerate -m "Backend-A: 설명"

# Backend-B용
alembic -x module=b revision --autogenerate -m "Backend-B: 설명"

# 마이그레이션 적용
alembic -x module=a upgrade head
alembic -x module=b upgrade head

# 마이그레이션 롤백
alembic -x module=a downgrade -1
alembic -x module=b downgrade -1
```

## 기술 스택

- **Framework**: FastAPI
- **Database**: PostgreSQL (개발 시 SQLite 가능)
- **Queue**: Redis + Celery (Backend-A 선택)
- **PDF 처리**: pypdf, pdfplumber (Backend-A)
- **PDF 생성**: WeasyPrint, ReportLab (Backend-B)
- **인증**: OAuth2, JWT

## 보안 고려사항

- 민감정보(주민번호/계좌/OTP)는 저장 시 마스킹/암호화 필수
- 영수증 해시는 canonical JSON 기반으로 생성 (재현 가능)
- OAuth 토큰은 최소 권한으로 요청하고 암호화 저장
- 모든 검증/해제/회수 액션은 감사 로그 기록
- 요청서에 주민번호/계좌/OTP 절대 포함 금지 (서버 검증)

## 문제 해결

### 포트 충돌
- 기본 포트 8000이 사용 중이면 `docker-compose.yml`에서 포트 변경
- 또는 환경 변수 `PORT`로 포트 지정

### 데이터베이스 연결 오류
- `.env` 파일의 `DATABASE_URL_A`, `DATABASE_URL_B` 확인
- PostgreSQL 실행 중인지 확인 (로컬 실행 시)
- Docker Compose 사용 시 `db` 서비스가 실행 중인지 확인

### WeasyPrint 설치 오류
- Docker 사용 시 시스템 라이브러리가 자동 설치됩니다
- 로컬 설치 시 시스템 패키지 관리자를 통해 필요한 라이브러리 설치 필요

## 라이선스

이 프로젝트는 해커톤용으로 개발되었습니다.
