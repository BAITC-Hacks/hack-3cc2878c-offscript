"""Generates shared/mocks/*.json with the exact shapes of docs/CONTRACTS.md. FAKE NUMBERS (\"_mock\": true). Re-run after contract changes."""
import json, math, random, hashlib, datetime as dt, pathlib
random.seed(7)
OUT = pathlib.Path(__file__).parent / "mocks"; OUT.mkdir(exist_ok=True)
Z = lambda t: t.strftime("%Y-%m-%dT%H:%M:%SZ")
L = lambda t: (t + dt.timedelta(hours=5)).strftime("%Y-%m-%dT%H:%M:%S+05:00")
def canon(o): return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
def sha(o): return hashlib.sha256(canon(o).encode()).hexdigest()
MODELS = ["ecmwf_ifs025", "gfs_seamless", "icon_seamless"]
def pc(v): return max(0.0, min(1.0, (v - 3) ** 3 / (12 - 3) ** 3)) if v > 3 else 0.0
def dates(a, n): d = dt.date.fromisoformat(a); return [str(d + dt.timedelta(days=i)) for i in range(n)]

def forecast(issue_date="2026-02-14", mode="test", with_actual=False):
    t0 = dt.datetime.fromisoformat(issue_date) - dt.timedelta(hours=5)
    rows = []
    for L_ in range(1, 49):
        T = t0 + dt.timedelta(hours=L_); base = 8 + 3.5 * math.sin(L_ / 7) + (2 if 20 < L_ < 30 else 0)
        nwp = {"ecmwf_ifs025": round(base - 0.8, 2), "gfs_seamless": round(base + 1.6, 2), "icon_seamless": round(base - 0.2, 2)}
        vm = sum(nwp.values()) / 3; sp = (sum((x - vm) ** 2 for x in nwp.values()) / 3) ** 0.5
        p50 = round(pc(vm), 3); w = 0.12 + 0.02 * L_ / 8 + 0.05 * sp
        k = min(7, math.ceil((L_ + 8) / 24))
        rows.append({"target_time": Z(T), "target_time_local": L(T), "lead_h": L_, "lead_day": k,
                     "p10": round(max(0, p50 - w), 3), "p50": p50, "p90": round(min(1, p50 + w), 3),
                     "v_hub_mean": round(vm, 2), "v_hub_spread": round(sp, 2), "nwp_v_hub": nwp,
                     "pc_raw": round(pc(vm) * 1.05 if pc(vm) < 0.95 else 1, 3), "temp_c": round(-6 + 5 * math.sin(L_ / 4), 1),
                     "actual": (round(max(0, min(1, p50 + random.gauss(0, 0.1))), 3) if with_actual else None)})
    flags = [{"code": "RAMP_UP", "severity": "warn", "start": rows[18]["target_time"], "end": rows[21]["target_time"], "value": 0.34,
              "message": "Ramp-up of +34% capacity within 3 h expected around 00:00 local"},
             {"code": "MODEL_DISAGREEMENT", "severity": "info", "start": rows[0]["target_time"], "end": rows[47]["target_time"], "value": 1.0,
              "message": "GFS is ~2.4 m/s windier than ECMWF/ICON: band widened"}]
    mean = sum(r["p50"] for r in rows) / 48
    return {"_mock": True, "issue_date": issue_date, "issue_time": Z(t0), "mode": mode, "variant": "hybrid",
            "model_version": "hybrid-qhgb-train2026-01-31-3f2a9c", "nwp_models_used": MODELS,
            "max_nwp_init_time_used": Z(t0 - dt.timedelta(hours=8)), "max_scada_time_used": Z(t0 - dt.timedelta(hours=1)),
            "latency_h": 8, "capacity_mw": 5.0, "widen": 0.05, "rows": rows,
            "summary": {"mean_p50": round(mean, 3), "energy_p50_mwh": round(mean * 5 * 48, 1), "max_p90": max(r["p90"] for r in rows),
                        "mean_band": round(sum(r["p90"] - r["p10"] for r in rows) / 48, 3),
                        "dayahead_mean_p50": round(sum(r["p50"] for r in rows[23:47]) / 24, 3)},
            "flags": flags}

brief = lambda lang, h, s: {"lang": lang, "headline": h, "summary": s,
    "risks": [{"code": "RAMP_UP", "text": {"en": "Ramp-up +34% around midnight", "ru": "Рост мощности +34% около полуночи", "kk": "Түн ортасында қуат +34% өседі"}[lang]}],
    "actions": [{"en": "Keep 1.7 MW balancing reserve 23:00–02:00", "ru": "Держать резерв 1,7 МВт 23:00–02:00", "kk": "23:00–02:00 аралығында 1,7 МВт резерв ұстау"}[lang]],
    "confidence": "medium", "grounded": True, "generated_by": "template"}
