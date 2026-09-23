from app.runs import RunRegistry


def test_completed_agent_run_survives_registry_restart(tmp_path):
    registry = RunRegistry(tmp_path)
    run = registry.create("2026-02-14", "test")
    run.status = "done"
    run.decision = "ACCEPT"
    registry.persist(run)

    restored = RunRegistry(tmp_path)
    assert restored.get(run.run_id) is not None
    assert restored.get(run.run_id).status == "done"
    assert restored.list()[0]["decision"] == "ACCEPT"
