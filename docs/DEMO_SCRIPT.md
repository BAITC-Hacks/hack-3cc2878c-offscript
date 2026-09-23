# DEMO SCRIPT & PITCH: SAMAL (3 minutes + Q&A). Owner: Person C (everyone rehearses)

## Slides (5–7)
1. **Title**: SAMAL: Self-Auditing Multi-model Agentic Loop. "An AI dispatcher that forecasts wind power 48 h ahead with an auditable availability policy."
2. **Problem**: wind output is volatile; day-ahead schedule errors mean imbalances the grid (KEGOC) must cover in the balancing
   market; Kazakhstan is scaling wind & solar (national renewables targets), so forecast quality = money + grid stability.
   *(Verify exact market rules/targets before quoting numbers: Ministry of Energy balancing market rules, order №112, amended 2023.)*
3. **Solution**: architecture picture (3 NWP models → TemporalGuard → physics-informed quantile model → agent loop with Critic → ledger → dashboard).
4. **Live demo** (below).
5. **Results**: validation Feb 2025 ("seasonal twin" of the Feb 2026 test): NMAE X%, skill vs persistence +Y%, P10–P90 coverage Z% (target 80%).
   Fill from `data/outputs/metrics/val_feb2025.json`. Show MAE-by-lead chart.
6. **Why it's different**: probabilistic, configured fixed-offset availability checks, tamper-evident forecasts, self-auditing agent, works offline.
7. **Scale**: any wind/solar farm = coordinates + SCADA; KEGOC / Samruk-Energy / private IPPs; next: solar, portfolio aggregation,
   bidding optimizer on P10/P90, Telegram alerts for dispatchers.

## Live demo flow (≈ 90 s): practise with LLM on AND off
1. Forecast tab → issue date **14 Feb 2026** → fan chart: "band = uncertainty; dashed lines = the three weather models disagree here".
2. Agent Console → **Run agent** → narrate while it streams: *plan → select 3 models (TemporalGuard ✓: estimated initialization time plus configured 8 h margin is no later than issue
   time) → forecast → risk scan finds a ramp → decider says accept → **Critic rejects: band too narrow for the model disagreement** → re-run
   widened → approved → briefing in Kazakh/Russian/English, numbers verified → sealed in ledger block #N.*
3. Switch briefing to **KZ**.
4. Run **15 Feb 2026** next: the RECALC trace compares 24 overlapping target hours with 14 Feb, showing comparable selected-NWP input hashes, forecast MAE/max change, and a new FORECAST block. The **Manual uncertainty review** button is explicitly operator-initiated; it must not be narrated as newly arrived weather. The optional cache watcher triggers a same-issue REVISION only after its selected input fingerprint changes.
5. Ledger tab → **Verify ✓** → **Tamper demo** on one block → **red: chain broken at block N**. "The chain detects edits to anchored forecast payloads and re-checks our configured offset policy; it cannot independently verify Open-Meteo publication time."
6. Backtest tab → one sentence on skill + coverage. Economics tab → savings number (say "illustrative assumptions").

## Likely jury questions (prepared answers)
- **How do you check future-weather risk?** Open-Meteo *Previous Runs* supplies fixed offsets from 1–7 days. Our lead-day rule
  K = ceil((lead+8 h)/24) checks an estimated initialization time against the issue time with an assumed 8-hour margin;
  tests cover policy boundaries, and new ledger blocks record the estimate and policy version. The API does not provide
  verified release times, so we do not claim exact publication-time proof.
- **Why not just use actual weather (ERA5)?** That's leakage; the task forbids it. We use ERA5-like data nowhere in forecasting.
- **Why is the agent needed if ML does the forecast?** The ML predicts; the agent *operates*: chooses models/variants when inputs are missing,
  audits physical plausibility, compares daily overlap, re-issues only when selected NWP inputs change (or an operator explicitly requests a manual review), and communicates risk. The watcher monitors a configured local cache; it does not fetch fresh provider data on its own.
- **What if the LLM hallucinates?** It never produces numbers; outputs are JSON-validated; briefing numbers are cross-checked against facts;
  rule-based fallback; the system runs fully without an LLM.
- **Why P10/P90?** Grid operators and traders need risk: reserve sizing and bidding use quantiles, not a single line.
- **Accuracy on the hidden test?** We can't see Feb 2026 actuals; we validated on Feb 2025 with the identical procedure and on winter
  2025/26. `samal_ml.cli evaluate --actuals` scores the submission instantly once actuals are released.
- **Why only ~2 years of weather training data?** The archive of issued forecasts starts ~Mar 2024; we use it honestly. The power curve still uses
  the full SCADA history since Mar 2023.
- **Scaling?** Coordinates + SCADA → cache → train (~minutes on a laptop). Multi-farm = one agent per farm + portfolio aggregation.
- **Is the "blockchain" real?** It's a SHA-256 hash chain (the core blockchain primitive) without consensus; anchoring the head hash to git
  (timestamped) or a public chain is a 1-line extension. It is there for auditability, not for hype.
