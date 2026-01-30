"""
ReceiptOS core pipeline.

Orchestrates: classify → extract fields → detect signals → build receipt.
"""
import logging

from app.a.schemas import ExtractResult, Receipt
from app.a.pipeline.classifier import classify
from app.a.pipeline.structurer import extract_fields
from app.a.pipeline.signals import detect_signals
from app.a.pipeline.receipt_builder import build_receipt

logger = logging.getLogger(__name__)


def process_document(
    raw_text: str, source_type: str = "other"
) -> tuple[Receipt, ExtractResult]:
    """Run the full extraction pipeline on a document.

    Returns ``(receipt, extract_result)``.
    """
    logger.info("Pipeline start — classify")
    doc_type, doc_type_evidence = classify(raw_text)
    logger.info("Classified as: %s", doc_type)

    logger.info("Pipeline — extract fields")
    fields = extract_fields(raw_text)
    logger.info("Extracted %d fields", len(fields))

    logger.info("Pipeline — detect signals")
    signals = detect_signals(fields, raw_text)
    logger.info("Detected %d signals", len(signals))

    extract_result = ExtractResult(
        document_type=doc_type,
        document_type_evidence=doc_type_evidence,
        fields=fields,
        signals=signals,
    )

    logger.info("Pipeline — build receipt")
    receipt = build_receipt(
        raw_text=raw_text,
        source_type=source_type,
        document_type=doc_type,
        fields=fields,
        signals=signals,
    )
    logger.info("Receipt built: %s", receipt.receipt_id)
    return receipt, extract_result
