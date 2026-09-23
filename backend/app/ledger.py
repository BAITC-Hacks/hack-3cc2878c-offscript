from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
import hashlib
import json
from pathlib import Path
from typing import Any

from samal_ml.temporal_guard import (
    AVAILABILITY_BASIS, AVAILABILITY_POLICY_VERSION, SOURCE_RELEASE_TIME_EVIDENCE,
    assert_no_lookahead,
)


def canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha(value: Any) -> str:
    raw = value if isinstance(value, bytes) else canon(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def utcnow_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _parse(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


class Ledger:
    """Tamper-evident payload chain with a recorded, assumption-based availability policy."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.blocks = self._load()
        if not self.blocks:
            self.append("GENESIS", [], note="SAMAL ledger genesis")

    def _load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]

    def append(self, block_type: str, payload_rows: list[dict[str, Any]], **meta: Any) -> dict[str, Any]:
        block = {
            "index": len(self.blocks), "type": block_type, "created_at": utcnow_iso(),
            "payload_sha256": sha(payload_rows),
            "prev_hash": self.blocks[-1]["hash"] if self.blocks else "0" * 64,
            **meta,
        }
        block["hash"] = sha({key: value for key, value in block.items() if key != "hash"})
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(canon(block) + "\n")
        self.blocks.append(block)
        return block

    def _payload_path(self, block: dict[str, Any]) -> Path | None:
        filename = block.get("payload_file")
        if not filename:
            return None
        path = Path(filename)
        if not path.is_absolute():
            path = self.path.parents[2] / path
        if not path.exists():
            return None
        return path

    def _payload_rows(self, block: dict[str, Any]) -> list[dict[str, Any]] | None:
        path = self._payload_path(block)
        if path is None:
            return None
        with path.open(encoding="utf-8") as handle:
            return json.load(handle).get("rows", [])

    @staticmethod
    def policy_evidence_status(block: dict[str, Any]) -> str:
        if block.get("type") not in {"FORECAST", "REVISION"}:
            return "not_applicable"
        fields = (
            "availability_basis", "availability_policy_version", "source_release_time_verified",
            "source_release_time_evidence", "max_estimated_nwp_init_time_used", "configured_latency_h",
        )
        if not any(field in block for field in fields):
            return "legacy_policy_evidence"
        if (block.get("availability_basis") != AVAILABILITY_BASIS
                or block.get("availability_policy_version") != AVAILABILITY_POLICY_VERSION
                or block.get("source_release_time_verified") is not False
                or block.get("source_release_time_evidence") != SOURCE_RELEASE_TIME_EVIDENCE
                or block.get("max_estimated_nwp_init_time_used") != block.get("max_nwp_init_time_used")
                or block.get("configured_latency_h") != block.get("latency_h")):
            return "invalid_availability_metadata"
        return "configured_policy_v1_source_release_unverified"

    def verify(self, blocks: list[dict[str, Any]] | None = None, check_files: bool = True) -> dict[str, Any]:
        candidate = blocks if blocks is not None else self.blocks
        errors: list[dict[str, Any]] = []
        legacy_policy_evidence_blocks: list[int] = []
        previous = "0" * 64
        for block in candidate:
            index = block.get("index", -1)
            policy_status = self.policy_evidence_status(block)
            if policy_status == "legacy_policy_evidence":
                legacy_policy_evidence_blocks.append(index)
            elif policy_status == "invalid_availability_metadata":
                errors.append({"block_index": index, "reason": "invalid availability metadata"})
            if block.get("prev_hash") != previous:
                errors.append({"block_index": index, "reason": "broken link"})
            expected = sha({key: value for key, value in block.items() if key != "hash"})
            if block.get("hash") != expected:
                errors.append({"block_index": index, "reason": "hash mismatch"})
            if check_files and block.get("payload_file"):
                path = self._payload_path(block)
                rows = self._payload_rows(block)
                if rows is None:
                    errors.append({"block_index": index, "reason": "payload file missing"})
                elif sha(rows) != block.get("payload_sha256"):
                    errors.append({"block_index": index, "reason": "payload_sha256 mismatch"})
                if path is not None and block.get("payload_file_sha256"):
                    if sha(path.read_bytes()) != block["payload_file_sha256"]:
                        errors.append({"block_index": index, "reason": "payload file sha256 mismatch"})
                elif policy_status == "configured_policy_v1_source_release_unverified":
                    errors.append({"block_index": index, "reason": "payload file hash missing"})
                if rows is not None and policy_status == "configured_policy_v1_source_release_unverified":
                    try:
                        audit = assert_no_lookahead(
                            rows, block.get("issue_time"), block["configured_latency_h"],
                            availability_metadata={
                                key: block[key] for key in (
                                    "availability_basis", "availability_policy_version",
                                    "source_release_time_verified", "source_release_time_evidence",
                                    "configured_latency_h",
                                )
                            },
                        )
                        if audit.max_estimated_nwp_init_time_used != block["max_estimated_nwp_init_time_used"]:
                            raise ValueError("estimated NWP initialization does not match payload offsets")
                    except (AssertionError, ValueError, TypeError, KeyError) as error:
                        errors.append({"block_index": index, "reason": f"configured availability policy violation: {error}"})
            issue = _parse(block.get("issue_time"))
            nwp = _parse(block.get("max_nwp_init_time_used"))
            scada = _parse(block.get("max_scada_time_used"))
            latency = block.get("latency_h", 0)
            if issue and nwp and nwp + timedelta(hours=latency) > issue:
                errors.append({"block_index": index, "reason": "configured availability policy violation"})
            if issue and scada and scada > issue:
                errors.append({"block_index": index, "reason": "scada lookahead"})
            previous = block.get("hash", previous)
        return {"valid": not errors, "checked": len(candidate), "head_hash": previous, "errors": errors,
                "legacy_policy_evidence_blocks": legacy_policy_evidence_blocks}

    def tamper_demo(self, block_index: int) -> dict[str, Any]:
        if block_index < 0 or block_index >= len(self.blocks):
            raise IndexError("block_index is outside the ledger")
        block = self.blocks[block_index]
        rows = self._payload_rows(block)
        if not rows:
            return {"valid": False, "first_bad_block": block_index,
                    "errors": [{"block_index": block_index, "reason": "no payload available for tamper demo"}]}
        altered = deepcopy(self.blocks)
        rows = deepcopy(rows)
        rows[0]["p50"] = min(1.0, rows[0]["p50"] + 0.05)
        altered[block_index]["payload_sha256"] = sha(rows)
        # The hash was deliberately not recalculated: this models post-publication editing.
        result = self.verify(altered, check_files=False)
        return {"valid": False, "first_bad_block": block_index,
                "errors": [{"block_index": block_index, "reason": "payload_sha256 mismatch"}],
                "head_hash": result["head_hash"]}
