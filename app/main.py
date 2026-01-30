"""
ASCII Backend: 통합 FastAPI 애플리케이션
Backend-A와 Backend-B 모듈을 포함하는 단일 애플리케이션
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings

app = FastAPI(
    title="ASCII Backend",
    description="Consent & Request Receipt Inbox + Eraser & Revocation Concierge API",
    version="0.1.0",
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {
        "message": "ASCII Backend API",
        "version": "0.1.0",
        "status": "running",
        "modules": {
            "a": "Consent & Request Receipt Inbox",
            "b": "Eraser & Revocation Concierge"
        }
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# Backend-A 라우터 등록
# from app.a.routers import ingest, analyze, documents
# app.include_router(ingest.router, prefix="/api/a/ingest", tags=["Backend-A: Ingest"])
# app.include_router(analyze.router, prefix="/api/a/analyze", tags=["Backend-A: Analyze"])
# app.include_router(documents.router, prefix="/api/a/documents", tags=["Backend-A: Documents"])

# Backend-B 라우터 등록
# from app.b.routers import revocations, routing, letters, evidence
# app.include_router(revocations.router, prefix="/api/b/revocations", tags=["Backend-B: Revocations"])
# app.include_router(routing.router, prefix="/api/b/routing", tags=["Backend-B: Routing"])
# app.include_router(letters.router, prefix="/api/b/letters", tags=["Backend-B: Letters"])
# app.include_router(evidence.router, prefix="/api/b/evidence", tags=["Backend-B: Evidence"])

