"""
Receipt builder — seven‑line summary card + suggested actions.
"""
from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, timezone

from app.a.schemas import (
    Action,
    ExtractedField,
    Receipt,
    SevenLines,
    Signal,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _field_summary(field: ExtractedField | None, max_items: int = 5) -> str:
    if field is None:
        return "명시되지 않음"
    if isinstance(field.value, list):
        items = field.value[:max_items]
        suffix = f" 외 {len(field.value) - max_items}건" if len(field.value) > max_items else ""
        return ", ".join(items) + suffix
    return field.value if field.value else "명시되지 않음"


def _risk_summary(signals: list[Signal]) -> str:
    if not signals:
        return "특이 위험 신호 없음"
    high = sum(1 for s in signals if s.severity == "high")
    medium = sum(1 for s in signals if s.severity == "medium")
    parts: list[str] = []
    if high:
        parts.append(f"높음 {high}건")
    if medium:
        parts.append(f"중간 {medium}건")
    titles = [s.title for s in signals[:3]]
    return f"위험 신호 {', '.join(parts)}: {'; '.join(titles)}"


_ENTITY_PATTERNS = [
    re.compile(r"(?:주식회사|㈜|\(주\))\s*([가-힣A-Za-z0-9]+)"),
    re.compile(r"([가-힣]{2,10}(?:은행|카드|보험|증권|캐피탈|저축은행))"),
    re.compile(r"([가-힣A-Za-z]{2,20})\s*(?:이하|에서|은\s|는\s)"),
]


def _detect_entity(raw_text: str) -> str:
    for pat in _ENTITY_PATTERNS:
        m = pat.search(raw_text)
        if m:
            return m.group(1) or m.group(0)
    return "명시되지 않음"


# ---------------------------------------------------------------------------
# Seven lines
# ---------------------------------------------------------------------------

def build_seven_lines(
    fields: dict[str, ExtractedField],
    signals: list[Signal],
    raw_text: str,
) -> SevenLines:
    return SevenLines(
        who=_detect_entity(raw_text),
        what=_field_summary(fields.get("data_collected")),
        why=_field_summary(fields.get("purposes")),
        when=_field_summary(fields.get("retention")),
        where=_field_summary(fields.get("third_party"), max_items=3),
        how_to_revoke=_field_summary(fields.get("revoke_path")),
        risk_summary=_risk_summary(signals),
    )


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

def _suggest_actions(
    signals: list[Signal], fields: dict[str, ExtractedField]
) -> list[Action]:
    actions: list[Action] = [
        Action(
            action_type="withdraw_consent",
            label="동의 철회 요청서 작성",
            description="이 동의에 대한 철회 요청서를 자동 생성합니다.",
        ),
    ]
    sig_ids = {s.signal_id for s in signals}
    if "third_party_present" in sig_ids or "vague_third_party_language" in sig_ids:
        actions.append(
            Action(
                action_type="stop_third_party",
                label="제3자 제공 중단 요청",
                description="제3자 제공 중단을 요청하는 서한을 작성합니다.",
            )
        )
    actions.append(
        Action(
            action_type="delete_data",
            label="개인정보 삭제 요청",
            description="수집된 개인정보의 삭제를 요청합니다.",
        )
    )
    return actions


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_receipt(
    raw_text: str,
    source_type: str,
    document_type: str,
    fields: dict[str, ExtractedField],
    signals: list[Signal],
) -> Receipt:
    content_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
    return Receipt(
        receipt_id=str(uuid.uuid4()),
        created_at=datetime.now(timezone.utc).isoformat(),
        source_type=source_type,
        document_type=document_type,
        seven_lines=build_seven_lines(fields, signals, raw_text),
        signals=signals,
        fields=fields,
        content_hash=content_hash,
        actions=_suggest_actions(signals, fields),
    )
