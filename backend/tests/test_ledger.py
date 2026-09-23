from __future__ import annotations

import json

from app.ledger import Ledger, sha
from openwind_ml.temporal_guard import availability_policy_metadata


def test_ledger_distinguishes_legacy_policy_from_configured_violation(tmp_path):
    ledger = Ledger(tmp_path / "ledger.jsonl")
    ledger.append("FORECAST", [{"p50": 0.2}], issue_time="2026-02-13T19:00:00Z",
                  max_nwp_init_time_used="2026-02-13T11:00:00Z", max_scada_time_used="2026-02-13T18:00:00Z", latency_h=8)
    assert ledger.verify()["valid"]
    assert ledger.verify()["legacy_policy_evidence_blocks"] == [1]
    ledger.append("FORECAST", [{"p50": 0.2}], issue_time="2026-02-13T19:00:00Z",
                  max_nwp_init_time_used="2026-02-13T12:00:00Z",
                  max_estimated_nwp_init_time_used="2026-02-13T12:00:00Z", latency_h=8,
                  **availability_policy_metadata())
    assert "configured availability policy violation" in {item["reason"] for item in ledger.verify()["errors"]}


def test_source_release_cannot_be_claimed_verified_by_offset_policy(tmp_path):
    ledger = Ledger(tmp_path / "ledger.jsonl")
    metadata = availability_policy_metadata()
    metadata["source_release_time_verified"] = True
    block = ledger.append("FORECAST", [{"p50": 0.2}], issue_time="2026-02-13T19:00:00Z",
                          max_nwp_init_time_used="2026-02-13T11:00:00Z",
                          max_estimated_nwp_init_time_used="2026-02-13T11:00:00Z", latency_h=8,
                          **metadata)
    assert ledger.policy_evidence_status(block) == "invalid_availability_metadata"
    assert "invalid availability metadata" in {item["reason"] for item in ledger.verify()["errors"]}


def test_new_block_hashes_entire_immutable_forecast_file(tmp_path):
    payload = tmp_path / "forecast.json"
    rows = [{"p50": 0.2, "target_time": "2026-02-13T20:00:00Z", "lead_h": 1, "lead_day": 1}]
    payload.write_text(json.dumps({"rows": rows, "briefing": "original"}), encoding="utf-8")
    ledger = Ledger(tmp_path / "ledger.jsonl")
    ledger.append("FORECAST", rows, issue_time="2026-02-13T19:00:00Z",
                  max_nwp_init_time_used="2026-02-12T20:00:00Z",
                  max_estimated_nwp_init_time_used="2026-02-12T20:00:00Z", latency_h=8,
                  payload_file=str(payload), payload_file_sha256=sha(payload.read_bytes()),
                  **availability_policy_metadata())
    assert ledger.verify()["valid"]
    payload.write_text(json.dumps({"rows": rows, "briefing": "changed"}), encoding="utf-8")
    assert "payload file sha256 mismatch" in {item["reason"] for item in ledger.verify()["errors"]}


def test_new_block_verifier_rechecks_row_offset_policy(tmp_path):
    payload = tmp_path / "forecast.json"
    rows = [{"p50": 0.2, "target_time": "2026-02-13T20:00:00Z", "lead_h": 1, "lead_day": 2}]
    payload.write_text(json.dumps({"rows": rows}), encoding="utf-8")
    ledger = Ledger(tmp_path / "ledger.jsonl")
    ledger.append("FORECAST", rows, issue_time="2026-02-13T19:00:00Z",
                  max_nwp_init_time_used="2026-02-12T20:00:00Z",
                  max_estimated_nwp_init_time_used="2026-02-12T20:00:00Z", latency_h=8,
                  payload_file=str(payload), payload_file_sha256=sha(payload.read_bytes()),
                  **availability_policy_metadata())
    assert any("lead_day 2 does not match" in error["reason"] for error in ledger.verify()["errors"])


def test_tamper_demo_never_writes_payload(tmp_path):
    payload = tmp_path / "forecast.json"
    payload.write_text(json.dumps({"rows": [{"p50": 0.2}]}), encoding="utf-8")
    ledger = Ledger(tmp_path / "ledger.jsonl")
    ledger.append("FORECAST", [{"p50": 0.2}], payload_file=str(payload))
    before = payload.read_text(encoding="utf-8")
    result = ledger.tamper_demo(1)
    assert result["valid"] is False
    assert result["first_bad_block"] == 1
    assert payload.read_text(encoding="utf-8") == before


def test_missing_published_payload_invalidates_proof(tmp_path):
    payload = tmp_path / "forecast.json"
    payload.write_text(json.dumps({"rows": [{"p50": 0.2}]}), encoding="utf-8")
    ledger = Ledger(tmp_path / "ledger.jsonl")
    ledger.append("FORECAST", [{"p50": 0.2}], payload_file=str(payload))
    assert ledger.verify()["valid"]
    payload.unlink()
    result = ledger.verify()
    assert not result["valid"]
    assert {error["reason"] for error in result["errors"]} == {"payload file missing"}
