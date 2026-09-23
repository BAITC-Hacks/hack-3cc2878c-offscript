from __future__ import annotations

from typing import Any, Callable

from ..ml_bridge import ml


TOOLS: dict[str, dict[str, Any]] = {
    "fetch_nwp": {"description": "Fetch archived NWP forecasts available at the forecast issue time.",
                  "parameters": {"type": "object", "properties": {"issue_date": {"type": "string"}, "models": {"type": "array", "items": {"type": "string"}}}, "required": ["issue_date"]},
                  "fn": ml.fetch_nwp},
    "check_inputs": {"description": "Check forecast input coverage, spread, and temporal validity.",
                     "parameters": {"type": "object", "properties": {"issue_date": {"type": "string"}}, "required": ["issue_date"]}, "fn": ml.check_inputs},
    "run_forecast": {"description": "Run a 48-hour P10/P50/P90 probabilistic power forecast.",
                     "parameters": {"type": "object", "properties": {"issue_date": {"type": "string"}, "variant": {"enum": ["hybrid", "mos_pc", "raw_pc", "climatology", "persistence"]}, "widen": {"type": "number", "minimum": 0, "maximum": 0.3}}, "required": ["issue_date"]}, "fn": ml.run_forecast},
    "risk_scan": {"description": "Detect ramps, icing, cut-out, low confidence, and model disagreement.",
                  "parameters": {"type": "object", "properties": {"forecast": {"type": "object"}}, "required": ["forecast"]}, "fn": ml.risk_scan},
}


def to_openai() -> list[dict[str, Any]]:
    return [{"type": "function", "function": {"name": name, "description": tool["description"], "parameters": tool["parameters"]}} for name, tool in TOOLS.items()]


def to_anthropic() -> list[dict[str, Any]]:
    return [{"name": name, "description": tool["description"], "input_schema": tool["parameters"]} for name, tool in TOOLS.items()]
