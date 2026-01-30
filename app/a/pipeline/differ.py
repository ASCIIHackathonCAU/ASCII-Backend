"""
Diff engine — field‑by‑field comparison of two extract results.
"""
from __future__ import annotations

import uuid

from app.a.schemas import (
    DiffChange,
    DiffResult,
    ExtractedField,
    Signal,
)


def _values_equal(a: str | list[str], b: str | list[str]) -> bool:
    if isinstance(a, list) and isinstance(b, list):
        return sorted(a) == sorted(b)
    return str(a) == str(b)


def diff_extract_results(
    result_a: dict[str, ExtractedField],
    result_b: dict[str, ExtractedField],
    signals_a: list[Signal],
    signals_b: list[Signal],
    receipt_a_id: str | None = None,
    receipt_b_id: str | None = None,
) -> DiffResult:
    """Compare two sets of extracted fields and signals."""
    changes: list[DiffChange] = []
    all_fields = sorted(set(list(result_a.keys()) + list(result_b.keys())))

    for field_name in all_fields:
        fa = result_a.get(field_name)
        fb = result_b.get(field_name)

        if fa and not fb:
            changes.append(
                DiffChange(
                    field=field_name,
                    change_type="removed",
                    old_value=fa.value,
                    new_value=None,
                    evidence_a=fa.evidence,
                    evidence_b=[],
                )
            )
        elif fb and not fa:
            changes.append(
                DiffChange(
                    field=field_name,
                    change_type="added",
                    old_value=None,
                    new_value=fb.value,
                    evidence_a=[],
                    evidence_b=fb.evidence,
                )
            )
        elif fa and fb and not _values_equal(fa.value, fb.value):
            changes.append(
                DiffChange(
                    field=field_name,
                    change_type="modified",
                    old_value=fa.value,
                    new_value=fb.value,
                    evidence_a=fa.evidence,
                    evidence_b=fb.evidence,
                )
            )

    ids_a = {s.signal_id for s in signals_a}
    ids_b = {s.signal_id for s in signals_b}

    return DiffResult(
        diff_id=str(uuid.uuid4()),
        receipt_a_id=receipt_a_id,
        receipt_b_id=receipt_b_id,
        changes=changes,
        new_signals=[s for s in signals_b if s.signal_id not in ids_a],
        resolved_signals=[s for s in signals_a if s.signal_id not in ids_b],
    )
