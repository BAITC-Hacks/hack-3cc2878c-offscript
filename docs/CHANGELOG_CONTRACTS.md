# Contract changes log
Format: HH:MM [who] what changed, why. Also update shared/mocks/.

- 15:32 [B/C] `/api/forecast` now omits ledger proof until an exact payload-hash match is published; avoids falsely attaching the chain head to an unrelated forecast. Updated the TypeScript type and unpublished demo fixture. Published forecasts use immutable per-run payload paths. The judge-facing README and keyless `.env.example` now describe the real integrated build.
- 15:36 [C] Local and Docker browser builds target `127.0.0.1:8000` by default; this avoids `localhost` resolving to IPv6 while the backend is bound to IPv4. No REST payload changed.
- 15:39 [B] `/api/agent/recalc` accepts optional `use_llm:false` for offline replay tests; the frontend still defaults to the AI path. The reason and input-hash comparison distinguish updated weather from a manual uncertainty review.
- 15:59 [B] README now states the fixed-offset NWP latency assumption explicitly instead of claiming exact source publication times; no API payload or mock contract changed.
