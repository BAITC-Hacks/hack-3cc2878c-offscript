# Original task text (HackAlem AI 2026), copied from the organizer Google Doc (EN version; RU/KZ in the source doc)
Source: https://docs.google.com/document/d/1Fn5IJoj87Fx7IAknG26zkfX8c0eq7feCujd0m66PCgY

**Case: Agentic AI for Wind Farm Generation Forecasting**

Develop an Agentic AI system for forecasting the hourly generation of a wind farm (WF) over a 24–48 hour horizon.
Participants are provided with the wind farm coordinates and historical operating data from March 2023 through January 31, 2026 inclusive.
Forecasts must be produced for the test period from February 1, 2026 to February 28, 2026.

**Data provided**: turbine 1 coordinates https://maps.app.goo.gl/iN6svMt69D5qRpFU9 (→ 43.645150, 78.535604);
turbine 2 coordinates https://maps.app.goo.gl/8UQMwsYavY6nLvFY8 (→ 43.643198, 78.538828); statistical time; average wind speed, m/s;
normalized active power on the line side; average ambient temperature, °C.

**Participants' task**: develop a solution that
1. Builds a model for forecasting the wind farm's hourly generation based on the provided historical data.
2. Independently retrieves, using the wind farm coordinates, weather forecasts from open sources that were available at the relevant forecasting moment.
3. Produces a wind farm generation forecast for the next 24–48 hours at hourly resolution.
4. Implements the process as Agentic AI, where the system independently performs the full cycle: retrieving external weather data → preparing data →
   running the forecasting model → producing the hourly forecast → analyzing the result → recalculating when input data is updated.

The choice of open weather data sources, ML models, data processing methods and AI agent architecture is up to the participants.
Participants must reproduce the process as if the forecast were being made in the past: on January 31, produce a forecast for the next 24–48 hours;
on February 1, produce a new forecast for the next 24–48 hours; then repeat sequentially throughout the test period.
For each forecast period, participants must use archived weather forecasts that were available at the corresponding point in time,
not actual weather values that became known later.

**Evaluation (100)**: Compliance with the task and functionality 25 · Technical implementation (approach, architecture, component interaction,
use of AI/agentic AI; consistency of implementation with stated logic) 25 · README and reproducibility 25 · Value and applicability 15 ·
Development potential and originality 10.

---
### Alternative task (NOT chosen): "Akim for 5 hours": AI city management simulator
Same budget for all teams, 5 decisions (transport, greening, social infrastructure, safety, city services), budget-overrun control, AI analysis,
Astana Quality of Life Score, explanation of strengths/risks. Why not chosen: likely the most crowded task, synthetic data only, and the AI part
tends to be shallow; the wind task has measurable accuracy, explicit agentic requirement and a clear money/grid value story.
