"""
Rule‑based document‑type classifier.

Scores each candidate type by keyword hits and returns the best match.
Every determination is backed by evidence spans.
"""
from __future__ import annotations

import re

from app.a.schemas import Evidence

# (regex pattern, weight)
DOC_TYPE_KEYWORDS: dict[str, list[tuple[str, int]]] = {
    "consent": [
        (r"동의서", 3),
        (r"개인정보\s*수집", 2),
        (r"개인정보.{0,5}이용", 2),
        (r"수집.{0,3}이용.{0,3}동의", 3),
        (r"동의합니다", 2),
        (r"동의\s*여부", 2),
        (r"필수\s*동의", 2),
        (r"선택\s*동의", 1),
    ],
    "change": [
        (r"변경\s*(사항|안내|내용)", 3),
        (r"개정\s*(사항|안내|내용)", 3),
        (r"업데이트", 2),
        (r"기존.{0,10}변경", 2),
        (r"신규\s*추가", 2),
        (r"정책\s*변경", 3),
    ],
    "marketing": [
        (r"마케팅", 3),
        (r"홍보", 2),
        (r"프로모션", 2),
        (r"광고", 2),
        (r"수신\s*동의", 3),
        (r"뉴스레터", 2),
        (r"이벤트\s*안내", 2),
    ],
    "third_party": [
        (r"제3자\s*제공", 3),
        (r"제삼자", 2),
        (r"개인정보.{0,5}제공", 2),
        (r"업무\s*위탁", 3),
        (r"처리\s*위탁", 3),
    ],
}

MIN_SCORE = 2


def classify(text: str) -> tuple[str, list[Evidence]]:
    """Return ``(doc_type, evidence_list)``."""
    lines = text.split("\n")
    scores: dict[str, float] = {dt: 0 for dt in DOC_TYPE_KEYWORDS}
    evidence_map: dict[str, list[Evidence]] = {dt: [] for dt in DOC_TYPE_KEYWORDS}

    for doc_type, patterns in DOC_TYPE_KEYWORDS.items():
        for pattern, weight in patterns:
            for line_num, line in enumerate(lines, 1):
                if re.search(pattern, line, re.IGNORECASE):
                    scores[doc_type] += weight
                    evidence_map[doc_type].append(
                        Evidence(quote=line.strip(), location=f"line {line_num}")
                    )
                    break  # one hit per pattern is enough

    best = max(scores, key=lambda k: scores[k])
    if scores[best] < MIN_SCORE:
        return "unknown", []

    # deduplicate evidence, keep first 3
    seen: set[str] = set()
    unique: list[Evidence] = []
    for ev in evidence_map[best]:
        if ev.quote not in seen:
            seen.add(ev.quote)
            unique.append(ev)
    return best, unique[:3]
