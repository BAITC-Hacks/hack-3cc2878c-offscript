# frontend/AGENTS.md: Person C (Frontend + README + Demo/Pitch)

Read first: `/PROJECT_PLAN.md` §7 & §13, `/docs/CONTRACTS.md` §2–§4, `/docs/DEMO_SCRIPT.md`.
You build a **control-room dashboard** that makes the agent's intelligence *visible*. Work against `shared/mocks/*.json` from
minute 0 (`VITE_USE_MOCKS=1`); switch to the real API when Person B says endpoints are live.
You also own the final `README.md` (judges score it 25/100!) and the 5–7 slide pitch.

## Stack (fast + good-looking, pinned)
Vite 5 + React 18 + TypeScript + TailwindCSS 3 + Recharts 2 + lucide-react icons + clsx. No heavy UI kit needed.
Scaffold: `npm create vite@latest . -- --template react-ts && npm i recharts lucide-react clsx && npm i -D tailwindcss@3 postcss autoprefixer && npx tailwindcss init -p`

## Structure
```
frontend/src/
  api/client.ts        fetchJSON(path) → if VITE_USE_MOCKS=1 map path → /mocks/*.json ; openAgentStream(runId, onEvent) (EventSource; in mock mode replay agent_events.json with 300 ms delay)
  api/types.ts         TS types mirroring CONTRACTS §4 (ForecastResult, RiskFlag, AgentEvent, Metrics, Block, Briefings, Economics, Meta)
  components/          FanChart.tsx, FlagChips.tsx, BriefingCard.tsx (lang tabs EN/RU/KZ, "✓ grounded" badge), LedgerBadge.tsx,
                       AgentTimeline.tsx, KpiTile.tsx, LeadErrorChart.tsx, DailyHeatmap.tsx, ReliabilityChart.tsx, BlockTable.tsx, Header.tsx
  pages/               ForecastPage.tsx, AgentPage.tsx, BacktestPage.tsx, LedgerPage.tsx, EconomicsPage.tsx
  App.tsx              top tabs + global state (selected issue_date, mode)
public/mocks/          copy of /shared/mocks (script: "predev": "cp -r ../shared/mocks public/")
```

## Pages & exact visuals
1. **Forecast** (hero)
   - Header: "SAMAL: Shelek wind farm · Agentic 48-h forecast", mode switch *Test Feb 2026 / Validation Feb 2025*, issue-date slider.
   - **FanChart** (Recharts `ComposedChart`): x = local time; `Area` dataKey={d => [d.p10, d.p90]} (band, 25% opacity), `Line` p50 (thick),
     dashed thin `Line`s per NWP model = `pc(nwp_v_hub[m])` if provided (or v_hub on right axis), `Line` actual (white dots) in validation mode,
     `ReferenceArea` for flag intervals, vertical `ReferenceLine` at lead 24 labelled "Day-ahead window →".
   - Right column: KPI tiles (Energy P50 MWh, mean band width, max P90), **FlagChips** (color by severity), **BriefingCard**, **LedgerBadge**
     ("Block #12 · 3f2a…9c · ✓ verified").
2. **Agent Console**
   - Button "▶ Run agent for {issue_date}" → POST /api/agent/run → open SSE → **AgentTimeline**: vertical stepper, each event = card with stage pill
     (PLAN/FETCH/…), actor icon (🤖 orchestrator, 🧐 critic, 🔧 tool, 🔗 ledger), title, collapsible JSON detail, duration, "LLM cached" tag.
   - Critic rejection = red card, then loop arrow back to PREDICT. Final card = decision + ledger block.
   - Secondary button "↻ Manual uncertainty review" → POST /api/agent/recalc with `reason:"manual_uncertainty_review"`;
     never portray this action as an automatic weather update. A keyless opt-in backend watcher handles changed-NWP polling.
3. **Backtest & Skill** (mode val_feb2025 / val_winter): KPI tiles NMAE, **Skill vs persistence**, **P10–P90 coverage** (target 80%);
   bar chart NMAE by model (hybrid highlighted vs persistence, climatology, raw_pc, mos_pc); line MAE by lead hour; calendar heatmap
   of daily MAE; reliability plot; series chart (actual vs p50 with band) for the whole month.
4. **Ledger**: BlockTable (index, type, issue date, short hash, prev hash, note), "Verify chain" (green banner with head hash) and
   "Tamper demo" (pick block → red banner "Chain broken at block #N: payload_sha256 mismatch"). Explain in one line why: *hash integrity detects edits to anchored payloads; the offset policy is checked, but provider release time is unverified*.
5. **Economics & Scale**: sliders capacity MW (default 5, labelled assumption) & imbalance price ₸/MWh → GET /api/economics; big number
   "Estimated savings vs naive forecast: X ₸/month"; small map/list of KZ wind regions (Shelek, Ereymentau, Zhanatas, Shokpar…) "same agent, new coordinates".

## Design tokens
Dark control-room: bg `#0B1220`, panels `#111A2E`, border `#1E2A44`, text `#E6EDF7`, muted `#8FA3BF`, accent wind-teal `#2DD4BF`,
P50 line `#38BDF8`, band `#38BDF8` @ 0.2, actual `#F8FAFC`, warn `#F59E0B`, critical `#EF4444`, ok `#22C55E`. Font: Inter.
Use tabular numbers for KPIs. Every chart has a title + one-line caption of what it proves.

## README.md (you own the final version; keep the skeleton's sections, required by rule 5.4.15)
Fill real metrics from `data/outputs/metrics/*.json`, add 3 screenshots (`docs/img/`), verify every command on a clean clone.

## Definition of done (C)
- [ ] All 5 tabs render from mocks, then from the real API; no console errors
- [ ] Agent Console streams live and looks impressive with `LLM_PROVIDER=none` too
- [ ] `docker compose up` serves the UI at http://localhost:5173
- [ ] README final + screenshots; slides; demo rehearsed twice (≤ 3 min)
