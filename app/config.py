"""
통합 애플리케이션 설정
"""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Backend-A 데이터베이스
    DATABASE_URL_A: str = "sqlite:///./data/ascii_a.db"
    
    # Backend-B 데이터베이스
    DATABASE_URL_B: str = "sqlite:///./data/ascii_b.db"
    
    # Redis (Backend-A 선택)
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # 보안
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # 환경
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]
    
    # 파일 저장
    DATA_DIR: str = "./data"
    UPLOAD_DIR: str = "./data/uploads"
    RECEIPTS_DIR: str = "./data/receipts"
    LETTERS_DIR: str = "./data/letters"
    EVIDENCE_PACKS_DIR: str = "./data/evidence_packs"
    
    # LLM (선택)
    LLM_PROVIDER: str = "openai"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

