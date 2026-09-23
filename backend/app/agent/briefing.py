from __future__ import annotations

import re
from typing import Any

from ..schemas import BriefingItem, Briefings


NUMBER = re.compile(r"-?\d+(?:[.,]\d+)?")


def _allowed_numbers(facts: dict[str, Any]) -> set[str]:
    rendered = str(facts).replace("%", "")
    allowed = set(NUMBER.findall(rendered))
    for number in list(allowed):
        try:
            value = float(number.replace(",", "."))
        except ValueError:
            continue
        allowed.update({str(round(value, 1)), str(round(value)), str(round(value * 100, 1)), str(round(value * 100))})
    return allowed


def is_grounded(text: str, facts: dict[str, Any]) -> bool:
    allowed = _allowed_numbers(facts)
    prose = re.sub(r"(?i)\bp(?:10|50|90)\b", "", text)
    return all(token.replace(",", ".") in allowed or token in allowed for token in NUMBER.findall(prose))


def briefings_are_grounded(briefings: Briefings, facts: dict[str, Any]) -> bool:
    for item in (briefings.en, briefings.ru, briefings.kk):
        parts = [item.headline, item.summary, *item.actions]
        parts.extend(risk.text for risk in item.risks)
        if not all(is_grounded(part, facts) for part in parts):
            return False
    return True


def template(forecast: dict[str, Any], flags: list[dict[str, Any]]) -> Briefings:
    summary = forecast["summary"]
    mean_percent = round(summary["dayahead_mean_p50"] * 100)
    band_percent = round(summary["mean_band"] * 100)
    energy = round(summary["energy_p50_mwh"], 1)
    confidence = "low" if any(flag["severity"] == "critical" for flag in flags) else "medium" if flags else "high"
    risk_codes = [{"code": flag["code"], "text": flag["message"]} for flag in flags[:3]]
    return Briefings(
        en=BriefingItem(lang="en", headline="OpenWind day-ahead wind forecast", summary=f"Expected median generation is {mean_percent}% of capacity, with {energy} MWh across the 48-hour horizon. P10–P90 width is {band_percent} percentage points.", risks=risk_codes, actions=["Keep balancing reserve available during flagged periods."], confidence=confidence, grounded=True, generated_by="template"),
        ru=BriefingItem(lang="ru", headline="Прогноз OpenWind на сутки вперёд", summary=f"Медианная выработка: {mean_percent}% мощности; за 48 часов: {energy} МВт·ч. Ширина P10–P90: {band_percent} п.п.", risks=risk_codes, actions=["Поддерживайте резерв на балансирование в отмеченные периоды."], confidence=confidence, grounded=True, generated_by="template"),
        kk=BriefingItem(lang="kk", headline="OpenWind келесі тәулікке болжамы", summary=f"Медианалық өндіріс қуаттың {mean_percent}%-ы; 48 сағатта {energy} МВт·сағ. P10–P90 ені: {band_percent} тармақ.", risks=risk_codes, actions=["Белгіленген кезеңдерде теңгерім резервін сақтаңыз."], confidence=confidence, grounded=True, generated_by="template"),
    )
