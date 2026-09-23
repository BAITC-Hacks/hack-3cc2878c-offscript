# backend/AGENTS.md: Person B (Backend + Agent + Ledger)

Read first: `/PROJECT_PLAN.md` §6, `/docs/CONTRACTS.md` §1–§4. You implement the REST/SSE API **exactly** as in CONTRACTS §2–3.
You consume `samal_ml.api` (CONTRACTS §1). Until Person A delivers, use `app/ml_stub.py` (reads `shared/mocks/`) behind
the same function names; switch with env `USE_ML_STUB=1|0`. Real ML is the default, and an import failure must fail startup rather than silently serve sample data.

## Layout
```
backend/
  requirements.txt   fastapi==0.115.* uvicorn[standard]==0.30.* pydantic==2.9.* sse-starlette==2.1.* python-dotenv
                     anthropic (latest) openai (latest) httpx
  Dockerfile         (build context = repo root; installs ml/ too)
  app/
    main.py          FastAPI app, CORS *, routers, startup: load ledger, ensure GENESIS block
    settings.py      pydantic-settings / os.environ (see /.env.example)
    schemas.py       Pydantic models mirroring CONTRACTS §4 (ForecastResult, RiskFlag, Briefing, Block, AgentEvent…)
    ml_bridge.py     try: import samal_ml.api as ml  except: import app.ml_stub as ml
    ml_stub.py       same functions as samal_ml.api, returning shared/mocks data
    ledger.py        hash chain: append/verify/tamper_demo (code below)
    runs.py          in-memory run registry + asyncio.Queue per run for SSE; persists to data/outputs/agent_runs/
    routers/ forecast.py agent.py ledger.py backtest.py economics.py live.py health.py
    agent/
      llm.py         provider adapter + cache (anthropic | openai | openai_compatible | none)
      tools.py       tool registry: name, JSON schema, python callable (wraps ml_bridge)
      orchestrator.py  state machine (PLAN→FETCH→QC→PREDICT→ANALYZE→DECIDE→CRITIC→BRIEF→PUBLISH; RECALC)
      critic.py      critic agent
      briefing.py    RU/KZ/EN briefing + numeric grounding check + template fallback
      policy.py      rule-based fallback decisions (used when LLM_PROVIDER=none or LLM fails)
      prompts/       planner.md, decider.md, critic.md, briefing.md
  tests/ test_ledger.py test_api_contract.py test_grounding.py
```
Run: `uvicorn app.main:app --reload --port 8000` from `backend/` with `PYTHONPATH=..:../ml` (or `pip install -e ../ml`).

## Orchestrator (async; emits AgentEvent at every step via `await run.emit(...)`)
```
PLAN     llm.json(planner prompt, context={issue_date, mode, available tools, last run decision}) → {"steps":[...],"variant":"hybrid","models":[...]}
         fallback: default plan
FETCH    tools.fetch_nwp(issue_date, models)                   → event tool_call + tool_result (coverage, max_init)
QC       tools.check_inputs(issue_date)                        → if models missing: note, continue with the rest
PREDICT  tools.run_forecast(issue_date, variant, widen, models, mode)
ANALYZE  tools.risk_scan(forecast)                             → flags
DECIDE   llm.json(decider prompt, facts)                       → {"action":"ACCEPT|RERUN|WIDEN|ESCALATE","variant":?, "widen":?, "rationale":"…"}
CRITIC   critic.review(forecast summary + flags + decision)    → {"approve":bool,"issues":[…],"suggestion":{"action","variant","widen"}}
         if not approve and loops < 2 → PREDICT again with suggestion
BRIEF    briefing.generate(facts, langs=["en","ru","kk"])      → grounded briefings (or template)
PUBLISH  ledger.append(FORECAST, payload=forecast rows, meta) + save forecast/briefing/run files → event ledger
DONE     event done {decision, block_index, loops}
RECALC   (endpoint /api/agent/recalc) re-run PREDICT with the newest data (e.g. the next issue's lower lead-days for overlapping
         hours); ml.forecast_diff(old,new); if mae > 0.05 or hours_outside_old_band > 0 → REVISION block + llm note; else "no revision needed".
```
Facts passed to the LLM = compact JSON: summary, flags, per-model mean v_hub, spread, band width, top 6 hours by p50, metrics headline.
**Never** send the full 48-row table unless needed; keep prompts < 3k tokens (cost + latency).

