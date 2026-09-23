from __future__ import annotations

import json

from app.ledger import Ledger


def test_ledger_detects_temporal_lookahead(tmp_path):
    ledger = Ledger(tmp_path / "ledger.jsonl")
    ledger.append("FORECAST", [{"p50": 0.2}], issue_time="2026-02-13T19:00:00Z",
                  max_nwp_init_time_used="2026-02-13T11:00:00Z", max_scada_time_used="2026-02-13T18:00:00Z", latency_h=8)
    assert ledger.verify()["valid"]
    ledger.append("FORECAST", [{"p50": 0.2}], issue_time="2026-02-13T19:00:00Z",
                  max_nwp_init_time_used="2026-02-13T12:00:00Z", latency_h=8)
    assert "lookahead violation" in {item["reason"] for item in ledger.verify()["errors"]}


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
