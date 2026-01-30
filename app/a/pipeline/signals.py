"""
Rule-based risk signal detection.

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
    """HIGH – No revocation / withdrawal path found."""
    if "revoke_path" in fields and _field_text(fields["revoke_path"]):
        return None
    return Signal(
        signal_id="revoke_path_missing",
        severity="high",
        title="동의 철회 경로 없음",
        description=(
            "동의 철회/삭제/정정 절차가 문서에서 확인되지 않았습니다. "
            "개인정보 보호법상 열람·정정·삭제 요청 방법을 안내해야 합니다."
        ),
        evidence=[
            Evidence(
                quote="(문서 전체에서 철회/삭제/정정 안내 없음)",
                location="문서 전체",
            )
        ],
    )


def check_third_party_present(
    fields: dict[str, ExtractedField], text: str
) -> Signal | None:
    """MEDIUM – Third-party data sharing detected."""
    tp = fields.get("third_party")
    if not tp or not _field_text(tp):
        return None
    return Signal(
        signal_id="third_party_present",
        severity="medium",
        title="제3자 제공 포함",
        description="개인정보가 제3자에게 제공됩니다. 제공처와 항목을 확인하세요.",
        evidence=tp.evidence[:2],
    )


def check_retention_long_or_vague(
    fields: dict[str, ExtractedField], text: str
) -> Signal | None:
    """HIGH – Retention >= 3 years, permanent, or vague phrases."""
    ret = fields.get("retention")
    ret_text = _field_text(ret)

    if not ret_text:
        return Signal(
            signal_id="retention_missing",
            severity="high",
            title="보유 기간 없음",
            description="보유·이용 기간이 명시되지 않았습니다.",
            evidence=[
                Evidence(
                    quote="(보유/보관/파기 기간 미기재)", location="문서 전체"
                )
            ],
        )

    if re.search(r"무기한|영구|무한", ret_text):
        return Signal(
            signal_id="retention_long",
            severity="high",
            title="무기한 보유",
            description="개인정보를 무기한 또는 영구 보유한다고 기재되어 있습니다.",
            evidence=ret.evidence[:2] if ret else [],
        )

    if re.search(r"목적\s*달성\s*시|필요\s*시까지|서비스\s*제공\s*시까지", ret_text):
        return Signal(
            signal_id="retention_vague",
            severity="high",
            title="보유 기간 모호",
            description="보유 기간이 '목적 달성 시' 등 추상 표현으로 되어 있습니다.",
            evidence=ret.evidence[:2] if ret else [],
        )

    m_year = re.search(r"(\d+)\s*년", ret_text)
    m_month = re.search(r"(\d+)\s*개월", ret_text)
    if m_year and int(m_year.group(1)) >= 3:
        years = m_year.group(1)
        return Signal(
            signal_id="retention_long",
            severity="high",
            title=f"{years}년 이상 보유",
            description=f"개인정보 보유 기간이 {years}년 이상으로 기재되어 있습니다.",
            evidence=ret.evidence[:2] if ret else [],
        )
    if m_month and int(m_month.group(1)) >= 36:
        months = m_month.group(1)
        return Signal(
            signal_id="retention_long",
            severity="high",
            title=f"{months}개월 이상 보유",
            description=f"개인정보 보유 기간이 {months}개월 이상으로 기재되어 있습니다.",
            evidence=ret.evidence[:2] if ret else [],
        )

    return None


def check_purpose_marketing(
    fields: dict[str, ExtractedField], text: str
) -> Signal | None:
    """MEDIUM – Purposes include marketing / advertising."""
    purposes_text = _field_text(fields.get("purposes"))
    marketing_kw = ["마케팅", "광고", "프로모션", "캠페인", "뉴스레터"]
    found = [kw for kw in marketing_kw if kw in purposes_text]

    if not found:
        # Fallback: scan raw text for marketing + purpose co-occurrence
        for line_num, line in enumerate(text.split("\n"), 1):
            for kw in marketing_kw:
                if kw in line and "목적" in line:
                    return Signal(
                        signal_id="purpose_expanded_to_marketing",
                        severity="medium",
                        title="마케팅 목적 포함",
                        description="개인정보 이용 목적에 마케팅/광고가 포함되어 있습니다.",
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
            f"개인정보 이용 목적에 마케팅·광고가 포함되어 있습니다: {', '.join(found)}"
        ),
        evidence=purposes.evidence[:2] if purposes else [],
    )


def check_vague_third_party(
    fields: dict[str, ExtractedField], text: str
) -> Signal | None:
    """MEDIUM – Third-party language uses vague/catch-all wording."""
    tp = fields.get("third_party")
    tp_text = _field_text(tp)
    if not tp_text:
        return None

    vague_patterns = [
        r"등\s*제3자",
        r"관련\s*회사",
        r"제휴\s*업체",
        r"필요\s*범위",
        r"관계사",
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
        title="제3자 표현 모호",
        description=f"제3자 제공 표현이 모호합니다: {', '.join(found)}",
        evidence=tp.evidence[:2] if tp else [],
    )


def check_over_collection(
    fields: dict[str, ExtractedField], text: str
) -> Signal | None:
    """HIGH – Potential over-collection or sensitive identifiers."""
    sensitive_keywords = [
        "주민등록",
        "주민번호",
        "계좌",
        "신용카드",
        "여권",
        "운전면허",
        "위치정보",
        "건강",
        "병력",
        "생체",
        "지문",
        "얼굴",
        "망막",
        "OTP",
        "보안코드",
    ]

    candidates = [
        _field_text(fields.get("required_items")),
        _field_text(fields.get("optional_items")),
        _field_text(fields.get("data_collected")),
    ]
    text_blob = " ".join(candidates)
    hits = [kw for kw in sensitive_keywords if kw in text_blob]

    if not hits:
        return None

    evidence_field = (
        fields.get("required_items")
        or fields.get("optional_items")
        or fields.get("data_collected")
    )
    return Signal(
        signal_id="over_collection_risk",
        severity="high",
        title="과잉 수집 의심",
        description="필수 범위를 넘어서는 민감/고유식별 정보가 포함되어 있습니다.",
        evidence=evidence_field.evidence[:2] if evidence_field else [],
    )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

SIGNAL_CHECKS = [
    check_revoke_path_missing,
    check_third_party_present,
    check_retention_long_or_vague,
    check_purpose_marketing,
    check_vague_third_party,
    check_over_collection,
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