briefings = {"en": brief("en", "Windy night ahead: 44% mean output tomorrow", "Day-ahead mean output 44% of capacity (P10–P90 band 38 pp). GFS is windier than ECMWF/ICON, so the band was widened."),
             "ru": brief("ru", "Ветреная ночь: завтра средняя выработка 44%", "Средняя выработка на сутки вперёд 44% от мощности (ширина P10–P90: 38 п.п.). GFS ветренее ECMWF/ICON, интервал расширен."),
             "kk": brief("kk", "Желді түн: ертең орташа өндіріс 44%", "Келесі тәулікке орташа өндіріс қуаттың 44%-ы (P10–P90 ені 38 п.п.). GFS ECMWF/ICON-ға қарағанда желдірек, интервал кеңейтілді.")}

f = forecast(); f_rows = f["rows"]
blocks = []; prev = "0" * 64
def add(b):
    global prev
    b = {**b, "prev_hash": prev}; b["hash"] = sha(b); blocks.append(b); prev = b["hash"]; return b
add({"index": 0, "type": "GENESIS", "issue_date": None, "issue_time": None, "created_at": "2026-09-23T09:00:00Z", "note": "OpenWind ledger genesis"})
add({"index": 1, "type": "MODEL_TRAINED", "issue_date": None, "issue_time": "2026-01-30T19:00:00Z", "created_at": "2026-09-23T09:30:00Z",
     "model_version": f["model_version"], "note": "trained on data <= 2026-01-30T19:00Z"})
for i, d in enumerate(dates("2026-01-31", 16)):
    ff = forecast(d); t0 = ff["issue_time"]
    add({"index": len(blocks), "type": "REVISION" if d == "2026-02-10" else "FORECAST", "issue_date": d, "issue_time": t0,
         "created_at": f"2026-09-23T10:{10+i:02d}:00Z", "model_version": ff["model_version"],
         "payload_file": f"data/outputs/forecasts/test/{d}.json", "payload_sha256": sha(ff["rows"]), "inputs_sha256": sha({"d": d}),
         "max_nwp_init_time_used": ff["max_nwp_init_time_used"], "max_scada_time_used": ff["max_scada_time_used"], "latency_h": 8,
         "note": "Revision: newer NWP moved P50 by 7% for 11 h" if d == "2026-02-10" else "ACCEPT after 1 critic loop"})
f["ledger"] = {"block_index": 16, "hash": blocks[16]["hash"], "verified": True}; f["briefing"] = briefings

meta = {"_mock": True, "farm": {"name": "Shelek corridor WF (2 turbines)", "lat": 43.6442, "lon": 78.5372,
        "turbines": [{"id": "T1", "lat": 43.645150, "lon": 78.535604}, {"id": "T2", "lat": 43.643198, "lon": 78.538828}],
        "capacity_mw": 5.0, "capacity_is_assumption": True, "hub_height_m": 100, "tz": "Asia/Almaty"},
        "nwp_models": MODELS, "variants": ["hybrid", "mos_pc", "raw_pc", "climatology", "persistence"],
        "issue_dates": {"test": dates("2026-01-31", 28), "val_feb2025": dates("2025-01-31", 28), "val_winter": dates("2025-10-31", 92)},
        "temporal_guard": {"latency_h": 8, "rule": "K = ceil((lead_h + latency_h)/24)"}}

m = lambda a, b, c, d, e, g: {"nmae": a, "nrmse": b, "bias": c, "skill_vs_persistence": d, "pinball": e, "picp_80": g}
metrics = {"_mock": True, "mode": "val_feb2025", "train_end": "2025-01-30T19:00:00Z", "n_issues": 28, "n_hours": 672, "leads": "24-47",
    "models": {"hybrid": m(0.121, 0.172, -0.01, 0.41, 0.048, 0.79), "mos_pc": m(0.138, 0.19, 0.02, 0.33, None, None),
               "raw_pc": m(0.171, 0.232, 0.06, 0.17, None, None), "climatology": m(0.19, 0.24, 0.0, 0.08, None, None),
               "persistence": m(0.206, 0.29, 0.0, 0.0, None, None)},
    "mae_by_lead": [{"lead_h": l, "hybrid": round(0.07 + 0.0012 * l, 4), "persistence": round(0.05 + 0.0045 * l if l < 36 else 0.21, 4),
                     "raw_pc": round(0.14 + 0.0008 * l, 4)} for l in range(1, 49)],
    "daily": [{"date": d, "hybrid": round(abs(random.gauss(0.12, 0.04)), 3), "persistence": round(abs(random.gauss(0.2, 0.07)), 3)} for d in dates("2025-02-01", 28)],
    "reliability": [{"nominal": n, "observed": round(n - 0.02 + random.random() * 0.03, 3)} for n in (0.2, 0.4, 0.6, 0.8)],
    "feature_importance": [{"feature": k, "importance": v} for k, v in [("pc_mos", .31), ("v_hub_mean", .18), ("pc_raw", .12), ("v_hub_std", .08),
                            ("hour_local_sin", .06), ("wd100_ecmwf_sin", .05), ("lead_h", .04), ("t2m_mean", .03)]]}
