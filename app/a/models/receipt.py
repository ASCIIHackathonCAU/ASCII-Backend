"""
SQLAlchemy model for receipt persistence.
"""
from sqlalchemy import Column, String, Text, JSON, Integer

from app.a.database import Base


class ReceiptModel(Base):
    __tablename__ = "receipts"

    id = Column(String, primary_key=True)
    created_at = Column(String, nullable=False)
    source_type = Column(String, nullable=False, default="other")
    document_type = Column(String, nullable=False, default="unknown")
    raw_text = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=False)
    extract_result_json = Column(JSON, nullable=False)
    receipt_json = Column(JSON, nullable=False)

