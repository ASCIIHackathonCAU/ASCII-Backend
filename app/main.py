"""
ReceiptOS Backend — FastAPI application entry‑point.
"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.a.database import Base, engine

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
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables ready (%s)", settings.DATABASE_URL_A)
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

app.include_router(receipts_router, prefix="/api", tags=["ReceiptOS"])
app.include_router(cookies_router, prefix="/api", tags=["Cookie Receipts"])
