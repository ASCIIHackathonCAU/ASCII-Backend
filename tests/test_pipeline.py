"""
Unit tests for ReceiptOS pipeline — classifier, structurer, signals, evidence, full pipeline.
"""
import pathlib

import pytest

from app.a.pipeline import process_document
from app.a.pipeline.classifier import classify
from app.a.pipeline.signals import (
    check_purpose_marketing,
    check_retention_long,
    check_revoke_path_missing,
    check_third_party_present,
    check_vague_third_party,
    detect_signals,
)
from app.a.pipeline.structurer import extract_fields
from app.a.schemas import Evidence, ExtractedField

FIXTURES = pathlib.Path(__file__).resolve().parent.parent / "fixtures"


# =====================================================================
# Classifier
# =====================================================================
class TestClassifier:
    def test_consent(self):
        doc_type, ev = classify("개인정보 수집·이용 동의서\n수집항목: 이름")
        assert doc_type == "consent"
        assert len(ev) >= 1

    def test_marketing(self):
        doc_type, _ = classify("마케팅 수신 동의\n프로모션 및 광고성 정보 수신에 동의합니다.")
        assert doc_type == "marketing"

    def test_change(self):
        doc_type, _ = classify("개인정보처리방침 변경 안내\n변경 사항: 수집항목 추가")
        assert doc_type == "change"

    def test_third_party(self):
        doc_type, _ = classify("개인정보 제3자 제공 동의서\n업무 위탁 내용")
        assert doc_type == "third_party"

    def test_unknown(self):
        doc_type, ev = classify("오늘 날씨가 좋습니다.")
        assert doc_type == "unknown"
        assert ev == []


# =====================================================================
# Structurer
# =====================================================================
class TestStructurer:
    def test_extracts_data_collected(self):
        text = "수집항목: 이름, 이메일, 전화번호"
        fields = extract_fields(text)
        assert "data_collected" in fields
        assert isinstance(fields["data_collected"].value, list)
        assert len(fields["data_collected"].value) >= 2

    def test_extracts_purposes(self):
        text = "이용 목적: 서비스 제공, 고객 상담"
        fields = extract_fields(text)
        assert "purposes" in fields

    def test_extracts_retention(self):
        text = "보유·이용 기간: 회원 탈퇴 시까지 또는 1년"
        fields = extract_fields(text)
        assert "retention" in fields

    def test_extracts_revoke_path(self):
        text = "동의 철회: 고객센터 1588-0000으로 전화"
        fields = extract_fields(text)
        assert "revoke_path" in fields

    def test_extracts_third_party(self):
        text = "제3자 제공: ○○마케팅에 이름, 이메일 제공"
        fields = extract_fields(text)
        assert "third_party" in fields


