# Progress log (evidence of hourly progress, rule 5.4.8)
Format: `HH:MM [A|B|C] what was done`. Commit after each line or batch of lines.

- 13:45 [all] Task chosen (Wind farm forecasting, Agentic AI). Plan, contracts, agent instructions, folder skeleton created.
- 13:58 [all] Docs complete: PROJECT_PLAN, AGENTS (root+3 folders), CONTRACTS, TIMELINE, RULES_CHECKLIST, DEMO_SCRIPT, ARCHITECTURE, README skeleton, mocks, docker-compose, Makefile.
- 13:52 [A] Organizer SCADA copied unchanged to `data/raw/turbine_1.csv` and `data/raw/turbine_2.csv`; both are 10-minute streams from 2023-03-11 through 2026-01-31 with the expected four Russian fields.
- 15:32 [A] Cached three archived NWP model histories, trained test and validation models, replayed both validations and all 28 February 2026 issues; submission has 672 unique day-ahead hours.
- 15:32 [B] Switched to real ML/OpenAI; verified planner, decider, critic, AI briefing, exact-match ledger proof, immutable payloads, and tamper detection.
- 15:32 [C] Switched Vite to the live API; checked all five dashboard tabs, winter and seasonal metrics, AI briefing, ledger, economics, and a clean browser console.
- 15:48 [B] Verified automatic daily rollover comparison across 24 overlapping hours with new NWP timestamps; keyless agent published a valid ledger block.
- 15:59 [B] Enforced real-ML startup, isolated API tests from the production ledger, aligned NWP latency config, and verified a fresh OpenAI plan/decision/critic/briefing run with a valid proof.
- 16:35 [A] Leak-safe curve and pre-cutoff availability/blended P50: Feb hybrid NMAE 22.08%→20.29%, bias +9.20→+2.13 pp; winter NMAE 18.41%→18.08%, bias +7.67→+1.25 pp; 18 tests passed.
- 17:04 [all] Audited Previous Runs evidence: v1 offset-plus-8h policy is explicit, 27 legacy cache chunks have honest SHA-256 sidecars with unknown retrieval times, 148 replay forecasts carry unverified-release metadata, new ledger blocks hash whole payloads and recheck row offsets, old blocks remain legacy; 39 ML/backend tests pass.
- 17:29 [B] Added per-target selected-NWP fingerprints, 24-hour adjacent-issue replay comparisons in trace/ledger, opt-in keyless cache watcher, no-op automatic recalc on unchanged inputs, and separately labelled manual uncertainty reviews; real two-issue replay verified (24 overlap hours, input changed, MAE 0.0431, max 0.2936, ledger valid); 45 ML/backend tests and frontend build passed.
- 17:40 [all] Renamed current product and Python package to OpenWind, migrated three trained bundles, labelled normalized-power chart percentages, and audited README deployment steps and task mapping against the case PDF; preserved anchored historical audit data.
- 17:45 [all] OpenWind release verified: 45 ML/backend tests, frontend production build, live localhost UI, 672 day-ahead rows, 8 valid ledger blocks; GitHub main confirmed at 976dc51 (release log will follow).
