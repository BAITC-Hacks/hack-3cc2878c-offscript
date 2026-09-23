from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


def test_health_meta_and_forecast_contract(tmp_path: Path):
    with TestClient(create_app(repo_root=tmp_path)) as client:
        assert client.get("/api/health").json()["status"] == "ok"
        meta = client.get("/api/meta").json()
        assert meta["farm"]["tz"] == "Asia/Almaty"
        response = client.get("/api/forecast", params={"issue_date": "2026-02-14", "mode": "test"})
        assert response.status_code == 200
        forecast = response.json()
        assert len(forecast["rows"]) == 48
        assert forecast["issue_time"] == "2026-02-13T19:00:00Z"
        assert forecast["availability_policy_version"] == "previous-runs-offset-v1"
        assert forecast["source_release_time_verified"] is False
        assert forecast["max_estimated_nwp_init_time_used"] == forecast["max_nwp_init_time_used"]
        assert all(row["p10"] <= row["p50"] <= row["p90"] for row in forecast["rows"])
        # A computed-but-unpublished forecast must not borrow another block's proof.
        assert forecast.get("ledger") is None or forecast["ledger"]["verified"] is True


def test_agent_run_completes_offline(tmp_path: Path):
    with TestClient(create_app(repo_root=tmp_path)) as client:
        launched = client.post("/api/agent/run", json={"issue_date": "2026-02-15", "mode": "test", "use_llm": False})
        assert launched.status_code == 200
        run_id = launched.json()["run_id"]
        for _ in range(200):
            status = client.get(f"/api/agent/runs/{run_id}").json()
            if status["status"] != "running":
                break
            time.sleep(0.05)
        assert status["status"] == "done"
        assert status["result"]["ledger"]["verified"] is True
        blocks = client.get("/api/ledger").json()["blocks"]
        latest = next(block for block in reversed(blocks) if block["type"] == "FORECAST")
        assert latest["availability_evidence_status"] == "configured_policy_v1_source_release_unverified"
        assert latest["source_release_time_verified"] is False
        with client.stream("GET", f"/api/agent/stream/{run_id}") as stream:
            body = "".join(stream.iter_text())
        assert "event: agent" in body
        assert '"type": "done"' in body
