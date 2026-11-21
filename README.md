# VTU Exam Radar

**Two AI agents that read VTU past question papers and tell students what to study first.**

Built for *Diwali Festiverse: The Agent-to-Agent Hackathon (India Edition)*, Research — Data & Build track.

## The problem
Lakhs of VTU students prepare for exams by flipping through stacks of old question papers, guessing
which topics matter. Nobody tells them which modules carry the most marks, which questions keep
coming back, or how to plan the few days before an exam.

## How it works

```
Student ──@Radar Data analyse BMATS101 days=5──▶ Radar Data
                                                   │  reads every past paper + syllabus (Gemini)
                                                   │  checks the live web for scheme / timetable news
                                                   ▼
                                    DATA_READY ──▶ Radar Builder
                                                   │  checks the data quality
           Radar Data ◀── NEED_MORE modules=3,5 ───┤  (if a module is thin, asks for more)
           searches web for more questions         │
                       └──── DATA_READY round=2 ──▶│
                                                   │  groups repeated questions, ranks modules,
                                                   │  writes a day-by-day study plan,
                                                   ▼  publishes to the dashboard (git push → GitHub Pages)
Student ◀── "Dashboard ready: top module M2, top repeated questions..., link"
```

| Agent | Job |
|---|---|
| **Radar Data** | Collects: extracts every question from past papers, reads the syllabus, pulls live info from the web, and fills gaps on request |
| **Radar Builder** | Builds: checks the data, asks Radar Data for more when a module is thin, then turns it into the dashboard and study plan |

The agents talk through a **BAND** room using @mentions. The conversation is saved and shown on the dashboard.

## Tech
- **BAND**: agent-to-agent messaging (`band-sdk`, LangGraph adapter)
- **Gemini API**: reading PDFs, grouping similar questions, study plans, live Google Search
- **GitHub Pages**: hosts the dashboard (`site/` folder, plain HTML + Chart.js), redeployed automatically on every push

**Live dashboard:** https://hacksevednmganesh37-alt.github.io/vtu-exam-radar/
- **GitHub Codespaces**: runs both agents

## Run it

1. Open this repo in **GitHub Codespaces** (Code → Codespaces → Create).
2. Add these **Codespaces secrets** (GitHub → Settings → Codespaces → Secrets):
   `GEMINI_API_KEY`, `RADAR_DATA_ID`, `RADAR_DATA_KEY`, `RADAR_BUILDER_ID`, `RADAR_BUILDER_KEY`, `SITE_URL`
3. Put PDFs in `papers/<SUBJECT_CODE>/` (see `papers/README.md`).
4. Test without BAND: `uv run python scripts/run_local.py BMATS101 --no-push`
5. Start the agents in two terminals:
   ```
   uv run python -m agents.data_agent
   uv run python -m agents.builder_agent
   ```
6. In BAND, create a room with both agents and type: `@Radar Data analyse BMATS101 days=5`

## Disclaimer
Predictions come from patterns in past papers. They are not official VTU information.
Students should still cover the full syllabus.
