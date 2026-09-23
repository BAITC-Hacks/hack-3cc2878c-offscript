from __future__ import annotations

import gzip
import hashlib
import json

from openwind_ml.config import ProjectPaths
from openwind_ml.temporal_guard import AVAILABILITY_POLICY_VERSION
from openwind_ml import weather


def test_legacy_cache_manifest_records_missing_retrieval_evidence(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(weather, "PATHS", ProjectPaths(root=tmp_path))
    cache = weather.PATHS.nwp_cache
    cache.mkdir(parents=True)
    artifact = cache / "gfs_seamless_2026-02-01_2026-02-02.csv.gz"
    with gzip.open(artifact, "wt", encoding="utf-8") as handle:
        handle.write("time,wind_speed_100m_previous_day1\n2026-02-01T00:00:00Z,8\n")

    assert weather.ensure_cache_manifests() == {"cache_chunks": 1, "manifests_created": 1}
    assert weather.ensure_cache_manifests() == {"cache_chunks": 1, "manifests_created": 0}
    manifest = json.loads(weather._manifest_path(artifact).read_text(encoding="utf-8"))
    assert manifest["model"] == "gfs_seamless"
    assert manifest["requested_date_range"] == {"start": "2026-02-01", "end": "2026-02-02"}
    assert manifest["request_parameters"]["models"] == "gfs_seamless"
    assert manifest["request_record_status"] == "reconstructed_from_filename_and_current_fetch_config"
    assert manifest["retrieved_at"] is None
    assert manifest["response_headers"] is None
    assert manifest["cache_sha256"] == hashlib.sha256(artifact.read_bytes()).hexdigest()
    assert manifest["availability_policy_version"] == AVAILABILITY_POLICY_VERSION
    assert manifest["source_release_time_verified"] is False
    assert manifest["provenance_status"] == "legacy_cache_retrieval_time_unavailable"
