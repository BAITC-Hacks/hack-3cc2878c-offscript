from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import re
from typing import Any, TypeVar

from pydantic import BaseModel

from ..settings import settings

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class LLMUnavailable(RuntimeError):
    pass


def _strip_fences(value: str) -> str:
    return re.sub(r"^```(?:json)?\s*|\s*```$", "", value.strip(), flags=re.IGNORECASE)


class LLM:
    """Provider-neutral, cached typed-JSON adapter.

    This layer intentionally has no access to numerical forecast computation tools.
    It may only plan, critique, and phrase facts calculated by Python.
    """

    def __init__(self, provider: str | None = None, model: str | None = None, api_key: str | None = None,
                 base_url: str | None = None, cache_dir: Path | None = None):
        self.provider = (provider or settings.llm_provider).lower()
        self.model = model or settings.llm_model
        self.api_key = api_key if api_key is not None else settings.llm_api_key
        self.base_url = base_url or settings.llm_base_url
        self.cache_dir = cache_dir or settings.llm_cache_dir

    def _cache_path(self, system: str, user: str, schema: type[BaseModel]) -> Path:
        payload = f"{self.provider}|{self.model}|{system}|{user}|{schema.__name__}".encode()
        return self.cache_dir / f"{hashlib.sha256(payload).hexdigest()}.json"

    async def json(self, system: str, user: str, schema: type[SchemaT], *, temperature: float = 0) -> tuple[SchemaT, dict[str, Any]]:
        if self.provider == "none":
            raise LLMUnavailable("LLM_PROVIDER=none")
        cache_path = self._cache_path(system, user, schema)
        if cache_path.exists():
            try:
                cached = json.loads(cache_path.read_text(encoding="utf-8"))
                return schema.model_validate(cached["response"]), {"provider": self.provider, "model": self.model, "cached": True, "latency_ms": 0}
            except (KeyError, ValueError):
                cache_path.unlink(missing_ok=True)
        if not self.api_key:
            raise LLMUnavailable("LLM_API_KEY is not configured")
        started = datetime.now(UTC)
        try:
            response = await self._request(system, user, schema, temperature)
            parsed = response if isinstance(response, schema) else schema.model_validate_json(_strip_fences(response))
        except Exception as exc:  # Provider failure must never stop the operational path.
            raise LLMUnavailable(str(exc)) from exc
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps({"request": {"provider": self.provider, "model": self.model, "schema": schema.__name__},
                                          "response": parsed.model_dump(mode="json"), "created_at": datetime.now(UTC).isoformat()},
                                         ensure_ascii=False, indent=2), encoding="utf-8")
        latency_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)
        return parsed, {"provider": self.provider, "model": self.model, "cached": False, "latency_ms": latency_ms}

    async def _request(self, system: str, user: str, schema: type[SchemaT], temperature: float) -> str | SchemaT:
        if self.provider in {"openai", "openai_compatible"}:
            try:
                from openai import AsyncOpenAI
            except ImportError as exc:  # pragma: no cover - dependency installation path
                raise LLMUnavailable("openai package is not installed") from exc
            client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url) if self.base_url else AsyncOpenAI(api_key=self.api_key)
            messages = [{"role": "system", "content": system + " Return only valid JSON."}, {"role": "user", "content": user}]
            # Native Pydantic Structured Outputs prevent enum/key drift for first-party OpenAI calls.
            if self.provider == "openai":
                response = await client.beta.chat.completions.parse(model=self.model or "gpt-4o-mini", messages=messages,
                                                                    response_format=schema, temperature=temperature)
                parsed = response.choices[0].message.parsed
                if parsed is None:
                    raise LLMUnavailable("OpenAI declined or truncated the structured response")
                return parsed
            response = await client.chat.completions.create(model=self.model or "gpt-4o-mini", messages=messages,
                                                            response_format={"type": "json_object"}, temperature=temperature)
            content = response.choices[0].message.content
            if not content:
                raise LLMUnavailable("OpenAI returned no JSON content")
            return content
        if self.provider == "anthropic":
            try:
                from anthropic import AsyncAnthropic
            except ImportError as exc:  # pragma: no cover
                raise LLMUnavailable("anthropic package is not installed") from exc
            client = AsyncAnthropic(api_key=self.api_key)
            response = await client.messages.create(model=self.model or "claude-3-5-haiku-latest", max_tokens=1200,
                                                    temperature=temperature, system=system + " Return only valid JSON.",
                                                    messages=[{"role": "user", "content": user}])
            text = "".join(block.text for block in response.content if getattr(block, "type", "") == "text")
            if not text:
                raise LLMUnavailable("Anthropic returned no JSON content")
            return text
        raise LLMUnavailable(f"Unsupported LLM_PROVIDER={self.provider!r}")
