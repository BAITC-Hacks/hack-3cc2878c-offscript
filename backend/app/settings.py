from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


_REPO_ROOT = Path(__file__).resolve().parents[2]
# Docker Compose injects .env itself; loading it here also makes direct uvicorn
# launches use the same local configuration without overriding shell variables.
load_dotenv(_REPO_ROOT / ".env", override=False)


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    repo_root: Path = _REPO_ROOT
    use_ml_stub: bool = _bool("USE_ML_STUB", True)
    weather_offline: bool = _bool("WEATHER_OFFLINE", True)
    llm_provider: str = os.getenv("LLM_PROVIDER", "none").lower()
    llm_model: str = os.getenv("LLM_MODEL", "")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_base_url: str | None = os.getenv("LLM_BASE_URL") or None
    demo_pacing: bool = _bool("DEMO_PACING", False)
    latency_h: int = int(os.getenv("NWP_LATENCY_H", "8"))
    capacity_mw: float = float(os.getenv("FARM_CAPACITY_MW", "5.0"))

    @property
    def mocks_dir(self) -> Path:
        return self.repo_root / "shared" / "mocks"

    @property
    def ledger_path(self) -> Path:
        return self.repo_root / "data" / "ledger" / "ledger.jsonl"

    @property
    def outputs_dir(self) -> Path:
        return self.repo_root / "data" / "outputs"

    @property
    def llm_cache_dir(self) -> Path:
        return self.repo_root / "data" / "llm_cache"


settings = Settings()
