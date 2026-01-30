"""
Rule‑based risk signal detection.

Every signal is deterministic and carries evidence quotes.
"""
from __future__ import annotations

import re

from app.a.schemas import Evidence, ExtractedField, Signal


def _field_text(field: ExtractedField | None) -> str:
    if field is None:
        return ""
    return " ".join(field.value) if isinstance(field.value, list) else field.value


# ---------------------------------------------------------------------------
# Individual signal checkers
# ---------------------------------------------------------------------------

def check_revoke_path_missing(
    fields: dict[str, ExtractedField], text: str
) -> Signal | None:
    """HIGH — No revocation / withdrawal path found."""
    if "revoke_path" in fields and _field_text(fields["revoke_path"]):
        return None
    return Signal(
        signal_id="revoke_path_missing",
        severity="high",
        title="철회 경로 누락",
        description=(
            "동의 철회 방법이 문서에 명시되지 않았습니다. "
            "개인정보 보호법에 따라 철회 방법 고지는 의무입니다."
        ),
        evidence=[
            Evidence(
                quote="(문서 전체에서 철회/삭제/거부 관련 내용 없음)",
                location="전체 문서",
            )
        ],
    )


def check_third_party_present(
    fields: dict[str, ExtractedField], text: str
) -> Signal | None:
    """MEDIUM — Third‑party data sharing detected."""
    tp = fields.get("third_party")
    if not tp or not _field_text(tp):
        return None
    return Signal(
        signal_id="third_party_present",
        severity="medium",
        title="제3자 제공 포함",
        description="개인정보가 제3자에게 제공됩니다. 제공 대상과 목적을 확인하세요.",
        evidence=tp.evidence[:2],
    )


def check_retention_long(
    fields: dict[str, ExtractedField], text: str
) -> Signal | None:
    """HIGH — Retention >= 3 years, permanent, or unspecified."""
    ret = fields.get("retention")
    ret_text = _field_text(ret)

    if not ret_text:
        return Signal(
            signal_id="retention_long",
            severity="high",
            title="보관기간 미명시",
            description="보관기간이 문서에 명시되지 않았습니다.",
            evidence=[
                Evidence(
                    quote="(보관/보유 기간 관련 내용 없음)", location="전체 문서"
                )
            ],
        )

    if re.search(r"영구|제한\s*없|무기한|반영구", ret_text):
        return Signal(
            signal_id="retention_long",
            severity="high",
            title="영구/무기한 보관",
            description="개인정보를 영구 또는 무기한 보관한다고 명시되어 있습니다.",
            evidence=ret.evidence[:2] if ret else [],
        )

    m = re.search(r"(\d+)\s*년", ret_text)
    if m and int(m.group(1)) >= 3:
        years = m.group(1)
        return Signal(
            signal_id="retention_long",
            severity="high",
            title=f"장기 보관 ({years}년)",
            description=f"개인정보 보관기간이 {years}년으로 장기입니다.",
            evidence=ret.evidence[:2] if ret else [],
        )

    return None


def check_purpose_marketing(
    fields: dict[str, ExtractedField], text: str
) -> Signal | None:
    """MEDIUM — Purposes include marketing / advertising."""
    purposes_text = _field_text(fields.get("purposes"))
    marketing_kw = ["마케팅", "홍보", "프로모션", "광고", "이벤트 안내", "뉴스레터"]
    found = [kw for kw in marketing_kw if kw in purposes_text]

    if not found:
        # Fallback: scan raw text for marketing + purpose co‑occurrence
        for line_num, line in enumerate(text.split("\n"), 1):
            for kw in marketing_kw:
                if kw in line and "목적" in line:
                    return Signal(
                        signal_id="purpose_expanded_to_marketing",
                        severity="medium",
                        title="마케팅 목적 포함",
                        description="개인정보 이용 목적에 마케팅/홍보가 포함되어 있습니다.",
                        evidence=[
                            Evidence(quote=line.strip(), location=f"line {line_num}")
                        ],
                    )
        return None

    purposes = fields.get("purposes")
    return Signal(
        signal_id="purpose_expanded_to_marketing",
        severity="medium",
        title="마케팅 목적 포함",
        description=(
            f"개인정보 이용 목적에 마케팅/홍보가 포함되어 있습니다: {', '.join(found)}"
        ),
        evidence=purposes.evidence[:2] if purposes else [],
    )


def check_vague_third_party(
    fields: dict[str, ExtractedField], text: str
) -> Signal | None:
    """MEDIUM — Third‑party language uses vague/catch‑all wording."""
    tp = fields.get("third_party")
    tp_text = _field_text(tp)
    if not tp_text:
        return None

    vague_patterns = [
        r"등\s*(제3자|업체|기관|회사|제삼자)",
        r"관계사",
        r"제휴\s*업체",
        r"협력\s*(업체|사)",
        r"기타\s*(업체|기관|협력)",
        r"필요\s*시",
    ]
    found: list[str] = []
    for pat in vague_patterns:
        m = re.search(pat, tp_text)
        if m:
            found.append(m.group(0))

    if not found:
        return None

    return Signal(
        signal_id="vague_third_party_language",
        severity="medium",
        title="제3자 제공 대상 모호",
        description=f"제3자 제공 대상이 구체적이지 않습니다: {', '.join(found)}",
        evidence=tp.evidence[:2] if tp else [],
    )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

SIGNAL_CHECKS = [
    check_revoke_path_missing,
    check_third_party_present,
    check_retention_long,
    check_purpose_marketing,
    check_vague_third_party,
]


def detect_signals(
    fields: dict[str, ExtractedField], text: str
) -> list[Signal]:
    """Run every registered check and return the list of fired signals."""
    signals: list[Signal] = []
    for fn in SIGNAL_CHECKS:
        sig = fn(fields, text)
        if sig is not None:
            signals.append(sig)
    return signals
