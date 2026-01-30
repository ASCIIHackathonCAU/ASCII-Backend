"""
Rule‑based field extractor (structurer).

Scans Korean privacy / consent documents for standard sections and
extracts structured fields with evidence spans.
"""
from __future__ import annotations

import re
from typing import Any

from app.a.schemas import Evidence, ExtractedField

# ---------------------------------------------------------------------------
# Per‑field configuration
# ---------------------------------------------------------------------------

FIELD_CONFIGS: dict[str, dict[str, Any]] = {
    "data_collected": {
        "triggers": [
            r"수집.{0,5}항목",
            r"수집하는\s*개인정보",
            r"개인정보\s*항목",
            r"수집.{0,5}정보",
            r"처리하는.{0,5}개인정보",
        ],
    },
    "purposes": {
        "triggers": [
            r"이용\s*목적",
            r"수집.{0,5}목적",
            r"처리\s*목적",
            r"개인정보.{0,5}목적",
            r"목적.{0,5}이용",
        ],
    },
    "retention": {
        "triggers": [
            r"보유.{0,5}기간",
            r"보관.{0,5}기간",
            r"이용\s*기간",
            r"보존.{0,5}기간",
            r"보유.{0,5}이용\s*기간",
        ],
    },
    "third_party": {
        "triggers": [
            r"제3자\s*제공",
            r"제삼자",
            r"개인정보.{0,5}제공",
            r"위탁",
            r"제공받는\s*자",
        ],
    },
    "overseas_transfer": {
        "triggers": [
            r"국외\s*이전",
            r"해외\s*이전",
            r"국외\s*제공",
            r"해외\s*서버",
            r"국외\s*보관",
        ],
    },
    "revoke_path": {
        "triggers": [
            r"동의\s*철회",
            r"철회",
            r"거부.{0,5}권리",
            r"삭제\s*요청",
            r"파기\s*요청",
            r"동의\s*거부",
        ],
    },
}

# All trigger regexes flattened (used to detect section boundaries)
_ALL_TRIGGERS: list[re.Pattern[str]] = []
for _cfg in FIELD_CONFIGS.values():
    for _pat in _cfg["triggers"]:
        _ALL_TRIGGERS.append(re.compile(_pat, re.IGNORECASE))


def _is_section_boundary(line: str, current_field: str) -> bool:
    """Return True if *line* starts a section belonging to a different field."""
    for other_field, cfg in FIELD_CONFIGS.items():
        if other_field == current_field:
            continue
        for pat in cfg["triggers"]:
            if re.search(pat, line, re.IGNORECASE):
                return True
    return False


# ---------------------------------------------------------------------------
# Section finder
# ---------------------------------------------------------------------------

def _find_sections(
    lines: list[str], field_name: str, config: dict
) -> list[dict]:
    """Return list of ``{text, start_line, end_line}``."""
    sections: list[dict] = []
    used_starts: set[int] = set()

    for trigger in config["triggers"]:
        for idx, line in enumerate(lines):
            if idx in used_starts:
                continue
            if not re.search(trigger, line, re.IGNORECASE):
                continue

            start = idx
            end = start + 1
            consecutive_empty = 0

            while end < len(lines):
                stripped = lines[end].strip()
                if not stripped:
                    consecutive_empty += 1
                    if consecutive_empty >= 2:
                        break
                    end += 1
                    continue
                consecutive_empty = 0
                if _is_section_boundary(stripped, field_name):
                    break
                end += 1

            block = "\n".join(l.strip() for l in lines[start:end] if l.strip())
            if block:
                sections.append(
                    {"text": block, "start_line": start + 1, "end_line": end}
                )
                used_starts.add(start)
            break  # first match per trigger

    return sections


# ---------------------------------------------------------------------------
# Value parser helpers
# ---------------------------------------------------------------------------

_LIST_SEP = re.compile(r"[,，、·\n]")
_BULLET = re.compile(r"^[\-·•■□●○▶▷]\s*")
_NUM_PREFIX = re.compile(r"^\d+[.\)]\s*")


def _extract_list_items(text: str) -> list[str]:
    """Split a text block into individual items."""
    items = _LIST_SEP.split(text)
    cleaned: list[str] = []
    for item in items:
        item = _BULLET.sub("", item.strip())
        item = _NUM_PREFIX.sub("", item).strip()
        if item and len(item) > 1:
            cleaned.append(item)
    return cleaned if cleaned else [text.strip()]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_fields(text: str) -> dict[str, ExtractedField]:
    """Extract all canonical fields from *text*. Each field carries evidence."""
    lines = text.split("\n")
    fields: dict[str, ExtractedField] = {}

    for field_name, config in FIELD_CONFIGS.items():
        sections = _find_sections(lines, field_name, config)
        if not sections:
            continue

        merged = "\n".join(s["text"] for s in sections)

        # Choose list vs scalar representation
        if field_name in ("data_collected", "purposes", "third_party"):
            value: str | list[str] = _extract_list_items(merged)
        else:
            value = merged.strip()

        # Build evidence entries (max 3)
        evidence: list[Evidence] = []
        for sec in sections[:3]:
            quote_lines = sec["text"].split("\n")
            quote = " ".join(quote_lines[:3])
            if len(quote) > 200:
                quote = quote[:200] + "…"
            loc = (
                f"line {sec['start_line']}"
                if sec["end_line"] <= sec["start_line"] + 1
                else f"lines {sec['start_line']}-{sec['end_line']}"
            )
            evidence.append(Evidence(quote=quote, location=loc))

        fields[field_name] = ExtractedField(value=value, evidence=evidence)

    return fields
