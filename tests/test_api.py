"""
Integration tests for the ReceiptOS HTTP endpoints.
"""
import pytest


SAMPLE_TEXT = (
    "[개인정보 수집·이용 동의서]\n"
    "수집항목: 이름, 이메일, 전화번호\n"
    "이용 목적: 서비스 제공\n"
    "보유기간: 1년\n"
    "동의 철회: 고객센터 1588-0000\n"
)


class TestIngest:
    def test_ingest_success(self, client):
        resp = client.post(
            "/api/ingest",
            json={"raw_text": SAMPLE_TEXT, "source_type": "consent_form"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "receipt" in body
        assert "extract_result" in body
        assert body["receipt"]["receipt_id"]
        assert body["extract_result"]["document_type"] == "consent"

    def test_ingest_empty_text(self, client):
        resp = client.post("/api/ingest", json={"raw_text": "   ", "source_type": "other"})
        assert resp.status_code == 400

    def test_ingest_persists(self, client):
        resp = client.post(
            "/api/ingest",
            json={"raw_text": SAMPLE_TEXT, "source_type": "other"},
        )
        rid = resp.json()["receipt"]["receipt_id"]
        get_resp = client.get(f"/api/receipts/{rid}")
        assert get_resp.status_code == 200
        assert get_resp.json()["receipt_id"] == rid


class TestReceipts:
    def test_list_empty(self, client):
        resp = client.get("/api/receipts")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_after_ingest(self, client):
        client.post("/api/ingest", json={"raw_text": SAMPLE_TEXT, "source_type": "other"})
        resp = client.get("/api/receipts")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_get_not_found(self, client):
        resp = client.get("/api/receipts/nonexistent")
        assert resp.status_code == 404


class TestDiff:
    def _ingest(self, client, text):
        return client.post(
            "/api/ingest", json={"raw_text": text, "source_type": "other"}
        ).json()["receipt"]["receipt_id"]

    def test_diff_by_ids(self, client):
        text_a = (
            "개인정보 수집 동의\n수집항목: 이름, 이메일\n이용 목적: 서비스 제공\n보유기간: 1년\n"
        )
        text_b = (
            "개인정보 수집 동의\n수집항목: 이름, 이메일, 전화번호\n"
            "이용 목적: 서비스 제공, 마케팅\n보유기간: 5년\n"
        )
        id_a = self._ingest(client, text_a)
        id_b = self._ingest(client, text_b)

        resp = client.post(
            "/api/diff",
            json={"receipt_id_a": id_a, "receipt_id_b": id_b},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["changes"]) > 0

    def test_diff_by_raw_texts(self, client):
        resp = client.post(
            "/api/diff",
            json={
                "raw_text_a": "개인정보 수집 동의\n수집항목: 이름\n보유기간: 1년\n",
                "raw_text_b": "개인정보 수집 동의\n수집항목: 이름, 이메일\n보유기간: 1년\n",
            },
        )
        assert resp.status_code == 200

    def test_diff_missing_side(self, client):
        resp = client.post("/api/diff", json={"receipt_id_a": "abc"})
        assert resp.status_code in (400, 404, 422)
