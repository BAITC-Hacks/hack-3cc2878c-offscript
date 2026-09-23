from __future__ import annotations

import asyncio
import json

from pydantic import BaseModel

from app.agent.llm import LLM


class SampleDecision(BaseModel):
    action: str


def test_cached_structured_decision_replays_without_key(tmp_path):
    llm = LLM(provider="openai", model="gpt-4o-mini", api_key="", cache_dir=tmp_path)
    cache_path = llm._cache_path("system", "facts", SampleDecision)
    cache_path.write_text(json.dumps({"response": {"action": "ACCEPT"}}), encoding="utf-8")

    result, metadata = asyncio.run(llm.json("system", "facts", SampleDecision))

    assert result.action == "ACCEPT"
    assert metadata["provider"] == "openai"
    assert metadata["cached"] is True
