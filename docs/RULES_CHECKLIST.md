# Hackathon rules → our actions (from "Important_.pdf", HackAlem AI regulations)

| Rule | What it says | What we do |
|---|---|---|
| 5.3.1 | Competition starts 23.09.2026 13:00 (Astana time) | All code written after 13:00 in the official repo |
| 5.4.4 / 5.4.6 | Disclose third-party code, libraries, models, datasets, templates | README "Third-party components & data" section (Open-Meteo CC BY 4.0, scikit-learn, FastAPI, React, Recharts…) + "AI tools used: Claude Code / Codex" |
| 5.4.4.2 | Pre-made components allowed only if not the core product | Plan/docs prepared at the start; all functional code written during the event |
| 5.4.5 | No previously built product | ✓ New project |
| 5.4.7 | Organizer may inspect repo history & individual contribution | Each person commits their own folder from their own account |
| 5.4.8 / 5.9.2 | **Intermediate result every hour**, else disqualification | Commit at 14:00, 15:00, 16:00, 17:00, 18:00 at minimum; log in `docs/PROGRESS.md` |
| 5.4.9 / 5.4.11 | Main development only in the organizer-created GitHub repo | Clone it first; do not keep work in private repos |
| 5.4.12 | Any AI tools allowed | We use Claude Code / Codex + an LLM API inside the product |
| 5.4.13 | Final version = repo state at **18:00** | Freeze 17:40, last push ≤ 17:55 |
| 5.4.15 | README must include: description & purpose, architecture, technologies, install, run, dependencies, env params, how to verify the main scenario | README skeleton already has all 8 sections: fill them |
| 5.4.16 / 5.6.5 | If it can't be launched from README, the team is out, and no fixes accepted afterwards | Clean-clone test at 17:00–17:40; Docker + manual path |
| 5.6.6 | Key functionality verifiable **without personal accounts/subscriptions**; provide demo access if external APIs are used | `LLM_PROVIDER=none` fallback, committed LLM cache, committed weather cache (`WEATHER_OFFLINE=1`) |
| Deploy notes | No live deploy required; Docker Compose allowed; don't push `.env`, provide `.env.example` | ✓ docker-compose.yml, .env.example, .gitignore |
| 5.1.7 | Stay on site; ≤ 60 min total absence with permission | Plan breaks; don't leave |

Scoring reminders: technical round = Compliance 25 · Technical (incl. agentic AI) 25 · README & reproducibility 25 · Value 15 · Potential/originality 10.
Demo Day = Value 25 · Result quality 20 · Innovation 15 · Scalability 20 · Presentation & Q&A 20.
