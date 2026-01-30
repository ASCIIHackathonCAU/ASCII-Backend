"""
receiptos-contracts — Canonical JSON schemas for the ReceiptOS pipeline.

All pipeline stages produce and consume these Pydantic v2 models.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------

class Evidence(BaseModel):
    """A verbatim quote from the source text that supports a claim."""
    quote: str = Field(..., description="Exact snippet from the document")
    location: str = Field(..., description="e.g. 'line 5' or 'lines 5-7'")


class ExtractedField(BaseModel):
    """A single extracted field with its value and supporting evidence."""
    value: str | list[str] = Field(..., description="Extracted value(s)")
    evidence: list[Evidence] = Field(default_factory=list)


class Signal(BaseModel):
    """A risk signal produced by deterministic rules."""
    signal_id: str
    severity: str = Field(..., description="high | medium | low")
    title: str
    description: str
    evidence: list[Evidence] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Extract result (pipeline output before receipt)
# ---------------------------------------------------------------------------

class ExtractResult(BaseModel):
    document_type: str = Field(
        ..., description="consent | change | marketing | third_party | unknown"
    )
    document_type_evidence: list[Evidence] = Field(default_factory=list)
    fields: dict[str, ExtractedField] = Field(default_factory=dict)
    signals: list[Signal] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Receipt card
# ---------------------------------------------------------------------------

class SevenLines(BaseModel):
    """Seven‑line summary card — one line per key dimension."""
    who: str = ""
    what: str = ""
    why: str = ""
    when: str = ""
    where: str = ""
    how_to_revoke: str = ""
    risk_summary: str = ""


class Action(BaseModel):
    """A suggested next‑step the user can take."""
    action_type: str
    label: str
    description: str


class Receipt(BaseModel):
    receipt_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    source_type: str = ""
    document_type: str = ""
    seven_lines: SevenLines = Field(default_factory=SevenLines)
    signals: list[Signal] = Field(default_factory=list)
    fields: dict[str, ExtractedField] = Field(default_factory=dict)
    content_hash: str = ""
    actions: list[Action] = Field(default_factory=list)
    required_items: list[str] = Field(default_factory=list)
    optional_items: list[str] = Field(default_factory=list)
    over_collection: bool = False
    over_collection_reasons: list[str] = Field(default_factory=list)
    transfers: list[dict] = Field(
        default_factory=list,
        description=(
            "List of data transfer destinations with type labels "
            "(third_party | outsourcing | overseas) and data_items"
        ),
    )


# ---------------------------------------------------------------------------
# API request / response envelopes
# ---------------------------------------------------------------------------

class IngestRequest(BaseModel):
    raw_text: str
    source_type: str = "other"
    metadata: Optional[dict] = None


class IngestResponse(BaseModel):
    receipt: Receipt
    extract_result: ExtractResult


class DiffChange(BaseModel):
    field: str
    change_type: str  # added | removed | modified
    old_value: Optional[str | list[str]] = None
    new_value: Optional[str | list[str]] = None
    evidence_a: list[Evidence] = Field(default_factory=list)
    evidence_b: list[Evidence] = Field(default_factory=list)


class DiffResult(BaseModel):
    diff_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    receipt_a_id: Optional[str] = None
    receipt_b_id: Optional[str] = None
    changes: list[DiffChange] = Field(default_factory=list)
    new_signals: list[Signal] = Field(default_factory=list)
    resolved_signals: list[Signal] = Field(default_factory=list)


class DiffRequest(BaseModel):
    receipt_id_a: Optional[str] = None
    raw_text_a: Optional[str] = None
    receipt_id_b: Optional[str] = None
    raw_text_b: Optional[str] = None