## Tool registry (tools.py): provider-neutral schema
```python
TOOLS = {
 "fetch_nwp":   {"description":"Fetch archived NWP forecasts available at issue time (TemporalGuard enforced).",
                 "parameters":{"type":"object","properties":{"issue_date":{"type":"string"},"models":{"type":"array","items":{"type":"string"}}},"required":["issue_date"]},
                 "fn": ml.fetch_nwp},
 "check_inputs":{"description":"Quality-check NWP inputs: coverage, missing models, spread.", ... "fn": ml.check_inputs},
 "run_forecast":{"description":"Run probabilistic forecast P10/P50/P90 for 48 h.", "parameters": {... "variant": {"enum":[...]}, "widen":{"type":"number","minimum":0,"maximum":0.3}}, "fn": ml.run_forecast},
 "risk_scan":   {"description":"Detect ramps, icing, cut-out, low confidence, model disagreement.", "fn": ml.risk_scan},
}
def to_anthropic(tools): return [{"name":n,"description":t["description"],"input_schema":t["parameters"]} for n,t in tools.items()]
def to_openai(tools):    return [{"type":"function","function":{"name":n,"description":t["description"],"parameters":t["parameters"]}} for n,t in tools.items()]
```
MVP: the orchestrator calls tools in a fixed order and uses the LLM only for PLAN/DECIDE/CRITIC/BRIEF (robust).
Stretch: let the planner LLM drive tool calls in a native tool-use loop (max 8 calls), with the same event stream.

## LLM adapter (llm.py)
```python
class LLM:
    def __init__(self, provider, model, api_key, base_url=None, cache=True): ...
    async def json(self, system: str, user: str, schema: type[BaseModel], temperature=0) -> tuple[BaseModel, dict]:
        # 1) key = sha256(provider|model|system|user|schema_name); if cache hit → return (parsed, {"cached":True})
        # 2) call provider: anthropic → client.messages.create(model, max_tokens=1200, system=system, messages=[{"role":"user","content":user}])
        #                   openai/openai_compatible → client.chat.completions.create(model, response_format={"type":"json_object"}, messages=[...])
        # 3) extract JSON (strip ``` fences), schema.model_validate_json; on failure 1 repair retry ("Return ONLY valid JSON for schema …")
        # 4) write cache file data/llm_cache/{key}.json {request, response, provider, model, ts}
        # 5) on any exception → raise LLMUnavailable (caller uses policy.py fallback and emits a 'warning' event)