# =====================================================================
# Signals
# =====================================================================
class TestSignals:
    def test_revoke_path_missing_fires(self):
        fields = {"data_collected": ExtractedField(value=["이름"], evidence=[])}
        sig = check_revoke_path_missing(fields, "")
        assert sig is not None
        assert sig.signal_id == "revoke_path_missing"
        assert sig.severity == "high"

    def test_revoke_path_present_no_signal(self):
        fields = {
            "revoke_path": ExtractedField(
                value="고객센터 1588-0000",
                evidence=[Evidence(quote="고객센터 1588-0000", location="line 10")],
            )
        }
        assert check_revoke_path_missing(fields, "") is None

    def test_third_party_present(self):
        fields = {
            "third_party": ExtractedField(
                value=["○○마케팅"],
                evidence=[Evidence(quote="제3자 제공: ○○마케팅", location="line 5")],
            )
        }
        sig = check_third_party_present(fields, "")
        assert sig is not None
        assert sig.signal_id == "third_party_present"

    def test_retention_permanent(self):
        fields = {
            "retention": ExtractedField(
                value="영구 보관",
                evidence=[Evidence(quote="영구 보관", location="line 7")],
            )
        }
        sig = check_retention_long(fields, "")
        assert sig is not None
        assert sig.severity == "high"

    def test_retention_5_years(self):
        fields = {
            "retention": ExtractedField(
                value="거래 종료 후 5년",
                evidence=[Evidence(quote="거래 종료 후 5년", location="line 7")],
            )
        }
        sig = check_retention_long(fields, "")
        assert sig is not None
        assert "5년" in sig.title

    def test_retention_1_year_ok(self):
        fields = {
            "retention": ExtractedField(
                value="회원 탈퇴 시까지 또는 1년",
                evidence=[Evidence(quote="1년", location="line 7")],
            )
        }
        assert check_retention_long(fields, "") is None

    def test_retention_missing(self):
        sig = check_retention_long({}, "no retention info")
        assert sig is not None
        assert sig.signal_id == "retention_long"

    def test_purpose_marketing(self):
        fields = {
            "purposes": ExtractedField(
                value=["서비스 제공", "마케팅"],
                evidence=[Evidence(quote="마케팅", location="line 3")],
            )
        }
        sig = check_purpose_marketing(fields, "")
        assert sig is not None
        assert sig.signal_id == "purpose_expanded_to_marketing"

    def test_vague_third_party(self):
        fields = {
            "third_party": ExtractedField(
                value=["○○마케팅", "제휴 업체 등"],
                evidence=[Evidence(quote="제휴 업체 등", location="line 5")],
            )
        }
        sig = check_vague_third_party(fields, "")
        assert sig is not None
        assert sig.signal_id == "vague_third_party_language"

    def test_no_vague_when_specific(self):
        fields = {
            "third_party": ExtractedField(
                value=["한국신용정보원"],
                evidence=[Evidence(quote="한국신용정보원", location="line 5")],
            )
        }
        assert check_vague_third_party(fields, "") is None


# =====================================================================
# Evidence mapping
# =====================================================================
class TestEvidence:
    def test_all_fields_have_evidence(self):
        text = (
            "개인정보 수집·이용 동의서\n"
            "수집항목: 이름, 이메일, 전화번호\n"
            "이용 목적: 서비스 제공, 고객 상담\n"
            "보유기간: 1년\n"
            "동의 철회: 고객센터 1588-0000\n"
        )
        fields = extract_fields(text)
        for name, field in fields.items():
            assert len(field.evidence) > 0, f"{name} has no evidence"
            for ev in field.evidence:
                assert ev.quote, f"{name} evidence has empty quote"
                assert ev.location, f"{name} evidence has empty location"


# =====================================================================
# Full pipeline
# =====================================================================
class TestFullPipeline:
    def test_simple_consent(self):
        text = (
            "[개인정보 수집·이용 동의서]\n"
            "수집항목: 이름, 이메일, 전화번호\n"
            "이용 목적: 서비스 제공\n"
            "보유기간: 1년\n"
            "동의 철회: 고객센터 1588-0000\n"
        )
        receipt, extract = process_document(text, "consent_form")
        assert extract.document_type == "consent"
        assert "data_collected" in extract.fields
        assert receipt.content_hash
        assert receipt.receipt_id

    def test_high_risk(self):
        text = (
            "개인정보 수집 동의\n"
            "수집항목: 주민등록번호, 계좌번호\n"
            "이용 목적: 금융서비스, 마케팅\n"
            "보유기간: 영구 보관\n"
            "제3자 제공: 관계사 등 제3자에게 제공\n"
        )
        receipt, extract = process_document(text)
        ids = {s.signal_id for s in extract.signals}
        assert "retention_long" in ids
        assert "purpose_expanded_to_marketing" in ids
        assert "third_party_present" in ids
        assert "revoke_path_missing" in ids

    @pytest.mark.parametrize(
        "fixture",
        sorted(FIXTURES.glob("sample_*.txt")),
        ids=lambda p: p.stem,
    )
    def test_fixture_produces_receipt(self, fixture: pathlib.Path):
        text = fixture.read_text(encoding="utf-8")
        receipt, extract = process_document(text)
        assert receipt.receipt_id
        assert receipt.content_hash
        assert extract.document_type != ""
        # every signal must have evidence
        for sig in extract.signals:
            assert len(sig.evidence) >= 1, f"Signal {sig.signal_id} lacks evidence"