vf = forecast("2025-02-10", "val_feb2025", True)
series = {"_mock": True, "mode": "val_feb2025", "rows": [{"target_time": r["target_time"], "p10": r["p10"], "p50": r["p50"], "p90": r["p90"], "actual": r["actual"]} for r in vf["rows"]]}

T0 = dt.datetime(2026, 9, 23, 10, 15, 0)
ev = []
def e(stage, typ, title, actor="orchestrator", detail=None, llm=None, dur=None):
    ev.append({"run_id": "r_20260214_demo", "seq": len(ev), "ts": Z(T0 + dt.timedelta(seconds=len(ev) * 2)), "stage": stage, "type": typ,
               "title": title, "detail": detail or {}, "actor": actor, "llm": llm, "duration_ms": dur})
LLM = {"provider": "anthropic", "model": "claude-sonnet", "cached": True, "latency_ms": 0}
e("PLAN", "stage_start", "Planning forecast for issue 2026-02-14 00:00 (UTC+5)")
e("PLAN", "llm_decision", "Plan: 3 NWP models, hybrid quantile model, full risk scan", detail={"steps": ["fetch_nwp", "check_inputs", "run_forecast", "risk_scan"], "variant": "hybrid"}, llm=LLM, dur=1400)
e("FETCH", "tool_call", "fetch_nwp(issue_date=2026-02-14)", actor="tool", detail={"models": MODELS})
e("FETCH", "tool_result", "Fetched 3/3 models · max NWP init used 2026-02-13 11:00Z ✓ TemporalGuard", actor="tool", detail={"coverage": {k: 1.0 for k in MODELS}, "latency_h": 8}, dur=380)
e("QC", "tool_result", "Inputs OK · mean model spread 1.9 m/s", actor="tool", detail={"ok": True, "spread_mean_ms": 1.9}, dur=40)
e("PREDICT", "tool_result", "Forecast ready: day-ahead mean 44% · band 31 pp", actor="tool", detail={"variant": "hybrid", "widen": 0.0}, dur=210)
e("ANALYZE", "tool_result", "2 flags: RAMP_UP (warn), MODEL_DISAGREEMENT (info)", actor="tool", detail={"flags": ["RAMP_UP", "MODEL_DISAGREEMENT"]}, dur=15)
e("DECIDE", "llm_decision", "ACCEPT: ramp is supported by all 3 models", detail={"action": "ACCEPT", "rationale": "Ramp consistent across ECMWF/GFS/ICON"}, llm=LLM, dur=1800)
e("CRITIC", "critic", "Critic rejects: band too narrow for 2.4 m/s GFS-ECMWF gap during ramp", actor="critic", detail={"approve": False, "issues": ["P10–P90 narrower than NWP spread implies at 22:00–02:00"], "suggestion": {"action": "WIDEN", "widen": 0.05}}, llm=LLM, dur=2100)
e("PREDICT", "tool_result", "Re-run with widen=0.05 → band 38 pp", actor="tool", detail={"variant": "hybrid", "widen": 0.05}, dur=190)
e("CRITIC", "critic", "Critic approves (loop 2)", actor="critic", detail={"approve": True, "issues": []}, llm=LLM, dur=1500)
e("BRIEF", "briefing", "Briefings generated EN/RU/KZ · ✓ numeric grounding passed", detail={"grounded": True, "langs": ["en", "ru", "kk"]}, llm=LLM, dur=3200)
e("PUBLISH", "ledger", "Sealed as block #16 · 3f2a9c…", actor="ledger", detail={"block_index": 16, "hash": blocks[16]["hash"]}, dur=5)
e("DONE", "done", "Done: ACCEPT after 2 critic loops", detail={"decision": "ACCEPT", "block_index": 16, "loops": 2})

econ = {"_mock": True, "mode": "val_feb2025", "capacity_mw": 5, "price_kzt_mwh": 15000, "assumption_note": "Illustrative flat imbalance price",
        "hours": 672, "imbalance_mwh": {"hybrid": 406.6, "persistence": 692.2, "climatology": 638.4},
        "cost_kzt": {"hybrid": 6099000, "persistence": 10383000}, "savings_vs_persistence_kzt": 4284000, "savings_pct": 41.3, "annualized_savings_kzt": 55800000}

files = {"meta.json": meta, "forecast.json": f, "agent_events.json": ev, "backtest_val_feb2025.json": metrics, "series_val_feb2025.json": series,
         "ledger.json": {"_mock": True, "length": len(blocks), "head_hash": prev, "blocks": blocks},
         "ledger_verify.json": {"valid": True, "checked": len(blocks), "head_hash": prev, "errors": []},
         "ledger_tamper.json": {"valid": False, "first_bad_block": 5, "errors": [{"block_index": 5, "reason": "payload_sha256 mismatch"}]},
         "economics.json": econ, "health.json": {"status": "ok", "version": "0.1.0", "llm_provider": "none", "weather_offline": True}}
for n, o in files.items(): (OUT / n).write_text(json.dumps(o, ensure_ascii=False, indent=1))
print("wrote", list(files))