```
`LLM_PROVIDER=none` → always LLMUnavailable → rule-based path. The UI must still look great in this mode.

## Prompts (prompts/*.md): keep them short, JSON-only, role-specific
- **planner.md**: "You are SAMAL-Orchestrator, an autonomous forecasting agent for a wind farm in the Shelek corridor, Kazakhstan.
  Goal: produce a reliable 48-h hourly probabilistic power forecast issued at {issue_time} using ONLY data available then.
  Available tools: … Return JSON {steps:[…], variant, models, reasoning (≤ 40 words)}."
- **decider.md**: given facts & flags choose ACCEPT/RERUN/WIDEN/ESCALATE. Rules of thumb: model disagreement → WIDEN 0.05–0.1;
  missing ECMWF → RERUN with remaining models + WIDEN; cut-out risk → ESCALATE (human check). JSON only.
- **critic.md**: "You are an independent grid-dispatch auditor at KEGOC. You did not build this forecast. Find physical or
  statistical problems: quantile crossing, band too narrow given model spread, ramps inconsistent with NWP, output > 0 at
  wind < 3 m/s, icing ignored… Return {approve, issues[], suggestion}." Pass deterministic check results as input too.
- **briefing.md**: operator briefing, ≤ 90 words per language, languages en/ru/kk; **use only numbers from FACTS**; units: % of
  capacity and MWh; local time (UTC+5). JSON per CONTRACTS §4.4.

## Numeric grounding check (briefing.py)
Extract numbers with regex `-?\d+(?:[.,]\d+)?`; allowed set = all numbers in FACTS (+ rounded to 0/1 decimals, ×100 for %,
hours 0–23, dates). Any number not in the allowed set → regenerate once with the offending numbers listed → else template briefing.
Set `grounded` true/false accordingly. Show "✓ grounded" badge in UI.

## Ledger (ledger.py): exact code to implement
```python
import hashlib, json
def canon(o): return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
def sha(o_or_bytes): b = o_or_bytes if isinstance(o_or_bytes, bytes) else canon(o_or_bytes).encode(); return hashlib.sha256(b).hexdigest()
class Ledger:
    def __init__(self, path="data/ledger/ledger.jsonl"): load lines → self.blocks; if empty → append GENESIS (prev_hash "0"*64)
    def append(self, type, payload_rows, **meta):
        blk = {"index": len(self.blocks), "type": type, **meta, "payload_sha256": sha(payload_rows),
               "prev_hash": self.blocks[-1]["hash"] if self.blocks else "0"*64, "created_at": utcnow_iso()}
        blk["hash"] = sha({k: v for k, v in blk.items() if k != "hash"}); append line; return blk
    def verify(self, blocks=None, check_files=True):
        errors = []; prev = "0"*64
        for b in blocks or self.blocks:
            if b["prev_hash"] != prev: errors.append((b["index"], "broken link"))
            if sha({k: v for k, v in b.items() if k != "hash"}) != b["hash"]: errors.append((b["index"], "hash mismatch"))
            if check_files and b.get("payload_file"): recompute sha(rows of file) == b["payload_sha256"] else "payload_sha256 mismatch"
            temporal: parse times; if max_nwp_init_time_used + latency_h > issue_time → "lookahead violation"
                      if max_scada_time_used > issue_time → "scada lookahead"
            prev = b["hash"]
        return {"valid": not errors, "checked": len(...), "head_hash": prev, "errors": [...]}
    def tamper_demo(self, i): copy blocks + load payload of block i into memory, bump rows[0]["p50"] += 0.05,
                              verify against the in-memory payload → returns first_bad_block = i  (never write to disk)
```
Also append a `MODEL_TRAINED` block when the backend first sees a new `model_version` (hash of the model bundle file).

## SSE (runs.py + routers/agent.py)
```python
from sse_starlette.sse import EventSourceResponse
@router.get("/api/agent/stream/{run_id}")
async def stream(run_id: str):
    run = RUNS[run_id]
    async def gen():
        for e in run.events: yield {"event": "agent", "data": json.dumps(e)}      # replay past events first
        while not run.finished or not run.queue.empty():
            e = await run.queue.get(); yield {"event": "agent", "data": json.dumps(e)}
    return EventSourceResponse(gen())
```
POST /api/agent/run starts `asyncio.create_task(orchestrator.run(...))` and returns run_id immediately.
Add a small `await asyncio.sleep(0.25)` between stages in demo mode (`DEMO_PACING=1`) so the UI animation is readable.

## Definition of done (B)
- [ ] All CONTRACTS §2 endpoints respond with correct shapes (stub first, real ml later); `pytest backend/tests` green
- [ ] Agent run works with `LLM_PROVIDER=none` AND with the real key; events stream live; runs persisted
- [ ] Critic can reject → loop visible in the stream at least in one demo case (use a date with high model disagreement)
- [ ] Ledger verify ✓, tamper demo ✗ at the right block; ledger file + llm cache committed for demo dates
- [ ] Batch: `python -m app.batch --mode test` runs the agent for all 28 test issues (fills ledger + briefings)
