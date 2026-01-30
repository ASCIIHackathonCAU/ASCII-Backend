"""
ReceiptOS Backend — FastAPI application entry‑point.
"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.a.database import Base as BaseA, engine as engine_a
from app.b.database import Base as BaseB, engine as engine_b

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-30s  %(levelname)-5s  %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure data dir + tables exist
    os.makedirs(settings.DATA_DIR, exist_ok=True)
    # Import models so Base.metadata knows about them
    import app.a.models  # noqa: F401
    import app.b.models  # noqa: F401
    BaseA.metadata.create_all(bind=engine_a)
    BaseB.metadata.create_all(bind=engine_b)
    logger.info("Database tables ready (A: %s, B: %s)", settings.DATABASE_URL_A, settings.DATABASE_URL_B)
    
    # 더미 데이터 초기화 (선택적)
    try:
        from app.a.database import SessionLocal as SessionLocalA
        from app.a.models.email_account import EmailAccountModel
        db_a = SessionLocalA()
        try:
            account_count = db_a.query(EmailAccountModel).filter(EmailAccountModel.is_active == True).count()
            if account_count == 0:
                logger.info("No email accounts found, creating dummy accounts on startup...")
                from app.a.routers.email import create_dummy_accounts
                create_dummy_accounts(db_a)
                logger.info("Dummy email accounts created successfully")
        finally:
            db_a.close()
    except Exception as e:
        logger.warning("Failed to initialize dummy data on startup: %s", e)
    
    yield
    logger.info("Shutting down")


app = FastAPI(
    title="ReceiptOS",
    description="Consent document → structured extraction → receipt card → diff",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"service": "ReceiptOS", "version": "0.1.0", "status": "running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# ── Register API router ──────────────────────────────────────────────────
from app.a.routers.receipts import router as receipts_router  # noqa: E402
from app.a.routers.cookies import router as cookies_router  # noqa: E402
from app.a.routers.email import router as email_router  # noqa: E402
from app.b.routers.revocation import router as revocation_router  # noqa: E402

app.include_router(receipts_router, prefix="/api", tags=["ReceiptOS"])
app.include_router(cookies_router, prefix="/api", tags=["Cookie Receipts"])
app.include_router(email_router, prefix="/api", tags=["Email Integration"])
app.include_router(revocation_router, prefix="/api", tags=["Revocation Requests"])
