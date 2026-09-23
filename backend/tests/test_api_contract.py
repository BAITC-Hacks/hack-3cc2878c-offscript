from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_health_meta_and_forecast_contract():
    with TestClient(app) as client:
        assert client.get("/api/health").json()["status"] == "ok"
        meta = client.get("/api/meta").json()
        assert meta["farm"]["tz"] == "Asia/Almaty"
        response = client.get("/api/forecast", params={"issue_date": "2026-02-14", "mode": "test"})
        assert response.status_code == 200
        forecast = response.json()
        assert len(forecast["rows"]) == 48
        assert forecast["issue_time"] == "2026-02-13T19:00:00Z"
        assert all(row["p10"] <= row["p50"] <= row["p90"] for row in forecast["rows"])
        assert forecast["ledger"]["verified"] is True


def test_agent_run_completes_offline():
    with TestClient(app) as client:
        launched = client.post("/api/agent/run", json={"issue_date": "2026-02-14", "mode": "test", "use_llm": False})
        assert launched.status_code == 200
        run_id = launched.json()["run_id"]
        for _ in range(100):
            status = client.get(f"/api/agent/runs/{run_id}").json()
            if status["status"] != "running":
                break
        assert status["status"] == "done"
        assert status["result"]["ledger"]["verified"] is True
        with client.stream("GET", f"/api/agent/stream/{run_id}") as stream:
            body = "".join(stream.iter_text())
        assert "event: agent" in body
        assert '"type": "done"' in body
