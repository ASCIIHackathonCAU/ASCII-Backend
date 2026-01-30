"""
Receipt builder – seven-line summary card + suggested actions.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Iterable

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

def _as_list(field: ExtractedField | None) -> list[str]:
    if field is None:
        return []
    if isinstance(field.value, list):
        return [str(v).strip() for v in field.value if str(v).strip()]
    if isinstance(field.value, str) and field.value.strip():
        return [field.value.strip()]
    return []


def _field_summary(values: Iterable[str], fallback: str = "미기재", max_items: int = 5) -> str:
    values = [v for v in values if v]
    if not values:
        return fallback
    items = list(values)[:max_items]
    suffix = f" 외 {len(values) - max_items}개" if len(values) > max_items else ""
    return ", ".join(items) + suffix


def _risk_summary(signals: list[Signal]) -> str:
    if not signals:
        return "추가 위험 신호 없음"
    high = sum(1 for s in signals if s.severity == "high")
    medium = sum(1 for s in signals if s.severity == "medium")
    parts: list[str] = []
    if high:
        parts.append(f"고위험 {high}건")
    if medium:
        parts.append(f"중위험 {medium}건")
    titles = [s.title for s in signals[:3]]
    return f"위험 신호 {', '.join(parts)}: {'; '.join(titles)}"


def _detect_entity(raw_text: str) -> str:
    # Very lightweight heuristic for issuer detection
    for line in raw_text.splitlines():
        if "주식회사" in line or "회사" in line or "기관" in line:
            return line.strip()[:80]
    return "발급 기관 미기재"


def _build_transfers(
    fields: dict[str, ExtractedField], data_items: list[str]
) -> list[dict]:
    transfers: list[dict] = []

    def add_transfer(field: ExtractedField | None, ttype: str, overseas: bool = False):
        for dest in _as_list(field):
            transfers.append(
                {
                    "type": ttype,
                    "destination": dest,
                    "is_overseas": overseas,
                    "data_items": data_items,
                }
            )

    add_transfer(fields.get("third_party"), "third_party", False)
    add_transfer(fields.get("outsourcing"), "outsourcing", False)
    add_transfer(fields.get("overseas_transfer"), "overseas", True)
    add_transfer(fields.get("data_transfers"), "transfer", False)
    return transfers


# ---------------------------------------------------------------------------
# Seven lines
# ---------------------------------------------------------------------------

def build_seven_lines(
    fields: dict[str, ExtractedField],
    signals: list[Signal],
    raw_text: str,
) -> SevenLines:
    required_items = _as_list(fields.get("required_items"))
    optional_items = _as_list(fields.get("optional_items"))
    collected = _as_list(fields.get("data_collected"))
    data_for_summary = required_items or collected or optional_items
    transfers = _as_list(fields.get("third_party")) + _as_list(fields.get("overseas_transfer"))

    return SevenLines(
        who=_detect_entity(raw_text),
        what=_field_summary(data_for_summary, fallback="수집 항목 미기재"),
        why=_field_summary(_as_list(fields.get("purposes")), fallback="목적 미기재"),
        when=_field_summary(_as_list(fields.get("retention")), fallback="보유기간 미기재"),
        where=_field_summary(transfers, fallback="제3자/이전 없음", max_items=3),
        how_to_revoke=_field_summary(_as_list(fields.get("revoke_path")), fallback="철회 경로 미기재"),
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
            label="마케팅 수신 거부",
            description="필요시 마케팅/광고 동의를 철회하세요.",
        ),
    ]
    sig_ids = {s.signal_id for s in signals}
    if {"third_party_present", "vague_third_party_language"} & sig_ids:
        actions.append(
            Action(
                action_type="stop_third_party",
                label="제3자 제공 중단 요청",
                description="제3자 제공 범위가 넓거나 모호할 때 중단을 요청합니다.",
            )
        )
    actions.append(
        Action(
            action_type="delete_data",
            label="개인정보 삭제 요청",
            description="수집 목적이 끝났거나 과잉 수집 시 삭제를 요청합니다.",
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

    required_items = _as_list(fields.get("required_items"))
    optional_items = _as_list(fields.get("optional_items"))
    collected = _as_list(fields.get("data_collected"))
    data_items = required_items or collected
    if optional_items:
        data_items = data_items + [f"(선택) {item}" for item in optional_items]

    transfers = _build_transfers(fields, data_items)

    over_signals = [s for s in signals if s.signal_id == "over_collection_risk"]
    over_collection = len(over_signals) > 0
    over_reasons = [s.title for s in over_signals] or []

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
        required_items=required_items,
        optional_items=optional_items,
        over_collection=over_collection,
        over_collection_reasons=over_reasons,
        transfers=transfers,
    )

