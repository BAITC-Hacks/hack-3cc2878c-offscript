"""One-time pre-release migration of mutable demo payload paths.

Only blocks created during local development can be migrated this way. Rehashing
changes the chain head, so never run it after a public ledger anchor exists.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import tempfile

from .ledger import Ledger, canon, sha
from .settings import settings


def main() -> None:
    ledger = Ledger(settings.ledger_path)
    if not ledger.verify()["valid"]:
        raise RuntimeError("The existing ledger must verify before migration")
    old_prefix = Path("data/outputs/forecasts")
    pending = [block for block in ledger.blocks if block.get("payload_file") and
               Path(block["payload_file"]).is_relative_to(old_prefix)]
    if not pending:
        print("No mutable payload paths to migrate")
        return
    backup = settings.ledger_path.with_suffix(".pre_immutable_migration.jsonl")
    if backup.exists():
        raise FileExistsError(f"Refusing to overwrite existing backup: {backup}")
    target_dir = settings.outputs_dir / "ledger_payloads"
    target_dir.mkdir(parents=True, exist_ok=True)
    for block in pending:
        source = settings.repo_root / block["payload_file"]
        rows = json.loads(source.read_text(encoding="utf-8"))["rows"]
        if sha(rows) != block["payload_sha256"]:
            raise RuntimeError(f"Payload for block {block['index']} does not match its hash")
        target = target_dir / f"legacy-block-{block['index']}.json"
        if target.exists():
            raise FileExistsError(f"Refusing to overwrite existing snapshot: {target}")
        shutil.copy2(source, target)
        block["payload_file"] = target.relative_to(settings.repo_root).as_posix()

    previous = "0" * 64
    for block in ledger.blocks:
        block["prev_hash"] = previous
        block["hash"] = sha({key: value for key, value in block.items() if key != "hash"})
        previous = block["hash"]
    shutil.copy2(settings.ledger_path, backup)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=settings.ledger_path.parent,
                                     prefix="ledger-migration-", suffix=".tmp", delete=False) as handle:
        temporary = Path(handle.name)
        for block in ledger.blocks:
            handle.write(canon(block) + "\n")
    os.replace(temporary, settings.ledger_path)
    verified = Ledger(settings.ledger_path).verify()
    if not verified["valid"]:
        raise RuntimeError(f"Migrated ledger failed verification: {verified['errors']}")
    print(f"Migrated {len(pending)} payload paths; new ledger head {verified['head_hash']}")


if __name__ == "__main__":
    main()
